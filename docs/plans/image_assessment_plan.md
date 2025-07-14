# Image Assessment Stage Implementation Plan

## 1. Objective

To introduce a new pipeline stage after image generation that automatically assesses the quality of the generated image. This stage will determine if the image meets the required criteria for visual concept adherence, subject preservation, and technical quality, and will output a structured assessment along with a boolean flag (`need_refinement`) to indicate if a regeneration or refinement loop is necessary.

## 2. Proposed Solution: A New Pipeline Stage

We will implement a new stage, `image_assessment.py`, to be inserted into the pipeline immediately after `image_generation.py`. This stage will leverage a multimodal Large Language Model (LLM) with vision capabilities to perform the assessment.

The choice of a scoring-based method provides a quantitative, structured, and reproducible way to evaluate the generated assets. It allows for nuanced feedback and enables a clear, threshold-based logic for triggering a refinement loop.

## 3. Implementation Details

### 3.1. Stage Placement and Configuration

-   **New Module**: `churns/stages/image_assessment.py`
-   **Execution Order**: This stage will run after `image_generation.py`. The `configs/stage_order.yml` will be updated to reflect this new order.

    ```yaml
    # configs/stage_order.yml
    - image_eval
    - strategy
    - style_guide
    - creative_expert
    - prompt_assembly
    - image_generation
    - image_assessment # New stage
    ```

### 3.2. Core Logic: Multimodal LLM Assessment

The stage's `run` function will orchestrate a call to a multimodal LLM.

-   **Inputs to the LLM**: The prompt will consist of:
    1.  **Generated Image**: The primary image to be assessed.
    2.  **Reference Image (if provided)**: The user-uploaded image for subject preservation analysis.
    3.  **Visual Concept**: The JSON output from the `creative_expert.py` stage, which serves as the ground truth for creative direction.
    4.  **Configuration Parameters**: The `creativity` level setting, to provide context for style variations.

-   **LLM Prompt Design**: The text prompt will instruct the LLM to act as a critical art director. It will be commanded to evaluate the image based on specific criteria and return its findings in a structured JSON format.

### 3.3. Assessment Criteria & Scoring

To provide a more granular and actionable assessment, the LLM will be asked to evaluate the generated image using a 5-point scoring scale. For each criterion, the prompt will include a detailed guide to ensure consistent and meaningful scoring.

-   **5: Excellent** - Flawless execution that meets or exceeds all expectations.
-   **4: Good** - High quality with minor, non-critical issues.
-   **3: Acceptable** - Noticeable flaws that detract from the quality, but the core objective is met. Refinement is recommended.
-   **2: Poor** - Significant issues that render the result unusable for its primary purpose.
-   **1: Very Poor** - Complete failure to address the criterion.

The LLM will score the following dimensions:

1.  **`concept_adherence` (Weight: 60%)**:
    -   **Question**: How well does the generated image align with the visual concept from the creative expert?
    -   **Scoring Guide**:
        -   **5**: Perfectly captures the specified themes, mood, color palette, composition, and all key elements.
        -   **4**: Captures the overall mood and most key elements, but with minor deviations.
        -   **3**: Adheres to the main theme but misses some secondary elements or misinterprets the mood.
        -   **2**: Major deviation from the concept; key elements are missing or incorrect.
        -   **1**: Completely ignores or contradicts the visual concept.

2.  **`subject_preservation` (Weight: 40%)**:
    -   **Question**: How faithfully is the subject from the reference image represented, considering the creativity level?
    -   **Scoring Guide (Creativity Level 1 - Low)**:
        -   **5**: Near-identical, photorealistic preservation of all features and details.
        -   **4**: Perfectly recognizable with only minuscule differences in texture or lighting.
        -   **3**: Recognizable, but with noticeable inaccuracies in some features.
        -   **2**: The subject's identity is distorted or partially lost.
        -   **1**: The subject is unrecognizable.
    -   **Scoring Guide (Creativity Level 2-3 - Medium/High)**:
        -   **5**: The subject's core identity and defining features are unmistakably preserved within the new artistic style.
        -   **4**: The identity is clear, but some minor features are lost or overly stylized.
        -   **3**: The likeness is weak; key identifying features are lost or ambiguous.
        -   **2**: The subject is barely recognizable.
        -   **1**: The subject is unrecognizable.
    -   *This criterion is only scored if a reference image is used.*

3.  **`technical_quality` (Weight: 40%)**:
    -   **Question**: Is the image technically sound (excluding rendered text)?
    -   **Scoring Guide**:
        -   **5**: Flawless execution: high resolution, perfect lighting, no artifacts or anatomical issues.
        -   **4**: Minor, hard-to-spot technical flaws (e.g., slight blurriness).
        -   **3**: Noticeable issues like minor artifacts, awkward proportions, or unnatural lighting.
        -   **2**: Significant technical problems: obvious artifacts, major anatomical errors, low resolution.
        -   **1**: A technical mess, plagued by severe artifacts and distortions.

4.  **`text_rendering_quality`**:
    -   **Question**: If text was requested, is it rendered correctly and integrated well?
    -   **Scoring Guide**:
        -   **5**: Text is perfectly legible, correctly spelled, and seamlessly integrated with the image style.
        -   **4**: Text is legible and correct, but its integration has minor stylistic flaws.
        -   **3**: Legible but with minor errors (e.g., one misspelled letter, slight warping).
        -   **2**: Significant rendering issues: misspelled, illegible, or heavily distorted.
        -   **1**: The text is garbled, nonsensical, or absent.
    -   *This criterion is only scored if the `render_text` input toggle was enabled for the run.*

### 3.4. Refinement Logic

Three boolean flags will be determined based on the assessment scores to provide granular control over the refinement process. The thresholds are set to be strict to ensure high-quality outputs.

-   **`needs_subject_repair`**: This flag is triggered by poor subject preservation, suggesting a targeted fix is needed.
    -   **Applicability**: Only evaluated when a reference image is used.
    -   **Trigger Condition**: `True` if `subject_preservation < 4`.

-   **`needs_text_repair`**: This flag is triggered by poor text rendering.
    -   **Applicability**: Only evaluated if text rendering was requested.
    -   **Trigger Condition**: `True` if `text_rendering_quality < 4`.

-   **`needs_regeneration`**: This flag indicates general quality issues related to the creative concept or technical execution, suggesting the image should be regenerated.
    -   **General Score Calculation**: A `general_score` is computed to measure overall quality, excluding subject and text-specific issues.
        `general_score = (concept_adherence * 0.6) + (technical_quality * 0.4)`
    -   **Trigger Condition**: `True` if `general_score < 3.5`.

## 4. Data Structure

The `image_assessment.py` stage will append the following JSON object to the `PipelineContext.data` dictionary under the key `image_assessment`.

```json
{
  "assessment_scores": {
    "concept_adherence": 4,
    "subject_preservation": 5,
    "technical_quality": 4,
    "text_rendering_quality": 2
  },
  "assessment_justification": {
    "concept_adherence": "The image captures the 'dramatic, high-contrast' mood and most key elements, but the color palette is slightly muted.",
    "subject_preservation": "The subject's facial features and unique hairstyle are perfectly preserved, matching the reference image despite the shift to a 'sci-fi' art style.",
    "technical_quality": "The image is high-resolution with no noticeable artifacts. The aspect ratio is correct.",
    "text_rendering_quality": "The requested text 'Welcome' is misspelled as 'Welcom' and appears warped."
  },
  "general_score": 4.0,
  "needs_subject_repair": false,
  "needs_regeneration": false,
  "needs_text_repair": true
}
```

## 5. Next Steps

1.  **Create Stage Module**: Implement the `churns/stages/image_assessment.py` file with the `run(ctx: PipelineContext)` function.
2.  **Develop LLM Prompt**: Craft and test the detailed prompt for the multimodal LLM to ensure reliable JSON output.
3.  **Update Pipeline Executor**: No changes are expected in `executor.py` as it dynamically loads stages.
4.  **Update Configuration**: Add `image_assessment` to `configs/stage_order.yml`.
5.  **Testing**:
    -   Create unit tests for the `image_assessment` stage with mocked LLM calls.
    -   Create integration tests to ensure it works correctly within the full pipeline.
    -   Test various scenarios (with/without reference image, different creativity levels) to validate the scoring and refinement logic. 