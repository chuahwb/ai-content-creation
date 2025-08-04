# Simplified On-Demand Noise Assessment for Refined Images: Implementation Plan (v4)

This document outlines a refined plan to implement a simplified, on-demand image assessment feature for refined images, focusing exclusively on **noise and grain impact**. This plan has been updated to ensure the new function inherits robust prompting practices.

## 1. Analysis & Refined Approach

Focusing solely on "noise and grain" for refined images is a highly effective simplification. The most valuable feedback at this stage is technical, and "noise and grain" is a key technical artifact of the refinement process.

### Advantages of this approach:

*   **Simplicity**: The result is a simple, actionable flag, making it easy for users to understand.
*   **Efficiency**: A more focused prompt for the LLM will result in a faster and cheaper assessment.
*   **Reduced Complexity**: We only need to store a single boolean flag (`needs_noise_reduction`) for each refinement.
*   **Universal Applicability**: This technical-only assessment is relevant for **all refinement types** (`subject`, `text`, `prompt`), as any of them can introduce generative artifacts. The implementation will be agnostic to the refinement category.

## 2. Detailed Implementation Plan

### Part 1: Backend Implementation (`churns` directory)

#### 1. Update Database Model (`churns/api/database.py`)
-   Modify the `Refinement` SQLAlchemy model to include a nullable boolean field.

    -   **New Field**: `needs_noise_reduction: Optional[bool] = Field(default=None)`
        -   `None`: Not yet assessed.
        -   `True`: Assessed, and noise was detected.
        -   `False`: Assessed, and the image is clean.

#### 2. Create Specialized Assessment Function in `image_assessment.py`
-   A new, dedicated method will be added to the `ImageAssessor` class.

    -   **New Method**: `async def assess_noise_only_async(self, image_path: str) -> bool:`
    -   **Inherited Prompting Practices**: To ensure reliability, this function will **reuse the robust prompting architecture** from the existing `assess_image_async` method. This includes:
        -   **System Prompts**: Using the same system prompts that enforce a JSON-only response, including special handling for problematic models (e.g., `o4-mini`).
        -   **API Call Parameters**: Using a low `temperature` (e.g., 0.1) for consistent output and an appropriate `max_tokens` limit.
        -   **Retry Logic**: Wrapping the API call in the same retry loop to handle transient network issues or API errors.
        -   **Robust Parsing**: Utilizing the existing `RobustJSONParser` to safely extract the JSON from the LLM's response.

    -   **Core Logic**:
        1.  Load the image from `image_path` to base64 using the `_load_image_as_base64` helper.
        2.  Construct the `system_content` and `user_content` (image + specialized text prompt) following the established practices.
        3.  Call the multimodal LLM within the retry loop.
        4.  Use `RobustJSONParser` to parse the response and extract the `noise_and_grain_impact` score.
        5.  Return `True` if the score is less than 3, `False` otherwise. It will handle parsing errors gracefully by returning `False`.

    -   **Specialized User Prompt**: The text part of the `user_content` will be minimal for efficiency.
        ```
        # ROLE & TASK
        You are an expert in image quality analysis. Your ONLY task is to assess the provided image for digital noise or unwanted graininess that is a result of the image generation process. Ignore intentional artistic grain.

        # REQUIRED JSON RESPONSE
        Respond ONLY with a valid JSON object in this exact format:
        {
          "noise_and_grain_impact": <integer 1-3>
        }

        # SCORING GUIDE (1-3)
        - 3: No significant noise or grain. The image is clean.
        - 2: Mild, acceptable noise/grain is present.
        - 1: Serious noise/grain that degrades quality.

        Begin your assessment now.
        ```

#### 3. Create New API Endpoint and Background Task
-   **New Endpoint (`churns/api/routers.py`)**: `POST /api/refinements/{refinement_id}/assess-noise`.
-   **Background Task (`churns/api/background_tasks.py`)**:
    -   The endpoint will trigger `run_noise_assessment_for_refinement(refinement_id: str)`.
    -   This task will instantiate `ImageAssessor`, call `assess_noise_only_async`, update the `needs_noise_reduction` field in the database, and emit WebSocket events for real-time UI feedback.

### Part 2: Frontend Implementation (`front_end` directory)

#### 1. Update Frontend Types (`front_end/src/types/api.ts`)
-   Locate the TypeScript interface for refinement results.
-   **New Field**: `needs_noise_reduction?: boolean | null;`

#### 2. Add "Assess Noise" Button (`front_end/src/components/RunResults.tsx`)
-   An "Assess Noise" button will appear on each refined image card.
-   It will be enabled only if `needs_noise_reduction` is `null`.
-   On click, it will call the new API endpoint and enter a loading state.

#### 3. Display the "Noise" Flag
-   The UI will conditionally render a minimal status indicator:
    -   If `true`, a compact red/warning tag (e.g., "Noisy") will be displayed.
    -   If `false`, a subtle green/success tag (e.g., "✓ Clean") will be displayed.
    -   The "Assess Noise" button will be hidden after an assessment is complete.

### Part 3: Validation and Testing
-   **Backend**: A new API test will be added for the `/api/refinements/{refinement_id}/assess-noise` endpoint. Unit tests for `assess_noise_only_async` will verify that it correctly uses the inherited prompting practices (system prompts, retry logic) and accurately parses the noise score.
-   **Frontend**: Manual testing will be required to ensure the "Assess Noise" button works correctly and the resulting flag is displayed appropriately.
