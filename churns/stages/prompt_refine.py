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
from PIL import Image
from typing import Dict, Any, Optional, List, Tuple
import logging
from ..pipeline.context import PipelineContext

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
from pydantic import BaseModel, Field
from pydantic_ai import Agent, BinaryContent

# Setup Logger
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(name)s] [%(levelname)s] [%(message)s]"
)
logger = logging.getLogger("prompt_refine")

# Setup Image Generation Client (injected by PipelineExecutor)
image_gen_client = None


class PromptRefinementAgentInput(BaseModel):
    prompt: str = Field(..., description="The original user-written prompt that needs refinement.")
    visual_concept: Dict = Field(
        default_factory=dict,
        description="Optional visual context or metadata related to the prompt. Used for contextual refinement if relevant."
    )

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
    
    logger.info("Starting prompt refinement stage...")
    
    try:
        # Validate required inputs using shared utility
        validate_refinement_inputs(ctx, "prompt")
        
        # Additional validation specific to prompt refinement
        _validate_prompt_refinement_inputs(ctx)
        
        # Load and prepare image using shared utility
        base_image = load_and_prepare_image(ctx, type='base')
        
        # Refine user prompt
        refined_prompt = await _refine_user_prompt(ctx)
        ctx.refined_prompt = refined_prompt
        
        # Handle mask (No coordinates will be passed)
        mask_path = None
        editing_type = "global" # Indicates the type of image editing region
        
        logger.info(f"Mask File Path = {ctx.mask_file_path}")
        
        # Prefer mask file over coordinates (new approach)
        if ctx.mask_file_path and os.path.exists(ctx.mask_file_path):
            mask_path = ctx.mask_file_path
            editing_type = "regional"
            # Convert selected region to fully transparent areas (e.g. where alpha is zero)
            _convert_region_alpha(mask_path)
            logger.info(f"Using provided mask file: {mask_path}")

        # TODO : Suggesestions - If the prompt is related to main subejct - maybe can pass the reference object in
        
        # Perform actual prompt refinement using OpenAI API
        # Determine image size using shared utility
        image_size = determine_api_image_size(base_image.size)
        ctx._api_image_size = image_size
        
        result_image_path = await call_openai_images_edit(
            ctx=ctx,
            enhanced_prompt=refined_prompt,
            image_size=image_size,
            mask_path=mask_path,
            image_gen_client=image_gen_client
        )
        
        
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
                    "refine_prompt": refined_prompt,
                    "enhancement_approach": "balanced"
                },
                "error_context": None
            }
            logger.info(f"Prompt refinement completed successfully: {result_image_path}")
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
            logger.info("Prompt refinement API call completed but no result was generated")
        
        # Calculate and track costs using shared utilities
        ctx.refinement_cost = calculate_refinement_cost(
            ctx,
            ctx.prompt or "",
            has_mask=mask_path is not None,
            refinement_type="prompt refinement"
        )
        track_refinement_cost(ctx, "prompt_refinement", ctx.refined_prompt or "", duration_seconds=6.0)
        
    except RefinementError as e:
        # Handle our custom refinement errors with detailed context
        error_msg = f"Prompt refinement failed: {e.message}"
        logger.error(error_msg)
        
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
        logger.error(error_msg)
        
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
        logger.warning("No prompt provided, using default enhancement prompt")


def _crop_image_with_mask(base_image_path: str, mask_path: str) -> Optional[Tuple[str, str]]:
    """
    Process the base image with the mask to create a transparent version where only
    the white regions from the mask are kept in the base image.
    
    Args:
        base_image_path: Path to the base image
        mask_path: Path to the mask image (white pixels indicate region to keep)
        
    Returns:
        Tuple of (result_image_path, overlay_path) or None if processing fails
    """
    try:
        # Open images
        base_img = Image.open(base_image_path).convert('RGBA')
        mask_img = Image.open(mask_path).convert('L')  # Convert mask to grayscale
        
        # Create output directory if it doesn't exist
        output_dir = Path(mask_path).parent
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # 1. Create a fully transparent version of the base image
        result = Image.new('RGBA', base_img.size, (0, 0, 0, 0))
        
        # 2. Convert mask to binary (0 or 255) and use as alpha channel
        # White in mask (255) becomes opaque, black (0) becomes transparent
        mask = mask_img.point(lambda x: 255 if x > 200 else 0, '1')
        
        # 3. Paste the base image onto the transparent image, using the mask
        result.paste(base_img, (0, 0), mask)
        
        # 4. Save the result
        result_path = str(output_dir / 'masked_region.png')
        result.save(result_path, 'PNG')
        
        logger.info(f"Saved masked region to {result_path}")
        
        return result_path
        
    except Exception as e:
        logger.error(f"Error in _crop_image_with_mask: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return None
    except Exception as e:
        logger.error(f"Error cropping image with mask: {str(e)}")
        return None

async def _refine_user_prompt(ctx: PipelineContext) -> str:
    logger.info("-----Performing prompt refinement-----")
    
    # Create Object Idenfitifaction Agent
    prompt_identify_agent = Agent(
        'openai:gpt-4.1-mini',
        retries=3,
        system_prompt="""
        You are an object identification assistant with vision capabilities.

        You will be provided with:
        1. Visual context about the image
        2. A cropped region of interest from the image 

        Your task is to identify the objects in the image by:
        - Identifying vague references (e.g., "this," "that," "the object") in the original prompt by analyzing the cropped region, if provided
        - If there are no vague reference then return the main subject from the input caption
                
        Example:
        Original prompt: “Replace this with a book”
        Cropped image shows a cup
        Identification: “cup”
        """
    )
    
    # Create Prompt Refinement Agent
    prompt_refinement_agent = Agent(
        'openai:gpt-4.1-mini',
        retries=3,
        system_prompt="""
        You are a prompt refinement assistant with vision capabilities.

        You will be provided with:
        1. The user's original prompt with a description of the subject to be edited
        2. Visual context about the image

        Your task is to refine the user's original prompt by:
        - Resolve any vague references (e.g., “this,” “that,” “the object”) in the original prompt by substituting them with the explicit object description provided
        - Preserving the original intent and any technical constraints
        - Ensuring the refined prompt is clear, concise, and actionable, with specific references to objects or elements in the visual contex
        - Keep the refined prompt concise and actionable
        
        Example:
        Original prompt: “Replace this with a book”
        Identified object: “a white ceramic mug”
        Refined prompt: “Replace the white ceramic mug with a closed hardcover book”
        """
    )

    
    # Get Image Visualization Context
    image_ctx, _ = get_image_ctx_and_main_object(ctx)
    
    # Get Object Identification
    identification_input = [
        f"Original Prompt: {ctx.prompt}",
    ]
    
        # Add cropped region if mask is available
    if ctx.mask_file_path and os.path.exists(ctx.mask_file_path):
        cropped_path = _crop_image_with_mask(ctx.base_image_path, ctx.mask_file_path)
        image_bytes = open(cropped_path, "rb").read()
        binary_content = BinaryContent(data=image_bytes, media_type='image/png')
        identification_input.append(binary_content)

    object_identification = await prompt_identify_agent.run(identification_input)
    logger.info(f"Refine Object Identification = {object_identification.output}")
    
    # Prepare user input with prompt and visual context
    base_prompt = f"Original Prompt: {ctx.prompt}\nIdentified Object: {object_identification.output}\nVisual Context: {image_ctx}"
    
    # Refine Prompt with visual context
    response = await prompt_refinement_agent.run(base_prompt)
    logger.info(f"Refined Prompt = {response.output}")
    return response.output


def _convert_region_alpha(mask_path: str) -> None:
    """
    Convert selected region to fully transparent areas (e.g. where alpha is zero) 
    """
    image = Image.open(mask_path)
    
    # Ensure image in RGBA mode
    if image.mode != 'RGBA':
        image = image.convert('RGBA')
    
    # Get pixel data
    pixels = image.load()
    width, height = image.size
    
    # Iterate over pixels and convert selected region to transparent
    for x in range(width):
        for y in range(height):
            r, g, b, a = pixels[x, y]
            if r == 255 and g == 255 and b == 255:  # If pixel is black
                pixels[x, y] = (255, 255, 255, 0)  # Set alpha to 0 (fully transparent)
    
    # Save the modified image
    image.save(mask_path)
    logger.info(f"Converted mask to fully transparent regions: {mask_path}")

