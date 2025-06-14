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

# Global variables for API clients and configuration (injected by pipeline executor)
instructor_client_style_guide = None
base_llm_client_style_guide = None
STYLE_GUIDER_MODEL_ID = None
STYLE_GUIDER_MODEL_PROVIDER = None
FORCE_MANUAL_JSON_PARSE = False
INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS = []


def _extract_json_from_llm_response(raw_text: str) -> Optional[str]:
    """
    Extracts a JSON string from an LLM's raw text response.
    Handles markdown code blocks and attempts to parse direct JSON,
    including cases with "Extra data" errors.
    """
    if not isinstance(raw_text, str):
        return None

    # 1. Try to find JSON within ```json ... ```
    import re
    match_md_json = re.search(r"```json\s*([\s\S]+?)\s*```", raw_text, re.IGNORECASE)
    if match_md_json:
        json_str = match_md_json.group(1).strip()
        try:
            json.loads(json_str)  # Validate
            return json_str
        except json.JSONDecodeError:
            pass  # Continue to other methods if this fails

    # 2. Try to find JSON within ``` ... ``` (generic code block)
    match_md_generic = re.search(r"```\s*([\s\S]+?)\s*```", raw_text, re.IGNORECASE)
    if match_md_generic:
        potential_json = match_md_generic.group(1).strip()
        if (potential_json.startswith('{') and potential_json.endswith('}')) or \
           (potential_json.startswith('[') and potential_json.endswith(']')):
            try:
                json.loads(potential_json)  # Validate
                return potential_json
            except json.JSONDecodeError:
                pass  # Continue

    # 3. Try to parse the stripped raw_text directly
    stripped_text = raw_text.strip()
    if not stripped_text:
        return None

    try:
        json.loads(stripped_text)  # Try to parse the whole stripped text
        return stripped_text  # If successful, the whole thing is JSON
    except json.JSONDecodeError as e:
        # If "Extra data" error, it means a valid JSON object was parsed,
        # but there was trailing data. e.pos is the index of the start of extra data.
        if "Extra data" in str(e) and e.pos > 0:
            potential_json_substring = stripped_text[:e.pos]
            try:
                json.loads(potential_json_substring)  # Re-validate the substring
                return potential_json_substring.strip()
            except json.JSONDecodeError:
                pass  # Fall through to other methods

    # 4. Fallback: find the first '{' to the last '}' or first '[' to last ']'
    first_brace = stripped_text.find('{')
    last_brace = stripped_text.rfind('}')
    first_bracket = stripped_text.find('[')
    last_bracket = stripped_text.rfind(']')

    json_candidate = None

    if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
        potential_obj_str = stripped_text[first_brace : last_brace + 1]
        try:
            json.loads(potential_obj_str)
            json_candidate = potential_obj_str
        except json.JSONDecodeError:
            pass

    if first_bracket != -1 and last_bracket != -1 and first_bracket < last_bracket:
        potential_arr_str = stripped_text[first_bracket : last_bracket + 1]
        try:
            json.loads(potential_arr_str)
            # If an object was also found, prefer the one that's not inside the other,
            # or prefer object if ambiguity. For simplicity, if both are valid and standalone,
            # this might need more sophisticated logic if LLM mixes them.
            # Here, if an object was found, we'll stick with it unless the array is clearly not part of it.
            if json_candidate:
                # If array is outside or wraps the object, consider it
                if not (first_bracket > first_brace and last_bracket < last_brace):
                     json_candidate = potential_arr_str  # Or decide based on which is "more complete"
            else:
                json_candidate = potential_arr_str
        except json.JSONDecodeError:
            pass

    return json_candidate


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
    image_subject_from_analysis: Optional[str],
    user_prompt_original: Optional[str],
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

    if image_subject_from_analysis: 
        prompt_parts.append(f"\nConsider that the primary visual subject (from image analysis, if an image was provided) is: '{image_subject_from_analysis}'. Styles should complement or creatively transform this if applicable.")
    if user_prompt_original: 
        prompt_parts.append(f"\nUser's original prompt hint for overall context: '{user_prompt_original}'.")

    prompt_parts.append(f"\nFor each of the {num_strategies} strategies, provide a `style_keywords` list (3-5 keywords), a detailed `style_description` (2-3 sentences including artistic constraints/references), and a `marketing_impact` statement. Ensure styles are significantly distinct across strategies and adhere to the creativity level guidance provided in the system prompt. The `source_strategy_index` for each style guidance set should correspond to the strategy index (0 to {num_strategies-1}).")

    if not use_instructor_parsing and STYLE_GUIDER_MODEL_ID not in INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS:
        prompt_parts.append("\nVERY IMPORTANT: Your entire response MUST be only the JSON object described in the system prompt (Style Guider section), starting with `{\"style_guidance_sets\": [` and ending with `]}`. Do not include any other text or formatting.")
    
    return "\n".join(prompt_parts)


def run(ctx: PipelineContext) -> None:
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
    image_subject_from_analysis = image_analysis.get("main_subject") if isinstance(image_analysis, dict) else None
    user_prompt_original = ctx.prompt

    ctx.log(f"Generating style guidance for {num_strategies} strategies (Creativity: {creativity_level})")

    # Use global client variables (injected by pipeline executor)
    client_to_use_sg = instructor_client_style_guide if instructor_client_style_guide and not FORCE_MANUAL_JSON_PARSE else base_llm_client_style_guide
    use_instructor_for_sg_call = bool(instructor_client_style_guide and not FORCE_MANUAL_JSON_PARSE and STYLE_GUIDER_MODEL_ID not in INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS)
    
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
        strategies, task_type, image_subject_from_analysis, 
        user_prompt_original, num_strategies, use_instructor_for_sg_call
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

        if actually_use_instructor_parsing_sg:
            style_guidance_list_data = [item.model_dump() for item in completion_sg.style_guidance_sets]
        else:  # Manual parse
            raw_content_sg = completion_sg.choices[0].message.content
            json_str_sg = _extract_json_from_llm_response(raw_content_sg)
            if not json_str_sg:
                error_details_sg = f"Style Guider JSON extraction failed. Could not find JSON in response.\nRaw Content: {raw_content_sg}"
                raise Exception(error_details_sg)
                
            try:
                parsed_json_sg = json.loads(json_str_sg)
                # Handle if LLM returns a list directly for style_guidance_sets
                data_for_pydantic_sg_validation = {}
                if isinstance(parsed_json_sg, list) and "style_guidance_sets" in StyleGuidanceList.model_fields:
                    data_for_pydantic_sg_validation = {"style_guidance_sets": parsed_json_sg}
                elif isinstance(parsed_json_sg, dict):  # Expected case
                    data_for_pydantic_sg_validation = parsed_json_sg
                else:
                    raise ValidationError(f"Parsed JSON for Style Guidance is not a list or dict as expected: {type(parsed_json_sg)}")

                validated_model_sg = StyleGuidanceList(**data_for_pydantic_sg_validation)
                style_guidance_list_data = [item.model_dump() for item in validated_model_sg.style_guidance_sets]
            except (json.JSONDecodeError, ValidationError) as err_sg_parse:
                error_details_sg = f"Style Guider JSON/Pydantic error: {err_sg_parse}\nExtracted JSON: {json_str_sg}\nRaw: {raw_content_sg}"
                raise Exception(error_details_sg)

        ctx.log(f"Successfully generated {len(style_guidance_list_data)} style guidance sets")
        
        # Extract usage information
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