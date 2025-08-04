# Prompt Assembly Refactoring and Enhancement Plan

## 1. Analysis of Current Implementation

The current `assemble_final_prompt` function in `churns/stages/prompt_assembly.py` uses a large `if/elif/else` structure to handle various prompt generation scenarios. This has led to:

*   **Code Repetition**: The logic for assembling `core_description_parts` is repeated across multiple branches with only minor differences (e.g., inclusion of `main_subject`, or labeling of `composition_and_framing`). This makes the code harder to maintain.
*   **Complex Conditional Logic**: The conditions for choosing a prompt prefix are intertwined and spread out, making it difficult to understand the decision-making process at a glance.
*   **Limited Style Adaptation**: The style adaptation logic (`is_style_adaptation_run`) currently assumes a reference image is always present and does not account for the presence of a logo, which limits its flexibility.

## 2. Proposed Refactoring

To address these issues, I propose a significant refactoring of `assemble_final_prompt` by breaking it down into smaller, more manageable helper functions.

### 2.1. Centralized Core Description Assembly

I will create a helper function, `_assemble_core_description`, to consolidate the assembly of the prompt's main body.

```python
def _assemble_core_description(vc: Dict[str, Any], user_inputs: Dict[str, Any], include_main_subject: bool) -> str:
    # ... implementation ...
```

This function will:
*   Accept a flag (`include_main_subject`) to conditionally include the `main_subject`.
*   The `main_subject` will be omitted from the prompt whenever a reference image exists, as the image itself defines the subject. The `include_main_subject` flag will be set to `not has_reference` in the main function.
*   The `composition_and_framing` component will always be prefixed with "Composition and Framing:" for better readability in all scenarios.
*   House all the logic for creating the core prompt string from the `visual_concept` (`vc`).

### 2.2. Decoupled Prefix Selection

I will create a second helper function, `_get_prompt_prefix`, to determine the appropriate prefix based on the context.

```python
def _get_prompt_prefix(is_style_adaptation: bool, has_reference: bool, has_logo: bool, has_instruction: bool, is_default_edit: bool, instruction_text: str) -> str:
    # ... implementation ...
```
This function will contain the decision logic for selecting a prefix, making it clean and testable.

### 2.3. Simplified Main Function

The `assemble_final_prompt` function will be simplified to orchestrate the calls to these new helper functions.

```python
def assemble_final_prompt(structured_prompt_data: Dict[str, Any], user_inputs: Dict[str, Any], platform_aspect_ratio: str) -> str:
    # 1. Extract context variables (has_logo, has_reference, etc.)
    # 2. Call _get_prompt_prefix()
    # 3. Call _assemble_core_description()
    # 4. Combine prefix, description, and suffix to form the final prompt.
```

## 3. Key Enhancement: Flexible Style Adaptation

The refactoring will enable a key enhancement: making style adaptation more flexible.

The `_get_prompt_prefix` function will be designed to handle style adaptation runs both with and without a logo. When `is_style_adaptation_run` is true, it will select a prefix that correctly reflects the inputs:

*   **With Reference Image only**: "Adapt the provided reference image..."
*   **With Reference Image and Logo**: "Adapt the provided reference image, integrating the provided logo, to match the following detailed visual concept..."

This preserves the core intent of style adaptation while expanding its capabilities to handle more complex scenarios involving brand assets.

By implementing this plan, `prompt_assembly.py` will become more modular, maintainable, and extensible. 