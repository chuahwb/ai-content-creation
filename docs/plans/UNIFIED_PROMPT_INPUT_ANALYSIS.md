# Enhancing User Input for Image Generation: A Proposal for a Unified Prompting Experience

## 1. Executive Summary

The application's current image generation pipeline is powerful, but its frontend user input mechanism, consisting of three separate text areas (`Prompt`, `Image Instruction`, `Task Description`), creates ambiguity and increases cognitive load for the user. This document analyzes how these inputs are used in the backend, identifies key friction points in the user experience, and proposes a solution.

The proposed solution is to **unify the user-facing inputs into a single "smart prompt" text area** and a separate, optional field for "Text to Render on Image". This simplification will be supported by a new **backend `IntentParser` stage** that uses an LLM to analyze the user's unified prompt and extract structured data for the downstream pipeline stages. This approach significantly improves usability while preserving the sophisticated control of the existing backend architecture.

## 2. Current State Analysis

The core of the problem lies in forcing the user to deconstruct their creative idea into three distinct categories, a task that is often unintuitive.

### 2.1. The Three-Prompt Problem

-   **`Prompt`**: Intended for the general theme, style, and subject.
-   **`Image Instruction`**: Only active when an image is uploaded, intended for specific edit instructions.
-   **`Task Description`**: Tied to specific task types and the "Render Text" toggle, intended for task-related details and text to be rendered.

This separation forces the user to ask themselves: "Does 'make it look like a cartoon' go in `Prompt` or `Image Instruction` if I've uploaded an image?" or "Should the text 'Buy 1 Get 1' go in the main `Prompt` or the `Task Description`?". This creates friction and can lead to suboptimal results if the user's mental model doesn't align with the system's.

### 2.2. Backend Pipeline Trace

Each input has a distinct and powerful role in the backend, which explains the separation but doesn't justify the user-facing complexity.

-   **`churns/stages/image_eval.py`**:
    -   **Input Used**: `Image Instruction`
    -   **Function**: A boolean check `bool(image_instruction)` determines the depth of the VLM analysis. If an instruction exists, the system asks for a detailed analysis; if not, it only asks for the `main_subject`.

-   **`churns/stages/strategy.py`**:
    -   **Inputs Used**: `Prompt`, `Task Description`
    -   **Function**: These inputs provide context to the LLM for identifying relevant F&B niches and generating diverse marketing goal combinations.

-   **`churns/stages/style_guide.py`**:
    -   **Inputs Used**: `Prompt`, `Image Instruction`
    -   **Function**: `Image Instruction` is treated as a **mandatory constraint** that the generated styles must adhere to. `Prompt` serves as a softer "overall context hint."

-   **`churns/stages/creative_expert.py`**:
    -   **Inputs Used**: `Prompt`, `Image Instruction`, `Task Description`
    -   **Function**: This stage is the primary point of synthesis. The LLM is prompted to act as a Creative Director, integrating all three inputs into a single, structured `VisualConceptDetails` object. The separation is critical here for the LLM to understand priorities.

-   **`churns/stages/prompt_assembly.py`**:
    -   **Input Used**: `Image Instruction`
    -   **Function**: The content of `image_instruction` directly forms part of the final prompt prefix sent to the image generation model (e.g., `...modify it according to the user instruction '{instruction_text}'...`), making it a powerful and direct controller of the final output.

### 2.3. Key Issues Identified

1.  **Role Confusion**: The distinction between `Prompt` and `Task Description` is blurry, leading to inconsistent user input.
2.  **Conditional Complexity**: The `Image Instruction` field's conditional appearance based on an image upload creates a disjointed UI.
3.  **Conflated Inputs**: `Task Description` mixes high-level instructions (e.g., "make it a holiday promo") with literal content to be rendered (e.g., "50% OFF"), which are distinct user intents.
4.  **High Cognitive Load**: Three text boxes for what a user perceives as a single request creates unnecessary mental overhead.

## 3. Proposed Solution: A Unified, User-Centric Model

We propose a two-phase enhancement to simplify the frontend and adapt the backend to handle a more natural, unified user input.

### 3.1. Phase 1: Frontend Simplification

The goal is to create an input experience that is as simple as a conversation.

-   **The New UI**:
    1.  **Primary Prompt (One text area)**: A single, large text area is the user's main point of interaction.
        -   **Label**: `Your Creative Request`
        -   **Placeholder Text**: `Describe the image you want. Include the subject, style, colors, and mood. If you've uploaded an image, tell us how you'd like to change it.`
    2.  **Text on Image (Optional field)**: A separate, clearly labeled text input.
        -   **Label**: `Text to appear on the image`
        -   **Visibility**: Can be tied to the `Render Text` toggle.

This design reduces the UI to its essential components, allowing users to express their intent in natural language without premature categorization.

### 3.2. Phase 2: Backend Adaptation

To support the simplified frontend, we will introduce a new pipeline stage to interpret the user's intent, preserving the detailed control required by downstream stages.

#### 3.2.1. New Stage: The `IntentParser`

This will become the first stage in the pipeline.

-   **Purpose**: To take the new unified `prompt` and deconstruct it into the structured components the rest of the pipeline expects.
-   **Logic**: It will use a single LLM call to populate a Pydantic model.
-   **Pydantic Output Model (`ParsedIntent`)**:
    ```python
    from pydantic import BaseModel, Field
    from typing import Optional

    class ParsedIntent(BaseModel):
        core_request: str = Field(description="A concise summary of the user's main creative request, combining theme, subject, and style.")
        image_modification_instructions: Optional[str] = Field(description="If the user's prompt implies a reference image is being edited, these are the specific instructions for how to modify it. Null if no instructions are given or no image is provided.")
        task_specific_details: Optional[str] = Field(description="Details specifically related to the selected marketing task type.")
    ```
-   **Output**: The `IntentParser` will populate the following fields in the pipeline context:
    -   `ctx.core_request`
    -   `ctx.image_instruction`
    -   `ctx.task_description`

#### 3.2.2. Adapting Downstream Stages

With the `IntentParser` providing structured data, the changes to existing stages are minimal and mostly involve changing the source variable. The new `ctx.text_to_render` (from the new UI field) will also be passed down.

| Stage                 | Old Inputs                                         | New Inputs                                                                      |
| --------------------- | -------------------------------------------------- | ------------------------------------------------------------------------------- |
| `image_eval`          | `ctx.image_reference.get("instruction")`           | `ctx.image_instruction` (from IntentParser)                                     |
| `strategy`            | `ctx.prompt`, `ctx.task_description`               | `ctx.core_request`, `ctx.task_description` (from IntentParser)                  |
| `style_guide`         | `ctx.prompt`, `ctx.image_reference.get("instruction")` | `ctx.core_request`, `ctx.image_instruction` (from IntentParser)                 |
| `creative_expert`     | `ctx.prompt`, `ctx.task_description`, `image_instruction` | `ctx.core_request`, `ctx.task_description`, `ctx.image_instruction`, **`ctx.text_to_render`** |
| `prompt_assembly`     | `ctx.image_reference.get("instruction")`           | `ctx.image_instruction` (from IntentParser)                                     |

The `creative_expert` stage's user prompt will be modified to accept the distinct `text_to_render` content, which it will use to populate the `promotional_text_visuals` field, while the `task_description` will inform other creative decisions.

#### 3.2.3. Why Keep the 'Image Instruction' Concept?

It's a fair question to ask why we don't eliminate the `image_instruction` concept entirely. The analysis reveals that this piece of data is a critical control signal for the pipeline when a reference image is present:

-   **It dictates edit type**: It's the primary signal that differentiates a "default edit" (change the background) from an "instructed edit" (change a specific part of the subject).
-   **It acts as a hard constraint**: The `style_guide` and `creative_expert` stages are explicitly prompted to treat the instruction as a non-negotiable directive, ensuring user commands are followed.
-   **It directly controls the final prompt**: The `prompt_assembly` stage injects the instruction text verbatim into the final prompt sent to the image generator.

The goal of this enhancement is not to remove this powerful functionality, but to **remove the burden from the user** of having to manually separate their thoughts. The `IntentParser` automates the extraction of this crucial instruction from a single, unified prompt, preserving backend control while maximizing frontend simplicity.

## 4. Benefits of the Proposed Approach

-   **Improved User Experience**: Drastically reduces user friction and cognitive load, making the tool faster and more intuitive.
-   **Increased Input Flexibility**: Empowers users to describe complex requests, including image edits, in natural, conversational language.
-   **Enhanced Backend Robustness**: Centralizes the messy task of interpreting user intent into a single, dedicated stage, providing clean, predictable inputs to all subsequent stages.
-   **Future-Proofing**: A single prompt input is more aligned with the direction of modern generative AI interfaces, making the application easier to extend in the future.

## 5. High-Level Implementation Plan

1.  **Step 1 (Backend):** Implement the `IntentParser` pipeline stage, including its Pydantic model and LLM prompting logic.
2.  **Step 2 (Backend):** Modify the main API endpoint to accept the new simplified input structure: `{ "prompt": "...", "text_to_render": "..." }`.
3.  **Step 3 (Backend):** Update the pipeline executor to run `IntentParser` first. Plumb the new context variables (`ctx.core_request`, `ctx.image_instruction`, `ctx.task_description`, `ctx.text_to_render`) to the subsequent stages.
4.  **Step 4 (Frontend):** Redesign the user input form to feature the single smart prompt and the optional "Text to appear on the image" field, removing the old three text areas.
5.  **Step 5 (Testing):** Conduct thorough end-to-end testing with a wide variety of prompts (e.g., simple generation, instructed edits, text rendering requests, combined requests) to ensure the new system correctly interprets user intent and produces high-quality results.

