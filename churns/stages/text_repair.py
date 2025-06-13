"""
Text Repair Stage - Refinement Pipeline

This stage fixes text-related issues in generated images, including spelling errors,
text clarity, and readability improvements. Uses OpenAI's gpt-image-1 model for 
text repair operations with marketing context integration.

IMPLEMENTATION GUIDANCE:
- Fix spelling and grammar in text overlays
- Improve text readability and contrast  
- Maintain original design and layout
- Preserve non-text elements unchanged
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
    cleanup_temporary_files
)


def run(ctx: PipelineContext) -> None:
    """
    Perform text repair/correction on generated images.
    
    REQUIRED CONTEXT INPUTS:
    - ctx.base_image_path: Path to the base image to modify
    - ctx.instructions: User instructions for text repair
    - ctx.refinement_type: Should be "text"

    
    SETS CONTEXT OUTPUTS:
    - ctx.refinement_result: Dict with result information
    - ctx.refinement_cost: Cost of the operation
    
    IMPLEMENTATION REQUIREMENTS:
    1. Load base image for analysis
    2. Identify text elements needing repair
    3. Apply text corrections and improvements
    4. Maintain original design elements
    5. Save result and update context
    """
    
    ctx.log("Starting text repair stage...")
    
    # Validate required inputs using shared utility
    validate_refinement_inputs(ctx, "text")
    
    # Additional validation specific to text repair
    _validate_text_repair_inputs(ctx)
    
    # Load and prepare image using shared utility
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
            "design_preserved": True,
            "instructions_applied": ctx.instructions
        }
    }
    
    # Calculate and track costs using shared utilities
    ctx.refinement_cost = calculate_refinement_cost(
        ctx,
        ctx.instructions or "",
        has_mask=False,
        refinement_type="text repair"
    )
    track_refinement_cost(ctx, "text_repair", ctx.instructions or "", duration_seconds=4.0)
    
    ctx.log(f"Text repair completed: {result_image_path}")


def _validate_text_repair_inputs(ctx: PipelineContext) -> None:
    """Validate inputs specific to text repair (beyond common validation)."""
    
    if not ctx.instructions:
        ctx.instructions = "Fix spelling errors and improve text clarity"
        ctx.log("No instructions provided, using default text repair instructions")


async def _perform_text_repair_api(ctx: PipelineContext, base_image) -> str:
    """
    Perform text repair using OpenAI's images.edit API.
    Uses shared utilities for consistency with other refinement stages.
    """
    
    from ..core.constants import IMAGE_GENERATION_MODEL_ID
    ctx.log(f"Performing text repair using {IMAGE_GENERATION_MODEL_ID or 'gpt-image-1'}...")
    ctx.log(f"Instructions: {ctx.instructions}")
    ctx.log("Starting text repair with moderate enhancement approach")
    
    # Prepare enhanced prompt using shared utility
    enhanced_prompt = _prepare_text_repair_prompt(ctx)
    
    # Determine image size using shared utility
    image_size = determine_api_image_size(base_image.size)
    
    # Call OpenAI API using shared utility (no mask for global text repair)
    result_image_path = await call_openai_images_edit(
        ctx=ctx,
        enhanced_prompt=enhanced_prompt,
        image_size=image_size,
        mask_path=None  # Text repair uses global editing
    )
    
    return result_image_path


def _prepare_text_repair_prompt(ctx: PipelineContext) -> str:
    """
    Prepare an enhanced prompt for text repair that incorporates
    marketing context and focuses on text quality improvements.
    """
    
    base_instructions = ctx.instructions
    
    # Load marketing context if available
    marketing_context = _load_marketing_context(ctx)
    
    # Enhance prompt with marketing context
    enhanced_prompt = f"{base_instructions}. Focus on fixing text elements while preserving the overall design and visual impact"
    
    # Add marketing context if available
    if marketing_context:
        enhanced_prompt += f". Ensure text aligns with the {marketing_context.get('platform', 'social media')} platform requirements"
        if marketing_context.get('audience'):
            enhanced_prompt += f" and resonates with {marketing_context['audience']}"
    
    # Apply moderate enhancement approach (no creativity level needed)
    enhanced_prompt += ". Use a balanced approach that improves text clarity and readability while maintaining the original design aesthetic."
    
    ctx.log(f"Enhanced text repair prompt: {enhanced_prompt}")
    return enhanced_prompt


def _load_marketing_context(ctx: PipelineContext) -> Optional[Dict[str, Any]]:
    """Load marketing context from parent run for text repair guidance."""
    
    try:
        metadata_path = Path(ctx.base_run_dir) / "pipeline_metadata.json"
        if metadata_path.exists():
            import json
            with open(metadata_path, 'r') as f:
                pipeline_data = json.load(f)
            
            # Extract relevant marketing context
            marketing_context = {}
            if "run_inputs" in pipeline_data:
                inputs = pipeline_data["run_inputs"]
                marketing_context.update({
                    "platform": inputs.get("platform_name"),
                    "audience": inputs.get("marketing_audience"), 
                    "objective": inputs.get("marketing_objective"),
                    "voice": inputs.get("marketing_voice")
                })
            
            return marketing_context if any(marketing_context.values()) else None
            
    except Exception as e:
        ctx.log(f"Could not load marketing context: {e}")
        return None 