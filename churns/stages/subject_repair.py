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
    get_image_ctx_and_main_object,
    get_original_reference_image_path,
    RefinementError
)

# Global variables for API clients are handled by refinement_utils and image_generation.py
image_gen_client = None

async def run(ctx: PipelineContext) -> None:
    """
    Perform subject repair/replacement using original reference image.
    
    This is a one-click repair that requires NO user input. It automatically:
    - Uses the original reference image from the parent pipeline run
    - Applies default repair instructions
    - Only works if an original reference image exists
    
    REQUIRED CONTEXT INPUTS:
    - ctx.base_image_path: Path to the base image to modify
    
    AUTOMATIC CONTEXT SETUP:
    - ctx.reference_image_path: Retrieved from original pipeline run
    - ctx.instructions: Set to default repair instructions
    - ctx.refinement_type: Should be "subject"

    
    SETS CONTEXT OUTPUTS:
    - ctx.refinement_result: Dict with result information
    - ctx.refinement_cost: Cost of the operation
    """
    
    ctx.log("Starting subject repair stage...")
    
    try:
        # Validate required inputs using shared utility
        validate_refinement_inputs(ctx, "subject")
        
        # Get original reference image path from parent pipeline run
        original_ref_path = get_original_reference_image_path(ctx)
        
        # Check if original reference image exists (required for subject repair)
        if not original_ref_path or not os.path.exists(original_ref_path):
            # Gracefully handle case where no original reference image exists
            ctx.refinement_result = {
                "type": "subject_repair",
                "status": "not_available",
                "output_path": None,
                "modifications": {
                    "subject_replaced": False,
                    "reason": "No original reference image available for repair"
                },
                "error_context": {
                    "error_type": "no_reference_image",
                    "user_message": "Quick repair is not available for this image as no reference image was used during generation",
                    "suggestion": "Try using the prompt refinement feature instead",
                    "is_retryable": False
                }
            }
            ctx.log("Subject repair not available - no original reference image found")
            ctx.refinement_cost = 0.0
            return
        
        # Set the reference image path and default instructions
        ctx.reference_image_path = original_ref_path
        ctx.instructions = "Replace main subject using reference image"
        ctx.log(f"Using original reference image: {original_ref_path}")
        ctx.log("Using default repair instructions (input-free operation)")
        
        # Additional validation specific to subject repair
        _validate_subject_repair_inputs(ctx)
        
        # Perform actual subject repair using OpenAI API
        result_image_path = await _perform_subject_repair_api(ctx)
        
        # Check if we got a result
        if result_image_path and os.path.exists(result_image_path):
            # Successful refinement
            ctx.refinement_result = {
                "type": "subject_repair",
                "status": "completed",
                "output_path": result_image_path,
                "modifications": {
                    "subject_replaced": True,
                    "background_preserved": True,
                    "reference_image_used": ctx.reference_image_path,
                    "instructions_applied": ctx.instructions,
                    "operation_type": "automatic_repair"
                },
                "error_context": None
            }
            ctx.log(f"Subject repair completed successfully: {result_image_path}")
        else:
            # This should not happen with the new error handling - if we get here, something unexpected occurred
            ctx.refinement_result = {
                "type": "subject_repair",
                "status": "api_no_result",
                "output_path": None,
                "modifications": {
                    "subject_replaced": False,
                    "reason": "API call completed but no result was generated"
                },
                "error_context": {
                    "error_type": "api_no_result",
                    "user_message": "The AI was unable to make the requested changes to your image",
                    "suggestion": "Try using different instructions or a different reference image",
                    "is_retryable": True
                }
            }
            ctx.log("Subject repair API call completed but no result was generated")
    
        # Calculate and track costs using shared utilities
        ctx.refinement_cost = calculate_refinement_cost(
            ctx, 
            ctx.instructions or "", 
            has_mask=False,
            refinement_type="subject repair"
        )
        track_refinement_cost(ctx, "subject_repair", ctx.instructions or "", duration_seconds=5.0)
        
    except RefinementError as e:
        # Handle our custom refinement errors with detailed context
        error_msg = f"Subject repair failed: {e.message}"
        ctx.log(error_msg)
        
        # Set detailed error result with user-friendly information
        ctx.refinement_result = {
            "type": "subject_repair",
            "status": "failed",
            "output_path": None,
            "modifications": {
                "subject_replaced": False,
                "error": e.message
            },
            "error_context": {
                "error_type": e.error_type,
                "user_message": e.message,
                "suggestion": e.suggestion or "Please try again with different settings",
                "is_retryable": e.is_retryable
            }
        }
        
        # Still track minimal cost for the attempt
        ctx.refinement_cost = 0.001
        
        # Re-raise to be handled by the executor
        raise
        
    except Exception as e:
        # Handle unexpected errors
        error_msg = f"Subject repair stage failed unexpectedly: {str(e)}"
        ctx.log(error_msg)
        
        # Set generic error result
        ctx.refinement_result = {
            "type": "subject_repair",
            "status": "failed",
            "output_path": None,
            "modifications": {
                "subject_replaced": False,
                "error": str(e)
            },
            "error_context": {
                "error_type": "unexpected_error",
                "user_message": "An unexpected error occurred during subject repair",
                "suggestion": "Please try again. If the problem persists, contact support.",
                "is_retryable": True
            }
        }
        
        # Still track minimal cost for the attempt
        ctx.refinement_cost = 0.001
        
        # Re-raise to be handled by the executor
        raise


def _validate_subject_repair_inputs(ctx: PipelineContext) -> None:
    """
    Validate inputs for subject repair (input-free operation).
    
    This validation assumes that:
    - ctx.reference_image_path has been set to the original reference image
    - ctx.instructions has been set to default instructions
    - All inputs are automatically configured, no user input required
    """
    
    if not ctx.base_image_path or not os.path.exists(ctx.base_image_path):
        raise ValueError("Base image path is required and must exist for subject repair")
    
    # Note: reference_image_path should already be validated in the main run() function
    # This is just a final safety check
    if not ctx.reference_image_path or not os.path.exists(ctx.reference_image_path):
        raise ValueError("Original reference image is required for subject repair but was not found")
    
    # Instructions should already be set to default in the main run() function
    if not ctx.instructions:
        ctx.instructions = "Replace main subject using reference image"
        ctx.log("Instructions not set, using default (this should not happen in normal operation)")


async def _perform_subject_repair_api(ctx: PipelineContext) -> str:
    """
    Perform subject repair using OpenAI's images.edit API.
    Uses shared utilities for consistency with other refinement stages.
    """
    
    from ..core.constants import IMAGE_GENERATION_MODEL_ID
    ctx.log(f"Performing subject repair using {IMAGE_GENERATION_MODEL_ID or 'gpt-image-1'}...")
    ctx.log("Starting subject repair with moderate enhancement approach")
    
    # Prepare enhanced prompt using shared utility
    enhanced_prompt = _prepare_subject_repair_prompt(ctx)
    
    # Determine image size using shared utility
    base_image = load_and_prepare_image(ctx, 'base')
    image_size = determine_api_image_size(base_image.size)
    
    # Store API image size in context for metadata
    ctx._api_image_size = image_size
    
    # Use injected client (initialized by PipelineExecutor)
    global image_gen_client
    if image_gen_client is None:
        raise RuntimeError("image_gen_client not properly injected by PipelineExecutor")
    
    # Call OpenAI API using shared utility (no mask for subject repair)
    result_image_path = await call_openai_images_edit(
        ctx=ctx,
        enhanced_prompt=enhanced_prompt,
        image_size=image_size,
        mask_path=None,
        image_gen_client=image_gen_client
    )
    
    return result_image_path


def _prepare_subject_repair_prompt(ctx: PipelineContext) -> str:
    """
    Prepare an enhanced prompt for subject repair that incorporates
    the user instructions and reference image context.
    """
    image_ctx_json, main_obj = get_image_ctx_and_main_object(ctx)
    
    # Add context about subject replacement
    enhanced_prompt = f"""
    You are editing a base image using a reference object image. The goal is to create a realistic and visually consistent composition based on the provided visual concept.

    **Instructions**:
    1. Replace the main object in the base image with relevant content from the reference image.
        - The reference object must retain its **exact shape, proportions, visual aesthetics and text** when inserted.
        - **Do not reinterpret or creatively modify** the reference object — replicate it **as-is**.

    2. The following visual concept was used during the generation of the original image. It may not fully align with the current image but can serve as **an optional creative reference** to guide stylistic consistency and atmosphere:

        Visual Concept:
        - Main Subject: {main_obj}
        - Composition & Framing: {image_ctx_json['visual_concept']['composition_and_framing']}
        - Background Environment: {image_ctx_json['visual_concept']['background_environment']}
        - Foreground Elements: {image_ctx_json['visual_concept']['foreground_elements']}
        - Lighting & Mood: {image_ctx_json['visual_concept']['lighting_and_mood']}
        - Color Palette: {image_ctx_json['visual_concept']['color_palette']}
        - Visual Style: {image_ctx_json['visual_concept']['visual_style']}
        - Texture & Details: {image_ctx_json['visual_concept']['texture_and_details']}
        - Creative Reasoning: {image_ctx_json['visual_concept']['creative_reasoning']}
        - Text Visuals : {image_ctx_json['visual_concept']['promotional_text_visuals']}
        - Branding Visuals : {image_ctx_json['visual_concept']['branding_visuals']}

    3. Seamlessly match the lighting, texture, perspective, and depth of field of the base image so that the inserted object looks naturally integrated.
    4. Align the inserted content with the image's narrative and composition principles (e.g., rule of thirds, natural diagonals, balance of elements).
    5. Ensure all elements in the edited image are visually coherent and logically consistent within the scene.
    6. Correct any visual or contextual inconsistencies introduced during the edit to maintain a believable and polished composition.
    7. Return only the edited base image, fully rendered and coherent. Do not include or concatenate the reference image.
    """
    
    # ctx.log(f"Enhanced subject repair prompt: {enhanced_prompt}")
    return enhanced_prompt 