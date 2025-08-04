# Image Assessment Enhancement Plan: Noise & Grain Detection (v2)

This document outlines the plan to enhance the `image_assessment.py` stage by adding a new criterion to assess noise and grain in generated images. This version incorporates user feedback for a simpler scale and a more streamlined UI integration.

## 1. Analysis and Recommendations

The proposal to add a noise and grain assessment is a valuable improvement. It isolates a common, model-specific artifact from the core creative and technical quality assessments, providing more targeted feedback for potential refinement.

### Recommendations (Updated):

*   **Scoring Scale**: We will implement a simplified **1-3 integer scale** for `noise_and_grain_impact`. This is more practical for the LLM and easier for users to interpret.
    *   **3**: No significant noise or grain.
    *   **2**: Mild, acceptable noise/grain present.
    *   **1**: Serious noise/grain that degrades quality.
*   **Flagging**: A new boolean flag, `needs_noise_reduction`, will be triggered if the `noise_and_grain_impact` score is **less than 3** (i.e., a score of 1 or 2). This provides a clear signal for UI highlighting.
*   **Justification**: As requested, the LLM will **not** be asked for a justification for this score.
*   **Independence**: This new criterion will **not** contribute to the `general_score` calculation.

## 2. Implementation Plan

### Backend Implementation (`churns` directory)

1.  **Update the Data Model (`churns/models/__init__.py`)**:
    *   Modify the `ImageAssessmentResult` Pydantic model. The `noise_and_grain_impact` score will be added to the `assessment_scores` dictionary for consistency, and the `needs_noise_reduction` flag will be a separate boolean field.
    *   **Modified `ImageAssessmentResult`**:
        *   `assessment_scores`: The dictionary will now be allowed to contain `"noise_and_grain_impact"`.
        *   Add new field: `needs_noise_reduction: bool = Field(False, description="Flag indicating if noise/grain is significant.")`

2.  **Enhance the Image Assessor (`churns/stages/image_assessment.py`)**:
    *   **Update Assessment Prompt (`_create_assessment_criteria_section`)**:
        *   Add a new section: `## 5. NOISE & GRAIN ASSESSMENT`.
        *   Define the criterion and provide the **1-3 scoring guide**.
    *   **Update JSON Format (`_create_json_format_section`)**:
        *   Modify the required JSON `assessment_scores` object to include the new optional field: `"noise_and_grain_impact": <integer 1-3>`.
    *   **Update Flag Calculation (`_calculate_refinement_flags`)**:
        *   Update the function to calculate the new flag.
        *   Logic: `flags["needs_noise_reduction"] = scores.get("noise_and_grain_impact", 3) < 3`. A default of 3 ensures no flag is raised if the score is missing.

### Frontend Implementation (`front_end` directory)

1.  **Update Frontend Types (`front_end/src/types/api.ts`)**:
    *   Locate the TypeScript interface for the image assessment result.
    *   Add the new optional fields to the `assessment_scores` object and the main interface:
        *   In `assessment_scores`: `noise_and_grain_impact?: number;`
        *   In the main result type: `needs_noise_reduction?: boolean;`

2.  **Display the Flag in UI (`front_end/src/components/RunResults.tsx` or `RefinementDetailsDialog.tsx`)**:
    *   In the component responsible for displaying image assessment details, there is no need to show the numeric score.
    *   A new colored tag (e.g., "Noise/Grain") will be rendered alongside the existing tags ("Subject," "Overall," "Text") **only if** the `needs_noise_reduction` flag is `true`. This provides an immediate, non-intrusive visual cue.

## 3. Validation and Testing

*   **Backend**: Update unit tests in `churns/tests/test_image_assessment_stage.py` to:
    *   Verify the prompt includes the new 1-3 scale.
    *   Confirm the `needs_noise_reduction` flag is correctly calculated from the 1-3 score.
*   **Frontend**: Manually test to ensure:
    *   The "Noise/Grain" tag appears only when `needs_noise_reduction` is true.
    *   The UI remains unchanged for older run data that lacks the new flag.

This revised plan is more streamlined and directly reflects the desired user experience.
