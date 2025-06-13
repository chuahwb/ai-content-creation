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
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from PIL import Image, ImageDraw

from ..pipeline.context import PipelineContext
from ..core.constants import IMAGE_GENERATION_MODEL_ID, MODEL_PRICING
from ..core.token_cost_manager import TokenCostManager, TokenUsage, CostBreakdown
from ..models import CostDetail

# Global variables for API clients and configuration (injected by pipeline executor)
# These will be set by the pipeline executor before stage execution
image_gen_client = None


def validate_refinement_inputs(ctx: PipelineContext, refinement_type: str) -> None:
    """Common input validation for all refinement stages."""
    
    # Import the client reference from image_generation stage for consistency
    from . import image_generation
    
    if not image_generation.image_gen_client:
        raise ValueError("Image generation client not configured")
    
    if not ctx.base_image_path or not os.path.exists(ctx.base_image_path):
        raise ValueError("Base image path is required and must exist")
    
    if ctx.refinement_type != refinement_type:
        raise ValueError(f"Invalid refinement type for {refinement_type} refinement: {ctx.refinement_type}")


def load_and_prepare_image(ctx: PipelineContext) -> Image.Image:
    """Load and validate the base image for refinement processing."""
    
    try:
        image = Image.open(ctx.base_image_path)
        ctx.log(f"Loaded base image: {image.size} {image.mode}")
        
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
    Uses the same logic as image_generation.py for consistency.
    """
    
    width, height = original_size
    aspect_ratio = width / height
    
    if abs(aspect_ratio - 1.0) < 0.1:  # Square-ish
        return "1024x1024"
    elif aspect_ratio > 1.2:  # Landscape
        return "1792x1024"
    else:  # Portrait
        return "1024x1792"


async def call_openai_images_edit(
    ctx: PipelineContext,
    enhanced_prompt: str,
    image_size: str,
    mask_path: Optional[str] = None
) -> str:
    """
    Common OpenAI images.edit API call with standardized error handling.
    Returns the path to the saved result image.
    """
    
    # Import the client reference for consistency with existing patterns
    from . import image_generation
    
    # Use global model ID (same pattern as image_generation.py)
    model_id = IMAGE_GENERATION_MODEL_ID or "gpt-image-1"
    
    operation_type = "regional editing" if mask_path else "global editing"
    ctx.log(f"--- Calling OpenAI Images Edit API ({model_id}) ---")
    ctx.log(f"   Base Image: {ctx.base_image_path}")
    ctx.log(f"   Enhanced Prompt: {enhanced_prompt}")
    ctx.log(f"   Size: {image_size}")
    if mask_path:
        ctx.log(f"   Mask Image: {mask_path}")
    
    try:
        # Prepare API call parameters
        api_params = {
            "model": model_id,
            "prompt": enhanced_prompt,
            "n": 1,
            "size": image_size,
            "response_format": "b64_json"
        }
        
        # Call OpenAI images.edit API
        if mask_path:
            # Regional editing with mask
            with open(ctx.base_image_path, "rb") as image_file, open(mask_path, "rb") as mask_file:
                response = await asyncio.to_thread(
                    image_generation.image_gen_client.images.edit,
                    image=image_file,
                    mask=mask_file,
                    **api_params
                )
        else:
            # Global editing without mask
            with open(ctx.base_image_path, "rb") as image_file:
                response = await asyncio.to_thread(
                    image_generation.image_gen_client.images.edit,
                    image=image_file,
                    **api_params
                )
        
        # Process API response (same pattern as image_generation.py)
        if response and response.data and len(response.data) > 0:
            image_data = response.data[0]
            
            if image_data.b64_json:
                ctx.log(f"✅ {operation_type.title()} successful (received base64 data)")
                
                # Decode and save the result image
                image_bytes = base64.b64decode(image_data.b64_json)
                output_path = save_refinement_result(ctx, image_bytes)
                
                return output_path
            else:
                raise RuntimeError("API response missing base64 image data")
        else:
            raise RuntimeError("API response did not contain expected data structure")
            
    except Exception as e:
        # Handle specific OpenAI exceptions (same pattern as image_generation.py)
        error_type = type(e).__name__
        if "APIConnectionError" in error_type:
            ctx.log(f"❌ ERROR: API connection error: {e}")
            raise RuntimeError(f"Connection error: {e}")
        elif "RateLimitError" in error_type:
            ctx.log(f"❌ ERROR: API rate limit exceeded: {e}")
            raise RuntimeError(f"Rate limit error: {e}")
        elif "APIStatusError" in error_type:
            ctx.log(f"❌ ERROR: API status error: {e}")
            error_message = f"API status error"
            try:
                if hasattr(e, 'status_code') and hasattr(e, 'response'):
                    error_message = f"API status error {e.status_code}"
                    error_details = e.response.json()
                    if 'error' in error_details and 'message' in error_details['error']:
                        error_message += f": {error_details['error']['message']}"
            except:
                pass
            raise RuntimeError(error_message)
        else:
            ctx.log(f"❌ ERROR: Unexpected error during {operation_type}: {e}")
            ctx.log(traceback.format_exc())
            raise RuntimeError(f"Unexpected error: {e}")


def save_refinement_result(ctx: PipelineContext, image_bytes: bytes) -> str:
    """
    Save refinement result image with consistent naming and organization.
    Uses the same patterns as established in save_outputs.py.
    """
    
    # Create output directory (same pattern as established)
    output_dir = Path(f"./data/runs/{ctx.parent_run_id}/refinements")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate filename with consistent pattern
    parent_id = ctx.parent_image_id
    if ctx.parent_image_type == "original":
        parent_id = f"{ctx.generation_index}"
    
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')
    filename = f"{ctx.run_id}_from_{parent_id}_{timestamp}.png"
    output_path = output_dir / filename
    
    # Save image
    try:
        with open(output_path, "wb") as f:
            f.write(image_bytes)
        ctx.log(f"Saved result image: {output_path}")
        return str(output_path)
        
    except Exception as e:
        raise RuntimeError(f"Failed to save result image: {e}")


def save_temporary_mask(ctx: PipelineContext, mask: Image.Image) -> str:
    """Save mask temporarily for API call, with automatic cleanup tracking."""
    
    temp_dir = Path(f"./data/runs/{ctx.parent_run_id}/temp")
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.datetime.now().strftime('%Y%m%d%H%M%S%f')
    mask_filename = f"temp_mask_{ctx.run_id}_{timestamp}.png"
    mask_path = temp_dir / mask_filename
    
    # Save mask as PNG
    mask.save(mask_path, format='PNG')
    ctx.log(f"Saved temporary mask: {mask_path}")
    
    # Track for cleanup
    if not hasattr(ctx, 'temp_files'):
        ctx.temp_files = []
    ctx.temp_files.append(str(mask_path))
    
    return str(mask_path)


def cleanup_temporary_files(temp_file_paths: list, ctx: PipelineContext) -> None:
    """Clean up temporary files with error handling."""
    
    for temp_path in temp_file_paths:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
                ctx.log(f"Cleaned up temporary file: {temp_path}")
            except Exception as e:
                ctx.log(f"Warning: Could not clean up temporary file {temp_path}: {e}")


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
    
    # Adjust based on creativity level
    creativity_multiplier = {1: 0.9, 2: 1.0, 3: 1.2}
    total_cost = base_cost * creativity_multiplier.get(ctx.creativity_level, 1.0)
    
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


def enhance_prompt_with_creativity_guidance(
    base_prompt: str,
    creativity_level: int,
    refinement_type: str
) -> str:
    """
    Enhance prompts with creativity level guidance specific to refinement type.
    Centralizes prompt enhancement logic to maintain consistency.
    """
    
    # Type-specific guidance
    type_guidance = {
        "subject": {
            1: "Make subtle, conservative changes that blend naturally with the existing image style.",
            2: "Apply moderate modifications while maintaining visual coherence with the original image.",
            3: "Make creative, bold modifications while ensuring the result looks professional and polished."
        },
        "text": {
            1: "Make minimal changes to fix obvious errors while maintaining the original text style and layout.",
            2: "Apply moderate improvements to text clarity, spelling, and readability while keeping the design aesthetic.",
            3: "Make comprehensive text improvements including style enhancements, better typography, and optimized layout for maximum impact."
        },
        "prompt": {
            1: "Apply subtle, conservative changes that blend naturally with the existing image style.",
            2: "Apply moderate adjustments while maintaining visual coherence.",
            3: "Apply creative, bold modifications while ensuring professional results."
        }
    }
    
    guidance = type_guidance.get(refinement_type, type_guidance["prompt"])
    creativity_text = guidance.get(creativity_level, guidance[2])
    
    enhanced_prompt = f"{base_prompt}. {creativity_text}"
    enhanced_prompt += " Ensure high quality, professional results with proper lighting and seamless integration."
    
    return enhanced_prompt


def create_mask_from_coordinates(
    ctx: PipelineContext, 
    image_size: Tuple[int, int]
) -> Optional[Image.Image]:
    """
    Create a mask image from coordinate data for regional editing.
    Returns None for global editing, mask Image for regional editing.
    Supports the same coordinate formats as established in the plan.
    """
    
    if not ctx.mask_coordinates:
        ctx.log("No mask coordinates provided, performing global refinement")
        return None
    
    try:
        # Parse mask coordinates
        mask_data = json.loads(ctx.mask_coordinates) if isinstance(ctx.mask_coordinates, str) else ctx.mask_coordinates
        ctx.log(f"Creating mask from coordinates: {mask_data.get('type', 'unknown')}")
        
        # Create blank mask (black = preserve, white = edit)
        mask = Image.new('L', image_size, 0)
        draw = ImageDraw.Draw(mask)
        
        width, height = image_size
        
        if mask_data.get('type') == 'rectangle':
            # Convert normalized coordinates to pixels
            x1 = int(mask_data['x1'] * width)
            y1 = int(mask_data['y1'] * height)
            x2 = int(mask_data['x2'] * width)
            y2 = int(mask_data['y2'] * height)
            
            draw.rectangle([x1, y1, x2, y2], fill=255)
            ctx.log(f"Created rectangular mask: ({x1}, {y1}) to ({x2}, {y2})")
            
        elif mask_data.get('type') == 'circle':
            # Convert normalized coordinates to pixels
            cx = int(mask_data['cx'] * width)
            cy = int(mask_data['cy'] * height)
            radius = int(mask_data['radius'] * min(width, height))
            
            draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=255)
            ctx.log(f"Created circular mask: center ({cx}, {cy}), radius {radius}")
            
        elif mask_data.get('type') == 'polygon':
            # Convert normalized coordinates to pixels
            points = []
            for point in mask_data['points']:
                x = int(point[0] * width)
                y = int(point[1] * height)
                points.append((x, y))
            
            draw.polygon(points, fill=255)
            ctx.log(f"Created polygon mask with {len(points)} points")
            
        else:
            ctx.log(f"Warning: Unsupported mask type: {mask_data.get('type')}")
            return None
        
        return mask
        
    except Exception as e:
        ctx.log(f"Warning: Failed to create mask from coordinates: {e}")
        return None 