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
import re
import asyncio
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, List
from pydantic_ai import Agent, BinaryContent
from ..pipeline.context import PipelineContext
from ..api.schemas import ImageAnalysisResult

from .refinement_utils import (
    validate_refinement_inputs,
    load_and_prepare_image,
    determine_api_image_size,
    call_openai_images_edit,
    calculate_refinement_cost,
    track_refinement_cost,
    get_image_ctx_and_main_object,
    get_reference_image_path,
    RefinementError
)
from sentence_transformers import SentenceTransformer, util

# Setup Logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("text_repair")

# Async model loading machinery
sentence_transformer_model = None
# Event to signal when model loading is complete
model_loaded_event = asyncio.Event()

async def async_load_sentence_transformer():
    """
    Asynchronously load the SentenceTransformer model in a background thread.
    This prevents blocking the event loop during model initialization.
    """
    global sentence_transformer_model
    try:
        model_path = './churns/stages/artifacts/model'
        logger.info(f"(Background) Attempting to load model from: {os.path.abspath(model_path)}")
        
        if not os.path.exists(model_path):
            logger.error(f"Model path does not exist: {os.path.abspath(model_path)}")
            raise FileNotFoundError(f"Model directory not found: {os.path.abspath(model_path)}")
            
        sentence_transformer_model = await asyncio.to_thread(
            SentenceTransformer, model_path
        )
        logger.info("(Background) SentenceTransformer model loaded successfully")
    except Exception as e:
        logger.exception(f"Failed to load SentenceTransformer model: {e}")
        raise
    finally:
        model_loaded_event.set()

async def get_sentence_transformer_model():
    """
    Await until the model is loaded and ready for inference.
    Returns:
        The loaded SentenceTransformer model.
    """
    global sentence_transformer_model
    
    if sentence_transformer_model is None:
        if model_loaded_event.is_set():
            # If event is set but model is None, there was an error loading
            raise RuntimeError("Failed to load SentenceTransformer model")
            
        logger.info("(Background) SentenceTransformer model not loaded yet, loading now...")
        # If we get here, we need to load the model
        await async_load_sentence_transformer()
        
    return sentence_transformer_model

# Initialize model loading in a way that works for both sync and async contexts
try:
    # If we're in an async context with a running loop
    loop = asyncio.get_running_loop()
    loop.create_task(async_load_sentence_transformer())
except RuntimeError:
    # If no running loop, we'll use lazy loading when first requested
    logger.info("No running event loop - model will be loaded on first request")

# Setup Image Generation Clients (injected by PipelineExecutor)
image_gen_client = None  # Legacy compatibility
image_refinement_client = None  # Dedicated refinement client

async def run(ctx: PipelineContext) -> None:
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
    
    try:
        logger.info("Starting text repair stage...")
        start_time = time.time()
        
        # Validate required inputs using shared utility
        validate_refinement_inputs(ctx, "text")
        
        # Additional validation specific to text repair
        _validate_text_repair_inputs(ctx)
        
        # Load and prepare image using shared utility
        base_image = load_and_prepare_image(ctx, type='base')
        
        # Perform text analysis
        analysis_result = await _perform_text_analysis(ctx)
        
        # Perform Similarity Check
        similarity_check = await _perform_similarity_check(ctx, analysis_result)
        
        # Perform actual text repair using OpenAI API
        result_image_path, image_prompt = await _perform_text_repair(
            ctx=ctx,
            analysis_result_json=analysis_result,
            cosine_sim=similarity_check,
            base_image=base_image
        )
        
        # Check if we got a result
        if result_image_path and os.path.exists(result_image_path):
            # Successful text repair
            ctx.refinement_result = {
                "type": "text_repair",
                "status": "completed", 
                "output_path": result_image_path,
                "modifications": {
                    "image_prompt": image_prompt,
                    "text_corrected": True,
                    "design_preserved": True,
                    "instructions_applied": ctx.instructions
                },
                "error_context": None
            }
            logger.info(f"Text repair completed successfully with path : {result_image_path}")
            logger.info(f"Refinement Result : {ctx.refinement_result}")
        else:
            # This should not happen with the new error handling - if we get here, something unexpected occurred
            ctx.refinement_result = {
                "type": "text_repair",
                "status": "api_no_result",
                "output_path": None,
                "modifications": {
                    "image_prompt": "",
                    "text_corrected": False,
                    "reason": "API call completed but no result was generated"
                },
                "error_context": {
                    "error_type": "api_no_result",
                    "user_message": "The AI was unable to make the requested text changes to your image",
                    "suggestion": "Try using different text repair instructions or check if the image actually contains text that needs correction",
                    "is_retryable": True
                }
            }
            logger.info("Text repair API call completed but no result was generated")
        
        # Calculate and track costs using shared utilities
        ctx.refinement_cost = calculate_refinement_cost(
            ctx,
            ctx.instructions or "",
            has_mask=False,
            refinement_type="text repair"
        )
        track_refinement_cost(ctx, "text_repair", ctx.instructions or "", duration_seconds=4.0)
        end_time = time.time()
        logger.info(f"Text repair completed in {end_time - start_time:.2f} seconds")
        
    except RefinementError as e:
        # Handle our custom refinement errors with detailed context
        if e.error_type == "no_changes_needed":
            # This is a legitimate case where no changes are needed
            logger.info(f"Text repair determined no changes needed: {e.message}")
            ctx.refinement_result = {
                "type": "text_repair",
                "status": "no_changes_needed",
                "output_path": None,
                "modifications": {
                    "text_corrected": False,
                    "reason": e.message
                },
                "error_context": {
                    "error_type": e.error_type,
                    "user_message": e.message,
                    "suggestion": e.suggestion,
                    "is_retryable": e.is_retryable
                }
            }
            # Don't re-raise for legitimate no changes cases
            return
        else:
            # Handle actual error cases
            error_msg = f"Text repair failed: {e.message}"
            logger.error(error_msg)
            
            # Set detailed error result with user-friendly information
            ctx.refinement_result = {
                "type": "text_repair",
                "status": "failed",
                "output_path": None,
                "modifications": {
                    "text_corrected": False,
                    "error": e.message
                },
                "error_context": {
                    "error_type": e.error_type,
                    "user_message": e.message,
                    "suggestion": e.suggestion or "Please try again with different text repair settings",
                    "is_retryable": e.is_retryable
                }
            }
            
            # Still track minimal cost for the attempt
            ctx.refinement_cost = 0.001
            
            # Re-raise to be handled by the executor
            raise
        
    except Exception as e:
        # Handle unexpected errors
        error_msg = f"Text repair stage failed unexpectedly: {str(e)}"
        logger.error(error_msg)
        
        # Set generic error result
        ctx.refinement_result = {
            "type": "text_repair",
            "status": "failed",
            "output_path": None,
            "modifications": {
                "text_corrected": False,
                "error": str(e)
            },
            "error_context": {
                "error_type": "unexpected_error",
                "user_message": "An unexpected error occurred during text repair",
                "suggestion": "Please try again. If the problem persists, contact support.",
                "is_retryable": True
            }
        }
        
        # Still track minimal cost for the attempt
        ctx.refinement_cost = 0.001
        
        # Re-raise to be handled by the executor
        raise


def _validate_text_repair_inputs(ctx: PipelineContext) -> None:
    """Validate inputs specific to text repair (beyond common validation)."""
    
    if not ctx.instructions:
        ctx.instructions = "Fix spelling errors and improve text clarity"
        logger.info("No instructions provided, using default text repair instructions")


async def _perform_text_analysis(ctx: PipelineContext):
    logger.info("-----Performing text analysis-----")
    try:
        analysis_agent = Agent(
            'openai:gpt-4.1-mini',
            result_type=ImageAnalysisResult,  
            retries=5,
        )
        
        # Get main object context
        _, main_obj = get_image_ctx_and_main_object(ctx)

        # Prepare prompt
        analysis_prompt = f"""
        You are analyzing an image to extract embedded textual and branding elements, with a specific distinction between background and object-based content.
        
        **Main Object Context**:
        - The main object in the image is: "{main_obj}"

        **Instructions**:
        1. Identify and transcribe all visible textual content located in the background or surrounding environment, excluding the main object. 
        This includes:
        - Promotional headlines, captions, or environmental signage
        - Printed or stylized background elements such as posters, labels, or callouts
        - Any text that appears outside the primary object's surface
        - If present, separate the text into:
            - `main_text`: the most prominent or central message
            - `secondary_texts`: any supporting or smaller texts
            - If no text is found, return an empty string (`""`) for both.

       2. From the main object (e.g., {main_obj}), extract:
        - `brand_name`: the brand name as printed on the object
        - `object_description`: visible text inside the main object, but excluding the brand name itself. Do not include repeated instances of the brand name. 
        - If no text is found, return an empty string (`""`) for the text fields.

        3. Text Correction and Language Handling:
        - If any extracted text (from background or object) contains:
            - Spelling mistakes, grammatical errors, or broken phrasing
        Then provide suggested corrections under:
            - `corrections`: a dictionary with keys corresponding to the related field, mapping to corrected or translated English versions.
        - Corrections must preserve the intended meaning and visual context of the image.
        - If the original text is already correct and in English, return an empty dictionary
        
        Focus on accuracy, even if text is small, curved, partially obscured, or stylized.
        """

        # Read image and encode to base64
        logger.info(f"Base image path: {ctx.base_image_path}")
        with open(ctx.base_image_path, "rb") as image_file:
            image_bytes = image_file.read()

        # Prepare the API call with gpt-4.1-mini
        response = await analysis_agent.run(
            [
                analysis_prompt,
                BinaryContent(data=image_bytes, media_type='image/png'),
            ]
        )

        logger.info(f"Text analysis result: {response.output.__dict__}")
        return response.output.__dict__

    except Exception as e:
        error_msg = f"Error in text analysis: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg) from e


async def _perform_similarity_check(ctx: PipelineContext, analysis_result: Dict):
    logger.info("-----Performing similarity check-----")

    detected_img_txt = analysis_result.get('main_text', '')
    logger.info(f"Detected Main Text = {detected_img_txt}")
    
    task_description = ctx.original_pipeline_data.get('user_inputs').get('task_description')
    logger.info(f"Task Desc = {task_description}")
    
    # Pre processing before passing to embedding model
    task_description = task_description.lower() if task_description else ""
    detected_img_txt = detected_img_txt.lower() if detected_img_txt else ""
    
    # Remove special characters
    task_description = re.sub(r'[^a-z0-9\s]', '', task_description)
    detected_img_txt = re.sub(r'[^a-z0-9\s]', '', detected_img_txt)
    logger.info(f"Processed Detected Text = {detected_img_txt}")
    logger.info(f"Processed Task Desc = {task_description}")
    
    if task_description and detected_img_txt:
        model = await get_sentence_transformer_model()
        emb1 = model.encode(task_description, convert_to_tensor=True)
        emb2 = model.encode(detected_img_txt, convert_to_tensor=True)

        cosine_sim = util.pytorch_cos_sim(emb1, emb2).item()
    else:
        cosine_sim = 0
    logger.info(f"Cosine Similarity = {cosine_sim}")
    
    return cosine_sim
    

async def _perform_text_rephrase(ctx: PipelineContext, analysis_result: Dict):
    logger.info("-----Performing text rephrasing-----")
    rephrase_agent = Agent(
        'openai:gpt-4.1-mini',
        retries=5,
    )
    
    # Branding Elements
    branding_elements = ctx.original_pipeline_data.get('user_inputs').get('branding_elements')
    logger.info(f"Branding Elements: {branding_elements}")
    
    # Detected Brand
    detected_brand = analysis_result.get('brand_name', '')
    logger.info(f"Detected Brand: {detected_brand}")
    
    # Prompt
    rephrase_prompt=f"""
    You are given a detected brand name that may contain variations or misspellings of a target brand name. 
    Your task is to replace any phrase or word that resembles the brand name with the exact canonical brand name.
    If no brand name is found in the detected brand name, return the  original brand name as it is.
    
    Expected Brand Names: {branding_elements}
    Detected Brand Name: {detected_brand}
    
    Return the corrected brand name.
    """
    
    # Call Agent
    rephrased_brand = await rephrase_agent.run(rephrase_prompt)
    logger.info(f"Rephrased Brand: {rephrased_brand.data}")
    return rephrased_brand.data
    

async def _perform_text_repair(ctx: PipelineContext, analysis_result_json: Dict, cosine_sim: float, base_image) -> tuple[str, str]:
    logger.info("-----Performing text repair-----")
    
    # Get main object
    image_ctx_json, main_obj = get_image_ctx_and_main_object(ctx)
    
    # Get Promotional Text Visuals
    promotional_text_visuals = image_ctx_json.get('promotional_text_visuals', '')
    logger.info(f"Promotional Text Visuals: {promotional_text_visuals}")

    # Check User Inputs
    user_inputs = ctx.original_pipeline_data.get('user_inputs')
    is_render_text = user_inputs.get('render_text')
    is_apply_branding = user_inputs.get('apply_branding')
    task_description = user_inputs.get('task_description')
    branding_elements = user_inputs.get('branding_elements')
    
    logger.info("User Inputs:")
    logger.info(f"- Render Text : {is_render_text}")
    logger.info(f"- Apply Branding : {is_apply_branding}")
    
    # Get analysis result
    main_text = analysis_result_json.get('main_text', '')
    detected_brand = analysis_result_json.get('brand_name', '')
    detected_desc = analysis_result_json.get('object_description', '')  
    corrections = analysis_result_json.get('corrections', '')
    corrected_desc = corrections.get('object_description', '')
    
    # Initialize prompts variable
    prompt_replace_brand = ''
    prompt_replace_text = ''
    prompt_fixed_spelling = ''
    # Check if apply branding is true
    #  Check if brand name exists in image
    #  Check if brand name is same as branding elements (Assuming that brand name will exists in branding elements)
    #  If brand name is not same as branding elements then replace brand name with rephrased brand name
    if is_apply_branding:
        logger.info("-----Enhanced Type : Brand Name-----")        

        # If brand name is empty
        if detected_brand == '':
            logger.warning(f"!!! Render Branding FAILED - Empty Brand Name Detected from Image.")
            prompt_replace_brand = f"Add the brand name '{branding_elements}' clearly to the main object ('{main_obj}') in a professional and visually integrated manner." 
        
        # Apply branding True but brand name is not found in image
        if branding_elements.lower() not in detected_brand.lower():
            logger.warning(f"!!! Brand Name - ({branding_elements}) not found in generated image. ")   
            
            # Perform text rephrasing
            rephrased_brand = await _perform_text_rephrase(ctx, analysis_result_json)
            
            # Create prompt for brand name replacement
            # (Optional)  Create prompt for object description replacement if corrections are suggested by agent
            prompt_replace_brand = f"""Replace the current brand name '{detected_brand}' on the main object ('{main_obj}') with '{rephrased_brand}', preserving the original placement, style, and formatting."""
    
    # Check if render text is true
    if is_render_text:
        logger.info("-----Enhanced Type : Task Description-----")
        # detected_img_txt = str(detected_img_txt).replace('\\n', ', ').replace('\n', ', ')
    
        # If no text generated in image although provided by user
        if not main_text:
            logger.warning("!!! Render Text FAILED - Empty Text Detected from Image")
            prompt_replace_text = _prepare_render_text_prompt(ctx)
            
        
        # If Generated text does not match the user input
        elif task_description and task_description.lower() not in str(main_text).lower() and cosine_sim < 0.6:
            logger.warning(f"!!! Task description text ('{task_description}') not found in generated image. \n")
            prompt_replace_text = _prepare_text_repair_prompt(
                detected_txt=main_text, 
                expected_txt=task_description
            )
    
    # Merge Prompts
    final_prompt = ""
    if prompt_replace_text:
        if prompt_replace_brand and prompt_fixed_spelling:
            final_prompt = prompt_replace_text + f"\n    Additional Instructions: \n 1. {prompt_replace_brand} \n 2. {prompt_fixed_spelling}"
        else: 
            final_prompt += prompt_replace_text + f"\n    Additional Instructions: {prompt_replace_brand or prompt_fixed_spelling}"
    else: 
        if prompt_replace_brand and prompt_fixed_spelling:
            final_prompt += f"\n    Instructions: 1. {prompt_replace_brand} \n 2. {prompt_fixed_spelling}"
        elif prompt_replace_brand: 
            final_prompt += f"\n    Instructions: {prompt_replace_brand}"
        elif prompt_fixed_spelling: 
            final_prompt += f"\n    Instructions: {prompt_fixed_spelling}"
    
    
    # Ensure the main text is same as pipeline metadata - promotional_text_visuals
    if promotional_text_visuals: 
        final_prompt += f"""\n 
        Review the detected main text: "{main_text}", and verify whether it aligns semantically and contextually with the provided reference sentence: "{promotional_text_visuals}".
        The `main_text` should be a direct or prominent phrase extracted from within `promotional_text_visuals`.
        If it does not align update the main text accordingly, any edits made to the image should preserve the original placement, visual style, and formatting of the main text area.
        """
    
    # Update to add suggested corrections of object description from analysis agent
    if corrected_desc: 
        final_prompt += f"""\n
        Replace the detected object description "{detected_desc}" on the main object {main_obj} with the corrected version: "{corrected_desc}".
        Preserve the original text's placement, style, and formatting on the object.
        """
    
    final_prompt += f"""\n
    Fix all spelling errors and abnormal text caused by image generation artifacts, including garbled, unclear, or unnatural phrases.
    A reference image of the main object is provided to ensure all changes preserve its appearance and integrity. **DO NOT alter any other text**.
    Return only the edited image with updated text if modifications are made.
    """
    logger.info(f"Final Prompt: {final_prompt}")
    
    # Determine image size using shared utility
    image_size = determine_api_image_size(base_image.size)
    logger.info(f"Base Image Size: {image_size}")
    
    # Store API image size in context for metadata
    ctx._api_image_size = image_size
    
    # Call OpenAI API using shared utility (no mask for global text repair)
    # Only call if prompt exists 
    if final_prompt.strip():
        logger.info(f"Calling OpenAI Text Repair API.")
        # Use dedicated refinement client (prioritize over legacy client)
        global image_refinement_client, image_gen_client
        client_to_use = image_refinement_client or image_gen_client
        if client_to_use is None:
            raise RuntimeError("Neither image_refinement_client nor image_gen_client properly injected by PipelineExecutor")
        
        # Pass in reference image here
        reference_image_path = get_reference_image_path(ctx)
        ctx.reference_image_path = reference_image_path
        
        result_image_path = await call_openai_images_edit(
            ctx=ctx,
            enhanced_prompt=final_prompt,
            image_size=image_size,
            mask_path=None,  # Text repair uses global editing
            image_gen_client=client_to_use,
            image_quality_setting="medium",  # Use same quality as original generation to prevent quality leap
            input_fidelity="high"  # High fidelity for all refinement operations
        )
        logger.info(f"Text repair API call completed: {result_image_path}")
    else:
        # This is a legitimate case where no changes are needed
        logger.info("No final prompt generated. No text changes are needed.")
        # Raise a special error to indicate legitimate no changes needed
        raise RefinementError(
            "no_changes_needed",
            "No text changes are required for this image",
            "The image text appears to be correct as-is, or no text was found that needs repair.",
            is_retryable=False
        )
    
    return result_image_path, final_prompt


def _prepare_text_repair_prompt(detected_txt: str, expected_txt: str) -> str:
    
    prompt = f"""
    You are editing an image that might contains visible branding and text description. 

    Instructions:
    1. Replace every instance of "{detected_txt}" with "{expected_txt}", preserving the original casing style — if the existing text is in all uppercase, the replacement must also appear in all uppercase.
    2. Correct all spelling errors and resolve any text issues caused by image generation artifacts, such as random, garbled, or incoherent words.
    3. Maintain the original font style, size, color, positioning, and alignment exactly as seen in the source image. The updated text must seamlessly match the formatting and spatial layout of the original.
    4. Ensure the new text blends naturally with the surrounding design — matching textures, shadows, lighting, and perspective.
    5. Do not alter any other elements of the image or introduce additional text.
    6. Return only the edited image with the updated text.
    """

    return prompt

def _prepare_render_text_prompt(ctx: PipelineContext) -> str:
    """
    Prepare a prompt for text rendering/repair.
    Updated to handle new brandkit data structure gracefully.
    """
    try:
        # Get main object with error handling
        _, main_obj = get_image_ctx_and_main_object(ctx)

        # Get image context with safe fallbacks
        image_ctx_json = {}
        try:
            processing_context = ctx.original_pipeline_data.get('processing_context', {})
            if not processing_context and hasattr(ctx, 'data') and ctx.data:
                processing_context = ctx.data.get('processing_context', {})
            
            generated_image_prompts = processing_context.get('generated_image_prompts', [])
            
            # For chain refinements, generation_index might be None
            if ctx.generation_index is not None and generated_image_prompts:
                if 0 <= ctx.generation_index < len(generated_image_prompts):
                    image_ctx_json = generated_image_prompts[ctx.generation_index]
                else:
                    # Use first available prompt context as fallback
                    image_ctx_json = generated_image_prompts[0] if generated_image_prompts else {}
                    ctx.log("Using fallback image context for chain refinement in text repair (index out of range)")
            else:
                # For chain refinements, use the first available prompt context as fallback
                image_ctx_json = generated_image_prompts[0] if generated_image_prompts else {}
                ctx.log("Using fallback image context for chain refinement in text repair")
        except Exception as e:
            ctx.log(f"Warning: Error accessing image context for text repair: {e}")
            image_ctx_json = {}

        # Safely extract text visuals with fallback
        text_visuals = "Standard promotional text"
        try:
            if isinstance(image_ctx_json, dict):
                visual_concept = image_ctx_json.get('visual_concept', {})
                if isinstance(visual_concept, dict):
                    text_visuals = visual_concept.get('promotional_text_visuals', 'Standard promotional text')
        except Exception as e:
            ctx.log(f"Warning: Error extracting text visuals: {e}")

        prompt_render = f"""
        You are editing an image to render promotional text onto it based on the following precise visual specification.

        **Contextual References**:
        - Main Object: {main_obj}
        - Text Styling Details: {text_visuals}
        
        **Instructions**:
        1. Carefully study the Text Styling Details to guide the appearance and placement of the promotional text.
        - These details serve as **style inspiration**, not fixed spatial rules.
        - You may adapt **positioning or layout** of the text to suit the image without compromising legibility or aesthetics.
        2. **Do not alter, shrink, resize, reposition, or visually obstruct** the main object ("{main_obj}").
        3. The promotional text should complement and enhance the overall composition while maintaining readability.
        4. Ensure the text integrates naturally with the image's existing visual elements and style.
        5. Return only the edited image with the text properly rendered.
        """
        
        ctx.log("Text repair prompt prepared successfully")
        return prompt_render
        
    except Exception as e:
        # Fallback prompt if data access fails
        ctx.log(f"Warning: Error preparing text repair prompt, using fallback: {e}")
        
        fallback_prompt = """
        You are editing an image to render promotional text onto it.
        
        **Instructions**:
        1. Add appropriate promotional text to the image.
        2. Do not alter, shrink, resize, or visually obstruct the main subject.
        3. Ensure the text is readable and complements the image composition.
        4. Return only the edited image with the text properly rendered.
        """
        
        return fallback_prompt