"""
Prompt Refine Stage - Refinement Pipeline

This stage performs prompt-based image refinement with optional masking.
Uses OpenAI's gpt-image-1 model via the images.edit API for both global and regional editing.
Leverages shared refinement utilities for consistency and code reuse.
"""

import os
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

from ..pipeline.context import PipelineContext
from .refinement_utils import (
    validate_refinement_inputs,
    load_and_prepare_image,
    determine_api_image_size,
    call_openai_images_edit,
    calculate_refinement_cost,
    track_refinement_cost,
    enhance_prompt_with_creativity_guidance,
    create_mask_from_coordinates,
    save_temporary_mask,
    cleanup_temporary_files
)

# Global variables for API clients are handled by refinement_utils and image_generation.py


def run(ctx: PipelineContext) -> None:
    """
    Perform prompt-based image refinement with optional masking.
    
    REQUIRED CONTEXT INPUTS:
    - ctx.base_image_path: Path to the base image to modify
    - ctx.prompt: User refinement prompt
    - ctx.refinement_type: Should be "prompt"
    - ctx.creativity_level: 1-3 for modification intensity
    - ctx.mask_coordinates: Optional mask coordinates for regional editing
    - ctx.original_pipeline_data: Original generation metadata for context
    
    SETS CONTEXT OUTPUTS:
    - ctx.refinement_result: Dict with result information
    - ctx.refinement_cost: Cost of the operation
    """
    
    ctx.log("Starting prompt refinement stage...")
    
    # Validate required inputs using shared utility
    validate_refinement_inputs(ctx, "prompt")
    
    # Additional validation specific to prompt refinement
    _validate_prompt_refinement_inputs(ctx)
    
    # Load and prepare base image using shared utility
    base_image = load_and_prepare_image(ctx)
    
    # Parse and create mask if provided using shared utility
    mask = create_mask_from_coordinates(ctx, base_image.size)
    
    # Perform actual prompt refinement using OpenAI API
    result_image_path = asyncio.run(_perform_prompt_refinement_api(ctx, base_image, mask))
    
    # Update context with results
    ctx.refinement_result = {
        "type": "prompt_refinement",
        "status": "completed",
        "output_path": result_image_path,
        "modifications": {
            "prompt_used": ctx.prompt,
            "mask_applied": mask is not None,
            "regional_edit": mask is not None,
            "creativity_level": ctx.creativity_level
        }
    }
    
    # Calculate and track costs using shared utilities
    ctx.refinement_cost = calculate_refinement_cost(
        ctx, 
        ctx.prompt or "", 
        has_mask=mask is not None,
        refinement_type="prompt refinement"
    )
    track_refinement_cost(ctx, "prompt_refine", ctx.prompt or "", duration_seconds=8.0)
    
    ctx.log(f"Prompt refinement completed: {result_image_path}")


def _validate_prompt_refinement_inputs(ctx: PipelineContext) -> None:
    """Validate inputs specific to prompt refinement (beyond common validation)."""
    
    if not ctx.prompt:
        raise ValueError("Refinement prompt is required for prompt refinement")


async def _perform_prompt_refinement_api(ctx: PipelineContext, base_image, mask: Optional) -> str:
    """
    Perform prompt refinement using OpenAI's images.edit API.
    Uses shared utilities for consistency with other refinement stages.
    Supports both global and regional editing with mask.
    """
    
    operation_type = "regional editing" if mask else "global refinement"
    from ..core.constants import IMAGE_GENERATION_MODEL_ID
    ctx.log(f"Performing {operation_type} using {IMAGE_GENERATION_MODEL_ID or 'gpt-image-1'}...")
    ctx.log(f"Prompt: {ctx.prompt}")
    ctx.log(f"Creativity level: {ctx.creativity_level}")
    
    # Prepare enhanced prompt using shared utility
    enhanced_prompt = _prepare_refinement_prompt(ctx)
    
    # Determine image size using shared utility
    image_size = determine_api_image_size(base_image.size)
    
    # Save mask temporarily if needed
    mask_path = None
    temp_files = []
    
    try:
        if mask:
            mask_path = save_temporary_mask(ctx, mask)
            temp_files.append(mask_path)
        
        # Call OpenAI API using shared utility
        result_image_path = await call_openai_images_edit(
            ctx=ctx,
            enhanced_prompt=enhanced_prompt,
            image_size=image_size,
            mask_path=mask_path
        )
        
        return result_image_path
        
    finally:
        # Clean up temporary files using shared utility
        if temp_files:
            cleanup_temporary_files(temp_files, ctx)


def _prepare_refinement_prompt(ctx: PipelineContext) -> str:
    """
    Prepare the refinement prompt with additional context from original generation.
    Uses shared utilities and adds context-specific enhancements.
    """
    
    base_prompt = ctx.prompt
    
    # Add context from original generation if available
    if ctx.original_pipeline_data:
        processing_context = ctx.original_pipeline_data.get("processing_context", {})
        
        # Extract style guidance
        style_guidance = processing_context.get("style_guidance_sets", [])
        if style_guidance:
            style_keywords = []
            for guidance in style_guidance:
                if isinstance(guidance, dict) and "style_keywords" in guidance:
                    style_keywords.extend(guidance["style_keywords"])
            
            if style_keywords:
                style_context = f", maintaining {', '.join(style_keywords[:3])} style"
                base_prompt += style_context
        
        # Extract marketing context
        strategies = processing_context.get("suggested_marketing_strategies", [])
        if strategies and len(strategies) > 0:
            strategy = strategies[0]  # Use first strategy
            if isinstance(strategy, dict):
                audience = strategy.get("target_audience", "")
                if audience:
                    base_prompt += f", appealing to {audience}"
    
    # Use shared utility for creativity guidance
    enhanced_prompt = enhance_prompt_with_creativity_guidance(
        base_prompt, 
        ctx.creativity_level, 
        "prompt"
    )
    
    ctx.log(f"Enhanced refinement prompt: {enhanced_prompt}")
    return enhanced_prompt 