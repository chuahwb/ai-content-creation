# Analysis and Enhancement Plan: Adapting Caption Generation for Style Recipes

## Executive Summary

The current captioning feature is not optimized for images generated via the style adaptation (style recipe) feature. It reuses marketing strategies from the original image, leading to captions that are thematically incorrect for the new image's subject. This plan proposes a minimally invasive, cost-effective solution by making the captioning stage "adaptation-aware." By adding a contextual instruction to the captioning AI, we can guide it to correctly synthesize the original marketing intent with the new visual subject, ensuring relevant and accurate captions without regenerating entire marketing strategies.

## 1. Problem Analysis

### Current Captioning Workflow

The `caption` stage (`churns/stages/caption.py`) employs a two-tier LLM system: an "Analyst" and a "Writer".

1.  **Analyst LLM**: This model receives a comprehensive prompt containing marketing strategy and visual context. Its sole job is to distill this information into a structured `CaptionBrief` JSON object.
2.  **Writer LLM**: This model takes the `CaptionBrief` and crafts the final, human-like caption.

A key input for the Analyst is the `Marketing Strategy` provided in the pipeline context (`ctx.suggested_marketing_strategies`). This strategy includes fields like `target_audience`, `target_niche`, `target_objective`, and `target_voice`. The `target_objective` is critical as it defines the core goal of the caption and often contains the specific product or subject (e.g., "boost the sales of the soy milk product").

### The Style Adaptation Conflict

The style adaptation feature allows users to apply a saved "style recipe" to a new subject. The pipeline for this feature is designed to be fast and efficient, so it **reuses the `suggested_marketing_strategies`** from the original image where the style recipe was saved.

This creates a direct conflict:
-   **New Image Subject**: The new, style-adapted image has a new subject (e.g., a "cocktail").
-   **Old Marketing Objective**: The captioning stage receives a `target_objective` for the old subject (e.g., "soy milk").

The result is a caption that is stylistically aligned but thematically incorrect, with the AI generating text about "soy milk" when describing a "cocktail".

## 2. Proposed Solution: Adaptation-Aware Captioning

The most effective and efficient solution is to empower the existing Caption Analyst LLM to handle this context switch intelligently. Instead of overhauling the pipeline to regenerate strategies, we will provide it with a clear, explicit directive.

### Core Idea

We will introduce a mechanism to signal to the caption stage that it is operating in a "style adaptation" context. When this signal is present, the Analyst LLM will be instructed to **adapt the provided marketing strategy to the new visual subject**, preserving the strategic intent while replacing the subject matter.

### Mechanism & Implementation

1.  **Context Flag**: A new flag, `ctx.is_style_adaptation: bool`, will be introduced into the `PipelineContext`. This flag will be set to `True` by the pipeline executor when initiating a run for style adaptation.

2.  **Prompt Injection**: The `_get_analyst_user_prompt` function in `churns/stages/caption.py` will be modified to check for this flag. If the flag is `True`, a special instruction block will be dynamically injected into the prompt for the Analyst LLM.

### Example Injected Instruction

This text would be added to the Analyst LLM's prompt, right after it receives the potentially conflicting marketing strategy:

```
**STYLE ADAPTATION MODE:** The provided marketing strategy is from another image. Your task is to adapt its core intent (objective, voice, audience) to the new Main Subject: '{main_subject}'. The final caption brief must be entirely about the new subject.
```

## 3. Benefits of this Approach

-   **Cost-Effective**: Avoids an extra, expensive LLM call to regenerate marketing strategies for every adaptation.
-   **Fast**: Adds negligible latency to the pipeline, as it's just a small addition to an existing prompt.
-   **Robust**: Leverages the advanced reasoning capabilities of the Analyst LLM to perform the context switch. This is far more flexible and reliable than brittle string manipulation.
-   **Preserves Intent**: This approach maintains the user's original strategic intent (the "why" behind the style), which is a valuable part of the saved recipe, while correctly applying it to the new subject.

## 4. Implementation Plan

1.  **Update Pipeline Executor**: The logic that initiates a style adaptation pipeline run must be updated to set `ctx.is_style_adaptation = True` in the pipeline context.
2.  **Modify `churns/stages/caption.py`**:
    -   In the `_get_analyst_user_prompt` function, add logic to check for `getattr(ctx, 'is_style_adaptation', False)`.
    -   If `True`, inject the new instructional text (as detailed above) into the `prompt_parts` list. This should be placed right after the "Marketing Strategy" section to provide immediate context for the LLM.

## 5. Alternatives Considered

-   **Full Strategy Regeneration**: Running the `strategy` stage again for the new subject.
    -   **Rejected**: High cost, high latency, and it potentially discards the strategic intent that the user wanted to save as part of the style recipe.
-   **Programmatic String Replacement**: Using Python's `.replace()` to swap the old subject with the new one in the `target_objective` string.
    -   **Rejected**: This is extremely brittle and unreliable. Objectives can be complex sentences, and a simple find/replace cannot understand nuance and is prone to grammatical errors. The LLM is far better suited for this linguistic task.
