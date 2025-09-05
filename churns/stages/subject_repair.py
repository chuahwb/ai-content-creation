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
import logging
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
    get_user_inputs,
    get_assessment_result,
    RefinementError
)
from pydantic_ai import Agent

# Setup Logger
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(name)s] [%(levelname)s] [%(message)s]"
)
logger = logging.getLogger("prompt_refine")

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
    
    logger.info("Starting subject repair stage...")
    
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
            logger.info("Subject repair not available - no original reference image found")
            ctx.refinement_cost = 0.0
            return
        
        # Set the reference image path and default instructions
        ctx.reference_image_path = original_ref_path
        ctx.instructions = "Replace main subject using reference image"
        logger.info(f"Using original reference image: {original_ref_path}")
        logger.info("Using default repair instructions (input-free operation)")
        
        # Additional validation specific to subject repair
        _validate_subject_repair_inputs(ctx)
        
        # Check if text rendering quality is below threshold
        text_refine_prompt = None
        score_justification = _get_text_assessment_result(ctx)
        if score_justification:
            text_refine_prompt = await _create_text_improvement_prompt(ctx, score_justification)
        ctx.text_refine_prompt = text_refine_prompt

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
            logger.info(f"Subject repair completed successfully: {result_image_path}")
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
            logger.info("Subject repair API call completed but no result was generated")
    
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
        logger.info(error_msg)
        
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
        logger.info(error_msg)
        
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
        logger.info("Instructions not set, using default (this should not happen in normal operation)")


async def _perform_subject_repair_api(ctx: PipelineContext) -> str:
    """
    Perform subject repair using OpenAI's images.edit API.
    Uses shared utilities for consistency with other refinement stages.
    """
    
    from ..core.constants import IMAGE_REFINEMENT_MODEL_ID
    logger.info(f"Performing subject repair using {IMAGE_REFINEMENT_MODEL_ID}...")
    logger.info("Starting subject repair with moderate enhancement approach")
    
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
        image_gen_client=image_gen_client,
        image_quality_setting="high",  # Use same quality as original generation to maintain consistency
        input_fidelity="low"  # Low fidelity for all refinement operations
    )
    
    return result_image_path


def _prepare_subject_repair_prompt(ctx: PipelineContext) -> str:
    """
    Prepare an enhanced prompt for subject repair that incorporates
    the user instructions and reference image context.
    Updated to handle new brandkit data structure gracefully.
    """
    try:
        image_ctx_json, main_obj = get_image_ctx_and_main_object(ctx) # For visual concepts
        user_inputs = get_user_inputs(ctx)  # For marketing, branding and logo image
        logger.info(f"User Inputs: {user_inputs}")
        
        # Safely extract visual concept data with fallbacks
        visual_concept = {}
        if isinstance(image_ctx_json, dict):
            visual_concept = image_ctx_json.get('visual_concept', {})
        
        # Ensure we have valid visual concept data with safe fallbacks
        def safe_get(key, default):
            """Safely get a value from visual_concept with fallback"""
            if isinstance(visual_concept, dict):
                return visual_concept.get(key, default)
            return default
        
        composition = safe_get('composition_and_framing', 'Standard composition with balanced framing')
        background = safe_get('background_environment', 'Appropriate background setting')
        foreground = safe_get('foreground_elements', 'Standard foreground elements')
        lighting = safe_get('lighting_and_mood', 'Natural lighting with appropriate mood')
        color_palette = safe_get('color_palette', 'Harmonious color palette')
        visual_style = safe_get('visual_style', 'Professional visual style')
        texture_details = safe_get('texture_and_details', 'Appropriate textures and details')
        creative_reasoning = safe_get('creative_reasoning', 'Maintain visual consistency')
        
        # For text and branding, provide safe defaults to maintain original functionality
        text_visuals = safe_get('promotional_text_visuals', 'No text elements')
        branding_visuals = safe_get('branding_visuals', 'No branding elements')

        # Marketing and branding image
        logo_dir = ''
        marketing_goals_str = 'Marketing goals not provided'
        if user_inputs and user_inputs.get('marketing_goals'):
            marketing_goals = user_inputs.get('marketing_goals')
            logo_dir = user_inputs.get('brand_kit', {}).get('saved_logo_path_in_run_dir', '')
            if marketing_goals:
                marketing_goals_str = f"""\n
                - Target Audience: {marketing_goals.get('target_audience', 'No target audience')}\n
                - Objective: {marketing_goals.get('objective', 'No marketing goals')}\n
                - Voice: {marketing_goals.get('voice', 'No voice')}\n
                - Niche: {marketing_goals.get('niche', 'No niche')}
                """
    
        # Set logo image path for subject repair
        # Will be checked in openai images edit API
        ctx.logo_image_path = logo_dir
        logger.info(f"Logo directory: {logo_dir}")
        logger.info(f"Marketing goals: {marketing_goals_str}")

        # Construct the enhanced prompt with safe data access
        enhanced_prompt = f"""
        You are editing a base image using two supporting image inputs: a main subject reference image and, optionally, a logo image.
        The goal is to create a realistic and visually consistent composition based on the provided visual concept and branding requirements.

        **You will receive the following images via API**:
        1. Base Image – the image to be edited.
        2. Main Subject Reference Image – the object to be extracted and inserted into the base image.
        3. (Optional) Logo Image – to be used if provided, for logo recreation based on branding visuals.

        **Instructions**:
        1. Replace the main object in the base image with relevant content from the reference image.
            - The reference object must retain its **exact shape, proportions, visual aesthetics and text** when inserted.
            - **Do not reinterpret or creatively modify** the reference object — replicate it **as-is**.

        2. The following visual concept and marketing goals were used during the generation of the original image. It may not fully align with the current image but can serve as **an optional creative reference** to guide stylistic consistency and atmosphere:

            Visual Concept:
            - Main Subject: {main_obj}
            - Composition & Framing: {composition}
            - Background Environment: {background}
            - Foreground Elements: {foreground}
            - Lighting & Mood: {lighting}
            - Color Palette: {color_palette}
            - Visual Style: {visual_style}
            - Texture & Details: {texture_details}
            - Creative Reasoning: {creative_reasoning}
            - Text Visuals: {text_visuals}
            - Branding Visuals: {branding_visuals}

            Marketing Goals: {marketing_goals_str}

        3. Seamlessly match the lighting, texture, perspective, and depth of field of the base image so that the inserted object looks naturally integrated.
        4. Align the inserted content with the image's narrative and composition principles (e.g., rule of thirds, natural diagonals, balance of elements).
        5. Ensure all elements in the edited image are visually coherent and logically consistent within the scene.
        6. Correct any visual or contextual inconsistencies introduced during the edit to maintain a believable and polished composition.
        7. Return only the edited base image, fully rendered and coherent. Do not include or concatenate the reference image.
        """
        
        # Include prompt for logo recreation if logo directory exists
        if logo_dir:
            enhanced_prompt += f"""\n
        8. Recreate the logo in the base image using the logo reference and ensure the logo is visually integrated and aligned with the `branding_visuals` described in the visual concept.
        9. Ensure the logo is transparent and opaque, not colorful and scaled to about 4-5% of the image's total width.
        """  

        # Add text refine prompt if available
        logger.info(f"Text refine prompt: {ctx.text_refine_prompt} (under subject repair)")
        if ctx.text_refine_prompt: 
            enhanced_prompt += f"""\n
        Additional Instructions: {ctx.text_refine_prompt}
        """
        
        logger.info("Subject repair prompt prepared successfully with visual context")
        logger.info("Subject repair prompt: \n\n" + enhanced_prompt)
        return enhanced_prompt
        
    except Exception as e:
        # Fallback to a basic prompt if data access fails
        logger.error(f"Error preparing subject repair prompt, using fallback: {e}", exc_info=True)
        
        fallback_prompt = """
        You are editing a base image using a reference object image. Replace the main object in the base image with the object from the reference image.
        
        **Instructions**:
        1. The reference object must retain its exact shape, proportions, and visual characteristics when inserted.
        2. Seamlessly match the lighting, texture, perspective, and depth of field of the base image.
        3. Ensure all elements are visually coherent and logically consistent.
        4. Return only the edited base image, fully rendered and coherent.
        """
        
        return fallback_prompt 

def _get_text_assessment_result(ctx: PipelineContext) -> str:
    assessment_result = get_assessment_result(ctx)
    if assessment_result['assessment_scores'].get('text_rendering_quality'):
        rendering_score = assessment_result['assessment_scores']['text_rendering_quality']
        rendering_justification = assessment_result['assessment_justification'].get('text_rendering_quality')
        if rendering_score < 4:
            logger.info(f"Text rendering quality: {rendering_score} < 4")
            logger.info(f"Text rendering justification: {rendering_justification}")
            return rendering_justification
    else:
        logger.info("Text rendering quality not found in assessment result")
    

async def _create_text_improvement_prompt(ctx: PipelineContext, score_justification: str) -> str:
    prompt_refinement_agent = Agent(
        'openai:gpt-4.1-mini',
        retries=3,
        system_prompt="""
        You are a prompt refinement assistant.
        
        You will be given a justification—produced by another language model—explaining why the text rendering appears poor.
        Your task: Based on that justification, generate a concise and actionable prompt that guides a model or system to correct the rendering issue effectively.
        Focus on clarity, relevance to the identified issue, and keeping the refined prompt tightly scoped to the rendering fix.
        """
    )
    
    user_input = f"Judgement: {score_justification}" 
    response = await prompt_refinement_agent.run(user_input)
    logger.info(f"Text improvement prompt: {response.output}")
    return response.output

