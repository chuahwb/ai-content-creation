# Style Adaptation Prompt Assembly Implementation Plan

## 1. Executive Summary

The `style_adaptation` stage (`style_adaptation.py`) was recently introduced to allow users to apply a saved `STYLE_RECIPE` preset to a new image reference. This stage generates an `adapted_visual_concept` that merges the recipe's style with the new image's subject. However, the downstream `prompt_assembly` stage (`prompt_assembly.py`) is not yet equipped to handle this specific output. It currently lacks a tailored prompt-generation strategy for style adaptation, which is a unique form of image editing.

This plan outlines the necessary changes to `prompt_assembly.py` to recognize and process the output from a style adaptation run, ensuring that the final generated prompt correctly instructs the image model to apply the desired style to the new subject from the reference image.

## 2. Analysis of the Current State

*   **`style_adaptation.py`**: This stage runs when a `STYLE_RECIPE` is used. It generates a new `visual_concept` and stores it in `ctx.generated_image_prompts`. Crucially, it also sets a flag, `ctx.adaptation_context`, which contains metadata about the adaptation process. This flag is the key to identifying a style adaptation run in subsequent pipeline stages.

*   **`prompt_assembly.py`**: This stage consumes `ctx.generated_image_prompts`. It determines an `assembly_type` (e.g., `full_generation`, `default_edit`, `instructed_edit`) based on the presence of a reference image, logo, and user instructions. It then constructs a final prompt string with a prefix corresponding to the assembly type.

*   **The Gap**: `prompt_assembly.py` has no concept of a "style adaptation edit." When it receives a `visual_concept` from the `style_adaptation` stage alongside a reference image, it defaults to one of the existing edit scenarios. These scenarios are not ideal because they don't capture the specific intent of applying a style. For instance, the "default edit" prompt tries to preserve the original subject, which is contrary to the goal of adapting to a *new* subject.

## 3. Proposed Solution

The solution is to introduce a new, dedicated logic path within `prompt_assembly.py` for style adaptation runs.

1.  **Detect Style Adaptation Runs**: In the `run` function of `prompt_assembly.py`, we will check for the existence of `ctx.adaptation_context`. If it exists, we will identify the current execution as a style adaptation run.

2.  **Introduce a New Assembly Type**: A new `assembly_type` called `style_adaptation_edit` will be created. This will provide a clear and explicit way to track and log this new prompt generation scenario.

3.  **Create a Specialized Prompt Prefix**: The core of the change will be in the `assemble_final_prompt` function. A new conditional branch will be added for the style adaptation scenario. This branch will use a new, carefully crafted prompt prefix. The prefix will instruct the image generation model to use the provided reference image as a strong compositional and subject guide, while applying the stylistic elements (lighting, color, mood, etc.) from the detailed text description of the `adapted_visual_concept`.

4.  **Pass Context to `assemble_final_prompt`**: To enable the function to recognize the new scenario, the "style adaptation" flag will be passed from the `run` function into `assemble_final_prompt` via the `user_inputs` dictionary.

## 4. Implementation Steps

1.  **Create Markdown Plan**: Write this implementation plan to a new file: `docs/plans/STYLE_ADAPTATION_PROMPT_ASSEMBLY_PLAN.md`.

2.  **Refine `prompt_assembly.py`**:
    *   **In the `run` function:**
        *   Add logic to check `hasattr(ctx, 'adaptation_context')` to determine if it's a style adaptation run.
        *   Store this boolean result in a variable (e.g., `is_style_adaptation_run`).
        *   Add this flag to the `user_inputs` dictionary that is passed to `assemble_final_prompt`.
        *   Update the `assembly_type` determination logic to include `style_adaptation_edit` as a new, high-priority condition.
    *   **In the `assemble_final_prompt` function:**
        *   Retrieve the `is_style_adaptation_run` flag from the `user_inputs` dictionary.
        *   Add a new `if is_style_adaptation_run:` block at the beginning of the main conditional logic.
        *   Inside this block, define the new prompt prefix for style adaptation. A suitable prefix would be: *"Adapt the provided reference image to match the following detailed visual concept, which combines a new subject with a specific, pre-defined style. Focus on applying the stylistic elements (lighting, color, mood, texture) from the description to the subject and composition of the reference image: "*.
        *   Construct the `final_prompt_str` using this new prefix and the existing `core_description` logic.

## 5. Expected Outcome

After implementation, when a user runs a pipeline with a `STYLE_RECIPE` preset on a new reference image, `prompt_assembly.py` will generate a highly specific and effective prompt. This prompt will guide the image generation model to successfully transfer the visual style from the recipe onto the new subject, leading to more accurate and predictable results for the style adaptation feature. 