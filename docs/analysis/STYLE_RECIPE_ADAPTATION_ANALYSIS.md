# Style Recipe Adaptation: Analysis and Recommendations

This document provides a comprehensive analysis of the "Style Recipe" feature. It evaluates the current implementation against its core objectives, identifies architectural gaps, and offers concrete recommendations for improvement to ensure the feature is robust, intuitive, and delivers on its promise of high-fidelity style adaptation.

---

## 1. Feature Approach Evaluation

The overall architectural approach of using `STYLE_RECIPE` presets is strong. Separating them from `INPUT_TEMPLATE` presets is a clean design choice, and saving the detailed, structured output from the creative pipeline (`visual_concept`, `strategy`, etc.) is the correct way to ensure high-fidelity style replication.

However, there is a significant disconnect between the stated goal and the current implementation's workflow, primarily concerning the trigger for style adaptation.

### Strengths:
- **High-Fidelity Data Capture**: Storing the `StyleRecipeData` (including `visual_concept`, `strategy`, and `style_guidance`) is excellent. It captures the full "creative DNA" of a generated image, which is essential for a true style adaptation.
- **Dedicated Adaptation Stage**: The `style_adaptation.py` stage provides a dedicated and isolated environment for the complex logic of merging a saved style with a new concept.
- **Robust Prompt Engineering**: The system prompt in `style_adaptation.py` is well-designed. It clearly instructs the AI on its role as a "Creative Director," establishes core principles (Preserve Style, Adapt Concept), and defines a clear output schema.

### Weaknesses & Gaps:
- **Flawed Adaptation Trigger**: The most critical issue is that the `StyleAdaptation` stage is **only triggered when a new text prompt is provided**. Your requirement states that adaptation should happen by default when a new image is provided, even *without* a prompt. The current logic in `style_adaptation.py` explicitly skips the stage if `ctx.overrides.get('prompt')` is missing. This undermines the primary use case.
- **Confusing User Experience (UX)**: On the frontend, loading a `STYLE_RECIPE` simply clears the form. This provides no guidance to the user. The user is expected to know that they *must* upload a new image and *can* add a new prompt. This is not intuitive and will lead to user error and frustration.
- **Implicit New Subject Handling**: The system assumes a new image is the new subject, but the connection between the user uploading a file on the frontend and that file's analysis being used in the `StyleAdaptation` stage is not explicitly implemented. The data needs to be captured, analyzed (if necessary), and passed as an override to the pipeline.

---

## 2. High-Impact Improvement Suggestions

To bridge the gap between concept and execution, the following improvements are recommended.

### 1. **Redesign the "Recipe Active" User Flow with a Modal**
Instead of just clearing the form, the UI should present a dedicated **modal overlay** when a `STYLE_RECIPE` is selected. This focuses the user on the specific adaptation task. The modal must:
-   Display the name of the active recipe (e.g., "Using 'My Favorite Look' recipe").
-   Show a preview thumbnail of the original image the recipe was saved from.
-   Present a clear, mandatory **file upload area for the new subject image**.
-   Provide an **optional text input for an accompanying prompt**.
-   Contain its own "Run" button that triggers a submission flow independent of the main form.
-   Keep the underlying main form disabled to prevent confusion.

### 2. **Make the New Subject Image the Primary Trigger**
The backend logic must be updated to reflect that the presence of a new image for a `STYLE_RECIPE` run is the primary trigger for adaptation.

-   **Modify `style_adaptation.py`**: The entry condition in the `run` function should be changed. Instead of checking only for a prompt, it should run if `ctx.preset_type == PresetType.STYLE_RECIPE` and a new subject is available (e.g., from a new image analysis result in the context).

    ```python
    # In churns/stages/style_adaptation.py

    async def run(ctx: PipelineContext) -> None:
        """
        Execute the StyleAdaptation stage to adapt a saved style recipe to a new concept.
        
        This stage runs when:
        1. A STYLE_RECIPE preset is applied.
        2. A new subject is introduced, typically via a new reference image analysis.
        """
        if ctx.preset_type != PresetType.STYLE_RECIPE:
            logger.info("StyleAdaptation skipped - no STYLE_RECIPE preset applied")
            return
        
        # A new image analysis result is the primary trigger for adaptation.
        # A new prompt is a secondary, optional input.
        new_image_analysis = getattr(ctx, 'image_analysis_result', None)
        new_user_prompt = ctx.overrides.get('prompt')

        if not new_image_analysis and not new_user_prompt:
            logger.info("StyleAdaptation skipped - no new image or prompt provided for adaptation.")
            return

        # ... rest of the function
    ```

### 3. **Enhance the System Prompt for Image-First Adaptation**
The system prompt is good but text-centric. It should be updated to clarify how to proceed when a new image is the *only* new input.

-   **Recommendation**: Add a principle emphasizing the new image as the new `main_subject`.

    ```
    **Core Principles & Constraints:**
    ...
    2. **Adapt the Concept**:
       - If a `new_image_analysis` is provided, its subject becomes the new `main_subject` of the `visual_concept`.
       - You MUST adapt the `main_subject`, `composition_and_framing`, and `background_environment` fields to fit the new subject and/or the `new_user_request`.
    ...
    ```

---

## 3. Implementation Progress Analysis (What's Missing)

Based on the analysis, here are the key missing pieces to complete the feature.

-   **Frontend (`PipelineForm.tsx` & new `StyleRecipeModal.tsx`)**:
    1.  **Create `StyleRecipeModal.tsx`**: Build a new modal component for this workflow. It should be triggered when a `STYLE_RECIPE` preset is selected from the `PresetManagementModal`.
    2.  **Self-Contained Logic**: The modal will manage its own state for the uploaded image and the optional text prompt.
    3.  **Dedicated Submission Handler**: The modal's "Run" button will have its own `onSubmit` function that:
        -   Calls the `POST /pipeline/run` endpoint.
        -   Passes the `preset_id` of the selected recipe.
        -   Sends the new image and the optional prompt in an `overrides` object.
        -   Upon success, calls the `onRunStarted` prop to navigate to the results page, bypassing the main form entirely.

-   **Backend (Pipeline & API)**:
    1.  **Image Analysis for New Subject**: The pipeline executor needs to ensure that if a new image is provided with a `STYLE_RECIPE`, it first runs through a `load_base_image` or similar analysis stage to generate the `image_analysis_result` that `StyleAdaptation` expects.
    2.  **Modify Adaptation Trigger**: As mentioned, the conditional logic in `preset_loader.py` and/or `style_adaptation.py` must be updated to correctly trigger the adaptation stage based on the presence of a new image, not just a new prompt.
    3.  **Default Adaptation Logic**: The case where a user provides a new image but *no text prompt* must be fully supported. The system needs to intelligently adapt the style to the new visual subject by default. The prompt change recommended above will help guide the LLM in this scenario.

---

## 4. Evaluation of `style_adaptation.py`

The `style_adaptation.py` file is a solid foundation, but its effectiveness is hampered by the trigger issue.

-   **Inputs (`original_visual_concept`, `new_user_request`, `new_image_analysis`)**: The chosen inputs are correct and sufficient for the task. The problem isn't the data being passed in, but the logic that prevents the stage from running in the first place.
-   **System Prompt**: The prompt is well-written and comprehensive. The use of clear principles, constraints (especially "No Minor Edits"), and a defined output schema is excellent. The suggested enhancement will make it even more robust.
-   **User Prompt (`_build_user_prompt`)**: The function correctly assembles the available information into a clear prompt for the AI. No issues here.
-   **Execution Logic**: The core logic, including model selection and JSON parsing, is sound. The primary flaw is the entry condition at the top of the `run` function. Fixing this is the highest priority.
-   **Stage Skipping**: The backend `preset_loader.py` correctly implements stage skipping for `STYLE_RECIPE` presets, which is a major strength.
-   **Data Flow Gap**: A critical finding is that while stages are modular, the data flow is incomplete. The skipped `creative_expert` stage is responsible for populating `ctx.generated_image_prompts`, which the downstream `prompt_assembly` stage requires. When skipped, this data is missing.

    **Solution**: The `style_adaptation` stage must be updated to bridge this gap by *fully mimicking* the outputs of the skipped creative block:
    1.  **`ctx.generated_image_prompts`** – wrap the adapted `visual_concept` in a dict with the same keys `creative_expert` would produce (e.g. `{ "source_strategy_index": 0, "visual_concept": adapted_visual_concept }`) and assign `[that_dict]` to the context.
    2.  **`ctx.suggested_marketing_strategies`** – a Style-Recipe already stores the original `strategy`. Copy it into a single-element list so Caption and later stages do not fail their validations.
    3.  **`ctx.style_guidance_sets`** – likewise copy the recipe’s `style_guidance` (if present) into `[ style_guidance ]`.
    With these three lists populated, every downstream stage (prompt-assembly, image-generation, caption, assessment) will find the data it expects.

    Finally, patch the pipeline executor’s `_needs_style_adaptation` helper to trigger when **either** a new image analysis result *or* a prompt override exists, mirroring the updated logic inside `style_adaptation.run`. 

---

## 5. Implementation Plan

This plan breaks down the required work into three phases, starting with the backend pipeline logic, moving to the executor, and finishing with the frontend user interface.

### Phase 1: Backend Pipeline Modifications (`churns/stages/style_adaptation.py`)

**Objective**: Make the `style_adaptation` stage a self-contained replacement for the creative block (`strategy`, `style_guide`, `creative_expert`).

1.  **Modify the Entry Trigger**:
    *   In the `run` function, change the entry condition. Instead of only checking for a prompt override, the stage must run if either a new image analysis result is present OR a new prompt is provided.
    *   **Code Change**:
        ```python
        # In churns/stages/style_adaptation.py -> run()

        new_image_analysis = getattr(ctx, 'image_analysis_result', None)
        new_user_prompt = ctx.overrides.get('prompt')

        if ctx.preset_type != PresetType.STYLE_RECIPE or (not new_image_analysis and not new_user_prompt):
            logger.info("StyleAdaptation skipped - no STYLE_RECIPE preset or no new inputs provided.")
            return
        ```

2.  **Enhance the System Prompt**:
    *   Update the `_build_system_prompt` function to include the refined logic for handling image-first adaptation.
    *   **Text Change**:
        ```
        # In churns/stages/style_adaptation.py -> _build_system_prompt()

        **Core Principles & Constraints:**
        ...
        2. **Adapt the Concept**:
           - If a `new_image_analysis` is provided, its subject becomes the new `main_subject` of the `visual_concept`.
           - You MUST adapt the `main_subject`, `composition_and_framing`, and `background_environment` fields to fit the new subject and/or the `new_user_request`.
        ...
        ```

3.  **Implement the Data Flow Bridge**:
    *   At the end of the `run` function, after the `adapted_visual_concept` has been successfully generated, add logic to populate the context variables that downstream stages depend on.
    *   **Code Change**:
        ```python
        # In churns/stages/style_adaptation.py -> run(), inside the try block after parsing

        # ...
        ctx.preset_data['visual_concept'] = adapted_visual_concept
        
        # --- NEW: Bridge the data flow gap ---
        # Mimic the output of the skipped creative stages for downstream consumers.
        
        # 1. Populate generated_image_prompts for prompt_assembly
        ctx.generated_image_prompts = [{
            "source_strategy_index": 0,
            "visual_concept": adapted_visual_concept
        }]

        # 2. Populate suggested_marketing_strategies for the caption stage
        if 'strategy' in ctx.preset_data:
            ctx.suggested_marketing_strategies = [ctx.preset_data['strategy']]

        # 3. Populate style_guidance_sets for the caption stage
        if 'style_guidance' in ctx.preset_data:
            ctx.style_guidance_sets = [ctx.preset_data['style_guidance']]
        # --- END: Bridge ---

        if ctx.overrides:
            ctx.preset_data = merge_recipe_with_overrides(ctx.preset_data, ctx.overrides)
        
        logger.info("✅ StyleAdaptation completed successfully")
        # ...
        ```

### Phase 2: Backend Executor Modifications (`churns/pipeline/executor.py`)

**Objective**: Ensure the pipeline executor correctly invokes the `style_adaptation` stage at the right time.

1.  **Update the Adaptation Trigger Condition**:
    *   Locate the `_needs_style_adaptation` helper method within the `PipelineExecutor` class.
    *   Modify its logic to check for the presence of a new image reference in the initial context, in addition to the prompt override. This ensures the executor's check matches the stage's new entry condition.
    *   **Code Change**:
        ```python
        # In churns/pipeline/executor.py -> PipelineExecutor

        def _needs_style_adaptation(self, ctx: PipelineContext) -> bool:
            """Check if StyleAdaptation stage is needed."""
            from churns.api.database import PresetType
            
            # A new image is provided if image_reference is populated for this run.
            has_new_image = ctx.image_reference is not None
            has_new_prompt = ctx.overrides and ctx.overrides.get('prompt')

            return (
                ctx.preset_type == PresetType.STYLE_RECIPE and
                (has_new_image or has_new_prompt)
            )
        ```

### Phase 3: Frontend UI/UX Implementation

**Objective**: Create an intuitive, modal-based workflow for applying Style Recipes.

1.  **Create `StyleRecipeModal.tsx`**:
    *   Create a new component file: `front_end/src/components/StyleRecipeModal.tsx`.
    *   Use `PresetManagementModal.tsx` as a template for structure and styling.
    *   The component will accept `preset: BrandPresetResponse`, `open: boolean`, `onClose: () => void`, and `onRunStarted: (run: PipelineRun) => void` as props.
    *   **UI Elements**:
        *   A title: "Adapt Style Recipe".
        *   Display the recipe name: `{preset.name}`.
        *   An `ImageWithAuth` component to show a thumbnail of the original image (Note: This may require ensuring a thumbnail URL is saved with the preset).
        *   A file uploader component (similar to the one in `LogoUploader.tsx`).
        *   A `TextField` for the optional prompt override.
        *   "Cancel" and "Run" buttons.

2.  **Implement Modal Logic**:
    *   Use `useState` hooks inside the modal to manage the selected file and the prompt text.
    *   The "Run" button will trigger an `async` submission handler. This handler will:
        *   Create a `FormData` object.
        *   Append the new image file, the optional prompt as an override, the `preset_id`, and `preset_type`.
        *   Call a new or existing function in `src/lib/api.ts` that submits this `FormData`.
        *   On a successful response, call the `onRunStarted(response)` prop to navigate to the results page.
        *   Handle errors with `toast.error()`.

3.  **Integrate Modal into `PipelineForm.tsx`**:
    *   Add state to manage the modal's visibility: `const [recipeModalOpen, setRecipeModalOpen] = useState(false);`
    *   In the `handlePresetSelected` function, modify the logic:
        ```typescript
        // In front_end/src/components/PipelineForm.tsx -> handlePresetSelected()
        
        if (preset.preset_type === 'STYLE_RECIPE') {
            setActivePreset(preset); // Keep track of the selected preset
            setRecipeModalOpen(true); // Open the new modal
            setPresetModalOpen(false); // Close the management modal
            return;
        }
        // ... existing logic for INPUT_TEMPLATE
        ```
    *   Render the modal in the `PipelineForm`'s JSX:
        ```jsx
        // In front_end/src/components/PipelineForm.tsx -> return (...)
        
        {activePreset && (
            <StyleRecipeModal
                preset={activePreset}
                open={recipeModalOpen}
                onClose={() => setRecipeModalOpen(false)}
                onRunStarted={onRunStarted}
            />
        )}
        ``` 