# Image Generation Enhancement Plan

This document outlines the implementation plan to enhance the `image_generation.py` stage to handle scenarios where both a main reference image and a brand logo are provided as inputs for image editing.

## 1. Objective

The primary goal is to upgrade the image generation pipeline to support a complex editing scenario that uses a text prompt, a primary reference image, and a secondary logo image simultaneously to produce a single, edited output image. This will allow for advanced branding applications, such as realistically "stamping" a logo onto an object within a scene.

The implementation should handle the following scenarios:
1.  **No Reference Image, No Logo**: Standard text-to-image generation.
2.  **Only Reference Image**: Standard image editing using the reference image and a prompt.
3.  **Reference Image and Logo**: A new, complex editing scenario utilizing both images and a prompt.
4.  **Only Logo**: Standard image editing, using the logo as the reference image.

## 2. Analysis of Current Implementation

The current implementation in `churns/stages/image_generation.py` uses two distinct OpenAI API calls:
- `client.images.generate`: For the text-to-image generation scenario.
- `client.images.edit`: For image editing.

**Limitation**: The `client.images.edit` endpoint accepts only a single input image. When both a main reference image and a logo are present, the current logic prioritizes the main image and uses it for the `edit` call, effectively ignoring the logo. This prevents the desired three-input (text, image, logo) editing.

## 3. Proposed Solution: Multi-Modal Image Editing

To support the complex editing scenario, we will transition from using the `client.images.edit` API to a more advanced, multi-modal API call when both a reference image and a logo are present. The provided API example suggests using a chat-based completions endpoint that can process multiple image inputs alongside a text prompt.

### Key Changes:
- **API Call:** We will use a `chat.completions.create`-style API call with the originally configured image generation model, which supports multi-modal inputs. This allows us to send a list of inputs (text, reference image, logo image) in a single request.
- **Prompt Engineering:** The prompt assembly stage will be updated to create specific instructions for the model on how to use the two images (e.g., "Use the first image as the base scene and the second image as the logo to be applied.").
- **Code Architecture:** The `image_generation.py` stage will be refactored to include a new function dedicated to this multi-modal API call, while retaining the existing methods for the simpler scenarios.

## 4. Detailed Implementation Steps

### Step 1: No Configuration Updates Needed
The existing `IMAGE_GENERATION_MODEL_ID` will be used for the new multi-modal API call. No changes to configuration files are required.

### Step 2: Enhance `prompt_assembly.py`

- **File**: `churns/stages/prompt_assembly.py`
- **Actions**:
    1.  **Update `assemble_final_prompt`**: Modify the function to detect the new scenario where both a reference image and a logo are present. The function will need to differentiate between a main reference image and a logo being the sole reference.
    2.  **Create New Prompt Structures**: Generate specific prefixes for each editing scenario:
        - **Reference Image + Logo**:
        ```python
        # In assemble_final_prompt
        prefix = f"Based on the provided primary reference image and the secondary image as a logo, modify it according to the user instruction '{instruction_text}' to achieve the following detailed visual concept:  "
        ```
        - **Logo Only**: When only a logo is provided as a reference.
        ```python
        # In assemble_final_prompt
        prefix = "Using the provided logo, adapt it according to the user instruction '{instruction_text}' to achieve the following detailed visual concept:  "
        ```
    3.  **Update `run` function**: In the main `run` function of the stage, the logic for determining `assembly_type` should be updated to include new types, such as `complex_edit` and `logo_only_edit`, for these scenarios.

### Step 3: Refactor `image_generation.py`

- **File**: `churns/stages/image_generation.py`
- **Actions**:
    1.  **Update `run` function**:
        - Modify the logic that determines the `reference_image_path`. Instead of a single path, it should identify and pass down paths for **both** the main reference image and the logo image if they exist.
        - The function will decide which generation function to call based on the available inputs (no image, one image, or two images).
    2.  **Refactor `generate_image`**: This function will act as a router. Its signature will be updated to accept an optional `logo_image_path`.
        ```python
        async def generate_image(
            ...,
            reference_image_path: Optional[str] = None,
            logo_image_path: Optional[str] = None,
            ...
        ):
            if reference_image_path and logo_image_path:
                # New complex edit scenario
                return await _generate_with_multiple_inputs(...)
            elif reference_image_path:
                # Simple edit (existing logic)
                return await _generate_with_single_input_edit(...) # Refactored existing edit logic
            else:
                # Generation (existing logic)
                return await _generate_with_no_input_image(...) # Refactored existing generation logic
        ```

### Step 4: Implement New Multi-Modal Generation Function

- **File**: `churns/stages/image_generation.py`
- **Actions**:
    1.  Create a new private asynchronous function: `async def _generate_with_multiple_inputs(...)`.
    2.  This function will:
        - Accept the text prompt, reference image path, and logo image path as arguments.
        - Read and base64-encode both the reference image and the logo image.
        - Construct the `messages` payload for the `client.chat.completions.create` API call, following the multi-modal format shown in the user-provided example.
        ```python
        # Example payload structure
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": final_prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_ref_image}"}},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_logo_image}"}},
            ]
        }]
        ```
        - The API call should be made to the `IMAGE_GENERATION_MODEL_ID`.
        - Process the API response to extract the generated image data (which will likely be a base64 string).
        - Decode the base64 string, save it to a file in the run directory, and return the status and file path, similar to the existing implementation.

## 5. Update Token and Cost Management

The existing token usage and cost calculation logic, primarily located in `churns/core/token_cost_manager.py` and utilized by `churns/api/background_tasks.py`, will be adapted to handle multiple image inputs with minimal changes.

- **File**: `churns/core/token_cost_manager.py`
  - **Action**: The `calculate_image_tokens` method already calculates tokens for a single image based on its dimensions. We will adapt the calling function to handle multiple images.
- **File**: `churns/api/background_tasks.py`
  - **Action**: In the `progress_callback` function, the logic for the `image_generation` stage will be updated.
    - It will now check for the presence of both a reference image and a logo.
    - It will call `token_manager.calculate_image_tokens` for *each* input image to get its token count.
    - The `prompt_tokens` sent to `token_manager.calculate_cost` will be the sum of the text prompt tokens and the token counts for all input images.
    - The `image_details` argument will be updated to reflect the number of input images used.

## 6. Error Handling and Fallbacks
- If the multi-modal API call fails, the system should log the error in detail.
- As a fallback, a warning should be logged, and the system could proceed by performing a simple edit using only the main reference image, thereby ignoring the logo. This ensures that the pipeline does not fail completely.

## 7. Testing Strategy

A new test file, `churns/tests/test_image_generation_scenarios.py`, should be created to validate the new logic.

- **Test Case 1**: Given no reference image and no logo, assert that the standard `generate` API is called.
- **Test Case 2**: Given a reference image but no logo, assert that the standard `edit` API is called.
- **Test Case 3**: Given both a reference image and a logo, assert that the new `_generate_with_multiple_inputs` function is called and that it makes a `chat.completions.create` call with the correctly structured multi-modal payload.
- **Test Case 4**: Given a logo but no reference image, assert that the standard `edit` API is called with the logo as the input image.
- **Test Case 5**: Test the fallback mechanism: mock a failure in the multi-modal API call and assert that the system falls back to a simple edit and logs a warning.
- **Test Case 6**: Add a new test to `churns/tests/test_token_cost_manager.py` to validate the cost calculation for a multi-modal image generation call with two input images. 