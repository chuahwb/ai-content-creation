# Unified Prompt Input: Detailed Implementation Plan

## 1. Overview

This document provides a detailed, step-by-step implementation plan for the unified prompt initiative, based on the analysis in `UNIFIED_PROMPT_INPUT_ANALYSIS.md`. The goal is to refactor the user input mechanism from three distinct text fields into a single "smart prompt" and an optional field for rendered text, supported by a new backend `IntentParser` stage.

**Success Criteria:**
-   The user interface is simplified to one primary text area and one optional text input for rendering.
-   The backend correctly interprets a wide variety of user inputs from the single prompt.
-   End-to-end image generation quality is maintained or improved across all scenarios (generation, default edits, instructed edits, text rendering).
-   The changes are modular and well-tested.

## 2. Phase 1: Backend Implementation

### Step 2.1: Create the `IntentParser` Stage

This new stage will be the first in the pipeline, responsible for deconstructing the user's unified prompt.

**1. Create New File:**
   -   `churns/stages/intent_parser.py`

**2. Define Pydantic Model in `churns/models/presets.py` (or a relevant models file):**
   ```python
   # In churns/models/presets.py or a new churns/models/intent.py
   
   from pydantic import BaseModel, Field
   from typing import Optional

   class ParsedIntent(BaseModel):
       """
       Represents the structured output from the IntentParser stage, deconstructing
       the user's single unified prompt into actionable components for the pipeline.
       """
       core_request: str = Field(
           description="A concise summary of the user's main creative request, combining theme, subject, and style. This should be a self-contained, clear instruction for a creative agent."
       )
       image_modification_instructions: Optional[str] = Field(
           default=None,
           description="If the user's prompt implies a reference image is being edited, these are the specific instructions for how to modify it (e.g., 'change the color of the car to red', 'remove the person in the background'). Null if no instructions are given or no image is provided."
       )
       task_specific_details: Optional[str] = Field(
           default=None,
           description="Details specifically related to the selected marketing task type that aren't part of the core creative request (e.g., 'for a summer campaign', 'to announce a new store opening'). Null if not applicable."
       )

   ```

**3. Implement the Stage Logic in `churns/stages/intent_parser.py`:**
   ```python
   """
   Stage 0: Intent Parser

   Analyzes the user's unified prompt using an LLM to deconstruct it into
   structured, actionable components for downstream pipeline stages.
   """
   
   from ..pipeline.context import PipelineContext
   from ..models.presets import ParsedIntent # Adjust import path as needed

   # Global variables for clients and models to be injected by the executor
   instructor_client_intent = None
   INTENT_PARSER_MODEL_ID = "gpt-4-turbo" # Or other suitable model

   def get_intent_parser_system_prompt() -> str:
       return """You are an expert at understanding user requests for an AI image generation tool in the F&B marketing domain. Your task is to analyze the user's single, unified prompt and deconstruct it into three distinct, structured components based on the `ParsedIntent` model.

**Key Objectives:**
1.  **Isolate Core Creativity**: Extract the central creative idea—the subject, theme, style, mood, and composition—into `core_request`. This should be a clear, standalone instruction for a creative director.
2.  **Identify Edit Instructions**: If a reference image is being used, meticulously identify any specific, direct commands to modify that image and place them in `image_modification_instructions`. If the user just describes a scene without giving a command like "change," "remove," or "add," this field should be null, even if a reference image is present.
3.  **Capture Task Context**: Extract any details that relate *only* to the marketing task (e.g., "for a Christmas promotion," "announcing a new flavor") and place them in `task_specific_details`.

**Strict Rules:**
-   Do NOT be conversational. Output only the JSON object.
-   If a piece of information fits into `image_modification_instructions` or `task_specific_details`, it should NOT be duplicated in `core_request`.
-   If the user's prompt is simple (e.g., "a photo of a coffee cup"), `image_modification_instructions` and `task_specific_details` should be null."""

   def get_intent_parser_user_prompt(unified_prompt: str, has_reference_image: bool, task_type: str) -> str:
       image_context = "A reference image HAS been provided." if has_reference_image else "No reference image has been provided."
       
       return f"""Analyze the following user prompt and deconstruct it into the required JSON format.

**Context:**
-   **Reference Image Status:** {image_context}
-   **Marketing Task Type:** '{task_type}'

**User's Unified Prompt:**
---
"{unified_prompt}"
---

Now, provide the structured `ParsedIntent` JSON object."""


   async def run(ctx: PipelineContext) -> None:
       """
       Parses the unified prompt and populates the context with structured intent.
       """
       ctx.log("Starting Intent Parser stage...")
       
       if not instructor_client_intent:
           raise Exception("Intent Parser LLM client not configured.")

       has_reference = ctx.image_reference is not None
       
       parsed_intent = instructor_client_intent.chat.completions.create(
           model=INTENT_PARSER_MODEL_ID,
           response_model=ParsedIntent,
           messages=[
               {"role": "system", "content": get_intent_parser_system_prompt()},
               {
                   "role": "user", 
                   "content": get_intent_parser_user_prompt(
                       ctx.unified_prompt, 
                       has_reference, 
                       ctx.task_type or "N/A"
                   )
               }
           ]
       )

       # Populate the context with the parsed results
       ctx.prompt = parsed_intent.core_request # Overwrite old `prompt`
       
       # For image_instruction, we need to place it where the pipeline expects it
       if ctx.image_reference and parsed_intent.image_modification_instructions:
           ctx.image_reference["instruction"] = parsed_intent.image_modification_instructions
       
       ctx.task_description = parsed_intent.task_specific_details # Overwrite old `task_description`

       ctx.log("Intent Parser stage completed successfully.")
       ctx.log(f"  - Core Request: {ctx.prompt[:100]}...")
       if ctx.image_reference and ctx.image_reference.get("instruction"):
           ctx.log(f"  - Image Instruction: {ctx.image_reference.get('instruction')}")
       if ctx.task_description:
           ctx.log(f"  - Task Details: {ctx.task_description}")

   ```

### Step 2.2: Update API Endpoint and Pipeline Executor

**1. Modify API Request Schema in `churns/api/schemas.py`:**
   -   Find the Pydantic model used for the pipeline request body.
   -   Remove `prompt`, `task_description`.
   -   Add `unified_prompt: str` and `text_to_render: Optional[str] = None`.
   -   The `image_instruction` was likely part of the `ImageReference` object; we will handle its removal from the API input but populate it later in the `IntentParser`. The API should no longer accept it directly from the user.

**2. Update Pipeline Executor in `churns/pipeline/executor.py`:**
   -   **Modify the pipeline stage order:** The new `intent_parser` stage must be the first stage to run.
   -   **Update context creation:** The initial `PipelineContext` should be populated with `unified_prompt` and `text_to_render` from the API request.

### Step 2.3: Adapt Downstream Stages

The changes here are minimal, mostly just ensuring the right variables are being read. Since `IntentParser` overwrites `ctx.prompt`, `ctx.task_description`, and `ctx.image_reference['instruction']`, the downstream stages (`image_eval`, `strategy`, `style_guide`, `prompt_assembly`) require **no changes** to their logic, as they will read the newly populated context variables.

**The only stage requiring modification is `creative_expert.py`:**

-   **Modify `_get_creative_expert_user_prompt`:** This function needs to be updated to handle the new, separate `text_to_render` field.
    -   It currently uses `task_description` for both task details and text content. We will separate these.
    -   **Precise Prompt Refinement:**
        -   **Find this line (or similar):**
            ```python
            if task_description:
                user_prompt_parts.append(f"- Specific Task Content/Description: '{task_description}' {text_render_status}...")
            ```
        -   **Replace with:**
            ```python
            # In _get_creative_expert_user_prompt in creative_expert.py

            # ...
            text_render_status = "(Text rendering enabled by user)" if render_text_flag else "(Text rendering DISABLED by user)"

            if task_description:
                user_prompt_parts.append(f"- Task-Specific Details: '{task_description}' (Use this for high-level context).")

            if render_text_flag and text_to_render:
                user_prompt_parts.append(f"- Text to Render on Image: '{text_to_render}' (This is the exact text the user wants. Describe its visualization in the `promotional_text_visuals` field).")
            elif render_text_flag:
                user_prompt_parts.append(f"- Text to Render on Image: Not provided, but text rendering is enabled. If text is essential for this task type, you may suggest some in `promotional_text_visuals`.")
            # ...
            ```
-   **Update the function signature and call:**
    -   Add `text_to_render: Optional[str]` to the function signature of `_get_creative_expert_user_prompt`.
    -   Pass `ctx.text_to_render` when calling it from `_generate_visual_concept_for_strategy`.

## 3. Phase 2: Frontend Implementation

### Step 3.1: Redesign the User Input Form

**Target File:** `front_end/src/components/PipelineForm.tsx`

**1. Update State Management:**
   -   Remove `prompt`, `imageInstruction`, `taskDescription` states.
   -   Add new state variables:
     ```typescript
     const [unifiedPrompt, setUnifiedPrompt] = useState<string>('');
     const [textToRender, setTextToRender] = useState<string>('');
     ```

**2. Modify the JSX:**
   -   Remove the three `Textarea` or `Input` components for the old fields.
   -   **Add the new Unified Prompt `Textarea`:**
     ```tsx
     <FormControl isRequired>
       <FormLabel>Your Creative Request</FormLabel>
       <Textarea
         placeholder="Describe the image you want. Include the subject, style, colors, and mood. If you've uploaded an image, tell us how you'd like to change it."
         value={unifiedPrompt}
         onChange={(e) => setUnifiedPrompt(e.target.value)}
         size="lg"
         minHeight="150px"
       />
     </FormControl>
     ```
   -   **Add the new (conditional) Text to Render `Input`:**
     ```tsx
     {renderText && (
       <FormControl mt={4}>
         <FormLabel>Text to Appear on Image (Optional)</FormLabel>
         <Input
           placeholder="e.g., 'Summer Sale' or 'Grand Opening'"
           value={textToRender}
           onChange={(e) => setTextToRender(e.target.value)}
         />
       </FormControl>
     )}
     ```
     *(Note: `renderText` is the state variable tied to the "Render Text" toggle)*

### Step 3.2: Update the API Submission Logic

**Target File(s):** `front_end/src/components/PipelineForm.tsx` and potentially `front_end/src/lib/api.ts`

-   Find the `handleSubmit` or equivalent function in `PipelineForm.tsx`.
-   Locate the construction of the request body for the API call.
-   Modify the payload to match the new backend API schema.
    -   **Old structure (example):**
      ```javascript
      const payload = {
        prompt: prompt,
        task_description: taskDescription,
        image_reference: {
          //...,
          instruction: imageInstruction
        }
      };
      ```
    -   **New structure:**
      ```javascript
      const payload = {
        unified_prompt: unifiedPrompt,
        text_to_render: renderText ? textToRender : undefined,
        // ... other fields like image_reference (without instruction), brand_kit etc.
      };
      ```

## 4. Phase 3: Testing Plan

Execute the following end-to-end tests to validate the implementation.

| Test Case                         | User Input (`unifiedPrompt` / `textToRender`)                                                                                              | Expected `IntentParser` Output                                                                                                                                                                                                                                                               |
| --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| **1. Simple Generation**            | `unifiedPrompt`: "A cinematic, photorealistic shot of a steaming cup of black coffee on a rustic wooden table in a cozy cafe."              | `core_request`: (The full prompt) <br> `image_modification_instructions`: null <br> `task_specific_details`: null                                                                                                                                                                              |
| **2. Generation w/ Text**           | `unifiedPrompt`: "A fun, vibrant graphic for a new milkshake flavor." <br> `textToRender`: "Introducing the Mango Tango!"                  | `core_request`: "A fun, vibrant graphic for a new milkshake flavor." <br> `image_modification_instructions`: null <br> `task_specific_details`: null (The text is handled by the separate field)                                                                                                |
| **3. Default Edit** (Image Uploaded) | `unifiedPrompt`: "Make this photo of a burger look more professional, with dramatic lighting and a clean background."                       | `core_request`: "Make this photo of a burger look more professional, with dramatic lighting and a clean background." <br> `image_modification_instructions`: null *(Crucial: no direct command like "change" was given)* <br> `task_specific_details`: null                                    |
| **4. Instructed Edit** (Image Upld) | `unifiedPrompt`: "I like the composition, but please change the color of the teapot to a bright royal blue."                                 | `core_request`: "I like the composition." <br> `image_modification_instructions`: "change the color of the teapot to a bright royal blue." <br> `task_specific_details`: null                                                                                                                 |
| **5. Complex Combined Request**     | `unifiedPrompt`: "For our grand opening event, please take the attached photo of our storefront and add festive balloons. Also, make the lighting feel warmer and more inviting." <br> `textToRender`: "Grand Opening - This Saturday!" | `core_request`: "Make the lighting of the storefront photo feel warmer and more inviting." <br> `image_modification_instructions`: "add festive balloons." <br> `task_specific_details`: "For our grand opening event." |
