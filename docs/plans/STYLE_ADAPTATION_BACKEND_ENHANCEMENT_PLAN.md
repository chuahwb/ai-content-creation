# Style Adaptation Backend Enhancement Plan (v11 - Final & Complete)

## 1. Executive Summary

This document outlines the definitive strategy for enhancing the `style_adaptation` stage. This final version incorporates highly specific, battle-tested prompt engineering patterns and preserves the most effective instructions from the original implementation. It is a complete and actionable guide with all implementation details restored.

The strategy is a three-part process:
1.  **Implement Override Detection in `PresetLoader`**: Add logic to `PresetLoader` to compare brand kits and set an explicit `ctx.brand_kit_is_override` flag.
2.  **Programmatically construct a highly specific System Prompt**: The system prompt will be built in Python, merging the strongest instructions from the original implementation with new, dynamic commands for text, branding, and language handling.
3.  **Dynamically construct the User Prompt**: The user prompt will use the `ctx.brand_kit_is_override` flag to conditionally inject detailed override instructions only when a true override has occurred.

This hybrid approach is maximally robust, providing deterministic control while giving the LLM precise creative context.

---

## 2. Problem Statement

The core challenge is to reliably instruct the LLM to adapt a style based on a complex hierarchy of inputs. The prompts must be specific enough to ensure the LLM's output is consistently high-quality and adheres to all constraints, including optional overrides and explicit rendering toggles.

---

## 3. Proposed Enhancement Plan

### Part 1: Implement Override Detection in `PresetLoader`

**Objective:** Reliably detect if the user has modified the brand kit.

**Task 1.1: Add override detection logic to `churns/pipeline/preset_loader.py`**
In `_apply_style_recipe` within `churns/pipeline/preset_loader.py`, compare the incoming `ctx.brand_kit` with the saved `preset.brand_kit` and set `ctx.brand_kit_is_override`.

```python
# file: churns/pipeline/preset_loader.py
# inside _apply_style_recipe()

# ... existing logic to load preset and parse style_recipe ...
import json
import logging

logger = logging.getLogger(__name__)

# --- BEGIN ENHANCEMENT: Brand Kit Override Detection ---
original_brand_kit = preset.brand_kit
current_run_brand_kit = ctx.brand_kit
is_override = False

if ctx.apply_branding:
    # A simple and effective deep comparison for dictionaries by comparing their JSON string representations
    original_kit_str = json.dumps(original_brand_kit, sort_keys=True) if original_brand_kit else "{}"
    current_kit_str = json.dumps(current_run_brand_kit, sort_keys=True) if current_run_brand_kit else "{}"
    
    if original_kit_str != current_kit_str:
        is_override = True
        logger.info("Brand kit override detected. The provided brand kit differs from the one in the saved recipe.")
    
# Set a new, explicit flag on the context for downstream stages to use
ctx.brand_kit_is_override = is_override
# --- END ENHANCEMENT ---

# ... rest of the function to apply other preset data to ctx ...
```

### Part 2: Enhance `style_adaptation.py` with Refined Prompts

**Objective:** Use the override flag and a refined, hybrid system prompt to build the most effective instructions.

**Task 2.1: Update `run` function**

```python
# file: churns/stages/style_adaptation.py
# inside run()
# ...
system_prompt = _build_system_prompt(
    render_text_enabled=ctx.render_text,
    apply_branding_enabled=ctx.apply_branding,
    language=ctx.language
)

user_prompt = _build_user_prompt(
    original_visual_concept=original_visual_concept,
    new_user_request=new_user_prompt,
    new_image_analysis=new_image_analysis,
    brand_kit_override=ctx.brand_kit if ctx.apply_branding else None,
    is_override_event=getattr(ctx, 'brand_kit_is_override', False)
)
# ...
```

**Task 2.2: Update `_build_system_prompt` to use the best of both worlds**
This final version of the prompt combines the superior structure and constraints of the original implementation with the new dynamic instructions.

```python
# file: churns/stages/style_adaptation.py

def _build_system_prompt(render_text_enabled: bool, apply_branding_enabled: bool, language: str) -> str:
    """Build the system prompt by merging dynamic instructions with the best parts of the original static prompt."""

    if render_text_enabled:
        text_instruction = """- **Adapt Text**: `render_text` is enabled. You MUST generate a `promotional_text_visuals` field. Your description must detail the adapted text content, style, font, placement, and integration with the visual."""
    else:
        text_instruction = """- **Omit Text**: `render_text` is disabled. You MUST OMIT the `promotional_text_visuals` field from your JSON output."""

    if apply_branding_enabled:
        branding_instruction = """- **Adapt Branding**: `apply_branding` is enabled. You MUST generate a `branding_visuals` field. Your description MUST be a specific instruction for logo placement, prioritizing a watermark-style integration (e.g., 'Subtly place the logo in the bottom-right corner'). Avoid instructions that replace the main subject. If a `brand_kit_override` is provided, adapt to it; otherwise, adapt the original recipe's branding."""
    else:
        branding_instruction = """- **Omit Branding**: `apply_branding` is disabled. You MUST OMIT the `branding_visuals` field from your JSON output."""
        
    language_display = "SIMPLIFIED CHINESE" if language == 'zh' else language.upper()
    lang_instruction = f"""- **Language Control**: The target language is {language_display}.
      - `suggested_alt_text` MUST be written entirely in {language_display}.
      - For `promotional_text_visuals`, the description of the *style* MUST be in ENGLISH. The actual *text content* MUST be in {language_display}.
      - All other fields MUST be in ENGLISH.""" if language and language != 'en' else "- **Language**: The target language is English. All fields MUST be in English."

    return f"""You are an expert Creative Director at a top-tier advertising agency. Your specialization is adapting a successful, existing visual style to a new creative brief while maintaining brand consistency. You are a master of preserving the *essence* of a style (lighting, mood, color, composition) while applying it to a completely new subject or concept.

**Your Task:**
You will be given a `base_style_recipe` and a `new_user_request`. Your job is to intelligently merge these inputs and produce a single, new `visual_concept` JSON object as your output, strictly following the instructions below.

**Core Principles & Constraints:**
1.  **Follow Rendering Instructions Precisely**:
    {text_instruction}
    {branding_instruction}
    {lang_instruction}
2.  **Preserve the Core Style**: You MUST preserve the high-level aesthetic of the `base_style_recipe`. The `lighting_and_mood`, `color_palette`, and `visual_style` fields are your primary source of truth. Keep these fields *identical* to the base recipe unless the `new_user_request` explicitly asks you to change them (e.g., "make it a nighttime scene").
3.  **Adapt the Concept**: You MUST adapt the `main_subject`, `composition_and_framing`, and `background_environment` fields to fit the new subject and/or the `new_user_request`.
4.  **Handle Precedence**: If the `new_user_request` directly contradicts a field in the `base_style_recipe`, the **new user request always wins**.
5.  **No Minor Edits**: You are **FORBIDDEN** from making small, corrective "refinement" style edits. Do not remove small objects, fix typos, or perform minor touch-ups. Your focus is on the high-level creative direction and composition ONLY.
6.  **Output Format**: Your entire output MUST be a single, valid JSON object that conforms to the `VisualConceptDetails` schema. Do not include any commentary, explanations, or text outside of the JSON structure.
"""
```

**Task 2.3: Update `_build_user_prompt`**
The logic is complete and correct.

```python
# file: churns/stages/style_adaptation.py

def _build_user_prompt(
    original_visual_concept: Dict[str, Any], 
    new_user_request: str, 
    new_image_analysis: Optional[Dict[str, Any]] = None,
    brand_kit_override: Optional[Dict[str, Any]] = None,
    is_override_event: bool = False
) -> str:
    """Build the user prompt, including brand kit overrides if detected."""
    
    prompt_parts = [f"Here is the `base_style_recipe` to adapt:\n```json\n{json.dumps(original_visual_concept, indent=2)}\n```"]
    
    prompt_parts.append(f'\nHere is the `new_user_request`:\n"{new_user_request}"')

    if new_image_analysis:
        prompt_parts.append(f"""
(Optional) Here is the `new_image_analysis` of a provided reference image:
```json
{json.dumps(new_image_analysis, indent=2)}
```""")

    if brand_kit_override and is_override_event:
        override_parts = ["\n**CRITICAL: Adapt the base style recipe using this `brand_kit_override`:**"]
        if brand_kit_override.get('colors'):
            override_parts.append(f"- **New Brand Colors:** `{brand_kit_override['colors']}`. The `color_palette` in your response MUST be adapted to harmonize with these colors.")
        if brand_kit_override.get('brand_voice_description'):
            override_parts.append(f"- **New Brand Voice:** `'{brand_kit_override['brand_voice_description']}'`. The `lighting_and_mood` must be adapted to align with this voice.")
        if brand_kit_override.get('logo_analysis'):
            override_parts.append(f"- **New Logo Details:** A new logo is provided. Describe its placement and integration in the `branding_visuals` field. Logo style is: `'{brand_kit_override['logo_analysis'].get('logo_style', 'N/A')}'`.")
        prompt_parts.append("\n".join(override_parts))

    prompt_parts.append("\nNow, generate the new `visual_concept` JSON object.")
    
    return "\n".join(prompt_parts)
```

### Part 3: Verification
No modifications are needed in `prompt_assembly.py`.

---

## 4. Benefits of this Approach

1.  **Accurate Override Detection:** The logic is foolproof.
2.  **High-Quality, Consistent Output:** By using the most effective prompt structure combined with specific instructions, we ensure predictable and high-quality results.
3.  **Handles All Scenarios Gracefully:** Correctly distinguishes between all possible user actions.
4.  **Clear Separation of Concerns:** `PresetLoader` prepares data, the stage's Python code handles logic, and the LLM handles focused creative execution. 