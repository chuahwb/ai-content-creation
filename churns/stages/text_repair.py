"""
Text Repair Stage - Refinement Pipeline

This stage performs text correction and enhancement on images.
Uses OpenAI's gpt-image-1 model via the images.edit API for text modifications.
Leverages shared refinement utilities for consistency and code reuse.

IMPLEMENTATION GUIDANCE:
- Extract and correct text elements in the image
- Regenerate text with proper fonts and styling
- Maintain original design aesthetic and layout
- Consider using: OCR + text generation/overlay APIs
"""

import os
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List

from ..pipeline.context import PipelineContext
from .refinement_utils import (
    validate_refinement_inputs,
    load_and_prepare_image,
    determine_api_image_size,
    call_openai_images_edit,
    calculate_refinement_cost,
    track_refinement_cost,
    enhance_prompt_with_creativity_guidance
)

# Global variables for API clients are handled by refinement_utils and image_generation.py


def run(ctx: PipelineContext) -> None:
    """
    Perform text repair and enhancement on the image.
    
    REQUIRED CONTEXT INPUTS:
    - ctx.base_image_path: Path to the base image to modify
    - ctx.instructions: User instructions for text repair
    - ctx.refinement_type: Should be "text"
    - ctx.creativity_level: 1-3 for text modification approach
    - ctx.original_pipeline_data: Original generation metadata for context
    
    SETS CONTEXT OUTPUTS:
    - ctx.refinement_result: Dict with result information
    - ctx.refinement_cost: Cost of the operation
    
    IMPLEMENTATION REQUIREMENTS:
    1. Extract existing text from image using OCR
    2. Identify text correction needs based on instructions
    3. Generate improved text elements
    4. Replace/overlay corrected text maintaining design
    5. Save result and update context
    """
    
    ctx.log("Starting text repair stage...")
    
    # Validate required inputs using shared utility
    validate_refinement_inputs(ctx, "text")
    
    # Additional validation specific to text repair
    _validate_text_repair_inputs(ctx)
    
    # Load and prepare base image using shared utility
    base_image = load_and_prepare_image(ctx)
    
    # Perform actual text repair using OpenAI API
    result_image_path = asyncio.run(_perform_text_repair_api(ctx, base_image))
    
    # Update context with results
    ctx.refinement_result = {
        "type": "text_repair",
        "status": "completed",
        "output_path": result_image_path,
        "modifications": {
            "text_corrected": True,
            "instructions_followed": ctx.instructions
        }
    }
    
    # Calculate and track costs using shared utilities
    ctx.refinement_cost = calculate_refinement_cost(
        ctx, 
        ctx.instructions or "", 
        has_mask=False,
        refinement_type="text repair"
    )
    track_refinement_cost(ctx, "text_repair", ctx.instructions or "", duration_seconds=3.0)
    
    ctx.log(f"Text repair completed: {result_image_path}")


def _validate_text_repair_inputs(ctx: PipelineContext) -> None:
    """Validate inputs specific to text repair (beyond common validation)."""
    
    if not ctx.instructions:
        ctx.instructions = "Fix and improve text elements in the image"
        ctx.log("No instructions provided, using default")


async def _perform_text_repair_api(ctx: PipelineContext, base_image) -> str:
    """
    Perform text repair using OpenAI's images.edit API.
    Uses shared utilities for consistency with other refinement stages.
    """
    
    from ..core.constants import IMAGE_GENERATION_MODEL_ID
    ctx.log(f"Performing text repair using {IMAGE_GENERATION_MODEL_ID or 'gpt-image-1'}...")
    ctx.log(f"Instructions: {ctx.instructions}")
    ctx.log(f"Creativity level: {ctx.creativity_level}")
    
    # Prepare enhanced prompt using shared utility
    enhanced_prompt = _prepare_text_repair_prompt(ctx)
    
    # Determine image size using shared utility
    image_size = determine_api_image_size(base_image.size)
    
    # Call OpenAI API using shared utility (no mask for text repair)
    result_image_path = await call_openai_images_edit(
        ctx=ctx,
        enhanced_prompt=enhanced_prompt,
        image_size=image_size,
        mask_path=None  # Text repair uses global editing, not masked editing
    )
    
    return result_image_path


def _prepare_text_repair_prompt(ctx: PipelineContext) -> str:
    """
    Prepare an enhanced prompt for text repair that incorporates
    the user instructions and text-specific guidance.
    """
    
    base_instructions = ctx.instructions
    
    # Add context about text correction and enhancement
    enhanced_prompt = f"{base_instructions}. Fix any text elements in the image including spelling errors, improve readability, and enhance text quality while preserving the original design and layout"
    
    # Use shared utility for creativity guidance
    enhanced_prompt = enhance_prompt_with_creativity_guidance(
        enhanced_prompt, 
        ctx.creativity_level, 
        "text"
    )
    
    # Add quality and legibility hints specific to text
    enhanced_prompt += " Ensure all text is clear, properly spelled, well-positioned, and easily readable. Maintain proper contrast and font characteristics appropriate for the image style."
    
    # Add marketing context if available from original generation
    if ctx.original_pipeline_data:
        processing_context = ctx.original_pipeline_data.get("processing_context", {})
        strategies = processing_context.get("suggested_marketing_strategies", [])
        if strategies and len(strategies) > 0:
            strategy = strategies[0]  # Use first strategy
            if isinstance(strategy, dict):
                audience = strategy.get("target_audience", "")
                if audience:
                    enhanced_prompt += f" Ensure text is appropriate and appealing for {audience}."
    
    ctx.log(f"Enhanced text repair prompt: {enhanced_prompt}")
    return enhanced_prompt 