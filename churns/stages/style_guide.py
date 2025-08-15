"""Style Guidance Generation Stage

This stage generates N distinct style guidance sets for N marketing strategies.
Each style guidance includes keywords, description, and marketing impact,
tailored to the creativity level and task type.

Extracted from combined_pipeline.py with 100% fidelity.
"""

import json
import time
import traceback
from typing import Dict, Any, List, Optional, Tuple
from pydantic import ValidationError

from churns.models import StyleGuidance, StyleGuidanceList
from churns.pipeline.context import PipelineContext
from churns.core.json_parser import (
    RobustJSONParser, 
    JSONExtractionError,
    TruncatedResponseError,
    should_use_manual_parsing
)
from churns.core.brand_kit_utils import build_brand_palette_prompt

# Global variables for API clients and configuration (injected by pipeline executor)
instructor_client_style_guide = None
base_llm_client_style_guide = None
STYLE_GUIDER_MODEL_ID = None
STYLE_GUIDER_MODEL_PROVIDER = None
FORCE_MANUAL_JSON_PARSE = False
INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS = []

# Initialize centralized JSON parser for this stage
_json_parser = RobustJSONParser(debug_mode=False)


def _get_style_guider_system_prompt(
    creativity_level: int,
    task_type: str,
    num_strategies: int,
    use_instructor_parsing: bool,
    target_model_family: Optional[str] = "openai"
) -> str:
    """Generate the system prompt for the Style Guider agent."""
    creativity_desc_sg = {1: "focused and conventional", 2: "impressionistic and stylized", 3: "abstract and illustrative"}
    
    base_persona_sg = f"""
You are an expert Art Director and Style Consultant specializing in F&B social media visuals.
Your task is to generate {num_strategies} distinct and varied sets of high-level style guidance, each uniquely tailored to its corresponding marketing strategy and the task type: '{task_type}'.
The creativity level is {creativity_level} ({creativity_desc_sg.get(creativity_level, 'balanced')}). Styles must strictly adhere to the defined artistic boundaries for this level, ensuring a clear progression from photorealistic (Level 1) to impressionistic/stylized (Level 2) to abstract/illustrative (Level 3).
Each style guidance set must include a specific artistic constraint or reference to guide the Creative Expert, a detailed 2-3 sentence description, and an explanation of marketing impact for shareability, engagement, or brand recall.
"""
    
    style_diversification_sg = """
Ensure each style set is significantly distinct in aesthetic framework (e.g., composition, color palette, texture, inspiration source) to avoid repetitive or clichéd interpretations of user prompt keywords (e.g., avoid defaulting to neon for 'futuristic,' wood for 'rustic,' or warm tones for 'cozy').
For each prompt keyword, draw from diverse aesthetic lenses (e.g., cultural motifs like Japanese wabi-sabi or Moroccan patterns, historical periods like Art Deco or Bauhaus, environmental themes like desert minimalism or oceanic fluidity) to create varied, contextually relevant styles that align with the marketing strategy and task type.
Styles must be appropriate for the F&B domain and social media marketing, balancing creativity with marketability.
"""
    
    creativity_instruction_sg = ""
    if creativity_level == 1:
        creativity_instruction_sg = """
**Style Guidance (Level 1 - Focused & Photorealistic):**
Propose clear, professional, photorealistic, or minimally stylized styles (e.g., 'studio product photography', 'clean minimalism', 'bright macro shot').
Avoid any artistic or experimental styles.
Include a constraint, e.g., 'use symmetrical composition for maximum clarity' or 'employ even, natural lighting'.
Styles must prioritize product or subject clarity for broad audience appeal.
"""
    elif creativity_level == 3:
        creativity_instruction_sg = """
**Style Guidance (Level 3 - Abstract & Illustrative):**
Propose highly imaginative, abstract, or illustrative styles (e.g., 'surrealist food illustration', 'cubist composition', 'graphic novel art inspired by Lichtenstein').
Include a bold constraint, e.g., 'depict the subject as an abstract entity' or 'use a fully illustrative rendering with no photorealistic elements'.
Styles must be visually striking and shareable, while supporting the marketing strategy's voice and objective.
"""
    else:  # Level 2 (Default)
        creativity_instruction_sg = """
**Style Guidance (Level 2 - Impressionistic & Stylized):**
Propose creative, stylized styles with impressionistic or cinematic qualities (e.g., 'cinematic food noir with dramatic lighting', 'bold flat design with textured patterns', 'impressionist brushstroke with vibrant food tones').
Include a stylization constraint, e.g., 'use cinematic lighting with soft shadows', 'incorporate textured patterns for depth', or 'apply impressionistic color blending for vibrancy'.
Styles must be visually appealing, marketable, and distinct from photorealism, while explicitly avoiding fully illustrative, cartoonish, or abstract renderings (e.g., no anthropomorphic elements or surreal compositions unless specified).
"""
    
    task_type_awareness_sg = f"**Task Type Context:** The task is '{task_type}'. Ensure styles are appropriate for this task's visual and marketing requirements."
    image_ref_context_sg = "**Image Reference Context:** If a reference image is provided (details in user prompt), ensure styles complement or transform it appropriately, maintaining focus on style diversity across strategies."
    marketing_impact_sg = "**Marketing Impact:** For each style, include a 'marketing_impact' field explaining how it supports social media marketing goals (e.g., 'vibrant colors drive engagement on Instagram', 'authentic style fosters trust on Xiaohongshu')."

    output_format_sg = ""
    if use_instructor_parsing and STYLE_GUIDER_MODEL_ID not in INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS:
        output_format_sg = "Output a list of JSON objects, each conforming to the `StyleGuidance` Pydantic model (fields: `style_keywords`, `style_description`, `marketing_impact`, `source_strategy_index`). Ensure `style_description` is 2-3 sentences, specifying artistic references or constraints. Styles must be distinct for each strategy."
    else:  # Manual JSON parsing or if model is problematic with instructor's tool mode
        output_format_sg = """
VERY IMPORTANT: Format your entire response *only* as a valid JSON object with a single key 'style_guidance_sets'.
This key should contain a list of objects, each with 'style_keywords' (list of 3-5 strings), 'style_description' (2-3 sentence string), 'marketing_impact' (string), and 'source_strategy_index' (integer).
Do not include any other text or formatting outside this JSON structure.
"""
    
    prompt_parts_sg = [
        base_persona_sg, style_diversification_sg, creativity_instruction_sg,
        task_type_awareness_sg, image_ref_context_sg, marketing_impact_sg, output_format_sg
    ]
    if target_model_family == "qwen": 
        prompt_parts_sg.append("   /no_thinking   ")  # Qwen specific
    
    return "\n".join(prompt_parts_sg)


def _get_style_guider_user_prompt(
    strategies: List[Dict[str, Any]],
    task_type: str,
    image_analysis: Optional[Dict[str, Any]],
    image_instruction: Optional[str],
    user_prompt_original: Optional[str],
    brand_kit: Optional[Dict[str, Any]],
    num_strategies: int,
    use_instructor_parsing: bool
) -> str:
    """Constructs the user prompt for the Style Guider agent."""
    prompt_parts = [
        f"Generate {num_strategies} distinct style guidance sets, one for each of the following {num_strategies} marketing strategies. The overall F&B task is: '{task_type}'.",
        "The marketing strategies are as follows:"
    ]
    
    for i, strategy in enumerate(strategies):
        prompt_parts.append(f"\nStrategy {i}:")
        prompt_parts.append(f"  - Audience: {strategy.get('target_audience', 'N/A')}")
        prompt_parts.append(f"  - Niche: {strategy.get('target_niche', 'N/A')}")
        prompt_parts.append(f"  - Objective: {strategy.get('target_objective', 'N/A')}")
        prompt_parts.append(f"  - Voice: {strategy.get('target_voice', 'N/A')}")

    if brand_kit:
        prompt_parts.append("\n**Brand Kit Context for Style Generation:**")
        prompt_parts.append("A brand kit has been provided. All style suggestions MUST be compatible with this kit.")
        if brand_kit.get('colors'):
            colors = brand_kit.get('colors')
            if colors:
                # Handle both old format (list of hex strings) and new semantic format
                if isinstance(colors[0], str):
                    prompt_parts.append("\n**Brand Color Palette:**")
                    prompt_parts.append(f"- **Colors:** {colors}")
                    prompt_parts.append("Honor semantic roles if known; avoid over‑specifying percentages.")
                else:
                    snippet = build_brand_palette_prompt(colors, layer="style")
                    prompt_parts.append(snippet)
                
                prompt_parts.append("Your style suggestions must strictly adhere to this brand color palette. The provided semantic roles and usage plans are not optional guidelines; they are constraints that must be followed to ensure brand consistency.")
        if brand_kit.get('brand_voice_description'):
            prompt_parts.append(f"- **Brand Voice:** `'{brand_kit.get('brand_voice_description')}'`. Your style descriptions must reflect this voice.")
        if brand_kit.get('logo_analysis') and brand_kit['logo_analysis'].get('logo_style'):
            prompt_parts.append(f"- **Logo Style:** `'{brand_kit['logo_analysis']['logo_style']}'`. Ensure your suggested styles do not clash with the logo's aesthetic.")
        if brand_kit.get('logo_analysis') and brand_kit['logo_analysis'].get('dominant_colors'):
            prompt_parts.append(f"- **Logo's Dominant Colors:** `{brand_kit['logo_analysis']['dominant_colors']}`. The style should also be harmonious with the logo's own colors.")

    if image_instruction and image_analysis:
        prompt_parts.append("\n**MANDATORY CONTEXT & CONSTRAINTS FOR STYLE GENERATION:**")
        prompt_parts.append(f"The user has provided a reference image and a specific instruction: '{image_instruction}'.")
        prompt_parts.append("Your generated styles MUST respect this instruction. Use the following analysis of the original image as context to inform your style suggestions. Your styles must reflect the user's desired changes, not contradict them.")
        
        analysis_details = ["- Analysis of Reference Image:"]
        
        def format_list(items: Optional[List[str]]) -> str:
            return ', '.join(items) if items else "N/A"
        
        details_map = {
            "Angle/Orientation": image_analysis.get("angle_orientation"),
            "Setting/Environment": image_analysis.get("setting_environment"),
            "Style/Mood": image_analysis.get("style_mood"),
            "Secondary Elements": format_list(image_analysis.get("secondary_elements")),
        }
        
        for key, value in details_map.items():
            if value and value != "N/A":
                analysis_details.append(f"  - {key}: {value}")
                
        if len(analysis_details) > 1:
            prompt_parts.append("\n".join(analysis_details))
        
        prompt_parts.append("\nFor example, if the user instruction is to 'preserve the angle', you are forbidden from suggesting styles with conflicting camera perspectives (like 'top-down'). If the user wants to 'make it more dramatic', your styles must introduce elements of drama, using the original style/mood as a starting point. This is a strict, non-negotiable requirement.")

    elif image_analysis:
        image_subject = image_analysis.get('main_subject')
        if image_subject:
            prompt_parts.append(f"\nConsider that the primary visual subject (from image analysis) is: '{image_subject}'.")

    if user_prompt_original: 
        prompt_parts.append(f"\nUser's original prompt hint for overall context: '{user_prompt_original}'.")

    prompt_parts.append(f"\nFor each of the {num_strategies} strategies, provide a `style_keywords` list (3-5 keywords), a detailed `style_description` (2-3 sentences including artistic constraints/references), and a `marketing_impact` statement. Ensure styles are significantly distinct across strategies and adhere to the creativity level guidance provided in the system prompt. The `source_strategy_index` for each style guidance set should correspond to the strategy index (0 to {num_strategies-1}).")

    if not use_instructor_parsing and STYLE_GUIDER_MODEL_ID not in INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS:
        prompt_parts.append("\nVERY IMPORTANT: Your entire response MUST be only the JSON object described in the system prompt (Style Guider section), starting with `{\"style_guidance_sets\": [` and ending with `]}`. Do not include any other text or formatting.")
    
    return "\n".join(prompt_parts)


async def run(ctx: PipelineContext) -> None:
    """Generates N distinct style guidance sets for N marketing strategies."""
    stage_name = "Style Guide"
    ctx.log(f"Starting {stage_name} stage")
    
    # Check if required models are available
    if not StyleGuidanceList or not StyleGuidance:
        error_msg = "Error: StyleGuider Pydantic model not available."
        ctx.log(f"ERROR: {error_msg}")
        ctx.style_guidance_sets = None
        return

    # Get strategies from previous stage
    strategies = ctx.suggested_marketing_strategies
    if not strategies:
        ctx.log("No marketing strategies provided to Style Guider")
        ctx.style_guidance_sets = []
        return

    num_strategies = len(strategies)
    task_type = ctx.task_type or "N/A"
    creativity_level = ctx.creativity_level
    
    # Get image analysis result
    image_analysis = ctx.image_analysis_result
    image_instruction = ctx.image_reference.get("instruction") if ctx.image_reference else None
    user_prompt_original = ctx.prompt
    brand_kit = ctx.brand_kit

    ctx.log(f"Generating style guidance for {num_strategies} strategies (Creativity: {creativity_level})")

    # Use global client variables (injected by pipeline executor)
    # Determine parsing strategy using centralized logic
    use_manual_parsing = should_use_manual_parsing(STYLE_GUIDER_MODEL_ID)
    client_to_use_sg = base_llm_client_style_guide if use_manual_parsing else instructor_client_style_guide
    use_instructor_for_sg_call = bool(instructor_client_style_guide and not use_manual_parsing)
    
    if not client_to_use_sg:
        error_msg = "LLM Client for Style Guider not available."
        ctx.log(f"ERROR: {error_msg}")
        ctx.style_guidance_sets = None
        return

    # Generate prompts
    system_prompt_sg = _get_style_guider_system_prompt(
        creativity_level=creativity_level, 
        task_type=task_type, 
        num_strategies=num_strategies,
        use_instructor_parsing=use_instructor_for_sg_call,
        target_model_family=STYLE_GUIDER_MODEL_PROVIDER.lower()
    )
    
    user_prompt_sg = _get_style_guider_user_prompt(
        strategies, task_type, image_analysis, image_instruction,
        user_prompt_original, brand_kit, num_strategies, use_instructor_for_sg_call
    )

    # Prepare LLM arguments
    llm_args_sg = {
        "model": STYLE_GUIDER_MODEL_ID, 
        "messages": [
            {"role": "system", "content": system_prompt_sg}, 
            {"role": "user", "content": user_prompt_sg}
        ],
        "temperature": 0.8, 
        "max_tokens": 1500 * num_strategies, 
        "extra_body": {}
    }
    
    if use_instructor_for_sg_call and StyleGuidanceList:
        llm_args_sg["response_model"] = StyleGuidanceList

    # Call LLM
    usage_info_sg = None
    error_details_sg = None
    style_guidance_list_data = None
    
    try:
        ctx.log(f"Calling {STYLE_GUIDER_MODEL_PROVIDER} model: {STYLE_GUIDER_MODEL_ID}")
        
        # Determine effective client and parsing strategy
        effective_client_sg = client_to_use_sg
        actually_use_instructor_parsing_sg = use_instructor_for_sg_call

        if use_instructor_for_sg_call and STYLE_GUIDER_MODEL_ID in INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS:
            ctx.log(f"Model {STYLE_GUIDER_MODEL_ID} is problematic with instructor tool mode. Forcing manual parse.")
            actually_use_instructor_parsing_sg = False
            if "response_model" in llm_args_sg: 
                del llm_args_sg["response_model"]
            if "tools" in llm_args_sg: 
                del llm_args_sg["tools"]
            if "tool_choice" in llm_args_sg: 
                del llm_args_sg["tool_choice"]

        completion_sg = effective_client_sg.chat.completions.create(**llm_args_sg)

        # Check for empty or invalid response before processing
        if completion_sg is None:
            raise Exception("API call returned None response - possible provider issue")
        
        if actually_use_instructor_parsing_sg:
            if not hasattr(completion_sg, 'style_guidance_sets') or not completion_sg.style_guidance_sets:
                raise Exception("Instructor response missing or empty style_guidance_sets - possible API failure")
            style_guidance_list_data = [item.model_dump() for item in completion_sg.style_guidance_sets]
        else:  # Manual parse using centralized parser
            if not hasattr(completion_sg, 'choices') or not completion_sg.choices:
                raise Exception("API response missing choices - possible provider failure")
            
            if not completion_sg.choices[0] or not hasattr(completion_sg.choices[0], 'message'):
                raise Exception("API response missing message in first choice - malformed response")
            
            raw_content_sg = completion_sg.choices[0].message.content
            
            # Check for empty response content
            if not raw_content_sg or not raw_content_sg.strip():
                # Log provider issue details
                provider_context = f"Provider: {STYLE_GUIDER_MODEL_PROVIDER}, Model: {STYLE_GUIDER_MODEL_ID}"
                ctx.log(f"WARNING: Empty response content from API. {provider_context}")
                raise Exception(f"Empty response content from API - provider may be experiencing issues. {provider_context}")
            
            try:
                # Use centralized parser with fallback validation for list handling
                def fallback_validation(data: Dict[str, Any]) -> Dict[str, Any]:
                    """Handle if LLM returns a list directly for style_guidance_sets."""
                    data_for_validation = {}
                    if isinstance(data, list) and "style_guidance_sets" in StyleGuidanceList.model_fields:
                        data_for_validation = {"style_guidance_sets": data}
                    elif isinstance(data, dict):  # Expected case
                        data_for_validation = data
                    else:
                        raise ValidationError(f"Parsed JSON for Style Guidance is not a list or dict as expected: {type(data)}")

                    validated_model = StyleGuidanceList(**data_for_validation)
                    return {"style_guidance_sets": [item.model_dump() for item in validated_model.style_guidance_sets]}
                
                result_data = _json_parser.extract_and_parse(
                    raw_content_sg,
                    expected_schema=StyleGuidanceList,
                    fallback_validation=fallback_validation
                )
                
                style_guidance_list_data = result_data.get("style_guidance_sets", [])
                
            except TruncatedResponseError as truncate_err_sg:
                current_max_tokens = llm_args_sg.get("max_tokens", 1500 * num_strategies)
                error_details_sg = (
                    f"Style Guider response was truncated mid-generation. "
                    f"Current max_tokens: {current_max_tokens} for {num_strategies} strategies. "
                    f"Consider increasing max_tokens or trying a different model. "
                    f"Truncation details: {truncate_err_sg}\n"
                    f"Raw response preview: {raw_content_sg[:500]}..."
                )
                raise Exception(error_details_sg)
            except JSONExtractionError as extract_err_sg:
                error_details_sg = f"Style Guider JSON extraction/parsing failed: {extract_err_sg}\nRaw: {raw_content_sg}"
                raise Exception(error_details_sg)

        ctx.log(f"Successfully generated {len(style_guidance_list_data)} style guidance sets")
        
        # Extract usage information
        usage_info_sg = None
        raw_response_sg_obj = getattr(completion_sg, '_raw_response', completion_sg)
        if hasattr(raw_response_sg_obj, 'usage') and raw_response_sg_obj.usage:
            usage_info_sg = raw_response_sg_obj.usage.model_dump()
            ctx.log(f"Token Usage (Style Guider): {usage_info_sg}")
        else:
            ctx.log("Token usage data not available for Style Guider")
        
        # Store results directly on context
        ctx.style_guidance_sets = style_guidance_list_data
        if usage_info_sg: 
            ctx.llm_usage["style_guider"] = usage_info_sg
            
        ctx.log(f"{stage_name} stage completed successfully")
        return
        
    except Exception as e:
        # If error_details_sg was already set (e.g. by extraction failure), use it. Otherwise, format the current exception.
        if not error_details_sg:
            error_details_sg = f"Style Guider general error: {e}\n{traceback.format_exc()}"
        ctx.log(f"ERROR (Style Guider): {error_details_sg}")
        ctx.style_guidance_sets = None
        return 