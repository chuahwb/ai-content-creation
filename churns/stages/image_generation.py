"""
Stage 6: Image Generation

Generates images using either OpenAI (gpt-image-1) or Gemini (gemini-2.5-flash-image-preview) 
image generation models. Provider selection is driven by IMAGE_GENERATION_MODEL_PROVIDER 
configuration. Handles both image generation and editing based on assembled prompts from
the previous stage. Supports different qualities, aspect ratios, and comprehensive error handling.

Extracted from original monolith: generate_image function (~line 2111)
Enhanced with Gemini provider support via adapter pattern.
"""

import os
import base64
import datetime
import traceback
import asyncio
from typing import Optional, Dict, Any, Tuple
import requests
import tiktoken
from PIL import Image

from ..pipeline.context import PipelineContext
from ..core.token_cost_manager import get_token_cost_manager

# Global variables for API clients and configuration (injected by pipeline executor)
image_gen_client = None  # Backward compatibility (OpenAI)
image_gen_client_openai = None
image_gen_client_gemini = None
IMAGE_GENERATION_PROVIDER = None


# OpenAI-style response classes for Gemini normalization
class _OpenAIStyleImageData:
    """Normalized image data for reusing _process_image_response."""
    def __init__(self, b64: str):
        self.b64_json = b64
        self.url = None


class _OpenAIStyleResponse:
    """Normalized response for reusing _process_image_response."""
    def __init__(self, b64: str):
        self.data = [_OpenAIStyleImageData(b64)]


def map_aspect_ratio_to_size_for_api(aspect_ratio: str, ctx: Optional[PipelineContext] = None) -> Optional[str]:
    """Maps aspect ratio string to size parameter supported (1024x1024, 1792x1024, 1024x1792)."""
    def log_msg(msg: str):
        """Helper to log messages either via context or print."""
        if ctx:
            ctx.log(msg)
        else:
            print(msg)
            
    if aspect_ratio == "1:1": 
        return "1024x1024"
    elif aspect_ratio in ["9:16", "3:4", "2:3"]:  # Vertical
        log_msg(f"Warning: Mapping aspect ratio '{aspect_ratio}' to supported vertical size '1024x1536' (2:3).")
        return "1024x1536"
    elif aspect_ratio in ["16:9", "1.91:1"]:  # Horizontal
        log_msg(f"Warning: Mapping aspect ratio '16:9' to supported horizontal size '1536x1024' (3:2).")
        return "1536x1024"
    else:
        log_msg(f"Warning: Unsupported aspect ratio '{aspect_ratio}'. Defaulting to '1024x1024'.")
        return "1024x1024"


async def generate_image(
    final_prompt: str,
    platform_aspect_ratio: str,
    client,  # OpenAI client
    run_directory: str,
    strategy_index: int,
    reference_image_path: Optional[str] = None,
    logo_image_path: Optional[str] = None,
    image_quality_setting: str = "medium",
    ctx: Optional[PipelineContext] = None
) -> Tuple[str, Optional[str], Optional[int]]:
    """
    Generates or edits an image using the OpenAI Images API (gpt-image-1)
    via the specified client. Routes to appropriate generation method based on available inputs.

    Args:
        final_prompt: The assembled text prompt string describing the desired outcome or edit.
        platform_aspect_ratio: The aspect ratio string ('1:1', '9:16', '16:9', '2:3', '3:4').
        client: The initialized OpenAI client.
        run_directory: The path to the directory where outputs for this run are saved.
        strategy_index: The index of the current strategy (for filename).
        reference_image_path: Optional path to the reference image for editing.
        logo_image_path: Optional path to the logo image for multi-modal editing.
        image_quality_setting: Quality setting for gpt-image-1 (default "medium").
        ctx: Optional pipeline context for logging.

    Returns:
        A tuple containing:
          - status: "success" or "error"
          - url_or_filepath: The image URL (for generation) or local file path (for edits)
                             if successful, or an error message string.
          - prompt_tokens_for_image_gen: Estimated prompt tokens
    """
    def log_msg(msg: str):
        """Helper to log messages either via context or print."""
        if ctx:
            ctx.log(msg)
        else:
            print(msg)

    # Use configured provider
    provider = IMAGE_GENERATION_PROVIDER or "OpenAI"
    
    # Route to appropriate generation method based on available inputs and provider
    if reference_image_path and logo_image_path:
        # Complex multi-modal case: reference image + logo
        log_msg(f"Routing to multi-modal generation (reference + logo) via {provider}")
        if provider.lower() == "gemini":
            return await _gemini_generate_with_multiple_inputs(
                final_prompt, platform_aspect_ratio, run_directory, 
                strategy_index, reference_image_path, logo_image_path, 
                image_quality_setting, ctx
            )
        else:
            return await _generate_with_multiple_inputs(
                final_prompt, platform_aspect_ratio, client, run_directory, 
                strategy_index, reference_image_path, logo_image_path, 
                image_quality_setting, ctx
            )
    elif reference_image_path:
        # Single image edit case
        log_msg(f"Routing to single image edit via {provider}")
        if provider.lower() == "gemini":
            return await _gemini_generate_with_single_input_edit(
                final_prompt, platform_aspect_ratio, run_directory,
                strategy_index, reference_image_path, image_quality_setting, ctx
            )
        else:
            return await _generate_with_single_input_edit(
                final_prompt, platform_aspect_ratio, client, run_directory,
                strategy_index, reference_image_path, image_quality_setting, ctx
            )
    else:
        # Generation case (no input images) or logo-only case
        input_image_path = logo_image_path if logo_image_path else None
        if input_image_path:
            log_msg(f"Routing to logo-only edit via {provider}")
            if provider.lower() == "gemini":
                return await _gemini_generate_with_single_input_edit(
                    final_prompt, platform_aspect_ratio, run_directory,
                    strategy_index, input_image_path, image_quality_setting, ctx
                )
            else:
                return await _generate_with_single_input_edit(
                    final_prompt, platform_aspect_ratio, client, run_directory,
                    strategy_index, input_image_path, image_quality_setting, ctx
                )
        else:
            log_msg(f"Routing to text-to-image generation via {provider}")
            if provider.lower() == "gemini":
                return await _gemini_generate_with_no_input_image(
                    final_prompt, platform_aspect_ratio, run_directory,
                    strategy_index, image_quality_setting, ctx
                )
            else:
                return await _generate_with_no_input_image(
                    final_prompt, platform_aspect_ratio, client, run_directory,
                    strategy_index, image_quality_setting, ctx
                )


async def _generate_with_no_input_image(
    final_prompt: str,
    platform_aspect_ratio: str,
    client,
    run_directory: str,
    strategy_index: int,
    image_quality_setting: str,
    ctx: Optional[PipelineContext] = None
) -> Tuple[str, Optional[str], Optional[int]]:
    """Handle text-to-image generation (no input images)."""
    # Use global model ID (injected by pipeline executor)
    model_id = IMAGE_GENERATION_MODEL_ID or "gpt-image-1"  # Fallback to default
    
    def log_msg(msg: str):
        """Helper to log messages either via context or print."""
        if ctx:
            ctx.log(msg)
        else:
            print(msg)

    # Calculate comprehensive token usage (text only for this case)
    token_breakdown = await _calculate_comprehensive_tokens(
        final_prompt, model_id=model_id, ctx=ctx
    )
    prompt_tokens_for_image_gen = token_breakdown["total_tokens"]

    if not client:
        return "error", "Image generation client not available.", prompt_tokens_for_image_gen
    if not final_prompt or final_prompt.startswith("Error:"):
        return "error", f"Invalid final prompt provided: {final_prompt}", prompt_tokens_for_image_gen
    if not run_directory or not os.path.isdir(run_directory):
        return "error", f"Invalid run_directory provided: {run_directory}", prompt_tokens_for_image_gen

    try:
        image_api_size = map_aspect_ratio_to_size_for_api(platform_aspect_ratio, ctx)
        if not image_api_size:
            return "error", f"Unsupported aspect ratio '{platform_aspect_ratio}' for image API.", prompt_tokens_for_image_gen

        log_msg(f"--- Calling Image Generation API ({model_id}) ---")

        generate_params: Dict[str, Any] = {
            "model": model_id,
            "prompt": final_prompt,
            "size": image_api_size,
            "n": 1,
            "quality": image_quality_setting
        }

        response = await asyncio.to_thread(client.images.generate, **generate_params)
        return await _process_image_response(response, "generation", run_directory, strategy_index, prompt_tokens_for_image_gen, ctx)

    except Exception as e:
        return _handle_image_api_error(e, "generation", prompt_tokens_for_image_gen, ctx)


async def _generate_with_single_input_edit(
    final_prompt: str,
    platform_aspect_ratio: str,
    client,
    run_directory: str,
    strategy_index: int,
    input_image_path: str,
    image_quality_setting: str,
    ctx: Optional[PipelineContext] = None
) -> Tuple[str, Optional[str], Optional[int]]:
    """Handle single image editing (reference image OR logo only)."""
    # Use global model ID (injected by pipeline executor)
    model_id = IMAGE_GENERATION_MODEL_ID or "gpt-image-1"  # Fallback to default
    
    def log_msg(msg: str):
        """Helper to log messages either via context or print."""
        if ctx:
            ctx.log(msg)
        else:
            print(msg)

    # Calculate comprehensive token usage (text + single input image)
    token_breakdown = await _calculate_comprehensive_tokens(
        final_prompt, reference_image_path=input_image_path, model_id=model_id, ctx=ctx
    )
    prompt_tokens_for_image_gen = token_breakdown["total_tokens"]

    # Enhanced input validation
    if not client:
        log_msg("❌ ERROR: Image generation client not available.")
        return "error", "Image generation client not available.", prompt_tokens_for_image_gen
    if not final_prompt or final_prompt.startswith("Error:"):
        log_msg(f"❌ ERROR: Invalid final prompt: {final_prompt}")
        return "error", f"Invalid final prompt provided: {final_prompt}", prompt_tokens_for_image_gen
    if not run_directory or not os.path.isdir(run_directory):
        log_msg(f"❌ ERROR: Invalid run directory: {run_directory}")
        return "error", f"Invalid run_directory provided: {run_directory}", prompt_tokens_for_image_gen
    if not input_image_path:
        log_msg("❌ ERROR: No input image path provided.")
        return "error", "No input image path provided for editing.", prompt_tokens_for_image_gen

    try:
        image_api_size = map_aspect_ratio_to_size_for_api(platform_aspect_ratio, ctx)
        if not image_api_size:
            log_msg(f"❌ ERROR: Unsupported aspect ratio: {platform_aspect_ratio}")
            return "error", f"Unsupported aspect ratio '{platform_aspect_ratio}' for image API.", prompt_tokens_for_image_gen

        if not os.path.exists(input_image_path):
            log_msg(f"❌ ERROR: Input image file not found: {input_image_path}")
            return "error", f"Input image not found at path: {input_image_path}", prompt_tokens_for_image_gen

        # Validate image file
        try:
            file_size = os.path.getsize(input_image_path)
            if file_size == 0:
                log_msg(f"❌ ERROR: Input image file is empty: {input_image_path}")
                return "error", f"Input image file is empty: {input_image_path}", prompt_tokens_for_image_gen
            if file_size > 50 * 1024 * 1024:  # 50MB limit
                log_msg(f"❌ WARNING: Input image file is very large ({file_size / 1024 / 1024:.1f} MB)")
        except Exception as size_err:
            log_msg(f"⚠️ WARNING: Could not check image file size: {size_err}")

        log_msg(f"--- Calling Image Editing API {model_id} with input image ---")
        log_msg(f"   Input Image: {input_image_path}")
        log_msg(f"   Image API Size: {image_api_size}")
        log_msg(f"   Quality Setting: {image_quality_setting}")
        
        try:
            with open(input_image_path, "rb") as image_file:
                response = await asyncio.to_thread(
                    client.images.edit,
                    model=model_id,
                    image=image_file,
                    prompt=final_prompt,
                    n=1,
                    size=image_api_size,
                    quality=image_quality_setting,
                    input_fidelity="high"  # High fidelity for all image editing operations
                )
            return await _process_image_response(response, "editing", run_directory, strategy_index, prompt_tokens_for_image_gen, ctx)
            
        except FileNotFoundError:
            log_msg(f"❌ ERROR: Input image file not found during API call: {input_image_path}")
            return "error", f"Input image not found at path: {input_image_path}", prompt_tokens_for_image_gen
        except PermissionError:
            log_msg(f"❌ ERROR: Permission denied accessing input image: {input_image_path}")
            return "error", f"Permission denied accessing input image: {input_image_path}", prompt_tokens_for_image_gen
        except Exception as file_err:
            log_msg(f"❌ ERROR: Error opening input image: {file_err}")
            return "error", f"Error opening input image: {file_err}", prompt_tokens_for_image_gen

    except Exception as e:
        return _handle_image_api_error(e, "editing", prompt_tokens_for_image_gen, ctx)


async def _generate_with_multiple_inputs(
    final_prompt: str,
    platform_aspect_ratio: str,
    client,
    run_directory: str,
    strategy_index: int,
    reference_image_path: str,
    logo_image_path: str,
    image_quality_setting: str,
    ctx: Optional[PipelineContext] = None
) -> Tuple[str, Optional[str], Optional[int]]:
    """Handle multi-modal image generation with reference image + logo."""
    # Use global model ID (injected by pipeline executor)
    model_id = IMAGE_GENERATION_MODEL_ID or "gpt-image-1"  # Fallback to default
    
    def log_msg(msg: str):
        """Helper to log messages either via context or print."""
        if ctx:
            ctx.log(msg)
        else:
            print(msg)

    # Calculate comprehensive token usage (text + reference image + logo image)
    token_breakdown = await _calculate_comprehensive_tokens(
        final_prompt, 
        reference_image_path=reference_image_path,
        logo_image_path=logo_image_path,
        model_id=model_id, 
        ctx=ctx
    )
    prompt_tokens_for_image_gen = token_breakdown["total_tokens"]

    if not client:
        log_msg("❌ ERROR: Image generation client not available.")
        return "error", "Image generation client not available.", prompt_tokens_for_image_gen
    if not final_prompt or final_prompt.startswith("Error:"):
        log_msg(f"❌ ERROR: Invalid final prompt: {final_prompt}")
        return "error", f"Invalid final prompt provided: {final_prompt}", prompt_tokens_for_image_gen
    if not run_directory or not os.path.isdir(run_directory):
        log_msg(f"❌ ERROR: Invalid run directory: {run_directory}")
        return "error", f"Invalid run_directory provided: {run_directory}", prompt_tokens_for_image_gen

    # Verify both image files exist
    if not os.path.exists(reference_image_path):
        log_msg(f"❌ ERROR: Reference image not found: {reference_image_path}")
        return "error", f"Reference image not found at path: {reference_image_path}", prompt_tokens_for_image_gen
    if not os.path.exists(logo_image_path):
        log_msg(f"❌ ERROR: Logo image not found: {logo_image_path}")
        return "error", f"Logo image not found at path: {logo_image_path}", prompt_tokens_for_image_gen

    try:
        image_api_size = map_aspect_ratio_to_size_for_api(platform_aspect_ratio, ctx)
        if not image_api_size:
            log_msg(f"❌ ERROR: Unsupported aspect ratio: {platform_aspect_ratio}")
            return "error", f"Unsupported aspect ratio '{platform_aspect_ratio}' for image API.", prompt_tokens_for_image_gen

        log_msg(f"--- Calling Multi-Modal Image Edit API ({model_id}) ---")
        log_msg(f"   Reference Image: {reference_image_path}")
        log_msg(f"   Logo Image: {logo_image_path}")
        log_msg(f"   Image API Size: {image_api_size}")
        log_msg(f"   Quality Setting: {image_quality_setting}")
        
        try:
            # Open both image files and pass them as a list to the API
            with open(reference_image_path, "rb") as ref_file, open(logo_image_path, "rb") as logo_file:
                response = await asyncio.to_thread(
                    client.images.edit,
                    model=model_id,
                    image=[ref_file, logo_file],  # List of image files
                    prompt=final_prompt,
                    n=1,
                    size=image_api_size,
                    quality=image_quality_setting,
                    input_fidelity="high"  # High fidelity for multi-image editing
                )
            
            log_msg("✅ Multi-modal image edit successful!")
            return await _process_image_response(response, "multimodal", run_directory, strategy_index, prompt_tokens_for_image_gen, ctx)
            
        except FileNotFoundError as file_err:
            log_msg(f"❌ ERROR: Image file not found during multi-modal API call: {file_err}")
            log_msg("⚠️ Falling back to single image edit with reference image.")
            return await _generate_with_single_input_edit(
                final_prompt, platform_aspect_ratio, client, run_directory,
                strategy_index, reference_image_path, image_quality_setting, ctx
            )
        except Exception as api_err:
            # Handle API errors - might be because multi-image edit isn't available yet
            error_type = type(api_err).__name__
            if "APIStatusError" in error_type or "APIError" in error_type:
                log_msg(f"⚠️ Multi-modal API error: {api_err}")
                log_msg("⚠️ This might indicate that multi-image editing is not yet available for this model.")
                log_msg("⚠️ Falling back to single image edit with reference image.")
            else:
                log_msg(f"❌ ERROR: Unexpected API error during multi-modal call: {api_err}")
                log_msg("⚠️ Falling back to single image edit with reference image.")
            
            return await _generate_with_single_input_edit(
                final_prompt, platform_aspect_ratio, client, run_directory,
                strategy_index, reference_image_path, image_quality_setting, ctx
            )

    except Exception as e:
        log_msg(f"❌ ERROR: Unexpected error in multi-modal generation: {e}")
        log_msg(f"❌ Error details: {traceback.format_exc()}")
        log_msg("⚠️ Falling back to single image edit with reference image.")
        try:
            return await _generate_with_single_input_edit(
                final_prompt, platform_aspect_ratio, client, run_directory,
                strategy_index, reference_image_path, image_quality_setting, ctx
            )
        except Exception as fallback_err:
            log_msg(f"❌ CRITICAL ERROR: Fallback also failed: {fallback_err}")
            return "error", f"Multi-modal generation failed and fallback failed: {fallback_err}", prompt_tokens_for_image_gen


async def _process_image_response(
    response,
    operation_type: str,
    run_directory: str,
    strategy_index: int,
    prompt_tokens_for_image_gen: int,
    ctx: Optional[PipelineContext] = None
) -> Tuple[str, Optional[str], Optional[int]]:
    """Process the API response from image generation/editing calls."""
    def log_msg(msg: str):
        """Helper to log messages either via context or print."""
        if ctx:
            ctx.log(msg)
        else:
            print(msg)

    if response and response.data and len(response.data) > 0:
        image_data = response.data[0]
        saved_filepath = None

        if image_data.b64_json:
            log_msg(f"✅ Image {operation_type} successful (received base64 data).")
            try:
                image_bytes = base64.b64decode(image_data.b64_json)
                timestamp_img = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')

                if operation_type == "editing":
                    local_filename = f"edited_image_strategy_{strategy_index}_{timestamp_img}.png"
                elif operation_type == "multimodal":
                    local_filename = f"edited_image_strategy_{strategy_index}_{timestamp_img}.png"
                else:  # Covers "generation"
                    local_filename = f"generated_image_strategy_{strategy_index}_{timestamp_img}.png"

                saved_filepath = os.path.join(run_directory, local_filename)
                with open(saved_filepath, "wb") as f:
                    f.write(image_bytes)
                log_msg(f"   Saved image to: {saved_filepath}")

                return "success", saved_filepath, prompt_tokens_for_image_gen
            except Exception as decode_save_err:
                log_msg(f"❌ Error decoding/saving base64 image: {decode_save_err}")
                return "error", f"Error processing base64 response: {decode_save_err}", prompt_tokens_for_image_gen
        elif image_data.url:  # Fallback if b64_json wasn't requested or provided
            log_msg(f"✅ Image {operation_type} successful (received URL). Downloading...")
            image_url = image_data.url
            try:
                img_response_download = await asyncio.to_thread(requests.get, image_url, stream=True, timeout=30)
                img_response_download.raise_for_status()
                timestamp_img_url = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')
                if operation_type == "editing":
                    url_filename = f"edited_image_strategy_{strategy_index}_{timestamp_img_url}.png"
                elif operation_type == "multimodal":
                    url_filename = f"edited_image_strategy_{strategy_index}_{timestamp_img_url}.png"
                else:
                    url_filename = f"generated_image_strategy_{strategy_index}_{timestamp_img_url}.png"

                saved_filepath = os.path.join(run_directory, url_filename)
                with open(saved_filepath, "wb") as f:
                    for chunk in img_response_download.iter_content(chunk_size=8192): 
                        f.write(chunk)
                log_msg(f"   Saved downloaded image to: {saved_filepath}")
                return "success", saved_filepath, prompt_tokens_for_image_gen
            except requests.exceptions.RequestException as req_err:
                return "error", f"Error downloading image URL {image_url}: {req_err}", prompt_tokens_for_image_gen
        else:
            return "error", f"Image API response format mismatch for {operation_type}. No b64_json or URL.", prompt_tokens_for_image_gen
    else:
        return "error", "Image API response did not contain expected data structure.", prompt_tokens_for_image_gen


def _handle_image_api_error(
    e: Exception,
    operation_type: str,
    prompt_tokens_for_image_gen: int,
    ctx: Optional[PipelineContext] = None
) -> Tuple[str, str, int]:
    """Handle errors from image API calls."""
    def log_msg(msg: str):
        """Helper to log messages either via context or print."""
        if ctx:
            ctx.log(msg)
        else:
            print(msg)

    # Handle specific OpenAI exceptions
    error_type = type(e).__name__
    if "APIConnectionError" in error_type:
        log_msg(f"❌ ERROR: Image API connection error: {e}")
        return "error", f"Connection error: {e}", prompt_tokens_for_image_gen
    elif "RateLimitError" in error_type:
        log_msg(f"❌ ERROR: Image API rate limit exceeded: {e}")
        return "error", f"Rate limit error: {e}", prompt_tokens_for_image_gen
    elif "APIStatusError" in error_type:
        log_msg(f"❌ ERROR: Image API status error: {e}")
        error_message = f"API status error"
        try:
            if hasattr(e, 'status_code') and hasattr(e, 'response'):
                error_message = f"API status error {e.status_code}"
                error_details = e.response.json()
                if 'error' in error_details and 'message' in error_details['error']:
                    error_message += f": {error_details['error']['message']}"
        except:
            pass
        return "error", error_message, prompt_tokens_for_image_gen
    else:
        log_msg(f"❌ ERROR: Unexpected error during image {operation_type}: {e}")
        log_msg(traceback.format_exc())
        return "error", f"Unexpected error: {e}", prompt_tokens_for_image_gen


def _calculate_comprehensive_tokens_sync(
    final_prompt: str,
    reference_image_path: Optional[str] = None,
    logo_image_path: Optional[str] = None,
    model_id: str = None,
    ctx: Optional[PipelineContext] = None
) -> Dict[str, Any]:
    """
    Calculate comprehensive token usage including text and input image tokens (synchronous helper).
    
    Args:
        final_prompt: Text prompt for image generation
        reference_image_path: Optional reference image path
        logo_image_path: Optional logo image path  
        model_id: Model ID for token calculation
        ctx: Pipeline context for logging
        
    Returns:
        Dictionary with comprehensive token breakdown
    """
    def log_msg(msg: str):
        if ctx:
            ctx.log(msg)
        else:
            print(msg)
    
    # Use model_id parameter or fallback to global/default
    model_for_calc = model_id or IMAGE_GENERATION_MODEL_ID or "gpt-image-1"
    
    try:
        token_manager = get_token_cost_manager()
        
        # Calculate text prompt tokens (improved estimation)
        try:
            # More accurate token count using tiktoken
            enc = tiktoken.encoding_for_model("gpt-4")  # Use gpt-4 encoding as proxy
            text_tokens = len(enc.encode(final_prompt))
        except Exception:
            # Fallback to word count estimation
            text_tokens = len(final_prompt.split()) * 1.3  # Words * 1.3 is closer to tokens
            text_tokens = int(text_tokens)
        
        # Calculate input image tokens
        input_image_tokens = 0
        num_input_images = 0
        image_details = []
        
        # Calculate reference image tokens
        if reference_image_path and os.path.exists(reference_image_path):
            try:
                with Image.open(reference_image_path) as img:
                    width, height = img.size
                ref_tokens = token_manager.calculate_image_tokens(width, height, model_for_calc)
                input_image_tokens += ref_tokens
                num_input_images += 1
                image_details.append({
                    "type": "reference_image",
                    "path": reference_image_path,
                    "size": f"{width}x{height}",
                    "tokens": ref_tokens
                })
                log_msg(f"Reference image tokens: {ref_tokens} (size: {width}x{height})")
            except Exception as e:
                log_msg(f"Could not calculate tokens for reference image: {e}")
        
        # Calculate logo image tokens  
        if logo_image_path and os.path.exists(logo_image_path):
            try:
                with Image.open(logo_image_path) as img:
                    width, height = img.size
                logo_tokens = token_manager.calculate_image_tokens(width, height, model_for_calc)
                input_image_tokens += logo_tokens
                num_input_images += 1
                image_details.append({
                    "type": "logo_image", 
                    "path": logo_image_path,
                    "size": f"{width}x{height}",
                    "tokens": logo_tokens
                })
                log_msg(f"Logo image tokens: {logo_tokens} (size: {width}x{height})")
            except Exception as e:
                log_msg(f"Could not calculate tokens for logo image: {e}")
        
        total_tokens = text_tokens + input_image_tokens
        
        return {
            "text_tokens": text_tokens,
            "input_image_tokens": input_image_tokens,
            "total_tokens": total_tokens,
            "num_input_images": num_input_images,
            "image_details": image_details,
            "model_id": model_for_calc
        }
        
    except Exception as e:
        log_msg(f"Error calculating comprehensive tokens: {e}")
        # Fallback to simple estimation
        fallback_tokens = len(final_prompt.split())
        return {
            "text_tokens": fallback_tokens,
            "input_image_tokens": 0,
            "total_tokens": fallback_tokens,
            "num_input_images": 0,
            "image_details": [],
            "model_id": model_for_calc,
            "error": str(e)
        }


async def _calculate_comprehensive_tokens(
    final_prompt: str,
    reference_image_path: Optional[str] = None,
    logo_image_path: Optional[str] = None,
    model_id: str = None,
    ctx: Optional[PipelineContext] = None
) -> Dict[str, Any]:
    """
    Calculate comprehensive token usage including text and input image tokens (asynchronous).
    
    Args:
        final_prompt: Text prompt for image generation
        reference_image_path: Optional reference image path
        logo_image_path: Optional logo image path  
        model_id: Model ID for token calculation
        ctx: Pipeline context for logging
        
    Returns:
        Dictionary with comprehensive token breakdown
    """
    return await asyncio.to_thread(
        _calculate_comprehensive_tokens_sync,
        final_prompt,
        reference_image_path,
        logo_image_path,
        model_id,
        ctx
    )


# ================================
# GEMINI IMAGE GENERATION FUNCTIONS
# ================================

async def _gemini_generate_with_no_input_image(
    final_prompt: str,
    platform_aspect_ratio: str,
    run_directory: str,
    strategy_index: int,
    image_quality_setting: str,
    ctx: Optional[PipelineContext] = None
) -> Tuple[str, Optional[str], Optional[int]]:
    """Handle text-to-image generation using Gemini."""
    from ..core.constants import get_image_generation_model_id
    model_id = get_image_generation_model_id()
    
    def log_msg(msg: str):
        if ctx:
            ctx.log(msg)
        else:
            print(msg)

    # Calculate comprehensive token usage (text only for this case)
    token_breakdown = await _calculate_comprehensive_tokens(
        final_prompt, model_id=model_id, ctx=ctx
    )
    prompt_tokens_for_image_gen = token_breakdown["total_tokens"]

    if not image_gen_client_gemini:
        return "error", "Gemini image generation client not available.", prompt_tokens_for_image_gen
    if not final_prompt or final_prompt.startswith("Error:"):
        return "error", f"Invalid final prompt provided: {final_prompt}", prompt_tokens_for_image_gen
    if not run_directory or not os.path.isdir(run_directory):
        return "error", f"Invalid run_directory provided: {run_directory}", prompt_tokens_for_image_gen

    try:
        # Add aspect ratio directive to prompt for Gemini
        aspect_prompt = _add_aspect_ratio_to_prompt(final_prompt, platform_aspect_ratio)
        log_msg(f"--- Calling Gemini Image Generation API ({model_id}) ---")

        # Build contents array for Gemini
        contents = [aspect_prompt]
        
        response = await asyncio.to_thread(
            image_gen_client_gemini.models.generate_content,
            model=model_id,
            contents=contents
        )
        
        # Normalize Gemini response to OpenAI-like format
        normalized_response = _normalize_gemini_response(response)
        return await _process_image_response(normalized_response, "generation", run_directory, strategy_index, prompt_tokens_for_image_gen, ctx)

    except Exception as e:
        return _handle_gemini_api_error(e, "generation", prompt_tokens_for_image_gen, ctx)


async def _gemini_generate_with_single_input_edit(
    final_prompt: str,
    platform_aspect_ratio: str,
    run_directory: str,
    strategy_index: int,
    input_image_path: str,
    image_quality_setting: str,
    ctx: Optional[PipelineContext] = None
) -> Tuple[str, Optional[str], Optional[int]]:
    """Handle single image editing using Gemini."""
    from ..core.constants import get_image_generation_model_id
    model_id = get_image_generation_model_id()
    
    def log_msg(msg: str):
        if ctx:
            ctx.log(msg)
        else:
            print(msg)

    # Calculate comprehensive token usage
    token_breakdown = await _calculate_comprehensive_tokens(
        final_prompt, model_id=model_id, reference_image_path=input_image_path, ctx=ctx
    )
    prompt_tokens_for_image_gen = token_breakdown["total_tokens"]

    if not image_gen_client_gemini:
        return "error", "Gemini image generation client not available.", prompt_tokens_for_image_gen
    if not final_prompt or final_prompt.startswith("Error:"):
        return "error", f"Invalid final prompt provided: {final_prompt}", prompt_tokens_for_image_gen
    if not os.path.exists(input_image_path):
        return "error", f"Input image not found: {input_image_path}", prompt_tokens_for_image_gen

    try:
        # Add aspect ratio directive to prompt
        aspect_prompt = _add_aspect_ratio_to_prompt(final_prompt, platform_aspect_ratio)
        log_msg(f"--- Calling Gemini Image Edit API ({model_id}) ---")

        # Read and encode input image
        with open(input_image_path, 'rb') as f:
            image_data = f.read()
        
        image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        # Determine MIME type
        if input_image_path.lower().endswith('.png'):
            mime_type = 'image/png'
        elif input_image_path.lower().endswith(('.jpg', '.jpeg')):
            mime_type = 'image/jpeg'
        else:
            mime_type = 'image/png'  # Default fallback
        
        # Build contents array for Gemini with image
        contents = [
            aspect_prompt,
            {"inline_data": {"mime_type": mime_type, "data": image_base64}}
        ]
        
        response = await asyncio.to_thread(
            image_gen_client_gemini.models.generate_content,
            model=model_id,
            contents=contents
        )
        
        # Normalize Gemini response to OpenAI-like format
        normalized_response = _normalize_gemini_response(response)
        return await _process_image_response(normalized_response, "editing", run_directory, strategy_index, prompt_tokens_for_image_gen, ctx)

    except Exception as e:
        return _handle_gemini_api_error(e, "edit", prompt_tokens_for_image_gen, ctx)


async def _gemini_generate_with_multiple_inputs(
    final_prompt: str,
    platform_aspect_ratio: str,
    run_directory: str,
    strategy_index: int,
    reference_image_path: str,
    logo_image_path: str,
    image_quality_setting: str,
    ctx: Optional[PipelineContext] = None
) -> Tuple[str, Optional[str], Optional[int]]:
    """Handle multi-image editing using Gemini."""
    from ..core.constants import get_image_generation_model_id
    model_id = get_image_generation_model_id()
    
    def log_msg(msg: str):
        if ctx:
            ctx.log(msg)
        else:
            print(msg)

    # Calculate comprehensive token usage
    token_breakdown = await _calculate_comprehensive_tokens(
        final_prompt, model_id=model_id, 
        reference_image_path=reference_image_path, 
        logo_image_path=logo_image_path, ctx=ctx
    )
    prompt_tokens_for_image_gen = token_breakdown["total_tokens"]

    if not image_gen_client_gemini:
        return "error", "Gemini image generation client not available.", prompt_tokens_for_image_gen
    if not final_prompt or final_prompt.startswith("Error:"):
        return "error", f"Invalid final prompt provided: {final_prompt}", prompt_tokens_for_image_gen
    if not os.path.exists(reference_image_path):
        return "error", f"Reference image not found: {reference_image_path}", prompt_tokens_for_image_gen
    if not os.path.exists(logo_image_path):
        return "error", f"Logo image not found: {logo_image_path}", prompt_tokens_for_image_gen

    try:
        # Add aspect ratio directive to prompt
        aspect_prompt = _add_aspect_ratio_to_prompt(final_prompt, platform_aspect_ratio)
        log_msg(f"--- Calling Gemini Multi-Image API ({model_id}) ---")

        # Read and encode reference image
        with open(reference_image_path, 'rb') as f:
            ref_image_data = f.read()
        ref_image_base64 = base64.b64encode(ref_image_data).decode('utf-8')
        ref_mime_type = 'image/png' if reference_image_path.lower().endswith('.png') else 'image/jpeg'
        
        # Read and encode logo image
        with open(logo_image_path, 'rb') as f:
            logo_image_data = f.read()
        logo_image_base64 = base64.b64encode(logo_image_data).decode('utf-8')
        logo_mime_type = 'image/png' if logo_image_path.lower().endswith('.png') else 'image/jpeg'
        
        # Build contents array for Gemini with multiple images
        contents = [
            aspect_prompt,
            {"inline_data": {"mime_type": ref_mime_type, "data": ref_image_base64}},
            {"inline_data": {"mime_type": logo_mime_type, "data": logo_image_base64}}
        ]
        
        response = await asyncio.to_thread(
            image_gen_client_gemini.models.generate_content,
            model=model_id,
            contents=contents
        )
        
        # Normalize Gemini response to OpenAI-like format
        normalized_response = _normalize_gemini_response(response)
        return await _process_image_response(normalized_response, "multimodal", run_directory, strategy_index, prompt_tokens_for_image_gen, ctx)

    except Exception as e:
        return _handle_gemini_api_error(e, "edit", prompt_tokens_for_image_gen, ctx)


def _add_aspect_ratio_to_prompt(prompt: str, aspect_ratio: str) -> str:
    """Add aspect ratio directive to prompt for Gemini (since it doesn't have size parameter)."""
    aspect_directive_map = {
        "1:1": "The image should be in a 1:1 aspect ratio (square).",
        "9:16": "The image should be in a 9:16 aspect ratio (vertical).",
        "16:9": "The image should be in a 16:9 aspect ratio (horizontal).",
        "2:3": "The image should be in a 2:3 aspect ratio (vertical).",
        "3:4": "The image should be in a 3:4 aspect ratio (vertical).",
        "1.91:1": "The image should be in a 1.91:1 aspect ratio (horizontal)."
    }
    
    directive = aspect_directive_map.get(aspect_ratio, "The image should be in a 1:1 aspect ratio (square).")
    return f"{prompt} {directive}"


def _normalize_gemini_response(response: Any) -> _OpenAIStyleResponse:
    """Normalize Gemini response to OpenAI-like format for reusing _process_image_response."""
    try:
        # Extract first inline_data image part from response
        if hasattr(response, 'candidates') and response.candidates:
            candidate = response.candidates[0]
            if hasattr(candidate, 'content') and hasattr(candidate.content, 'parts'):
                for part in candidate.content.parts:
                    if hasattr(part, 'inline_data') and hasattr(part.inline_data, 'data'):
                        # Gemini's inline_data.data contains the image data
                        gemini_data = part.inline_data.data
                        
                        # Handle different data formats from Gemini
                        if isinstance(gemini_data, bytes):
                            # Convert raw bytes to base64 for OpenAI compatibility
                            gemini_base64_data = base64.b64encode(gemini_data).decode('utf-8')
                        elif isinstance(gemini_data, str):
                            # Assume it's already base64 encoded
                            gemini_base64_data = gemini_data
                        else:
                            raise ValueError(f"Unexpected Gemini data type: {type(gemini_data)}")
                        
                        return _OpenAIStyleResponse(gemini_base64_data)
        
        # If we get here, no image data was found
        raise ValueError("No image data found in Gemini response")
        
    except Exception as e:
        raise ValueError(f"Failed to normalize Gemini response: {e}")


def _handle_gemini_api_error(
    error: Exception, 
    operation_type: str, 
    prompt_tokens: Optional[int], 
    ctx: Optional[PipelineContext] = None
) -> Tuple[str, str, Optional[int]]:
    """Handle Gemini API errors and map to standardized error format."""
    def log_msg(msg: str):
        if ctx:
            ctx.log(msg)
        else:
            print(msg)
    
    error_msg = str(error)
    log_msg(f"Gemini API error during {operation_type}: {error_msg}")
    
    # Map common Gemini errors to user-friendly messages
    if "quota" in error_msg.lower() or "limit" in error_msg.lower():
        friendly_msg = "Gemini API quota exceeded. Please try again later."
    elif "safety" in error_msg.lower() or "blocked" in error_msg.lower():
        friendly_msg = "Content was blocked by Gemini safety filters. Please modify your prompt."
    elif "invalid" in error_msg.lower():
        friendly_msg = f"Invalid request to Gemini API: {error_msg}"
    else:
        friendly_msg = f"Gemini API error: {error_msg}"
    
    return "error", friendly_msg, prompt_tokens


async def run(ctx: PipelineContext) -> None:
    """
    Stage 6: Image Generation
    
    Generates images using gpt-image-1 via OpenAI Images API based on assembled prompts
    from the previous stage. Handles both generation and editing scenarios.
    
    Input: ctx.final_assembled_prompts (list of assembled prompt dicts)
    Output: ctx.generated_image_results (list of image generation results)
    """
    ctx.log("Starting Image Generation stage...")
    
    # Get data from previous stages
    assembled_prompts = ctx.final_assembled_prompts or []
    
    # Check if the required client is available based on provider
    provider = IMAGE_GENERATION_PROVIDER or "OpenAI"
    has_client = (provider == "Gemini" and image_gen_client_gemini) or (provider == "OpenAI" and (image_gen_client or image_gen_client_openai))
    
    if not has_client:
        ctx.log(f"ERROR: {provider} Image Generation Client not configured.")
        # Generate error results for each assembled prompt
        error_results = []
        for i, prompt_data in enumerate(assembled_prompts):
            error_results.append({
                "index": i,
                "status": "error",
                "result_path": None,
                "error_message": f"{provider} image generation client not available.",
                "prompt_tokens": 0
            })
        ctx.generated_image_results = error_results
        return
        
    if not assembled_prompts:
        ctx.log("WARNING: No assembled prompts available to generate images from.")
        ctx.generated_image_results = []
        return
        
    # Get platform aspect ratio and reference image path
    platform_aspect_ratio = "1:1"  # Default
    if ctx.target_platform and ctx.target_platform.get("resolution_details"):
        platform_aspect_ratio = ctx.target_platform["resolution_details"].get("aspect_ratio", "1:1")
        
    # Determine image inputs for multi-modal support
    reference_image_path = None
    logo_image_path = None
    
    # Get reference image path
    if ctx.image_reference and ctx.image_reference.get("saved_image_path_in_run_dir"):
        reference_image_path = ctx.image_reference["saved_image_path_in_run_dir"]
        ctx.log(f"Found primary reference image: {reference_image_path}")
    
    # Get logo image path
    if ctx.brand_kit and ctx.brand_kit.get("saved_logo_path_in_run_dir"):
        logo_image_path = ctx.brand_kit["saved_logo_path_in_run_dir"]
        ctx.log(f"Found brand logo image: {logo_image_path}")
    
    # Log the determined routing scenario
    if reference_image_path and logo_image_path:
        ctx.log("🎯 Multi-modal scenario detected: Reference image + Logo")
    elif reference_image_path:
        ctx.log("📸 Single image editing scenario: Reference image only")
    elif logo_image_path:
        ctx.log("🏷️ Logo-only editing scenario: Logo as reference")
    else:
        ctx.log("✨ Text-to-image generation scenario: No input images")
        
    # Determine output directory - prefer run-specific directory
    output_directory = getattr(ctx, 'output_directory', None)
    
    # If no output_directory attribute, try to derive from image reference path
    if not output_directory and ctx.image_reference and ctx.image_reference.get("saved_image_path_in_run_dir"):
        saved_image_path = ctx.image_reference["saved_image_path_in_run_dir"]
        # Extract run directory from the saved image path
        # e.g., "data/runs/9e6fef80-252d-424b-822d-51af992e290a/input_image.jpg" -> "data/runs/9e6fef80-252d-424b-822d-51af992e290a"
        output_directory = os.path.dirname(saved_image_path)
        ctx.log(f"Using run-specific output directory derived from image path: {output_directory}")
    
    # Alternative fallback: try to derive from pipeline timestamp if available
    if not output_directory and hasattr(ctx, 'data') and ctx.data:
        pipeline_settings = ctx.data.get("pipeline_settings", {})
        run_timestamp = pipeline_settings.get("run_timestamp")
        if run_timestamp:
            # Try to find the run directory based on timestamp pattern
            data_dir = os.path.join(os.getcwd(), "data", "runs")
            if os.path.exists(data_dir):
                for dir_name in os.listdir(data_dir):
                    run_dir_path = os.path.join(data_dir, dir_name)
                    if os.path.isdir(run_dir_path):
                        output_directory = run_dir_path
                        ctx.log(f"Using run-specific output directory found in data/runs: {output_directory}")
                        break
    
    # Final fallback to default directory if nothing else works
    if not output_directory:
        output_directory = os.path.join(os.getcwd(), 'output')
        os.makedirs(output_directory, exist_ok=True)
        ctx.log(f"⚠️  Warning: Using default output directory: {output_directory}")
    
    # Ensure the directory exists
    os.makedirs(output_directory, exist_ok=True)
    
    ctx.log(f"Generating images for {len(assembled_prompts)} assembled prompts...")
    
    # Prepare tasks for parallel execution
    tasks = []
    valid_prompts = []
    generated_image_results = []
    
    for prompt_data in assembled_prompts:
        strategy_index = prompt_data.get("index", "N/A")
        final_text_prompt = prompt_data.get("prompt", "")
        
        ctx.log(f"Preparing image generation for Strategy {strategy_index}...")
        
        if final_text_prompt.startswith("Error:"):
            ctx.log(f"   Skipping image generation due to prompt assembly error: {final_text_prompt}")
            generated_image_results.append({
                "index": strategy_index, 
                "status": "error", 
                "result_path": None, 
                "error_message": final_text_prompt
            })
            continue
            
        # Create async task for this image generation
        task = generate_image(
            final_text_prompt,
            platform_aspect_ratio,
            image_gen_client,
            output_directory,
            strategy_index,
            reference_image_path=reference_image_path,
            logo_image_path=logo_image_path,
            image_quality_setting="medium",  # Default for gpt-image-1
            ctx=ctx
        )
        tasks.append(task)
        valid_prompts.append((strategy_index, final_text_prompt))
    
    if tasks:
        ctx.log(f"Processing {len(tasks)} image generations in parallel...")
        
        try:
            # Run all image generation tasks concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Process results
            for i, result in enumerate(results):
                strategy_index, final_text_prompt = valid_prompts[i]
                
                if isinstance(result, Exception):
                    ctx.log(f"   ❌ Image generation failed for Strategy {strategy_index}: {result}")
                    generated_image_results.append({
                        "index": strategy_index, 
                        "status": "error", 
                        "result_path": None, 
                        "error_message": str(result)
                    })
                    continue
                
                img_status, img_result_path_or_msg, img_prompt_tokens = result
                
                if img_status == "success":
                    # Store just the filename for frontend API compatibility
                    filename_only = os.path.basename(img_result_path_or_msg) if img_result_path_or_msg else None
                    
                    # Calculate comprehensive token breakdown for metadata
                    from ..core.constants import get_image_generation_model_id
                    breakdown_model_id = get_image_generation_model_id()
                    
                    token_breakdown = await _calculate_comprehensive_tokens(
                        final_text_prompt,
                        reference_image_path=reference_image_path,
                        logo_image_path=logo_image_path,
                        model_id=breakdown_model_id,
                        ctx=ctx
                    )
                    
                    # Use configured provider and get corresponding model ID
                    provider = IMAGE_GENERATION_PROVIDER or "OpenAI"
                    actual_model_id = breakdown_model_id
                    
                    # Determine output resolution and quality based on provider
                    if provider.lower() == "openai":
                        output_resolution = map_aspect_ratio_to_size_for_api(platform_aspect_ratio, ctx) or "1024x1024"
                        output_quality = "medium"  # Default for OpenAI
                    else:  # Gemini
                        output_resolution = "1024x1024"  # Gemini default (unless resized)
                        output_quality = "default"  # Gemini uses "default" quality
                    
                    generated_image_results.append({
                        "index": strategy_index, 
                        "status": "success", 
                        "result_path": filename_only, 
                        "error_message": None,
                        "prompt_tokens": img_prompt_tokens,
                        # Enhanced token breakdown for metadata
                        "token_breakdown": {
                            "text_tokens": token_breakdown.get("text_tokens", 0),
                            "input_image_tokens": token_breakdown.get("input_image_tokens", 0), 
                            "total_tokens": token_breakdown.get("total_tokens", img_prompt_tokens),
                            "num_input_images": token_breakdown.get("num_input_images", 0),
                            "image_details": token_breakdown.get("image_details", [])
                        },
                        # Provider and model metadata for cost calculation
                        "generation_metadata": {
                            "provider": provider.lower(),
                            "model_id": actual_model_id,
                            "output_resolution": output_resolution,
                            "output_quality": output_quality
                        }
                    })
                    ctx.log(f"   ✅ Image generated successfully: {img_result_path_or_msg}")
                    
                    # Log token breakdown for multi-modal scenarios
                    if token_breakdown.get("num_input_images", 0) > 0:
                        ctx.log(f"   📊 Token breakdown: {token_breakdown['text_tokens']} text + {token_breakdown['input_image_tokens']} image = {token_breakdown['total_tokens']} total")
                else:
                    generated_image_results.append({
                        "index": strategy_index, 
                        "status": "error", 
                        "result_path": None, 
                        "error_message": img_result_path_or_msg,
                        "prompt_tokens": img_prompt_tokens
                    })
                    ctx.log(f"   ❌ Image generation failed: {img_result_path_or_msg}")
                    
        except Exception as e:
            ctx.log(f"ERROR during parallel image generation: {e}")
            # Add error results for all remaining tasks
            for strategy_index, _ in valid_prompts:
                generated_image_results.append({
                    "index": strategy_index, 
                    "status": "error", 
                    "result_path": None, 
                    "error_message": f"Parallel execution error: {e}"
                })
    else:
        ctx.log("No valid prompts to process for image generation")
    
    # Store results in context
    ctx.generated_image_results = generated_image_results
    
    successful_generations = len([r for r in generated_image_results if r["status"] == "success"])
    total_attempts = len(generated_image_results)
    
    ctx.log(f"✅ Image Generation stage completed")
    ctx.log(f"   Generated {successful_generations}/{total_attempts} images successfully")
    
    if successful_generations > 0:
        ctx.log("   Generated images:")
        for result in generated_image_results:
            if result["status"] == "success":
                ctx.log(f"   - Strategy {result['index']}: {result['result_path']}") 