# Creative Expert Stage: Refinement and Improvement Plan

This document outlines potential improvements for the `churns/stages/creative_expert.py` stage. The recommendations are divided into two categories: prompt architecture enhancements and code logic/mechanism refinements.

## 1. Prompt Architecture Improvements

The current prompt is long and detailed, which is a strength for achieving precision. The following suggestions aim to enhance its effectiveness and manage its complexity without sacrificing detail.

### 1.1. Strategic Instruction Placement

*   **Observation:** The most critical, action-oriented instructions are correctly placed at the end of the user prompt (within the `final_instruction` block). This serves as a powerful "final checklist" for the LLM before it generates its response.
*   **Recommendation:** This is a key architectural strength and should be maintained. Its effectiveness should be recognized and preserved in any future prompt modifications.

### 1.2. Instruction Distillation

*   **Observation:** Some sections, particularly the `task_type_guidance_map`, are verbose. While descriptive, this verbosity increases the cognitive load on the model, potentially diluting the importance of other instructions.
*   **Recommendation:** Consider distilling some of the guidance into more direct, keyword-based instructions. For example, instead of a full sentence, the guidance for a task could be a list of key concepts (e.g., `["clear product focus", "vibrant", "sales-oriented"]`). This could make the prompt more efficient without losing the core intent.

### 1.3. Strengthen Role-Playing Persona

*   **Observation:** The prompt successfully establishes an expert "Creative Director" persona at the beginning. This could be leveraged more strongly at the end to focus the model.
*   **Recommendation:** Modify the final instruction to be a direct command to the persona. For example: *"As the Creative Director, your final task is to deliver the `ImageGenerationPrompt` JSON object now, ensuring it meets all the above requirements."* This reinforces the persona and can help improve adherence to the requested format.

## 2. Code Logic and Mechanism Improvements

The Python code is robust and handles numerous edge cases. These recommendations focus on improving modularity, clarity, and long-term maintainability.

### 2.1. Encapsulate LLM Client and Parsing Strategy

*   **Observation:** The logic for selecting the LLM client (`instructor` vs. `base`) and determining the JSON parsing strategy (`manual` vs. `instructor-native`) is spread across multiple variables and conditional checks (e.g., `use_manual_parsing`, `INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS`).
*   **Recommendation:** Create a dedicated helper function or a small class to encapsulate this decision-making process. This would significantly simplify the main generation function and centralize the client-selection logic, making it easier to update and maintain.
    ```python
    # Example of a helper function
    def select_llm_strategy(model_id: str) -> Tuple[Any, bool]:
        """
        Determines the correct LLM client and parsing strategy for a given model ID.
        Returns a tuple: (client_instance, use_instructor_parsing_flag).
        """
        # ... logic to check for problematic models and return appropriate client ...
        pass
    ```

### 2.2. Simplify and Modularize Prompt Construction

*   **Observation:** The main prompt-building functions, `_get_creative_expert_system_prompt` and `_get_creative_expert_user_prompt`, are monolithic and assemble many f-string blocks. This makes them difficult to read and modify.
*   **Recommendation:** Break down these large functions into smaller, single-purpose functions. For example, the system prompt function could be composed of calls to `_get_creativity_guidance(level)`, `_get_image_reference_handling_rules(has_ref, has_inst)`, etc. This improves readability, testability, and makes the overall structure more modular.

### 2.3. Address Root Cause of `fallback_validation` for `promotional_text_visuals`

*   **Observation:** The code includes a complex `fallback_validation` function to handle cases where the LLM incorrectly formats `promotional_text_visuals` as a dictionary instead of a string. This is excellent defensive coding, but it treats a symptom.
*   **Recommendation:** Attempt to prevent the error at the source by making the prompt instruction for this field even more explicit. For example: *"The `promotional_text_visuals` field MUST be a single JSON string. If you need to describe multiple text elements (like a headline and a sub-headline), describe them all within this single string, using markdown or clear separators."* This could reduce the need for complex and potentially brittle parsing logic.

### 2.4. Refine Configuration Management

*   **Observation:** The module relies on several globally-scoped variables that are injected at runtime (e.g., `CREATIVE_EXPERT_MODEL_ID`, various clients). This service locator pattern is functional but can make unit testing and dependency management more difficult.
*   **Recommendation:** For a more robust long-term architecture, introduce a dedicated configuration object (e.g., a Pydantic model or a dataclass) that is passed into the main functions. This `CreativeExpertConfig` would bundle all necessary clients and settings, making the module's dependencies explicit and improving its testability and reusability.
    ```python
    # Example Pydantic model for configuration
    class CreativeExpertConfig(BaseModel):
        model_id: str
        model_provider: str
        instructor_client: Any
        base_llm_client: Any
        # ... other settings ...

    # Example of updated function signature
    async def run(ctx: PipelineContext, config: CreativeExpertConfig) -> None:
        # ... use config.model_id, config.instructor_client, etc. ...
        pass
    ``` 