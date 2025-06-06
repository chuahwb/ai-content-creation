"""
Image Evaluation Stage - Performs VLM analysis on uploaded images.

Extracted verbatim from combined_pipeline.py with minimal changes:
- Replaced print() with ctx.log()
- Adapted to use PipelineContext instead of nested dict
- Preserved all original logic and constants
"""

import json
import re
import time
import traceback
from typing import Dict, Any, List, Optional, Tuple
from openai import APIConnectionError, RateLimitError, APIStatusError
from openai.types.chat import ChatCompletionMessageParam
from tenacity import RetryError
from pydantic import ValidationError

from ..pipeline.context import PipelineContext
from ..models import ImageAnalysisResult

# Global variables for API clients and configuration (injected by pipeline executor)
instructor_client_img_eval = None
base_llm_client_img_eval = None
IMG_EVAL_MODEL_ID = None
IMG_EVAL_MODEL_PROVIDER = None
FORCE_MANUAL_JSON_PARSE = False
INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS = []


def extract_json_from_llm_response(raw_text: str) -> Optional[str]:
    """
    Extracts a JSON string from an LLM's raw text response.
    Handles markdown code blocks and attempts to parse direct JSON,
    including cases with "Extra data" errors.
    """
    if not isinstance(raw_text, str):
        return None

    # 1. Try to find JSON within ```json ... ```
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
            if json_candidate:
                if not (first_bracket > first_brace and last_bracket < last_brace):
                     json_candidate = potential_arr_str
            else:
                json_candidate = potential_arr_str
        except json.JSONDecodeError:
            pass

    return json_candidate


def simulate_image_evaluation_fallback(user_has_provided_instruction: bool) -> Dict[str, Any]:
    """Provides a simulated structured analysis if Pydantic model or LLM fails."""
    if not ImageAnalysisResult:
         return {"error": "Pydantic model ImageAnalysisResult not defined", "main_subject": "Simulated Subject (No Pydantic)"}
    
    data = {
        "main_subject": "Simulated Main Subject (e.g., Cupcake)",
        "secondary_elements": None, 
        "setting_environment": None,
        "style_mood": None, 
        "extracted_text": None,
    }
    if user_has_provided_instruction:
        data["secondary_elements"] = ["Simulated secondary item 1", "Simulated frosting detail"]
        data["setting_environment"] = "Simulated clean background"
        data["style_mood"] = "Simulated bright and cheerful"
    
    try:
      return ImageAnalysisResult(**data).model_dump()
    except Exception as e:
        return {"error": f"Fallback creation failed: {e}", "main_subject": "Error"}


def run(ctx: PipelineContext) -> None:
    """Performs image analysis using VLM, updates pipeline context."""
    ctx.log("Starting image evaluation stage")
    
    image_ref = ctx.image_reference
    analysis_result_dict = None
    status_message = "No image provided for evaluation."
    usage_info = None
    status_code = 'NO_IMAGE'

    if not image_ref:
        ctx.image_analysis_result = None
        ctx.log(f"Status: {status_message}")
        return

    filename = image_ref.get("filename")
    user_has_provided_instruction = bool(image_ref.get("instruction"))
    content_type = image_ref.get("content_type")
    size = image_ref.get("size_bytes")
    image_content_base64 = image_ref.get("image_content_base64")

    task_type = ctx.task_type or "N/A"
    platform = ctx.target_platform.get("name") if ctx.target_platform else "N/A"
    status_prefix = f"Image '{filename}' ({content_type}, {size} bytes): "

    vlm_prompt_text_parts = [
        "You are an expert visual analyst for F&B marketing. Analyze the provided image objectively.",
        f"The F&B marketing context is: Task='{task_type}', Target Platform='{platform}'.",
    ]
    if user_has_provided_instruction:
        vlm_prompt_text_parts.append("Provide a detailed visual analysis. Identify the `main_subject` concisely. Also describe any `secondary_elements`, the `setting_environment`, the visual `style_mood` of the image, and extract any `extracted_text` visible in the image.")
    else:
        vlm_prompt_text_parts.append("Strictly identify ONLY the `main_subject` of the image. Do not provide analysis for any other fields like secondary elements, setting, style, or extracted text, even if they are part of the response model. Those fields should be omitted or explicitly set to null/None if the model requires them.")
    vlm_prompt_text_parts.append("Focus strictly on what is visually present in the image. Do not infer or add elements not visible. Provide the analysis based on the `ImageAnalysisResult` response model. Be concise and objective.")
    final_vlm_text_prompt = "\n".join(vlm_prompt_text_parts)

    # Determine which client to use (instructor or base)
    client_to_use = instructor_client_img_eval if instructor_client_img_eval and not FORCE_MANUAL_JSON_PARSE else base_llm_client_img_eval
    use_instructor_for_call = bool(instructor_client_img_eval and not FORCE_MANUAL_JSON_PARSE)

    if client_to_use and ImageAnalysisResult:
        ctx.log(f"Attempting VLM call for image '{filename}' using {IMG_EVAL_MODEL_PROVIDER} model: {IMG_EVAL_MODEL_ID}")
        try:
            user_content_for_vlm = [{"type": "text", "text": final_vlm_text_prompt}]
            if image_content_base64:
                 user_content_for_vlm.append({"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{image_content_base64}"}})
            else: 
                raise ValueError("Image content (base64) is missing for VLM analysis.")

            messages: List[ChatCompletionMessageParam] = [
                {"role": "system", "content": "You are an expert visual analyst for F&B marketing. Adhere to the Pydantic response model. Ensure all requested fields are populated appropriately based on the user prompt (e.g., null if not applicable or not requested for minimal analysis)."},
                {"role": "user", "content": user_content_for_vlm}
            ]
            llm_args: Dict[str, Any] = {
                "model": IMG_EVAL_MODEL_ID, 
                "messages": messages,
                "temperature": 0.2, 
                "max_tokens": 400,
            }
            if use_instructor_for_call:
                llm_args["response_model"] = ImageAnalysisResult

            completion = client_to_use.chat.completions.create(**llm_args)

            if use_instructor_for_call:
                analysis_result_dict = completion.model_dump()
            else:  # Manual parse
                raw_content = completion.choices[0].message.content
                json_str = extract_json_from_llm_response(raw_content)
                if not json_str:
                    ctx.log("ERROR: Could not extract JSON from VLM response.")
                    ctx.log(f"Raw VLM content: {raw_content}")
                    raise Exception(f"JSON object not found in VLM response. Raw: {raw_content}")
                try:
                    parsed_data = json.loads(json_str)
                    analysis_result_dict = ImageAnalysisResult(**parsed_data).model_dump()
                except (json.JSONDecodeError, ValidationError) as parse_err:
                    ctx.log(f"ERROR: Manual JSON parsing/validation failed for VLM response: {parse_err}")
                    ctx.log(f"Extracted JSON string: {json_str}")
                    ctx.log(f"Raw VLM content: {raw_content}")
                    raise Exception(f"VLM response parsing error: {parse_err}")

            raw_response_obj = getattr(completion, '_raw_response', completion)
            if hasattr(raw_response_obj, 'usage') and raw_response_obj.usage:
                usage_info = raw_response_obj.usage.model_dump()
                ctx.log(f"Token Usage (Image Eval): {usage_info}")
            else: 
                ctx.log("Token usage data not directly available from VLM response object.")
            ctx.log("Successfully received and validated Pydantic response from VLM.")
            status_message = status_prefix + "Analysis complete (via VLM)."
            status_code = 'SUCCESS'
            
        except ValueError as ve:  # E.g. missing base64
             ctx.log(f"ERROR preparing VLM call: {ve}")
             status_message = status_prefix + f"Analysis skipped ({ve}). Falling back to simulation."
             analysis_result_dict = simulate_image_evaluation_fallback(user_has_provided_instruction)
             status_code = 'SIMULATED_FALLBACK_PREPARATION_ERROR'
        except (APIConnectionError, RateLimitError, APIStatusError) as api_error:
             ctx.log(f"ERROR: VLM API call failed: {api_error}")
             status_message = status_prefix + f"Analysis failed ({type(api_error).__name__}). Falling back to simulation."
             analysis_result_dict = simulate_image_evaluation_fallback(user_has_provided_instruction)
             status_code = 'API_ERROR'
        except Exception as e:
            if isinstance(e, RetryError): 
                ctx.log(f"ERROR: VLM call failed after retries. Cause: {e.last_attempt.exception()}")
            else: 
                ctx.log(f"ERROR during VLM API call/parsing: {e}")
                ctx.log(traceback.format_exc())
            status_message = status_prefix + f"Analysis failed (Error: {e}). Falling back to simulation."
            analysis_result_dict = simulate_image_evaluation_fallback(user_has_provided_instruction)
            status_code = 'API_ERROR_GENERAL'
    else:
         ctx.log("VLM client or Pydantic ImageAnalysisResult not configured, using basic simulation for image evaluation")
         analysis_result_dict = simulate_image_evaluation_fallback(user_has_provided_instruction)
         status_message = status_prefix + "Analysis simulated (No API Key / Library / Model)."
         status_code = 'SIMULATED_NO_API_CONFIG'

    ctx.image_analysis_result = analysis_result_dict
    if usage_info:
        ctx.llm_usage["image_eval"] = usage_info
    
    ctx.log(f"Status: {status_message}")
    ctx.log("Image evaluation stage completed") 