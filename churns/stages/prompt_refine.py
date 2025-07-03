"""
Prompt Refinement Stage - Refinement Pipeline

This stage performs global or regional prompt-based refinements on images.
Supports both global enhancements and regional masking for targeted improvements.
Uses OpenAI's gpt-image-1 model for sophisticated image modifications.

IMPLEMENTATION GUIDANCE:
- Apply global or regional prompt-based enhancements
- Support mask-based regional editing
- Maintain image quality while applying changes
- Use balanced approach for consistent results
"""

import os
import asyncio
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

from ..pipeline.context import PipelineContext
from ..core.client_config import get_configured_clients
from .refinement_utils import (
    validate_refinement_inputs,
    load_and_prepare_image, 
    determine_api_image_size,
    call_openai_images_edit,
    calculate_refinement_cost,
    track_refinement_cost,
    create_mask_from_coordinates,
    cleanup_temporary_files,
    get_image_ctx_and_main_object,
    RefinementError
)

# Global variables for API clients (consistent with other stages)
image_gen_client = None


async def run(ctx: PipelineContext) -> None:
    """
    Perform prompt-based refinement on images with optional regional masking.
    
    REQUIRED CONTEXT INPUTS:
    - ctx.base_image_path: Path to the base image to modify
    - ctx.prompt: User prompt for refinement
    - ctx.refinement_type: Should be "prompt"

    
    OPTIONAL CONTEXT INPUTS:
    - ctx.mask_coordinates: JSON string of mask coordinates for regional editing
    
    SETS CONTEXT OUTPUTS:
    - ctx.refinement_result: Dict with result information  
    - ctx.refinement_cost: Cost of the operation
    """
    
    ctx.log("Starting prompt refinement stage...")
    
    try:
        # Validate required inputs using shared utility
        validate_refinement_inputs(ctx, "prompt")
        
        # Additional validation specific to prompt refinement
        _validate_prompt_refinement_inputs(ctx)
        
        # Load and prepare image using shared utility
        base_image = load_and_prepare_image(ctx, type='base')
        
        # Handle mask (either file or coordinates)
        mask_path = None
        editing_type = "global"
        
        # Prefer mask file over coordinates (new approach)
        if ctx.mask_file_path and os.path.exists(ctx.mask_file_path):
            mask_path = ctx.mask_file_path
            editing_type = "regional"
            ctx.log(f"Using provided mask file: {mask_path}")
        elif ctx.mask_coordinates:
            # Legacy support: generate mask from coordinates
            mask_path, editing_type = _prepare_regional_mask(ctx, base_image)
        
        # Perform actual prompt refinement using OpenAI API
        result_image_path = await _perform_prompt_refinement_api(ctx, base_image, mask_path)
        
        # Cleanup mask file if it was generated from coordinates (legacy)
        if mask_path and ctx.mask_coordinates and not ctx.mask_file_path:
            cleanup_temporary_files([mask_path])
            ctx.log(f"Cleaned up generated mask file: {mask_path}")
        
        # Check if we got a result
        if result_image_path and os.path.exists(result_image_path):
            # Successful refinement
            ctx.refinement_result = {
                "type": "prompt_refinement",
                "status": "completed",
                "output_path": result_image_path,
                "modifications": {
                    "editing_type": editing_type,
                    "has_mask": mask_path is not None,
                    "prompt_applied": ctx.prompt,
                    "enhancement_approach": "balanced"
                },
                "error_context": None
            }
            ctx.log(f"Prompt refinement completed successfully: {result_image_path}")
        else:
            # This should not happen with the new error handling - if we get here, something unexpected occurred
            ctx.refinement_result = {
                "type": "prompt_refinement",
                "status": "api_no_result",
                "output_path": None,
                "modifications": {
                    "prompt_applied": False,
                    "reason": "API call completed but no result was generated"
                },
                "error_context": {
                    "error_type": "api_no_result",
                    "user_message": "The AI was unable to make the requested enhancements to your image",
                    "suggestion": "Try using different enhancement instructions or check if the image needs any changes",
                    "is_retryable": True
                }
            }
            ctx.log("Prompt refinement API call completed but no result was generated")
        
        # Calculate and track costs using shared utilities
        ctx.refinement_cost = calculate_refinement_cost(
            ctx,
            ctx.prompt or "",
            has_mask=mask_path is not None,
            refinement_type="prompt refinement"
        )
        track_refinement_cost(ctx, "prompt_refinement", ctx.prompt or "", duration_seconds=6.0)
        
    except RefinementError as e:
        # Handle our custom refinement errors with detailed context
        error_msg = f"Prompt refinement failed: {e.message}"
        ctx.log(error_msg)
        
        # Set detailed error result with user-friendly information
        ctx.refinement_result = {
            "type": "prompt_refinement",
            "status": "failed",
            "output_path": None,
            "modifications": {
                "prompt_applied": False,
                "error": e.message
            },
            "error_context": {
                "error_type": e.error_type,
                "user_message": e.message,
                "suggestion": e.suggestion or "Please try again with different enhancement settings",
                "is_retryable": e.is_retryable
            }
        }
        
        # Cleanup mask file on error if it was generated from coordinates (legacy)
        if mask_path and ctx.mask_coordinates and not ctx.mask_file_path:
            cleanup_temporary_files([mask_path])
        
        # Still track minimal cost for the attempt
        ctx.refinement_cost = 0.001
        
        # Re-raise to be handled by the executor
        raise
        
    except Exception as e:
        # Handle unexpected errors
        error_msg = f"Prompt refinement stage failed unexpectedly: {str(e)}"
        ctx.log(error_msg)
        
        # Set generic error result
        ctx.refinement_result = {
            "type": "prompt_refinement",
            "status": "failed",
            "output_path": None,
            "modifications": {
                "prompt_applied": False,
                "error": str(e)
            },
            "error_context": {
                "error_type": "unexpected_error",
                "user_message": "An unexpected error occurred during prompt refinement",
                "suggestion": "Please try again. If the problem persists, contact support.",
                "is_retryable": True
            }
        }
        
        # Cleanup mask file on error if it was generated from coordinates (legacy)
        if mask_path and ctx.mask_coordinates and not ctx.mask_file_path:
            cleanup_temporary_files([mask_path])
        
        # Still track minimal cost for the attempt
        ctx.refinement_cost = 0.001
        
        # Re-raise to be handled by the executor
        raise


def _validate_prompt_refinement_inputs(ctx: PipelineContext) -> None:
    """Validate inputs specific to prompt refinement (beyond common validation)."""
    
    if not ctx.prompt:
        ctx.prompt = "Enhance the overall image quality and appeal"
        ctx.log("No prompt provided, using default enhancement prompt")


def _prepare_regional_mask(ctx: PipelineContext, base_image) -> Tuple[Optional[str], str]:
    """
    Prepare regional mask for targeted editing if coordinates are provided.
    Returns mask path and editing type.
    """
    
    try:
        import json
        mask_data = json.loads(ctx.mask_coordinates)
        
        ctx.log(f"Creating regional mask from coordinates: {mask_data}")
        
        # Create mask using shared utility
        mask_path = create_mask_from_coordinates(
            mask_data, 
            base_image.size,
            ctx.base_run_dir
        )
        
        if mask_path and os.path.exists(mask_path):
            ctx.log(f"Regional mask created: {mask_path}")
            return mask_path, "regional"
        else:
            ctx.log("Failed to create mask, falling back to global editing")
            return None, "global"
            
    except Exception as e:
        ctx.log(f"Error creating regional mask: {e}. Using global editing.")
        return None, "global"


async def _perform_prompt_refinement_api(ctx: PipelineContext, base_image, mask_path: Optional[str]) -> str:
    """
    Perform prompt refinement using OpenAI's images.edit API.
    Supports both global and regional editing based on mask presence.
    Uses shared utilities for consistency with other refinement stages.
    """
    
    from ..core.constants import IMAGE_GENERATION_MODEL_ID
    ctx.log(f"Performing prompt refinement using {IMAGE_GENERATION_MODEL_ID or 'gpt-image-1'}...")
    ctx.log(f"Prompt: {ctx.prompt}")
    ctx.log(f"Editing type: {'Regional' if mask_path else 'Global'}")
    ctx.log("Starting prompt refinement with balanced enhancement approach")
    
    # Prepare enhanced prompt using shared utility
    enhanced_prompt = _prepare_prompt_refinement_prompt(ctx)
    
    # Determine image size using shared utility
    image_size = determine_api_image_size(base_image.size)
    
    # Store API image size in context for metadata
    ctx._api_image_size = image_size
    
    # Initialize client if not already done (lazy initialization)
    global image_gen_client
    if image_gen_client is None:
        image_gen_client = get_configured_clients().get('image_gen_client')
    
    # Call OpenAI API using shared utility
    result_image_path = await call_openai_images_edit(
        ctx=ctx,
        enhanced_prompt=enhanced_prompt,
        image_size=image_size,
        mask_path=mask_path,  # None for global, path for regional editing
        image_gen_client=image_gen_client
    )
    
    return result_image_path


def _prepare_prompt_refinement_prompt(ctx: PipelineContext) -> str:
    """
    Prepare an enhanced prompt for refinement that incorporates
    the user prompt and context-appropriate guidance.
    """
    
    base_prompt = ctx.prompt
    
    # Get image context and main object using shared utility
    image_ctx_json, main_obj = get_image_ctx_and_main_object(ctx)
    
    # Load marketing context if available
    marketing_context = _load_marketing_context(ctx)
    
    # Enhance prompt with context
    enhanced_prompt = f"{base_prompt}. Apply enhancements while maintaining the original image's quality and aesthetic appeal"
    
    # Add marketing context if available
    if marketing_context:
        platform = marketing_context.get('platform', 'social media')
        enhanced_prompt += f". Ensure the result is optimized for {platform}"
        
        if marketing_context.get('audience'):
            enhanced_prompt += f" and appealing to {marketing_context['audience']}"
    
    # Add visual concept context for consistency
    if image_ctx_json and 'visual_concept' in image_ctx_json:
        enhanced_prompt += f". The main subject is {main_obj}. Maintain consistency with the original visual style and composition."
    
    # Apply balanced enhancement approach (no creativity level needed)
    enhanced_prompt += ". Use a balanced approach that enhances the image quality while preserving its original character and style."
    
    # ctx.log(f"Enhanced refinement prompt: {enhanced_prompt}")
    return enhanced_prompt


def _load_marketing_context(ctx: PipelineContext) -> Optional[Dict[str, Any]]:
    """Load marketing context from parent run for refinement guidance."""
    
    try:
        # Use original pipeline data if available (consistent with other stages)
        if hasattr(ctx, 'original_pipeline_data') and ctx.original_pipeline_data:
            pipeline_data = ctx.original_pipeline_data
        else:
            # Fallback to loading from metadata file
            metadata_path = Path(ctx.base_run_dir) / "pipeline_metadata.json"
            if metadata_path.exists():
                import json
                with open(metadata_path, 'r') as f:
                    pipeline_data = json.load(f)
            else:
                return None
        
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