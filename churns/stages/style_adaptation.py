"""
StyleAdaptation Stage - Intelligent style transfer for STYLE_RECIPE presets.

This stage is triggered when a user applies a STYLE_RECIPE preset AND provides a new text prompt.
It acts as a specialized Creative Director that adapts the saved style to the new concept.
"""

import json
import logging
import asyncio
from typing import Dict, Any, Optional
from churns.pipeline.context import PipelineContext
from churns.pipeline.preset_loader import merge_recipe_with_overrides
from churns.models import VisualConceptDetails
from churns.api.database import PresetType
from churns.core.json_parser import (
    RobustJSONParser,
    JSONExtractionError,
    TruncatedResponseError,
    should_use_manual_parsing
)

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
    
    This stage only runs when:
    1. A STYLE_RECIPE preset is applied (ctx.preset_type == "STYLE_RECIPE")
    2. The user provides a new text prompt (ctx.overrides.get('prompt'))
    """
    
    # Check if StyleAdaptation is needed
    if ctx.preset_type != PresetType.STYLE_RECIPE:
        logger.info("StyleAdaptation skipped - no STYLE_RECIPE preset applied")
        return
    
    if not ctx.overrides or not ctx.overrides.get('prompt'):
        logger.info("StyleAdaptation skipped - no new prompt provided")
        return
    
    if not ctx.preset_data:
        logger.error("StyleAdaptation failed - no preset data available")
        return
    
    logger.info("🎨 Starting StyleAdaptation stage")
    
    # Extract components from the saved style recipe
    base_recipe = ctx.preset_data
    new_user_prompt = ctx.overrides.get('prompt')
    
    # Get the original visual concept from the recipe
    original_visual_concept = base_recipe.get('visual_concept', {})
    
    # Check if we have a new image analysis (for image + prompt combination)
    new_image_analysis = getattr(ctx, 'image_analysis_result', None)
    
    # Build the system prompt for the StyleAdaptation agent
    system_prompt = _build_system_prompt()
    
    # Build the user prompt with the recipe data and new request
    user_prompt = _build_user_prompt(original_visual_concept, new_user_prompt, new_image_analysis)
    
    # Determine parsing strategy using centralized logic
    use_manual_parsing = should_use_manual_parsing(STYLE_ADAPTATION_MODEL_ID)
    client_to_use = base_llm_client_style_adaptation if use_manual_parsing else instructor_client_style_adaptation
    use_instructor_for_call = bool(instructor_client_style_adaptation and not use_manual_parsing)
    
    if not client_to_use:
        logger.error("StyleAdaptation client not configured")
        return
    
    # Prepare LLM arguments
    llm_args = {
        "model": STYLE_ADAPTATION_MODEL_ID,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.7,  # Moderate creativity to balance consistency with adaptation
        "max_tokens": 4000
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
                result_data = _json_parser.extract_and_parse(
                    raw_response_content,
                    expected_schema=VisualConceptDetails
                )
                adapted_visual_concept = result_data
            except TruncatedResponseError as truncate_err:
                logger.error(f"StyleAdaptation response was truncated: {truncate_err}")
                logger.error(f"Raw response preview: {raw_response_content[:500]}...")
                return
            except JSONExtractionError as extract_err:
                logger.error(f"StyleAdaptation JSON extraction failed: {extract_err}")
                logger.error(f"Raw response: {raw_response_content}")
                return
        
        # Update the preset data with the adapted visual concept
        ctx.preset_data['visual_concept'] = adapted_visual_concept
        
        # Apply any additional overrides to the adapted recipe
        if ctx.overrides:
            ctx.preset_data = merge_recipe_with_overrides(ctx.preset_data, ctx.overrides)
        
        logger.info("✅ StyleAdaptation completed successfully")
        
        # Log the adaptation for debugging
        logger.info(f"Adapted style from '{original_visual_concept.get('main_subject', 'unknown')}' to '{adapted_visual_concept.get('main_subject', 'unknown')}'")
        
    except Exception as e:
        logger.error(f"StyleAdaptation failed: {str(e)}")
        # Don't raise exception - let the pipeline continue with the original recipe
        return


def _build_system_prompt() -> str:
    """Build the system prompt for the StyleAdaptation agent."""
    return """You are an expert Creative Director at a top-tier advertising agency. Your specialization is adapting a successful, existing visual style to a new creative brief while maintaining brand consistency. You are a master of preserving the *essence* of a style (lighting, mood, color, composition) while applying it to a completely new subject or concept.

**Your Task:**
You will be given a `base_style_recipe` as a structured JSON object, which represents the detailed aesthetic of a previously successful image. You will also be given a `new_user_request` as a text string, which describes the new concept to be created.

Your job is to intelligently merge these two inputs and produce a single, new `visual_concept` JSON object as your output.

**Core Principles & Constraints:**
1. **Preserve the Style**: You MUST preserve the high-level aesthetic of the `base_style_recipe`. The `lighting_and_mood`, `color_palette`, and `visual_style` fields from the original recipe are your primary source of truth. **Keep these three fields *identical* to the base recipe unless the `new_user_request` explicitly asks you to change them (e.g., "make it a nighttime scene").**
2. **Adapt the Concept**: You MUST adapt the `main_subject`, `composition_and_framing`, and `background_environment` fields to fit the `new_user_request`.
3. **Handle Precedence**: If the `new_user_request` directly contradicts a field in the `base_style_recipe`, the **new user request always wins**. For example, if the recipe specifies a "warm, sunny" mood but the user asks for "a dark, moody atmosphere," your output must reflect the "dark, moody atmosphere."  
   • *Brand-visual precedence*: retain `promotional_text_visuals` and `branding_visuals` from the base recipe unless the new_user_request explicitly overrides or removes them.
   • *Image vs. Text Precedence*: If a `new_image_analysis` is provided alongside a `new_user_request`, treat the user request text as the primary instruction. Use the image analysis for contextual details (like subject shape, specific textures, or background elements) but if the text gives a conflicting instruction, the text instruction always takes precedence.
4. **No Minor Edits**: You are **FORBIDDEN** from making small, corrective "refinement" style edits. Do not remove small objects, fix typos, or perform minor touch-ups. Your focus is on the high-level creative direction and composition ONLY.
5. **Output Format**: Your entire output MUST be a single, valid JSON object that conforms to the `VisualConceptDetails` schema. Do not include any commentary, explanations, or text outside of the JSON structure.

**Output Schema (your response):**
Adhere strictly to the Pydantic JSON output format (`VisualConceptDetails`). Note that `main_subject`, `promotional_text_visuals`, and `branding_visuals` are optional and should be omitted (set to null) if the specific scenario instructs it. The `suggested_alt_text` field is mandatory. Ensure all other required descriptions are detailed enough to guide image generation effectively.
"""


def _build_user_prompt(original_visual_concept: Dict[str, Any], new_user_request: str, new_image_analysis: Optional[Dict[str, Any]] = None) -> str:
    """Build the user prompt for the StyleAdaptation agent."""
    
    prompt = f"""Here is the `base_style_recipe` to adapt:
```json
{json.dumps(original_visual_concept, indent=2)}
```

Here is the `new_user_request`:
"{new_user_request}"
"""
    
    if new_image_analysis:
        prompt += f"""
(Optional) Here is the `new_image_analysis` of a provided reference image:
```json
{json.dumps(new_image_analysis, indent=2)}
```
"""
    
    prompt += """
Now, generate the new `visual_concept` JSON object that adapts the original style to the new request."""
    
    return prompt


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