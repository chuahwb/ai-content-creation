# Captioning Feature Refactoring Analysis

## 1. Executive Summary

This document analyzes the caption generation stage (`caption.py`) and proposes a refactoring to improve its performance, maintainability, and reliability.

**Problem:** The current implementation delegates the core logic for handling "Auto" vs. "Custom" generation modes to the Language Model (LLM) by embedding complex conditional instructions within the prompts. This approach leads to oversized prompts, increased token cost and latency, and makes the system brittle and hard to maintain.

**Recommendation:** We recommend refactoring `caption.py` to move the mode-selection logic from the LLM prompts into the Python code. The Python code should be responsible for interpreting user settings, resolving the final parameters, and providing the LLM with simple, direct, and unambiguous instructions.

**Benefits:**
-   **Reduced Prompt Complexity & Size:** Simplifies prompts, leading to lower token usage and costs.
-   **Improved Performance:** Smaller, more direct prompts reduce LLM processing time and latency.
-   **Enhanced Reliability:** Eliminates ambiguity and reduces the risk of the LLM misinterpreting complex conditional logic.
-   **Better Maintainability:** Moves business logic into testable, maintainable Python code instead of free-form text prompts.

## 2. Current Implementation Analysis

The current approach in `churns/stages/caption.py` builds large, complex prompts that contain explicit instructions for how the LLM should behave in different modes.

### Analyst System Prompt

The system prompt for the analyst LLM contains a detailed `Auto Mode Logic` section, instructing the model on how to infer settings when they are not provided by the user.

```python
# From _get_analyst_system_prompt()
**Auto Mode Logic:**
- **Auto-Tone Selection:** In auto-mode, you MUST create a *new, refined* `tone_of_voice`.
  - **Source Hierarchy:** Check for available voice sources in this order: 1. Global Brand Voice, 2. Tactical Marketing Voice. Use the first one you find.
  - **Synthesis:** Blend the chosen voice source with the 'Visual Mood' to create the final, specific `tone_of_voice`.
# ... and more
```

### Analyst User Prompt

The user prompt is constructed with conditional logic that presents the LLM with two different paths depending on whether a user setting is available. This increases prompt length and complexity.

```python
# Logic from _get_analyst_user_prompt()
prompt_parts.append("**User Settings:**")

if settings.tone:
    prompt_parts.append(f"- Caption Tone: {settings.tone} (USER OVERRIDE)")
else:
    # Auto mode: Provide the available ingredients for tone synthesis
    prompt_parts.append("- Caption Tone: Auto mode")
    if brand_voice:
        prompt_parts.append(f"  - Available Global Brand Voice: '{brand_voice}' (Primary preference)")
    # ... and so on
```

This pattern forces the LLM to parse the instructions, determine which mode to operate in, and then execute. This is an inefficient use of the LLM's capabilities.

### Inefficient Use of `generation_mode`

The `CaptionSettings` model now includes a `generation_mode` field. The current code sets this field *after* the caption is generated, using it only for logging purposes. It does not leverage this field to control the generation logic itself.

```python
# From run()
# ... (caption generation is complete)
settings.generation_mode = 'Custom' if user_provided_settings else 'Auto'

caption_result = CaptionResult(
    # ...
    settings_used=settings,
    # ...
)
```
This is a missed opportunity to simplify the control flow significantly.

## 3. Proposed Refactoring Strategy

The primary goal of this refactoring is to enhance the maintainability, performance, and reliability of the captioning stage by relocating the mode-selection logic from LLM prompts to the Python application layer. This must be executed with precision to ensure that no existing functionality is broken and that the strategic intent of the prompts is fully preserved.

### 3.1. Guiding Principles for Refactoring

The refactoring process will be governed by the following strict principles:

-   **Preservation of Logic:** All conditional logic currently embedded in the prompts (e.g., source hierarchy for auto-tone, CTA generation based on objective) must be perfectly replicated in the Python code. This is a **transference of responsibility**, not an alteration of the core business logic.
-   **Maintain Prompt Essence:** The strategic and creative essence of the prompts must be preserved. The goal is to provide the LLM with clearer, more direct instructions, not to dilute the quality of the guidance it receives. The core objective of each prompt will remain unchanged.
-   **Strategic Prompt Refinement:** While moving the conditional logic, we will seize the opportunity to refine the prompts for conciseness and clarity. The objective is to remove the burden of logic-processing from the LLM, allowing it to focus on its core competency: creative generation based on unambiguous instructions.

### 3.2. Step 1: Leverage `generation_mode`

The `run` function should rely on the incoming `settings.generation_mode` ('Auto' or 'Custom') to dictate the logic path. This field should be correctly set by the frontend/API based on user interaction, making it a reliable switch for our Python logic.

### 3.3. Step 2: Implement a Settings Resolver

A new helper function, `_resolve_final_instructions`, will be created. This function is the heart of the refactor, containing the logic currently embedded in the prompts. Its purpose is to produce a dictionary of clear, final instructions for the prompt generator.

**Example Implementation for `_resolve_final_instructions`:**

```python
def _resolve_final_instructions(ctx, settings, strategy_data, visual_data, brand_voice):
    """
    This function consolidates all conditional logic to determine the final,
    unambiguous instructions for the Analyst LLM. It faithfully replicates
    the original logic from the prompts.
    """
    instructions = {}

    # 1. Resolve Tone Instruction
    # Preserves: User override, then auto-mode synthesis logic.
    if settings.generation_mode == 'Custom' and settings.tone:
        instructions['tone'] = f"Adopt this exact tone of voice: '{settings.tone}'."
    else:  # Auto mode
        # Replicates the original source hierarchy: Brand Voice > Tactical Voice > Default
        base_voice = brand_voice or strategy_data.get('target_voice') or "a friendly and engaging tone"
        visual_mood = visual_data.get('lighting_mood')
        
        instruction = f"Synthesize a new, refined tone of voice by blending the primary voice ('{base_voice}')"
        if visual_mood:
            instruction += f" with the visual mood ('{visual_mood}')."
        else:
            instruction += "."
        instructions['tone'] = instruction

    # 2. Resolve Call to Action Instruction
    # Preserves: User override, then auto-mode generation from objective.
    if settings.generation_mode == 'Custom' and settings.call_to_action:
        instructions['cta'] = f"Use this exact call to action: '{settings.call_to_action}'."
    else:  # Auto mode
        target_objective = strategy_data['target_objective']
        instructions['cta'] = f"Generate a context-aware call to action based on the target objective: '{target_objective}'."

    # 3. Resolve Emoji Usage Instruction
    # Preserves: User override, then auto-mode default (enabled).
    use_emojis = settings.include_emojis if settings.include_emojis is not None else True
    if use_emojis:
        instructions['emojis'] = "Use emojis appropriately and sparingly to match the selected tone."
    else:
        instructions['emojis'] = "Do NOT use any emojis in the caption."
        
    # 4. Resolve Hashtag Strategy Instruction
    # Preserves: User override, then auto-mode default ('Balanced Mix').
    hashtag_strategy = settings.hashtag_strategy or "Balanced Mix"
    if hashtag_strategy == "Balanced Mix":
        instructions['hashtags'] = "Generate a 'Balanced Mix' of hashtags: extract keywords from style and subject for niche hashtags, and supplement with 1-2 broader terms."
    else:
        # This handles any other specific strategy provided by the user.
        instructions['hashtags'] = f"Follow this user-provided hashtag strategy: '{hashtag_strategy}'."

    return instructions
```

### 3.4. Step 3: Simplify the Prompts

With the conditional logic handled by Python, the prompt-building functions can be refactored to provide direct, unambiguous instructions. This simplification comes from removing the `if/else` branching logic *within the prompt's text*, not from removing essential context. The LLM's new task is to execute a clear plan, not formulate one from multiple options.

**Simplified `_get_analyst_system_prompt`:**
The entire `Auto Mode Logic` section will be removed. The prompt becomes a more direct declaration of the LLM's role and the required JSON output structure, as the "how-to" is now determined by the Python code.

**Simplified `_get_analyst_user_prompt`:**
This function will now take the resolved instructions from `_resolve_final_instructions` and insert them directly into the prompt. The complex conditional blocks are eliminated in favor of simple, direct guidance.

```python
# Simplified logic in _get_analyst_user_prompt
def _get_analyst_user_prompt(ctx, settings, platform_name, strategy, visual_concept, ...):
    
    # ... (extract strategy_data, visual_data, brand_voice)
    
    # Get direct, final instructions from the new resolver function
    final_instructions = _resolve_final_instructions(ctx, settings, strategy_data, visual_data, brand_voice)

    prompt_parts = [
        # ... (all existing context data like Brand Voice, Marketing Strategy, Visual Context, etc.)
        "",
        "**Guidance for Caption Brief:**",
        f"- Tone of Voice Instruction: {final_instructions['tone']}",
        f"- Call to Action Instruction: {final_instructions['cta']}",
        f"- Hashtag Strategy Instruction: {final_instructions['hashtags']}",
        f"- Emoji Usage Instruction: {final_instructions['emojis']}",
        "",
        "Based on the context and the explicit guidance above, generate a CaptionBrief JSON object."
    ]
    return "\n".join(prompt_parts)

```

## 4. Conclusion

By shifting the responsibility for logic and control flow from the LLM prompts to the Python application layer, we can create a more robust, efficient, and maintainable captioning feature. This refactoring aligns with software engineering best practices by separating concerns: Python handles the deterministic logic, while the LLM focuses on the creative task of generation. Executed carefully according to the principles above, this change will yield immediate benefits in cost, performance, and reliability without compromising the quality of the generated captions.

## 5. Detailed Implementation Plan

This section provides a precise, step-by-step guide to executing the refactor on `churns/stages/caption.py`. Each step includes the exact code and prompt changes required.

### Step 1: Prerequisite - Model and API Alignment

Before modifying the stage logic, ensure the necessary data structures and API contracts are in place.

**Action:** In `churns/api/schemas.py`, confirm or add the `generation_mode` field to the `CaptionSettings` Pydantic model. It is critical that the front-end application sends this value correctly based on user interaction.

```python
# In churns/api/schemas.py, inside the CaptionSettings model
from typing import Literal, Optional

class CaptionSettings(...):
    # ... other fields
    generation_mode: Literal['Auto', 'Custom'] = 'Auto'
```
*(Also ensure any corresponding front-end type definitions are updated.)*


### Step 2: Implement the Settings Resolver Function (`_resolve_final_instructions`)

This new private helper function will centralize all conditional logic.

**Action:** In `churns/stages/caption.py`, add the following function. It should be placed directly **above** `_get_analyst_system_prompt` to keep related helpers together.

```python
def _resolve_final_instructions(
    ctx: PipelineContext,
    settings: CaptionSettings,
    strategy_data: Dict[str, Any],
    visual_data: Dict[str, Any],
    brand_voice: Optional[str]
) -> Dict[str, str]:
    """
    Consolidates all conditional logic to determine the final, unambiguous
    instructions for the Analyst LLM. It faithfully replicates the original
    logic from the prompts.
    """
    instructions = {}

    # 1. Resolve Tone Instruction
    if settings.generation_mode == 'Custom' and settings.tone:
        instructions['tone'] = f"You MUST adopt this exact tone of voice: '{settings.tone}'."
    else:  # Auto mode
        base_voice = brand_voice or strategy_data.get('target_voice') or "a friendly and engaging tone"
        visual_mood = visual_data.get('lighting_mood')
        instruction = f"Your task is to synthesize a new, refined tone of voice. Start with the primary voice ('{base_voice}')"
        if visual_mood:
            instruction += f" and blend it with the visual mood ('{visual_mood}')."
        else:
            instruction += "."
        instructions['tone'] = instruction

    # 2. Resolve Call to Action Instruction
    if settings.generation_mode == 'Custom' and settings.call_to_action:
        instructions['cta'] = f"You MUST use this exact call to action: '{settings.call_to_action}'."
    else:  # Auto mode
        target_objective = strategy_data.get('target_objective', 'drive engagement')
        instructions['cta'] = f"Your task is to generate a context-aware call to action that directly supports the marketing objective: '{target_objective}'."

    # 3. Resolve Emoji Usage Instruction
    use_emojis = settings.include_emojis if settings.include_emojis is not None else True
    if use_emojis:
        instructions['emojis'] = "You should use emojis appropriately and sparingly to match the determined tone of voice."
    else:
        instructions['emojis'] = "You MUST NOT use any emojis in the caption."
        
    # 4. Resolve Hashtag Strategy Instruction
    hashtag_strategy = settings.hashtag_strategy or "Balanced Mix"
    if hashtag_strategy == "Balanced Mix":
        instructions['hashtags'] = "Your task is to generate a 'Balanced Mix' of hashtags. This involves extracting specific keywords from the provided style and subject matter to create niche hashtags, and then supplementing those with 1-2 broader, high-traffic terms."
    else:
        instructions['hashtags'] = f"You MUST follow this user-provided hashtag strategy precisely: '{hashtag_strategy}'."

    return instructions
```

### Step 3: Refactor the Analyst System Prompt (`_get_analyst_system_prompt`)

The system prompt is simplified by removing all conditional logic and focusing on the core role and output format.

**Action:** Replace the existing `_get_analyst_system_prompt` function with the following.

```python
def _get_analyst_system_prompt(language: str = 'en') -> str:
    """Returns the system prompt for the Analyst LLM."""
    
    language_names = {
        'en': 'ENGLISH', 'zh': 'SIMPLIFIED CHINESE', 'es': 'SPANISH',
        'fr': 'FRENCH', 'ja': 'JAPANESE'
    }
    language_name = language_names.get(language, language.upper())
    
    return f"""You are a master social media strategist and SEO expert. Your task is to analyze a comprehensive set of marketing and visual data and distill it into a structured JSON "Caption Brief" for a creative copywriter. You will receive explicit instructions for how to handle creative elements like tone and CTAs. Your role is to follow those instructions and synthesize the provided data into the required JSON format. You do not write the final caption yourself.

**Instructions:**
- Carefully analyze all the provided CONTEXT_DATA.
- Follow the explicit INSTRUCTIONS_FOR_BRIEF that you are given. These are non-negotiable.
- Generate a single, valid JSON object based on the CaptionBrief schema. The entire output must be only the JSON object, with no other text or explanation.
- **Language Consistency:** The fields `core_message`, `primary_call_to_action`, `hashtags`, and `seo_keywords` MUST be generated in {language_name}.
- ALL fields in the JSON schema are REQUIRED and must be included.

**Platform Optimizations (Enhanced for SEO):**
- **Instagram:** Structure as "Hook + Value + CTA". The `seo_keywords` are critical for the image's Alt Text. Encourage engagement with questions to earn comments and saves.
- **Facebook:** Focus on value-driven, longer-form content that sparks meaningful conversation and shares. Ensure the structure is friendly to outbound links if applicable.
- **Pinterest:** Treat this as a visual search engine. The caption must be a mini-blog post: a compelling, keyword-rich Title followed by a detailed, helpful description that makes it a top search result.
- **Xiaohongshu:** The caption title MUST be a hook-y, attention-grabbing long-tail keyword phrase (标题党 style). The body should be a helpful, authentic note, using emojis to enhance readability. The goal is to provide immense value to encourage saves (收藏) and comments.

**CRITICAL JSON STRUCTURE REQUIREMENTS:**
You must output a valid JSON object with exactly these fields. Do not omit any field:

{{
  "core_message": "A concise, one-sentence summary of the main message.",
  "key_themes_to_include": ["Array of 3-5 key themes or concepts"],
  "seo_keywords": ["Array of 3-5 important SEO keywords"],
  "target_emotion": "Primary emotion to evoke (e.g., 'Aspirational', 'Trustworthy')",
  "tone_of_voice": "The specific tone the writer must adopt. This is derived from your instructions.",
  "platform_optimizations": {{
    "[EXACT_PLATFORM_NAME]": {{
      "caption_structure": "Brief instruction on structure for this platform",
      "style_notes": "Platform-specific style guidance"
    }}
  }},
  "primary_call_to_action": "The final call to action string, derived from your instructions.",
  "hashtags": ["Array of hashtag strings with # symbol, derived from your instructions"],
  "emoji_suggestions": ["Array of 2-3 relevant emoji characters, derived from your instructions"],
  "task_type_notes": "Optional concise note about task-type optimization. Set to null if no task type guidance was provided."
}}

**CRITICAL:** The platform_optimizations object must contain exactly one key matching the target platform name provided in the context. Use the EXACT platform name as given in the context (e.g., "Instagram Post (1:1 Square)", not just "Instagram"). This field is mandatory and cannot be omitted."""
```

### Step 4: Refactor the Analyst User Prompt (`_get_analyst_user_prompt`)

This function will be updated to call the new resolver and directly insert the resolved instructions. The existing, unchanged logic for `Task Type Context` and `Style Context` must be preserved.

**Action:** Replace the existing `_get_analyst_user_prompt` function with the following. **Crucially, you must copy the existing code blocks for "Task Type Context" and "Style Context" from the original file into the indicated placeholder.**

```python
def _get_analyst_user_prompt(
    ctx: PipelineContext,
    settings: CaptionSettings,
    platform_name: str,
    strategy: Dict[str, Any],
    visual_concept: Dict[str, Any],
    alt_text: str,
    prompt_index: int = 0
) -> str:
    """Constructs the user prompt for the Analyst LLM."""
    
    strategy_data = _safe_extract_strategy_data(strategy)
    visual_data = _safe_extract_visual_data(visual_concept)
    main_subject = _extract_main_subject(ctx, visual_concept)
    _validate_required_data(strategy_data, visual_data, main_subject)
    brand_voice = ctx.brand_kit.get('brand_voice_description') if hasattr(ctx, 'brand_kit') and ctx.brand_kit else None
    
    final_instructions = _resolve_final_instructions(ctx, settings, strategy_data, visual_data, brand_voice)

    language_names = {
        'en': 'English', 'zh': 'Simplified Chinese', 'es': 'Spanish',
        'fr': 'French', 'ja': 'Japanese'
    }
    language_name = language_names.get(ctx.language, ctx.language.upper())
    
    prompt_parts = ["**CONTEXT_DATA**"]
    if brand_voice:
        prompt_parts.extend(["**Brand Voice Guidelines:**", f'"{brand_voice}"', ""])
    
    prompt_parts.extend([
        f"**Target Platform:** {platform_name}",
        "**Marketing Strategy:**",
        f"- Target Audience: {strategy_data['target_audience']}",
        f"- Target Objective: {strategy_data['target_objective']}",
    ])
    
    if strategy_data['target_voice']:
        prompt_parts.append(f"- Tactical Voice: {strategy_data['target_voice']}")
    if strategy_data['target_niche']:
        prompt_parts.append(f"- Target Niche: {strategy_data['target_niche']}")
    
    prompt_parts.extend(["", "**Visual Context:**", f"- Main Subject: {main_subject}"])
    
    if visual_data['lighting_mood']:
        prompt_parts.append(f"- Lighting and Mood: {visual_data['lighting_mood']}")
    if visual_data['visual_style']:
        prompt_parts.append(f"- Visual Style: {visual_data['visual_style']}")
    if alt_text and alt_text != 'Generated image':
        prompt_parts.append(f"- Alt Text (for SEO context): {alt_text}")
    if visual_data['promotional_text']:
        prompt_parts.append(f"- Text on Image: {visual_data['promotional_text']}")
        
    # >>> CRITICAL: COPY EXISTING CODE BLOCK FOR "Task Type Context" HERE <<<
    
    # >>> CRITICAL: COPY EXISTING CODE BLOCK FOR "Style Context" HERE <<<
    
    prompt_parts.extend([
        "",
        "**INSTRUCTIONS_FOR_BRIEF**",
        "Based on all the CONTEXT_DATA above, you must follow these explicit instructions to generate the CaptionBrief JSON object:",
        f"- Tone of Voice Instruction: {final_instructions['tone']}",
        f"- Call to Action Instruction: {final_instructions['cta']}",
        f"- Emoji Usage Instruction: {final_instructions['emojis']}",
        f"- Hashtag Strategy Instruction: {final_instructions['hashtags']}",
        "",
        f"**Language Control:** Remember to write `core_message`, `primary_call_to_action`, `hashtags`, and `seo_keywords` in {language_name.upper()}.",
        "",
        f"**CRITICAL REMINDER:** Your JSON response must contain the key: \"{platform_name}\".",
    ])
    
    return "\n".join(prompt_parts)
```

### Step 5: Refactor the Main `run` Function

The main `run` function needs critical changes to use the `generation_mode` field correctly *before* calling the analyst and to remove now-redundant logic.

**Action:** In the `run` function, inside the `for i, prompt_data in prompts_to_process:` loop, perform the following modifications:

1.  **Set `generation_mode` Upfront:** Add logic to determine the mode based on user settings *before* the `_run_analyst` call.
2.  **Delete Redundant Logic:** Completely remove the old block of code *after* the caption is generated that recalculated `generation_mode` and `processing_mode`.

**Example `run` function modification:**

```python
# ... inside the run function's loop ...
for i, prompt_data in prompts_to_process:
    # ... (existing setup code)
    
    # === INSERT THIS BLOCK ===
    # Determine generation mode UPFRONT based on original user input
    original_settings = getattr(ctx, 'caption_settings', {})
    user_provided_settings = bool(
        original_settings.get('tone') or 
        original_settings.get('call_to_action') or 
        original_settings.get('hashtag_strategy') or 
        original_settings.get('include_emojis') is False
    )
    # This ensures the settings object passed to the resolver has the correct mode
    settings.generation_mode = 'Custom' if user_provided_settings else 'Auto'
    # === END INSERT ===

    if regenerate_writer_only and cached_brief:
        # ...
    else:
        # ...
        brief = await _run_analyst(ctx, settings, platform_name, strategy, visual_concept, alt_text)
        # ...
    
    # ... (rest of the function) ...

    # === DELETE THIS ENTIRE BLOCK ===
    # The old logic block starting with:
    # # Determine generation mode based on original user input
    # and ending before:
    # # Create caption result
    # must be deleted.
    # === END DELETE ===

    # Create caption result
    caption_result = CaptionResult(...)
    # ...
```

### Step 6: Verification and Testing

To ensure the refactor was successful without altering output quality, rigorous testing is required.

**Action:** Extend `tests/test_caption_stage.py` (or create a new dedicated test file) with the following mandatory tests:
1.  **Auto Mode Parity Test:** Create a parametrised test case with `generation_mode='Auto'`. Assert that the generated `CaptionBrief` and the final caption text are semantically identical to a pre-refactor snapshot.
2.  **Custom Mode Parity Test:** Create a parametrised test case with `generation_mode='Custom'` and user-provided settings (`tone`, `call_to_action`, etc.). Assert that the `CaptionBrief` and final caption honor these inputs exactly and match a pre-refactor snapshot.
3.  **Use `pytest` and `deepdiff`** to assert structural equality of the `CaptionBrief` objects for a robust comparison. 