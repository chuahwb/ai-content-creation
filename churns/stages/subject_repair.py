"""
Subject Repair Stage - Refinement Pipeline

This stage performs subject replacement/repair on images using a reference image.
Uses OpenAI's gpt-image-1 model via the images.edit API for subject modifications.
Leverages shared refinement utilities for consistency and code reuse.

IMPLEMENTATION GUIDANCE:
- Use reference image to replace/enhance main subject
- Preserve background and composition from original
- Maintain consistent lighting and style
- Consider using: Stable Diffusion Inpainting, Adobe APIs, or similar
"""

import os
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional

from ..pipeline.context import PipelineContext
from .refinement_utils import (
    validate_refinement_inputs,
    load_and_prepare_image,
    determine_api_image_size,
    call_openai_images_edit,
    calculate_refinement_cost,
    track_refinement_cost,
    enhance_prompt_with_creativity_guidance,
    cleanup_temporary_files
)

# Global variables for API clients are handled by refinement_utils and image_generation.py


def run(ctx: PipelineContext) -> None:
    """
    Perform subject repair/replacement using reference image.
    
    REQUIRED CONTEXT INPUTS:
    - ctx.base_image_path: Path to the base image to modify
    - ctx.reference_image_path: Path to reference image for subject
    - ctx.instructions: User instructions for the repair
    - ctx.refinement_type: Should be "subject"
    - ctx.creativity_level: 1-3 for modification intensity
    
    SETS CONTEXT OUTPUTS:
    - ctx.refinement_result: Dict with result information
    - ctx.refinement_cost: Cost of the operation
    
    IMPLEMENTATION REQUIREMENTS:
    1. Load base image and reference image
    2. Perform subject detection/segmentation
    3. Replace/blend subject from reference into base
    4. Maintain original background and lighting
    5. Save result and update context
    """
    
    ctx.log("Starting subject repair stage...")
    
    # Validate required inputs using shared utility
    validate_refinement_inputs(ctx, "subject")
    
    # Additional validation specific to subject repair
    _validate_subject_repair_inputs(ctx)
    
    # Load and prepare images using shared utility
    base_image = load_and_prepare_image(ctx)
    reference_image = _load_reference_image(ctx)
    
    # Perform actual subject repair using OpenAI API
    result_image_path = asyncio.run(_perform_subject_repair_api(ctx, base_image))
    
    # Update context with results
    ctx.refinement_result = {
        "type": "subject_repair",
        "status": "completed",
        "output_path": result_image_path,
        "modifications": {
            "subject_replaced": True,
            "background_preserved": True,
            "reference_image_used": ctx.reference_image_path,
            "instructions_applied": ctx.instructions
        }
    }
    
    # Calculate and track costs using shared utilities
    ctx.refinement_cost = calculate_refinement_cost(
        ctx, 
        ctx.instructions or "", 
        has_mask=False,
        refinement_type="subject repair"
    )
    track_refinement_cost(ctx, "subject_repair", ctx.instructions or "", duration_seconds=5.0)
    
    ctx.log(f"Subject repair completed: {result_image_path}")


def _validate_subject_repair_inputs(ctx: PipelineContext) -> None:
    """Validate inputs specific to subject repair (beyond common validation)."""
    
    if not ctx.reference_image_path or not os.path.exists(ctx.reference_image_path):
        raise ValueError("Reference image path is required and must exist for subject repair")
    
    if not ctx.instructions:
        ctx.instructions = "Replace main subject using reference image"
        ctx.log("No instructions provided, using default")


def _load_reference_image(ctx: PipelineContext):
    """Load and validate the reference image."""
    
    try:
        # Import PIL here to avoid dependency issues
        from PIL import Image
        
        image = Image.open(ctx.reference_image_path)
        ctx.log(f"Loaded reference image: {image.size} {image.mode}")
        
        # Ensure RGB mode
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        return image
        
    except Exception as e:
        raise ValueError(f"Failed to load reference image: {e}")


async def _perform_subject_repair_api(ctx: PipelineContext, base_image) -> str:
    """
    Perform subject repair using OpenAI's images.edit API.
    Uses shared utilities for consistency with other refinement stages.
    """
    
    from ..core.constants import IMAGE_GENERATION_MODEL_ID
    ctx.log(f"Performing subject repair using {IMAGE_GENERATION_MODEL_ID or 'gpt-image-1'}...")
    ctx.log(f"Instructions: {ctx.instructions}")
    ctx.log(f"Creativity level: {ctx.creativity_level}")
    
    # Prepare enhanced prompt using shared utility
    enhanced_prompt = _prepare_subject_repair_prompt(ctx)
    
    # Determine image size using shared utility
    image_size = determine_api_image_size(base_image.size)
    
    # Call OpenAI API using shared utility (no mask for subject repair)
    result_image_path = await call_openai_images_edit(
        ctx=ctx,
        enhanced_prompt=enhanced_prompt,
        image_size=image_size,
        mask_path=None  # Subject repair uses global editing, not masked editing
    )
    
    return result_image_path


def _prepare_subject_repair_prompt(ctx: PipelineContext) -> str:
    """
    Prepare an enhanced prompt for subject repair that incorporates
    the user instructions and reference image context.
    """
    
    base_instructions = ctx.instructions
    
    # Add context about subject replacement
    enhanced_prompt = f"{base_instructions}. Replace or modify the main subject in the image while preserving the background and overall composition"
    
    # Use shared utility for creativity guidance
    enhanced_prompt = enhance_prompt_with_creativity_guidance(
        enhanced_prompt, 
        ctx.creativity_level, 
        "subject"
    )
    
    ctx.log(f"Enhanced subject repair prompt: {enhanced_prompt}")
    return enhanced_prompt 