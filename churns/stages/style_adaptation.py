"""
StyleAdaptation Stage - Intelligent style transfer for STYLE_RECIPE presets.

This stage is triggered when a user applies a STYLE_RECIPE preset AND provides a new text prompt.
It acts as a specialized Creative Director that adapts the saved style to the new concept.
"""

import json
import logging
import asyncio
import traceback
from typing import Dict, Any, Optional
from churns.pipeline.context import PipelineContext

from churns.models import VisualConceptDetails
from churns.api.database import PresetType
from churns.core.json_parser import (
    RobustJSONParser,
    JSONExtractionError,
    TruncatedResponseError,
    should_use_manual_parsing
)
from churns.core.brand_kit_utils import build_brand_palette_prompt

logger = logging.getLogger(__name__)

# Global variables for API clients and configuration (injected by pipeline executor)
instructor_client_style_adaptation = None
base_llm_client_style_adaptation = None
STYLE_ADAPTATION_MODEL_ID = None
STYLE_ADAPTATION_MODEL_PROVIDER = None
FORCE_MANUAL_JSON_PARSE = False
INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS = []

# Initialize a centralized JSON parser for this stage
_json_parser = RobustJSONParser(debug_mode=False)

async def run(ctx: PipelineContext) -> None:
    """
    Execute the StyleAdaptation stage to adapt a saved style recipe to a new concept.
    
    This stage runs when:
    1. A STYLE_RECIPE preset is applied.
    2. A new subject is introduced, typically via a new reference image analysis.
    """
    stage_name = "StyleAdaptation"
    logger.info(f"Starting {stage_name} stage")
    
    # Check if required models are available
    if not VisualConceptDetails:
        error_msg = "Error: StyleAdaptation Pydantic models not available."
        logger.error(f"ERROR: {error_msg}")
        ctx.stage_error = error_msg
        ctx.generated_image_prompts = []
        return
    
    # Check if StyleAdaptation is needed
    if ctx.preset_type != PresetType.STYLE_RECIPE:
        logger.info("StyleAdaptation skipped - no STYLE_RECIPE preset applied")
        return
    
    # A new image analysis result is the primary trigger for adaptation.
    # A new prompt is a secondary, optional input.
    new_image_analysis = getattr(ctx, 'image_analysis_result', None)
    new_user_prompt = ctx.adaptation_prompt

    if not new_image_analysis and not new_user_prompt:
        logger.info("StyleAdaptation skipped - no new image or prompt provided for adaptation.")
        return
    
    if not ctx.preset_data:
        error_msg = "StyleAdaptation failed - no preset data available"
        logger.error(f"ERROR: {error_msg}")
        ctx.stage_error = error_msg
        ctx.generated_image_prompts = []
        return
    
    logger.info("🎨 Starting StyleAdaptation stage")
    
    # Extract components from the saved style recipe
    base_recipe = ctx.preset_data
    
    # Get the original visual concept from the recipe
    original_visual_concept = base_recipe.get('visual_concept', {})
    
    # Build the system prompt for the StyleAdaptation agent
    system_prompt = _build_system_prompt(
        render_text_enabled=ctx.render_text,
        apply_branding_enabled=ctx.apply_branding,
        language=ctx.language
    )
    
    # Build the user prompt with the recipe data and new request
    user_prompt = _build_user_prompt(
        original_visual_concept=original_visual_concept,
        new_user_request=new_user_prompt,
        new_image_analysis=new_image_analysis,
        brand_kit_override=ctx.brand_kit if ctx.apply_branding else None,
        is_override_event=getattr(ctx, 'brand_kit_is_override', False)
    )
    
    # Determine parsing strategy using centralized logic
    use_manual_parsing = should_use_manual_parsing(STYLE_ADAPTATION_MODEL_ID)
    client_to_use = base_llm_client_style_adaptation if use_manual_parsing else instructor_client_style_adaptation
    use_instructor_for_call = bool(instructor_client_style_adaptation and not use_manual_parsing)
    
    # Check if global client is available (injected by pipeline executor)
    if not instructor_client_style_adaptation and not base_llm_client_style_adaptation:
        error_msg = "LLM Client for StyleAdaptation not available."
        logger.error(f"ERROR: {error_msg}")
        ctx.stage_error = error_msg
        ctx.generated_image_prompts = []
        return
    
    if not client_to_use:
        error_msg = "StyleAdaptation client not configured"
        logger.error(f"ERROR: {error_msg}")
        ctx.stage_error = error_msg
        ctx.generated_image_prompts = []
        return
    
    # Prepare LLM arguments
    llm_args = {
        "model": STYLE_ADAPTATION_MODEL_ID,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.7,  # Moderate creativity to balance consistency with adaptation
        "max_tokens": 6000  # Increased to handle complex JSON responses
    }
    
    # Add response model for instructor mode
    if use_instructor_for_call and VisualConceptDetails:
        llm_args["response_model"] = VisualConceptDetails
    
    # Handle problematic models
    actually_use_instructor_parsing = use_instructor_for_call
    if use_instructor_for_call and STYLE_ADAPTATION_MODEL_ID in INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS:
        logger.info(f"Model {STYLE_ADAPTATION_MODEL_ID} is problematic with instructor tool mode. Forcing manual parse.")
        actually_use_instructor_parsing = False
        if "response_model" in llm_args:
            del llm_args["response_model"]
    
    # Make the LLM call
    try:
        logger.info(f"Calling StyleAdaptation with model {STYLE_ADAPTATION_MODEL_ID} using {'instructor' if actually_use_instructor_parsing else 'manual'} parsing")
        
        completion = await asyncio.to_thread(client_to_use.chat.completions.create, **llm_args)
        
        if actually_use_instructor_parsing:
            # Direct Pydantic object from instructor
            adapted_visual_concept = completion.model_dump()
        else:
            # Manual parsing using centralized parser
            raw_response_content = completion.choices[0].message.content
            
            try:
                # Custom fallback handler for nested JSON objects
                def style_adaptation_fallback(data: dict) -> dict:
                    """Handle nested objects that should be strings."""
                    if isinstance(data, dict):
                        # Handle main_subject as nested object
                        if 'main_subject' in data and isinstance(data['main_subject'], dict):
                            main_subj_dict = data['main_subject']
                            if 'description' in main_subj_dict:
                                desc = main_subj_dict['description']
                                garnish = main_subj_dict.get('garnish', '')
                                data['main_subject'] = f"{desc} {garnish}".strip()
                            else:
                                data['main_subject'] = str(main_subj_dict)
                        
                        # Handle promotional_text_visuals as nested object
                        if 'promotional_text_visuals' in data and isinstance(data['promotional_text_visuals'], dict):
                            ptv_dict = data['promotional_text_visuals']
                            parts = []
                            if 'text_content' in ptv_dict:
                                parts.append(f"Text: '{ptv_dict['text_content']}'")
                            if 'font_style' in ptv_dict:
                                parts.append(f"Font: {ptv_dict['font_style']}")
                            if 'color' in ptv_dict:
                                parts.append(f"Color: {ptv_dict['color']}")
                            if 'placement' in ptv_dict:
                                parts.append(f"Placement: {ptv_dict['placement']}")
                            data['promotional_text_visuals'] = ". ".join(parts) if parts else str(ptv_dict)
                        
                        # Handle logo_visuals as nested object
                        if 'logo_visuals' in data and isinstance(data['logo_visuals'], dict):
                            lv_dict = data['logo_visuals']
                            parts = []
                            if 'logo_description' in lv_dict:
                                parts.append(f"Logo: {lv_dict['logo_description']}")
                            if 'placement' in lv_dict:
                                parts.append(f"Placement: {lv_dict['placement']}")
                            if 'style' in lv_dict:
                                parts.append(f"Style: {lv_dict['style']}")
                            data['logo_visuals'] = ". ".join(parts) if parts else str(lv_dict)
                    
                    return data
                
                result_data = _json_parser.extract_and_parse(
                    raw_response_content,
                    expected_schema=VisualConceptDetails,
                    fallback_validation=style_adaptation_fallback
                )
                adapted_visual_concept = result_data
                
            except TruncatedResponseError as truncate_err:
                current_max_tokens = llm_args.get("max_tokens", 6000)
                error_details = (
                    f"StyleAdaptation response was truncated mid-generation. "
                    f"Current max_tokens: {current_max_tokens}. "
                    f"Consider increasing max_tokens or trying a different model. "
                    f"Truncation details: {truncate_err}\n"
                    f"Raw response preview: {raw_response_content[:500]}..."
                )
                raise Exception(error_details)
                
            except JSONExtractionError as extract_err:
                error_details = f"StyleAdaptation JSON extraction/parsing failed: {extract_err}\nRaw: {raw_response_content}"
                raise Exception(error_details)
        
        # Store original subject for metadata
        original_visual_concept = base_recipe.get('visual_concept', {})
        ctx.original_subject = original_visual_concept.get('main_subject', 'unknown_from_recipe')
        
        # Update the preset data with the adapted visual concept
        ctx.preset_data['visual_concept'] = adapted_visual_concept
        
        # Store adaptation context for metadata
        ctx.adaptation_context = {
            "original_visual_concept": original_visual_concept,
            "adapted_visual_concept": adapted_visual_concept,
            "adaptation_reasoning": f"Adapted {original_visual_concept.get('visual_style', 'style')} to new subject: {new_image_analysis.get('main_subject') if new_image_analysis else 'prompt override'}",
            "adaptation_trigger": "new_subject_image" if new_image_analysis else "prompt_override"
        }
        
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
        
        # Note: Brand kit overrides are now handled via the brand_kit_is_override flag
        # and are incorporated directly into the LLM prompts above
        
        # Store token usage for cost calculation (following creative_expert pattern)
        raw_response_obj = getattr(completion, '_raw_response', completion)
        if hasattr(raw_response_obj, 'usage') and raw_response_obj.usage:
            usage_dict = raw_response_obj.usage.model_dump()
            if not hasattr(ctx, 'llm_usage'):
                ctx.llm_usage = {}
            ctx.llm_usage["style_adaptation"] = usage_dict
            logger.info(f"Token Usage (StyleAdaptation): {usage_dict}")
        else:
            logger.info("Token usage data not available for StyleAdaptation.")
        
        logger.info("✅ StyleAdaptation completed successfully")
        
        # Log the adaptation for debugging
        logger.info(f"Adapted style from '{original_visual_concept.get('main_subject', 'unknown')}' to '{adapted_visual_concept.get('main_subject', 'unknown')}'")
        
    except Exception as e:
        # Follow the same error handling pattern as creative_expert
        error_details = f"StyleAdaptation failed: {str(e)}"
        if "Raw:" not in error_details and 'raw_response_content' in locals():
            error_details += f"\nRaw Content: {raw_response_content}"
        
        logger.error(f"ERROR (StyleAdaptation): {error_details}")
        logger.error(f"Full traceback: {traceback.format_exc()}")
        
        # Set error state so it's visible in the UI (consistent with executor expectations)
        ctx.stage_error = error_details
        ctx.generated_image_prompts = []
        
        # Don't raise exception - let the pipeline continue with the original recipe
        return


def _build_system_prompt(render_text_enabled: bool, apply_branding_enabled: bool, language: str) -> str:
    """Build the system prompt by merging dynamic instructions with the best parts of the original static prompt."""

    if render_text_enabled:
        text_instruction = """- **Adapt Text**: `render_text` is enabled. You MUST generate a `promotional_text_visuals` field. Your description must detail the adapted text content, style, font, placement, and integration with the visual."""
    else:
        text_instruction = """- **Omit Text**: `render_text` is disabled. You MUST OMIT the `promotional_text_visuals` field from your JSON output."""

    if apply_branding_enabled:
        branding_instruction = """- **Adapt Branding**: `apply_branding` is enabled. You MUST generate a `logo_visuals` field. Your description MUST be a specific instruction for logo placement, prioritizing a watermark-style integration (e.g., 'Subtly place the logo in the bottom-right corner'). Avoid instructions that replace the main subject. If a `brand_kit_override` is provided, adapt to it; otherwise, adapt the original recipe's branding."""
    else:
        branding_instruction = """- **Omit Branding**: `apply_branding` is disabled. You MUST OMIT the `logo_visuals` field from your JSON output."""
        
    language_display = "SIMPLIFIED CHINESE" if language == 'zh' else language.upper()
    lang_instruction = f"""- **Language Control**: The target language is {language_display}.
      - `suggested_alt_text` MUST be written entirely in {language_display}.
      - For `promotional_text_visuals`, the description of the *style* MUST be in ENGLISH. The actual *text content* MUST be in {language_display}.
      - All other fields MUST be in ENGLISH.""" if language and language != 'en' else "- **Language**: The target language is English. All fields MUST be in English."

    return f"""You are an expert Creative Director at a top-tier advertising agency. Your specialization is adapting a successful, existing visual style to a new creative brief while maintaining brand consistency. You are a master of preserving the *essence* of a style (lighting, mood, color, composition) while applying it to a completely new subject or concept.

**Your Task:**
You will be given a `base_style_recipe`, which represents the detailed aesthetic of a previously successful image. You will also be given a `new_user_request`, which describes the new concept to be created. Your job is to intelligently merge these inputs and produce a single, new `visual_concept` JSON object as your output, strictly following the instructions below.

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


def _build_user_prompt(
    original_visual_concept: Dict[str, Any], 
    new_user_request: str, 
    new_image_analysis: Optional[Dict[str, Any]] = None,
    brand_kit_override: Optional[Dict[str, Any]] = None,
    is_override_event: bool = False
) -> str:
    """Build the user prompt, including brand kit overrides if detected."""
    
    prompt_parts = [f"Here is the `base_style_recipe` to adapt:\n```json\n{json.dumps(original_visual_concept, indent=2)}\n```"]
    
    if new_user_request:
        prompt_parts.append(f'\nHere is the `new_user_request`:\n"{new_user_request}"')
    elif new_image_analysis:
        # If no text prompt, explicitly state that the image analysis is the new request.
        prompt_parts.append('\nA new reference image has been provided. The `new_image_analysis` below defines the new subject and context. Your task is to adapt the `base_style_recipe` to this new subject.')

    if new_image_analysis:
        prompt_parts.append(f"""
Here is the `new_image_analysis` of the provided reference image:
```json
{json.dumps(new_image_analysis, indent=2)}
```""")

    if brand_kit_override and is_override_event:
        override_parts = ["\n**CRITICAL: Adapt the base style recipe using this `brand_kit_override`:**"]
        if brand_kit_override.get('colors'):
            colors = brand_kit_override.get('colors')
            if colors:
                # Handle both old format (list of hex strings) and new semantic format
                if isinstance(colors[0], str):
                    override_parts.append(f"- **New Brand Colors:** `{colors}`. The `color_palette` in your response MUST be adapted to harmonize with these colors.")
                else:
                    # Use centralized builder with conditional usage inclusion for STYLE_ADAPTATION layer
                    snippet = build_brand_palette_prompt(colors, layer="creative")
                    override_parts.append(snippet.replace("**Brand Color Palette:**", "- **New Brand Color Palette:**"))
                    override_parts.append("- The `color_palette` in your response MUST be adapted to harmonize with these colors and respect their semantic roles.")
        if brand_kit_override.get('brand_voice_description'):
            override_parts.append(f"- **New Brand Voice:** `'{brand_kit_override['brand_voice_description']}'`. The `lighting_and_mood` must be adapted to align with this voice.")
        if brand_kit_override.get('logo_analysis'):
            override_parts.append(f"- **New Logo Details:** A new logo is provided. Describe its placement and integration in the `logo_visuals` field. Logo style is: `'{brand_kit_override['logo_analysis'].get('logo_style', 'N/A')}'`.")
        prompt_parts.append("\n".join(override_parts))

    # --- NEW: CONSISTENCY CHECKLIST ---
    prompt_parts.append("""
### CONSISTENCY CHECKLIST (Must-Pass)
- Match the **camera angle & framing** from the structural framework exactly.
- Re-use the **lighting setup & shadow direction** from the framework.
- Preserve the **text style, font category, colour, and placement**, adapting only the wording to suit the new subject.
- Use the **branding placement & scale** exactly as defined in the framework.
- Translate the **colour hierarchy** (primary / accent) into the new palette without introducing off-brand colours.
""")

    # --- PART 5: FINAL INSTRUCTION ---
    prompt_parts.append("\nNow, generate the new `visual_concept` JSON object. Remember to replace subject-specific descriptions (like `main_subject`, `foreground_elements`) with new content appropriate for the new subject, while strictly maintaining the specified framework.")
    prompt_parts.append("\n**CRITICAL: Ensure all descriptions in the new `visual_concept` refer *only* to the new subject and its context. Do not mention the original subject from the framework (e.g., 'soy milk bottle').**")
    
    return "\n".join(prompt_parts)


def _apply_token_budget_mitigation(visual_concept: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply token budget mitigation by pruning non-essential fields.
    This is called when the combined prompt size exceeds 85% of the model's limit.
    """
    # Remove verbose fields that are not critical for style adaptation
    pruned_concept = visual_concept.copy()
    
    # Remove or truncate verbose fields
    if 'creative_reasoning' in pruned_concept:
        del pruned_concept['creative_reasoning']
    
    if 'texture_and_details' in pruned_concept and len(pruned_concept['texture_and_details']) > 200:
        pruned_concept['texture_and_details'] = pruned_concept['texture_and_details'][:200] + "..."
    
    if 'negative_elements' in pruned_concept and len(pruned_concept['negative_elements']) > 100:
        pruned_concept['negative_elements'] = pruned_concept['negative_elements'][:100] + "..."
    
    logger.info("Applied token budget mitigation to visual concept")
    return pruned_concept


def _estimate_token_count(text: str) -> int:
    """Rough estimation of token count (approximately 4 characters per token)."""
    return len(text) // 4


def _check_token_budget(system_prompt: str, user_prompt: str, limit: int = 8000) -> bool:
    """Check if the combined prompt exceeds 85% of the token limit."""
    total_tokens = _estimate_token_count(system_prompt + user_prompt)
    threshold = int(limit * 0.85)
    return total_tokens <= threshold 