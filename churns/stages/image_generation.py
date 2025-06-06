"""
Stage 6: Image Generation

Generates images using the gpt-image-1 model via OpenAI Images API.
Handles both image generation and editing based on assembled prompts from
the previous stage. Supports different qualities, aspect ratios, and 
comprehensive error handling.

Extracted from original monolith: generate_image function (~line 2111)
"""

import os
import base64
import datetime
import traceback
from typing import Optional, Dict, Any, Tuple
import requests

from ..pipeline.context import PipelineContext

# Global variables for API clients and configuration (injected by pipeline executor)
image_gen_client = None
IMAGE_GENERATION_MODEL_ID = None


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


def generate_image(
    final_prompt: str,
    platform_aspect_ratio: str,
    client,  # OpenAI client
    run_directory: str,
    strategy_index: int,
    reference_image_path: Optional[str] = None,
    image_quality_setting: str = "medium",
    ctx: Optional[PipelineContext] = None
) -> Tuple[str, Optional[str], Optional[int]]:
    """
    Generates or edits an image using the OpenAI Images API (gpt-image-1)
    via the specified client. Uses client.images.edit if reference_image_path is provided,
    Otherwise, uses client.images.generate.

    Args:
        final_prompt: The assembled text prompt string describing the desired outcome or edit.
        platform_aspect_ratio: The aspect ratio string ('1:1', '9:16', '16:9', '2:3', '3:4').
        client: The initialized OpenAI client.
        run_directory: The path to the directory where outputs for this run are saved.
        strategy_index: The index of the current strategy (for filename).
        reference_image_path: Optional path to the reference image for editing.
        image_quality_setting: Quality setting for gpt-image-1 (default "medium").
        ctx: Optional pipeline context for logging.

    Returns:
        A tuple containing:
          - status: "success" or "error"
          - url_or_filepath: The image URL (for generation) or local file path (for edits)
                             if successful, or an error message string.
          - prompt_tokens_for_image_gen: Estimated prompt tokens
    """
    # Use global model ID (injected by pipeline executor)
    model_id = IMAGE_GENERATION_MODEL_ID or "gpt-image-1"  # Fallback to default
    
    def log_msg(msg: str):
        """Helper to log messages either via context or print."""
        if ctx:
            ctx.log(msg)
        else:
            print(msg)

    prompt_tokens_for_image_gen = len(final_prompt.split())  # Simple estimation

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

        response = None
        operation_type = "generation"

        if reference_image_path and os.path.exists(reference_image_path):
            if model_id:
                operation_type = "editing"
                log_msg(f"--- Calling Image Editing API {model_id} with reference image ---")
                log_msg(f"   Reference Image: {reference_image_path}")
                try:
                    with open(reference_image_path, "rb") as image_file:
                        response = client.images.edit(
                            model=model_id,
                            image=image_file,
                            prompt=final_prompt,
                            n=1,
                            size=image_api_size,
                            quality=image_quality_setting
                        )
                except FileNotFoundError:
                    return "error", f"Reference image not found at path: {reference_image_path}", prompt_tokens_for_image_gen
                except Exception as file_err:
                    return "error", f"Error opening reference image: {file_err}", prompt_tokens_for_image_gen
        else:  # No reference image path, or path was invalid
            operation_type = "generation"
            if reference_image_path:  # Path provided but file not found
                log_msg(f"⚠️ Warning: Reference image path provided but file not found: {reference_image_path}. Proceeding with generation.")
            log_msg(f"--- Calling Image Generation API ({model_id}) ---")

            generate_params: Dict[str, Any] = {
                "model": model_id,
                "prompt": final_prompt,
                "size": image_api_size,
                "n": 1,
                "quality": image_quality_setting
            }

            response = client.images.generate(**generate_params)

        # --- Process Response ---
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
                    else:  # Covers "generation" and "generation_with_reference_in_prompt"
                        local_filename = f"generated_image_strategy_{strategy_index}_{timestamp_img}.png"

                    saved_filepath = os.path.join(run_directory, local_filename)
                    with open(saved_filepath, "wb") as f:
                        f.write(image_bytes)
                    log_msg(f"   Saved image to: {saved_filepath}")

                    return "success", saved_filepath, prompt_tokens_for_image_gen
                except Exception as decode_save_err:
                    log_msg(f"❌ Error decoding/saving base64 image: {decode_save_err}")
                    return "error", f"Error processing base64 response: {decode_save_err}", prompt_tokens_for_image_gen
            elif image_data.url:  # Fallback if b64_json wasn't requested or provided (should be rare now)
                log_msg(f"✅ Image {operation_type} successful (received URL). Downloading...")
                image_url = image_data.url
                try:
                    img_response_download = requests.get(image_url, stream=True, timeout=30)
                    img_response_download.raise_for_status()
                    timestamp_img_url = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')
                    if operation_type == "editing":
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

    except Exception as e:
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


def run(ctx: PipelineContext) -> None:
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
    
    # Use global client variable (injected by pipeline executor)
    if not image_gen_client:
        ctx.log("ERROR: Image Generation Client not configured. Skipping image generation.")
        ctx.generated_image_results = []
        return
        
    if not assembled_prompts:
        ctx.log("WARNING: No assembled prompts available to generate images from.")
        ctx.generated_image_results = []
        return
        
    # Get platform aspect ratio and reference image path
    platform_aspect_ratio = "1:1"  # Default
    if ctx.target_platform and ctx.target_platform.get("resolution_details"):
        platform_aspect_ratio = ctx.target_platform["resolution_details"].get("aspect_ratio", "1:1")
        
    reference_image_path = None
    if ctx.image_reference and ctx.image_reference.get("saved_image_path_in_run_dir"):
        reference_image_path = ctx.image_reference["saved_image_path_in_run_dir"]
        
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
    
    generated_image_results = []
    
    for prompt_data in assembled_prompts:
        strategy_index = prompt_data.get("index", "N/A")
        final_text_prompt = prompt_data.get("prompt", "")
        
        ctx.log(f"Processing image generation for Strategy {strategy_index}...")
        
        if final_text_prompt.startswith("Error:"):
            ctx.log(f"   Skipping image generation due to prompt assembly error: {final_text_prompt}")
            generated_image_results.append({
                "index": strategy_index, 
                "status": "error", 
                "result_path": None, 
                "error_message": final_text_prompt
            })
            continue
            
        # Generate/edit the image using global client
        img_status, img_result_path_or_msg, img_prompt_tokens = generate_image(
            final_text_prompt,
            platform_aspect_ratio,
            image_gen_client,
            output_directory,
            strategy_index,
            reference_image_path=reference_image_path,
            image_quality_setting="medium",  # Default for gpt-image-1
            ctx=ctx
        )
        
        if img_status == "success":
            # Store just the filename for frontend API compatibility
            filename_only = os.path.basename(img_result_path_or_msg) if img_result_path_or_msg else None
            
            generated_image_results.append({
                "index": strategy_index, 
                "status": "success", 
                "result_path": filename_only, 
                "error_message": None,
                "prompt_tokens": img_prompt_tokens
            })
            ctx.log(f"   ✅ Image generated successfully: {img_result_path_or_msg}")
        else:
            generated_image_results.append({
                "index": strategy_index, 
                "status": "error", 
                "result_path": None, 
                "error_message": img_result_path_or_msg,
                "prompt_tokens": img_prompt_tokens
            })
            ctx.log(f"   ❌ Image generation failed: {img_result_path_or_msg}")
    
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