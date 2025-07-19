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
import base64
import asyncio

from ..pipeline.context import PipelineContext
from ..models import ImageAnalysisResult, LogoAnalysisResult
from ..core.json_parser import (
    RobustJSONParser, 
    JSONExtractionError,
    TruncatedResponseError,
    should_use_manual_parsing
)

# Global variables for API clients and configuration (injected by pipeline executor)
instructor_client_img_eval = None
base_llm_client_img_eval = None
IMG_EVAL_MODEL_ID = None
IMG_EVAL_MODEL_PROVIDER = None
FORCE_MANUAL_JSON_PARSE = False
INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS = []

# Initialize centralized JSON parser for this stage
_json_parser = RobustJSONParser(debug_mode=False)

# Old manual JSON extraction function removed - now using centralized parser


async def _run_logo_analysis(ctx: PipelineContext):
    """Performs VLM analysis on an uploaded brand logo, if present and not already analyzed."""
    if not (ctx.brand_kit and ctx.brand_kit.get("saved_logo_path_in_run_dir") and not ctx.brand_kit.get("logo_analysis")):
        return  # No logo to analyze or analysis already done

    ctx.log("Starting logo evaluation sub-task...")
    logo_path = ctx.brand_kit.get("saved_logo_path_in_run_dir")
    
    try:
        with open(logo_path, "rb") as image_file:
            logo_content_base64 = base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        ctx.log(f"ERROR: Could not read and encode logo file at {logo_path}: {e}")
        return

    # Determine which client to use
    use_manual_parsing_logo = should_use_manual_parsing(IMG_EVAL_MODEL_ID)
    client_to_use = base_llm_client_img_eval if use_manual_parsing_logo else instructor_client_img_eval
    use_instructor_for_call = bool(instructor_client_img_eval and not use_manual_parsing_logo)

    if not client_to_use:
        ctx.log("WARNING: Client for logo evaluation not available. Skipping.")
        return

    system_prompt_logo = "You are an expert logo analyst. Your task is to analyze the provided logo image and return a structured analysis of its key visual properties. Focus ONLY on the logo itself. Adhere strictly to the `LogoAnalysisResult` Pydantic response model. Identify the logo's overall style, whether it contains text, and if so, what that text is. Also, extract the dominant colors of the logo."
    
    messages: List[ChatCompletionMessageParam] = [
        {"role": "system", "content": system_prompt_logo},
        {"role": "user", "content": [
            {"type": "text", "text": "Analyze this logo."},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{logo_content_base64}"}}
        ]}
    ]

    llm_args: Dict[str, Any] = {
        "model": IMG_EVAL_MODEL_ID, 
        "messages": messages,
        "temperature": 0.1, 
        "max_tokens": 1000,
    }
    if use_instructor_for_call:
        llm_args["response_model"] = LogoAnalysisResult

    try:
        completion = await asyncio.to_thread(
            client_to_use.chat.completions.create,
            **llm_args
        )

        logo_analysis_result_dict = None
        if use_instructor_for_call:
            logo_analysis_result_dict = completion.model_dump()
        else:
            raw_content = completion.choices[0].message.content
            logo_analysis_result_dict = _json_parser.extract_and_parse(
                raw_content,
                expected_schema=LogoAnalysisResult
            )
        
        ctx.brand_kit['logo_analysis'] = logo_analysis_result_dict
        ctx.log(f"✅ Logo analysis successful. Style: {logo_analysis_result_dict.get('logo_style')}")
        
        raw_response_obj = getattr(completion, '_raw_response', completion)
        if hasattr(raw_response_obj, 'usage') and raw_response_obj.usage:
            usage_info = raw_response_obj.usage.model_dump()
            if not hasattr(ctx, 'llm_usage'):
                 ctx.llm_usage = {}
            ctx.llm_usage["logo_eval"] = usage_info
            ctx.log(f"Token Usage (Logo Eval): {usage_info}")

    except Exception as e:
        ctx.log(f"❌ ERROR during logo analysis: {e}")
        ctx.log(traceback.format_exc())


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


async def run(ctx: PipelineContext) -> None:
    """Performs image analysis using VLM, updates pipeline context."""
    # Run logo analysis first if applicable. This operates independently of the main image analysis.
    await _run_logo_analysis(ctx)
    
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
    
    # Check if we need to perform base64 encoding (deferred from task creation)
    if not image_content_base64 and image_ref.get("_image_data_bytes"):
        ctx.log("Performing deferred base64 encoding of image data...")
        image_data_bytes = image_ref.get("_image_data_bytes")
        image_content_base64 = base64.b64encode(image_data_bytes).decode('utf-8')
        # Update the image reference for future use
        image_ref["image_content_base64"] = image_content_base64
        # Remove the temporary bytes data to save memory
        del image_ref["_image_data_bytes"]

    task_type = ctx.task_type or "N/A"
    platform = ctx.target_platform.get("name") if ctx.target_platform else "N/A"
    status_prefix = f"Image '{filename}' ({content_type}, {size} bytes): "

    vlm_prompt_text_parts = [
        "You are an expert visual analyst for F&B marketing. Analyze the provided image objectively.",
        f"The F&B marketing context is: Task='{task_type}', Target Platform='{platform}'.",
    ]
    if user_has_provided_instruction:
        vlm_prompt_text_parts.append("Provide a detailed visual analysis. Identify the `main_subject` concisely. Also describe its `angle_orientation` (e.g., 'top-down view', 'side view'). For `secondary_elements`, list items that SURROUND the main subject, not elements ON it. Also describe the `setting_environment`, the visual `style_mood` of the image, and extract any `extracted_text` visible in the image.")
    else:
        vlm_prompt_text_parts.append("Strictly identify ONLY the `main_subject` of the image. Do not provide analysis for any other fields like secondary elements, setting, style, or extracted text, even if they are part of the response model. Those fields should be omitted or explicitly set to null/None if the model requires them.")
    vlm_prompt_text_parts.append("Focus strictly on what is visually present in the image. Do not infer or add elements not visible. Provide the analysis based on the `ImageAnalysisResult` response model. Be concise and objective.")
    final_vlm_text_prompt = "\n".join(vlm_prompt_text_parts)

    # Determine which client to use using centralized logic
    use_manual_parsing = should_use_manual_parsing(IMG_EVAL_MODEL_ID)
    client_to_use = base_llm_client_img_eval if use_manual_parsing else instructor_client_img_eval
    use_instructor_for_call = bool(instructor_client_img_eval and not use_manual_parsing)

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

            completion = await asyncio.to_thread(
                client_to_use.chat.completions.create,
                **llm_args
            )

            if use_instructor_for_call:
                analysis_result_dict = completion.model_dump()
            else:  # Manual parse using centralized parser
                raw_content = completion.choices[0].message.content
                try:
                    analysis_result_dict = _json_parser.extract_and_parse(
                        raw_content,
                        expected_schema=ImageAnalysisResult
                    )
                except TruncatedResponseError as truncate_err:
                    ctx.log(f"ERROR: VLM response was truncated: {truncate_err}")
                    ctx.log(f"Raw VLM content preview: {raw_content[:300]}...")
                    raise Exception(f"VLM response truncated - consider increasing max_tokens or trying different model: {truncate_err}")
                except JSONExtractionError as extract_err:
                    ctx.log(f"ERROR: JSON extraction/parsing failed for VLM response: {extract_err}")
                    ctx.log(f"Raw VLM content: {raw_content}")
                    raise Exception(f"VLM response parsing error: {extract_err}")

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
        if not hasattr(ctx, 'llm_usage'):
            ctx.llm_usage = {}
        ctx.llm_usage["image_eval"] = usage_info
    
    ctx.log(f"Status: {status_message}")
    ctx.log("Image evaluation stage completed") 