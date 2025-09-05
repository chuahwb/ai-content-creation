# Caption Feature Enhancement Plan: User Instructions & Length Control

## 1. Objective

This document outlines the plan to enhance the caption generation feature by introducing two new user-configurable options:
1.  **User Instructions**: A free-text input field allowing users to provide direct requests or instructions for the caption.
2.  **Caption Length**: A set of predefined options (e.g., Short, Medium, Long) to guide the length of the final generated caption, overriding the default auto-detection logic.

The goal is to provide users with more granular control over the creative output while integrating these new features seamlessly into the existing architecture.

## 2. Analysis of Current Architecture

The current caption generation system, located in `churns/stages/caption.py`, employs a sophisticated two-stage LLM pipeline:

1.  **Analyst LLM**: This model acts as a "Social Media Strategist". It receives a wide range of context, including marketing strategy, visual analysis of the image, brand kit details (like brand voice), and user settings. Its primary role is to synthesize this information and produce a structured JSON object called a `CaptionBrief`. This brief contains strategic guidance (e.g., core message, SEO keywords, tone of voice, call to action) for the next stage.

2.  **Writer LLM**: This model acts as a "Creative Copywriter". It receives the `CaptionBrief` from the Analyst and is tasked with writing the final, polished caption. Its instructions emphasize adhering strictly to the brief to ensure the output aligns with the upfront strategy.

This two-stage approach is robust because it separates strategic planning from creative execution, leading to more consistent and on-brand results.

### Key Architectural Considerations:

*   **`CaptionSettings`**: A Pydantic model that defines the user-configurable options passed from the API. This will need to be extended.
*   **`CaptionBrief`**: A Pydantic model that defines the contract between the Analyst and Writer LLMs. This will also need modification to carry the new length instruction.
*   **`_resolve_final_instructions`**: A critical function that translates user settings from `CaptionSettings` into explicit, non-negotiable instructions for the Analyst LLM. This is the ideal place to inject our new controls.
*   **Regeneration Logic**: The system has an optimized flow to regenerate only the writer's output if the strategic brief hasn't changed. This logic (located upstream from the caption stage) must be updated to recognize when the new settings require the Analyst to be re-run.

## 3. Proposed Implementation Plan

The following plan is designed to integrate the new features with minimal disruption while maximizing their effectiveness.

### 3.1. Data Model Modifications

The first step is to update the core data structures to accommodate the new options.

**File:** `churns/api/schemas.py` (or equivalent model definition file)

1.  **`CaptionSettings` Schema**:
    *   Add `user_instructions: Optional[str] = None`: This field will capture the user's custom request.
    *   Add `caption_length: Optional[Literal["Auto", "Short", "Medium", "Long"]] = "Auto"`: This provides a controlled vocabulary for the desired caption length, with "Auto" as the default to maintain existing behavior.

2.  **`CaptionBrief` Schema**:
    *   Add `length_guidance: Optional[str] = None`: This new field will be populated by the Analyst LLM with a descriptive instruction for the Writer LLM based on the user's `caption_length` selection.

### 3.2. Feature 1: User Instructions Integration

The user's direct instructions must be a high-priority driver for the strategic `CaptionBrief`.

**File:** `churns/stages/caption.py`

1.  **Modify `_resolve_final_instructions()`**:
    *   This function will generate a new instruction key, `user_request`.
    *   If `settings.user_instructions` is provided, the instruction will be precise and directive:
        *   `instructions['user_request'] = f"You MUST prioritize and directly address the following user instruction in your brief. It should heavily influence the 'core_message' and 'key_themes_to_include'. User Instruction: '{settings.user_instructions}'"`

2.  **Modify `_get_analyst_user_prompt()`**:
    *   The new instruction will be placed prominently within the `INSTRUCTIONS_FOR_BRIEF` section to ensure it is not missed.
    *   **Example Prompt Structure:**
        ```
        ...
        **INSTRUCTIONS_FOR_BRIEF**
        Based on all the CONTEXT_DATA above, you must follow these explicit instructions to generate the CaptionBrief JSON object:
        - User Request Instruction: {final_instructions['user_request']}
        - Tone of Voice Instruction: {final_instructions['tone']}
        - Call to Action Instruction: {final_instructions['cta']}
        ...
        ```

### 3.3. Feature 2: Caption Length Control

This feature translates a user's choice into a direct, actionable instruction for the Writer LLM, using the Analyst as the intermediary.

**File:** `churns/stages/caption.py`

1.  **Modify `_resolve_final_instructions()`**:
    *   A new instruction key, `length`, will be generated.
    *   If `settings.caption_length` is not "Auto", this function will instruct the Analyst on how to populate the `length_guidance` field in the brief. This mapping ensures the guidance is dynamic and context-aware.
    *   **Refined Mapping Logic (Platform-Aware):**
        *   **"Short"**: `instructions['length'] = "The user has requested a 'Short' caption. Your task is to populate the `length_guidance` field in the JSON brief with a clear, firm instruction for the writer, such as: 'Generate a very concise, high-impact caption, under 125 characters. It must be a powerful hook or a direct question to grab attention immediately. This is ideal for visually-driven content where the message must be instant.'"`
        *   **"Medium"**: `instructions['length'] = "The user has requested a 'Medium' caption. Your task is to populate the `length_guidance` field in the JSON brief with a clear, firm instruction for the writer, such as: 'Generate a balanced caption of about 3-5 sentences (around 125-500 characters). This length should provide valuable context, tell a mini-story, and encourage engagement without overwhelming the reader.'"`
        *   **"Long"**: `instructions['length'] = "The user has requested a 'Long' caption. Your task is to populate the `length_guidance` field in the JSON brief with a clear, firm instruction for the writer, such as: 'Generate a detailed, long-form caption (500+ characters), like a micro-blog post. This must be used for in-depth storytelling or providing significant educational value. Structure it with line breaks for readability to create save-worthy content.'"`

2.  **Modify `_get_analyst_system_prompt()`**:
    *   The `CaptionBrief` JSON schema within the Analyst's system prompt must be updated to include the new `length_guidance` field, making it a valid output parameter.
    *   **Exact schema addition:**
        ```json
        {{
          ...
          "emoji_suggestions": [...],
          "length_guidance": "Optional. A specific instruction for the writer regarding the desired length of the caption. Set to null if no specific length is requested.",
          "task_type_notes": "..."
        }}
        ```

3.  **Modify `_get_writer_user_prompt()`**:
    *   When constructing the prompt for the Writer LLM, a new, clearly marked section for the length requirement will be added if `brief.length_guidance` is present.
    *   **Example Prompt Structure:**
        ```
        Write a social media caption based on this strategic brief:

        **Core Message:** {brief.core_message}
        **Tone of Voice:** {brief.tone_of_voice}
        **Length Requirement:** {brief.length_guidance}
        ...
        ```

4.  **Modify `_get_writer_system_prompt()`**:
    *   A `CRITICAL` instruction will be added to the Writer's system prompt to ensure the length requirement is strictly followed.
    *   **Exact instruction to add:**
        *   ` - **CRITICAL LENGTH:** If a 'Length Requirement' is provided in the brief, you MUST strictly adhere to it. This is a non-negotiable instruction.`

### 3.4. Handling Caption Regeneration

It is crucial that the Analyst is re-run when these new settings are modified during a regeneration request.

**File:** `churns/api/routers.py` and/or `churns/api/background_tasks.py` (wherever regeneration logic is handled)

1.  **Update Regeneration Logic**:
    *   Locate the logic that determines whether to set the `regenerate_writer_only` flag to `True`.
    *   This logic likely compares the new `caption_settings` from the user's request with the `settings_used` in the previous `CaptionResult`.
    *   Extend this comparison to include `user_instructions` and `caption_length`. If either of these fields has changed, `regenerate_writer_only` **must be set to `False`** to force the Analyst LLM to create an updated `CaptionBrief`.

## 4. Summary of Changes by File

*   **`churns/api/schemas.py`**:
    *   Add `user_instructions` and `caption_length` fields to `CaptionSettings`.
    *   Add `length_guidance` field to `CaptionBrief`.
*   **`churns/stages/caption.py`**:
    *   Update `_resolve_final_instructions` to process the two new settings.
    *   Update `_get_analyst_system_prompt` and `_get_analyst_user_prompt` to pass new instructions to the Analyst.
    *   Update `_get_writer_system_prompt` and `_get_writer_user_prompt` to ensure the Writer adheres to the new length guidance.
*   **`churns/api/routers.py`** (or `background_tasks.py`):
    *   Modify the regeneration conditional logic to ensure the Analyst is re-run when `user_instructions` or `caption_length` change.
*   **`front_end/`**:
    *   (Future Task) UI components (e.g., `PipelineForm.tsx` or a dedicated caption settings modal) will need to be updated to include a text area for "User Instructions" and a dropdown/radio group for "Caption Length".

This approach ensures the new features are deeply and correctly integrated into the existing pipeline, respecting its strategic design and maintaining high-quality output.
