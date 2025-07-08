"""
Shared Refinement Utilities

Common functions and patterns used across all refinement stages.
Centralizes API calling, error handling, cost calculation, and file management
to maintain consistency and reduce duplication.
"""

import os
import base64
import datetime
import traceback
import asyncio
import json
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from PIL import Image, ImageDraw
from openai import OpenAI
from ..pipeline.context import PipelineContext
from ..core.constants import IMAGE_GENERATION_MODEL_ID, MODEL_PRICING
from ..core.token_cost_manager import TokenCostManager, TokenUsage, CostBreakdown
from ..models import CostDetail

# Global variables for API clients and configuration (injected by pipeline executor)
# These will be set by the pipeline executor before stage execution

def get_reference_image_path(ctx: PipelineContext):
    if ctx.reference_image_path:
        return ctx.reference_image_path
    else:
        user_inputs = ctx.original_pipeline_data.get('user_inputs')
        image_reference = user_inputs.get('image_reference')
        if image_reference:
            return image_reference['saved_image_path_in_run_dir']

def get_image_ctx_and_main_object(ctx: PipelineContext):
    processing_ctx = ctx.original_pipeline_data.get('processing_context')
    
    # Get Image Prompts Context
    image_prompts = processing_ctx.get('generated_image_prompts')
    
    # For chain refinements, generation_index might be None
    if ctx.generation_index is not None:
        image_ctx_json = image_prompts[ctx.generation_index]
    else:
        # For chain refinements, use the first available prompt context as fallback
        # or try to infer from the parent image context
        image_ctx_json = image_prompts[0] if image_prompts else {}
        ctx.log("Using fallback image context for chain refinement")
    
    # Get Main Object from Image Analysis Result
    image_analysis_result = processing_ctx.get('image_analysis_result')
    analysis_main_obj = image_analysis_result.get('main_subject')

    main_obj = image_ctx_json.get('main_subject')
    if not main_obj:
        if analysis_main_obj:
            ctx.log(f"Setting main object from image analysis: {analysis_main_obj}")
            main_obj = analysis_main_obj
    else:
        ctx.log(f"Main object identified: {main_obj}")
    return image_ctx_json, main_obj

def validate_refinement_inputs(ctx: PipelineContext, refinement_type: str) -> None:
    """Common input validation for all refinement stages."""
    
    if not ctx.base_image_path or not os.path.exists(ctx.base_image_path):
        raise ValueError("Base image path is required and must exist")
    
    if ctx.refinement_type != refinement_type:
        raise ValueError(f"Invalid refinement type for {refinement_type} refinement: {ctx.refinement_type}")


def load_and_prepare_image(ctx: PipelineContext, type: str) -> Image.Image:
    """Load and validate the base image for refinement processing."""
    
    try:
        if type=='base':
            image = Image.open(ctx.base_image_path)
            ctx.log(f"Loaded base image: {image.size} {image.mode}")
        elif type=='reference':
            image = Image.open(ctx.reference_image_path)
            ctx.log(f"Loaded reference image: {image.size} {image.mode}")
        
        # Ensure RGB mode for processing
        if image.mode != 'RGB':
            image = image.convert('RGB')
            ctx.log("Converted image to RGB mode")
        
        return image
        
    except Exception as e:
        raise ValueError(f"Failed to load base image: {e}")


def determine_api_image_size(original_size: Tuple[int, int]) -> str:
    """
    Determine the appropriate OpenAI API size parameter based on original image dimensions.
    OpenAI images.edit API supports: '1024x1024', '1024x1536', '1536x1024', and 'auto'.
    """
    
    width, height = original_size
    aspect_ratio = width / height
    
    if abs(aspect_ratio - 1.0) < 0.1:  # Square-ish
        return "1024x1024"
    elif aspect_ratio > 1.2:  # Landscape
        return "1536x1024"
    else:  # Portrait
        return "1024x1536"


class RefinementError(Exception):
    """Custom exception for refinement-specific errors with detailed context."""
    def __init__(self, error_type: str, message: str, suggestion: str = None, is_retryable: bool = False):
        self.error_type = error_type
        self.message = message
        self.suggestion = suggestion
        self.is_retryable = is_retryable
        super().__init__(message)


async def call_openai_images_edit(
    ctx: PipelineContext,
    enhanced_prompt: str,
    image_size: str,
    mask_path: Optional[str] = None,
    image_gen_client: Optional[OpenAI] = None
) -> str:
    """
    Common OpenAI images.edit API call with enhanced error handling and classification.
    Returns the path to the saved result image or raises RefinementError with detailed context.
    """    
    
    # Use global model ID (same pattern as image_generation.py)
    model_id = IMAGE_GENERATION_MODEL_ID or "gpt-image-1"
    
    operation_type = "regional editing" if mask_path else "global editing"
    ctx.log(f"Calling OpenAI Images Edit API ({model_id})")
    ctx.log(f"Operation: {operation_type}, Size: {image_size}")
    if mask_path:
        ctx.log("Using mask for regional editing")
    
    try:
        # Prepare API call parameters
        api_params = {
            "model": model_id,
            "prompt": enhanced_prompt,
            "n": 1,
            "size": image_size,
        }
        
        # Call OpenAI images.edit API
        if mask_path:
            # Regional editing with mask
            response = await asyncio.to_thread(
                image_gen_client.images.edit,
                image=[
                    open(ctx.base_image_path, "rb"),
                    open(ctx.reference_image_path, "rb")
                ] if ctx.reference_image_path else [
                    open(ctx.base_image_path, "rb")
                ],
                mask=open(mask_path, "rb"),
                **api_params
            )
        else:
            # Global editing without mask
            if ctx.reference_image_path:
                image_list = [
                    open(ctx.base_image_path, "rb"),
                    open(ctx.reference_image_path, "rb")
                ]
            else:
                image_list = [
                    open(ctx.base_image_path, "rb")
                ]
            print(f"Image List Length for API Image Edit Call: {len(image_list)}")
            response = await asyncio.to_thread(
                image_gen_client.images.edit,
                image=image_list,
                **api_params
            )
        
        # Process API response with enhanced error detection
        if not response:
            raise RefinementError(
                "api_no_response", 
                "OpenAI API returned empty response",
                "This usually indicates a temporary service issue. Please try again.",
                is_retryable=True
            )
            
        if not response.data or len(response.data) == 0:
            raise RefinementError(
                "api_empty_data", 
                "OpenAI API returned no image data",
                "The API processed the request but didn't generate any images. Try adjusting your prompt or reference image.",
                is_retryable=True
            )
            
        image_data = response.data[0]
        
        if not hasattr(image_data, 'b64_json') or not image_data.b64_json:
            raise RefinementError(
                "api_no_image_data", 
                "OpenAI API response missing image data",
                "The API responded but didn't include the generated image. This may indicate the request was filtered or rejected.",
                is_retryable=True
            )
        
        # Calculate size for logging without exposing data
        b64_size = len(image_data.b64_json)
        data_size_mb = b64_size / (1024 * 1024)
        ctx.log(f"API call successful (received {data_size_mb:.2f}MB image data)")
        
        # Decode and save the result image
        try:
            image_bytes = base64.b64decode(image_data.b64_json)
            if len(image_bytes) < 1000:  # Very small file, likely corrupt
                raise RefinementError(
                    "invalid_image_data", 
                    "Generated image data appears to be corrupted",
                    "The API returned image data but it appears invalid. Please try again.",
                    is_retryable=True
                )
            output_path = save_refinement_result(ctx, image_bytes)
            return output_path
        except Exception as decode_error:
            raise RefinementError(
                "image_decode_error", 
                f"Failed to decode generated image: {str(decode_error)}",
                "The API returned image data but it couldn't be processed. Please try again.",
                is_retryable=True
            )
            
    except RefinementError:
        # Re-raise our custom errors as-is
        raise
    except Exception as e:
        # Handle specific OpenAI exceptions with enhanced error messages
        error_type = type(e).__name__
        ctx.log(f"API error ({error_type}): {str(e)}")
        
        if "APIConnectionError" in error_type:
            raise RefinementError(
                "connection_error", 
                "Unable to connect to OpenAI API",
                "Check your internet connection and try again. If the problem persists, OpenAI services may be temporarily unavailable.",
                is_retryable=True
            )
        elif "RateLimitError" in error_type:
            raise RefinementError(
                "rate_limit", 
                "OpenAI API rate limit exceeded",
                "You've made too many requests. Please wait a moment and try again.",
                is_retryable=True
            )
        elif "APIStatusError" in error_type:
            status_code = getattr(e, 'status_code', 'unknown')
            error_message = f"OpenAI API error (status {status_code})"
            suggestion = "Please try again. If the problem persists, check your API usage or contact support."
            
            try:
                if hasattr(e, 'response') and e.response:
                    error_details = e.response.json()
                    if 'error' in error_details and 'message' in error_details['error']:
                        api_message = error_details['error']['message']
                        error_message = f"OpenAI API error: {api_message}"
                        
                        # Provide specific suggestions based on common error messages
                        if "content policy" in api_message.lower():
                            suggestion = "Your image or prompt may violate OpenAI's content policy. Try using different instructions or a different reference image."
                        elif "invalid" in api_message.lower() and "image" in api_message.lower():
                            suggestion = "The image format may not be supported. Please try with a different image file."
                        elif "too large" in api_message.lower():
                            suggestion = "Your image file is too large. Please resize it and try again."
            except:
                pass
                
            raise RefinementError(
                "api_error", 
                error_message,
                suggestion,
                is_retryable=status_code != 400  # Don't retry client errors
            )
        elif "AuthenticationError" in error_type:
            raise RefinementError(
                "auth_error", 
                "OpenAI API authentication failed",
                "There's an issue with the API credentials. Please contact support.",
                is_retryable=False
            )
        else:
            ctx.log(f"Unexpected error details: {traceback.format_exc()}")
            raise RefinementError(
                "unexpected_error", 
                f"Unexpected error during image processing: {str(e)}",
                "An unexpected error occurred. Please try again, and if the problem persists, contact support.",
                is_retryable=True
            )


def save_refinement_result(ctx: PipelineContext, image_bytes: bytes) -> str:
    """
    Save refinement result using hybrid approach:
    1. Create dedicated refinement directory with rich metadata
    2. Save output image, reference image, and metadata.json
    3. Return path for backward compatibility with centralized index
    """
    
    # Create refinement-specific directory
    refinement_dir = Path(f"./data/runs/{ctx.parent_run_id}/refinements/{ctx.run_id}")
    refinement_dir.mkdir(parents=True, exist_ok=True)
    
    # Save output image
    output_path = refinement_dir / "output.png"
    try:
        with open(output_path, "wb") as f:
            f.write(image_bytes)
        ctx.log(f"Saved refinement output: {output_path}")
    except Exception as e:
        raise RuntimeError(f"Failed to save refinement output: {e}")
    
    # Check if reference image already exists in job directory (hybrid structure)
    # With the new API structure, reference images are already saved directly to job directories
    if hasattr(ctx, 'reference_image_path') and ctx.reference_image_path and os.path.exists(ctx.reference_image_path):
        reference_source = Path(ctx.reference_image_path)
        # Check if the reference image is already in the correct job directory
        if str(refinement_dir) in str(reference_source):
            ctx.log("Reference image already in correct location")
        else:
            # Copy reference image to preserve it (legacy behavior)
            try:
                # Preserve original file extension
                original_extension = reference_source.suffix or ".png"
                reference_dest = refinement_dir / f"reference{original_extension}"
                shutil.copy2(ctx.reference_image_path, reference_dest)
                ctx.log("Preserved reference image")
            except Exception as e:
                ctx.log(f"Warning: Could not preserve reference image: {e}")
    
    # Save rich metadata
    _save_refinement_metadata(ctx, refinement_dir)
    
    # For backward compatibility, also save in old flat structure
    # This ensures the centralized index still works
    legacy_dir = Path(f"./data/runs/{ctx.parent_run_id}/refinements")
    legacy_dir.mkdir(parents=True, exist_ok=True)
    
    parent_id = ctx.parent_image_id
    if ctx.parent_image_type == "original":
        parent_id = f"{ctx.generation_index}"
    
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')
    legacy_filename = f"{ctx.run_id}_from_{parent_id}_{timestamp}.png"
    legacy_path = legacy_dir / legacy_filename
    
    # Create symlink or copy for backward compatibility
    try:
        if hasattr(os, 'symlink'):
            # Use relative symlink if possible
            relative_output = os.path.relpath(output_path, legacy_dir)
            os.symlink(relative_output, legacy_path)
            ctx.log("Created legacy compatibility symlink")
        else:
            # Fallback to copy on systems without symlink support
            shutil.copy2(output_path, legacy_path)
            ctx.log("Created legacy compatibility copy")
    except Exception as e:
        ctx.log(f"Warning: Could not create legacy compatibility file: {e}")
        # Return the new path if legacy creation fails
        return str(output_path)
    
    # Return legacy path for backward compatibility with existing code
    return str(legacy_path)


def _check_reference_image_exists(refinement_dir: Path) -> bool:
    """Check if any reference image exists in the refinement directory."""
    reference_patterns = ["reference.*"]
    for pattern in reference_patterns:
        if list(refinement_dir.glob(pattern)):
            return True
    return False


def _get_reference_image_filename(refinement_dir: Path) -> Optional[str]:
    """Get the filename of the reference image in the refinement directory."""
    reference_patterns = ["reference.*"]
    for pattern in reference_patterns:
        matches = list(refinement_dir.glob(pattern))
        if matches:
            return matches[0].name
    return None


def _save_refinement_metadata(ctx: PipelineContext, refinement_dir: Path) -> None:
    """Save rich metadata for the refinement in JSON format."""
    
    metadata = {
        "refinement_info": {
            "job_id": ctx.run_id,
            "parent_run_id": ctx.parent_run_id,
            "parent_image_id": ctx.parent_image_id,
            "parent_image_type": ctx.parent_image_type,
            "generation_index": ctx.generation_index,
            "refinement_type": ctx.refinement_type,
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        },
        "inputs": {
            "instructions": getattr(ctx, 'instructions', None),
            "prompt": getattr(ctx, 'prompt', None),
            "mask_coordinates": getattr(ctx, 'mask_coordinates', None),  # Legacy
            "mask_file_path": getattr(ctx, 'mask_file_path', None),  # New approach
            "creativity_level": getattr(ctx, 'creativity_level', None),
        },
        "processing": {
            "model_used": IMAGE_GENERATION_MODEL_ID or "gpt-image-1",
            "api_image_size": getattr(ctx, '_api_image_size', None),
            "operation_type": "global_editing",  # Could be enhanced to track regional
        },
        "results": {
            "status": (getattr(ctx, 'refinement_result', None) or {}).get('status', 'in_progress'),
            "output_generated": os.path.exists(refinement_dir / "output.png"),
            "reference_preserved": _check_reference_image_exists(refinement_dir),
            "modifications": (getattr(ctx, 'refinement_result', None) or {}).get('modifications', {}),
        },
        "costs": {
            "refinement_cost_usd": getattr(ctx, 'refinement_cost', 0.0),
            "model_pricing_used": MODEL_PRICING.get(IMAGE_GENERATION_MODEL_ID or "gpt-image-1", {}),
        },
        "images": {
            "base_image_metadata": getattr(ctx, 'base_image_metadata', {}),
            "output_path": "output.png",
            "reference_path": _get_reference_image_filename(refinement_dir),
        },
        "context": {
            "original_pipeline_data": getattr(ctx, 'original_pipeline_data', {}),
            "pipeline_mode": getattr(ctx, 'pipeline_mode', 'refinement'),
        }
    }
    
    # Save metadata
    metadata_path = refinement_dir / "metadata.json"
    try:
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2, default=str)
        ctx.log("Saved refinement metadata")
    except Exception as e:
        ctx.log(f"Warning: Could not save refinement metadata: {e}")


def save_temporary_mask(ctx: PipelineContext, mask: Image.Image) -> str:
    """Save mask temporarily for API call, with automatic cleanup tracking."""
    
    temp_dir = Path(f"./data/runs/{ctx.parent_run_id}/temp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')
    mask_filename = f"temp_mask_{ctx.run_id}_{timestamp}.png"
    mask_path = temp_dir / mask_filename
    
    # Save mask as PNG
    mask.save(mask_path, format='PNG')
    ctx.log("Saved temporary mask file")
    
    # Track for cleanup
    if not hasattr(ctx, 'temp_files'):
        ctx.temp_files = []
    ctx.temp_files.append(str(mask_path))
    
    return str(mask_path)


def cleanup_temporary_files(temp_file_paths: list) -> None:
    """Clean up temporary files with error handling."""
    
    for temp_path in temp_file_paths:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
                # Use print for cleanup as ctx is not available
                print(f"Cleaned up temporary file: {os.path.basename(temp_path)}")
            except Exception as e:
                print(f"Warning: Could not clean up temporary file {os.path.basename(temp_path)}: {e}")


def calculate_refinement_cost(
    ctx: PipelineContext, 
    prompt_text: str,
    has_mask: bool = False,
    refinement_type: str = "general"
) -> float:
    """
    Calculate refinement cost using the centralized TokenCostManager.
    Uses actual OpenAI pricing from constants.py.
    """
    
    # Get model pricing from constants
    model_id = IMAGE_GENERATION_MODEL_ID or "gpt-image-1"
    pricing = MODEL_PRICING.get(model_id, {})
    
    if not pricing:
        ctx.log(f"Warning: No pricing found for model {model_id}, using fallback")
        # Fallback pricing (approximate DALL-E costs)
        base_cost = 0.020  # $0.020 for 1024x1024
    else:
        # Use actual pricing from constants
        token_counts = pricing.get("token_counts_by_quality", {})
        medium_quality = token_counts.get("medium", {})
        
        # Determine image size
        image_size = "1024x1024"  # Default
        try:
            if ctx.base_image_metadata:
                width = ctx.base_image_metadata.get("width", 1024)
                height = ctx.base_image_metadata.get("height", 1024)
                if max(width, height) > 1024:
                    image_size = "1024x1536" if width < height else "1536x1024"
        except:
            pass
        
        # Calculate based on token costs
        output_tokens = medium_quality.get(image_size, 1056)  # Default to 1024x1024 medium
        output_cost_per_mtok = pricing.get("output_image_cost_per_mtok", 40.0)
        base_cost = (output_tokens / 1_000_000) * output_cost_per_mtok
    
    # Regional editing might have slight overhead
    if has_mask:
        base_cost *= 1.05  # 5% overhead for mask processing
    
    total_cost = base_cost
    
    operation_type = "regional" if has_mask else "global"
    ctx.log(f"Estimated {refinement_type} cost: ${total_cost:.3f} ({operation_type} edit)")
    return total_cost


def track_refinement_cost(
    ctx: PipelineContext,
    stage_name: str,
    prompt_text: str,
    duration_seconds: float = 5.0
) -> None:
    """
    Track detailed cost information using the established CostDetail pattern.
    Integrates with existing cost tracking in the pipeline.
    """
    
    try:
        # Estimate prompt tokens (simple word count estimation)
        prompt_tokens = len(prompt_text.split()) if prompt_text else 0
        
        # Get model info from constants
        model_id = IMAGE_GENERATION_MODEL_ID or "gpt-image-1"
        
        cost_detail = CostDetail(
            stage_name=stage_name,
            model_id=model_id,
            provider="OpenAI",
            duration_seconds=duration_seconds,
            input_tokens=prompt_tokens,
            output_tokens=0,  # Image generation doesn't have output tokens
            images_generated=1,
            resolution="1024x1024",  # Default, could be dynamic
            quality="standard",
            image_cost_usd=ctx.refinement_cost or 0.0,
            total_stage_cost_usd=ctx.refinement_cost or 0.0,
            cost_calculation_notes=f"{stage_name} using OpenAI images.edit API"
        )
        
        # Add to context cost summary (same pattern as save_outputs.py)
        if ctx.cost_summary and 'stage_costs' in ctx.cost_summary:
            ctx.cost_summary['stage_costs'].append(cost_detail.model_dump())
            
    except Exception as e:
        ctx.log(f"Warning: Could not track cost for {stage_name} stage: {e}")


def create_mask_from_coordinates(
    mask_data: Dict[str, Any], 
    image_size: Tuple[int, int],
    base_run_dir: str
) -> Optional[str]:
    """
    Create a mask image from coordinate data for regional editing.
    Returns None for global editing, mask file path for regional editing.
    Supports the same coordinate formats as established in the plan.
    """
    
    if not mask_data:
        return None
    
    try:
        # Create blank mask (black = preserve, white = edit)
        mask = Image.new('L', image_size, 0)
        draw = ImageDraw.Draw(mask)
        
        width, height = image_size
        
        if mask_data.get('type') == 'rectangle' or ('x' in mask_data and 'y' in mask_data):
            # Handle both explicit rectangle type and coordinate object from frontend
            if 'x' in mask_data and 'y' in mask_data:
                # Frontend coordinate format: {x, y, width, height} (normalized 0-1)
                x1 = int(mask_data['x'] * width)
                y1 = int(mask_data['y'] * height)
                x2 = int((mask_data['x'] + mask_data['width']) * width)
                y2 = int((mask_data['y'] + mask_data['height']) * height)
            else:
                # Legacy format: {x1, y1, x2, y2}
                x1 = int(mask_data['x1'] * width)
                y1 = int(mask_data['y1'] * height)
                x2 = int(mask_data['x2'] * width)
                y2 = int(mask_data['y2'] * height)
            
            draw.rectangle([x1, y1, x2, y2], fill=255)
            
        elif mask_data.get('type') == 'circle':
            # Convert normalized coordinates to pixels
            cx = int(mask_data['cx'] * width)
            cy = int(mask_data['cy'] * height)
            radius = int(mask_data['radius'] * min(width, height))
            
            draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=255)
            
        elif mask_data.get('type') == 'polygon':
            # Convert normalized coordinates to pixels
            points = []
            for point in mask_data['points']:
                x = int(point[0] * width)
                y = int(point[1] * height)
                points.append((x, y))
            
            draw.polygon(points, fill=255)
            
        else:
            # Use ctx.log if available, otherwise fallback to print
            try:
                ctx.log(f"Warning: Unsupported mask type: {mask_data.get('type')}")
            except:
                print(f"Warning: Unsupported mask type: {mask_data.get('type')}")
            return None
        
        # Save mask to temporary file
        temp_dir = Path(base_run_dir) / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')
        mask_filename = f"temp_mask_{timestamp}.png"
        mask_path = temp_dir / mask_filename
        
        mask.save(mask_path, format='PNG')
        return str(mask_path)
        
    except Exception as e:
        # Use ctx.log if available, otherwise fallback to print
        try:
            ctx.log(f"Warning: Failed to create mask from coordinates: {e}")
        except:
            print(f"Warning: Failed to create mask from coordinates: {e}")
        return None 