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
from pathlib import Path
from typing import Dict, Any, Optional, List
from pydantic_ai import Agent, BinaryContent
from ..pipeline.context import PipelineContext
from ..api.schemas import ImageAnalysisResult
from ..core.client_config import get_configured_clients
from .refinement_utils import (
    validate_refinement_inputs,
    load_and_prepare_image,
    determine_api_image_size,
    call_openai_images_edit,
    calculate_refinement_cost,
    track_refinement_cost,
    get_image_ctx_and_main_object
)
from sentence_transformers import SentenceTransformer, util

# Setup Logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("text_repair")

# Setup Image Generation Client
image_gen_client = get_configured_clients().get('image_gen_client')

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
        
        # Validate required inputs using shared utility
        validate_refinement_inputs(ctx, "text")
        
        # Additional validation specific to text repair
        _validate_text_repair_inputs(ctx)
        
        # Load and prepare image using shared utility
        base_image = load_and_prepare_image(ctx, type='base')
        
        # Perform text analysis
        analysis_result = await _perform_text_analysis(ctx)
        
        # Perform Similarity Check
        similarity_check = _perform_similarity_check(ctx, analysis_result)
        
        # Perform actual text repair using OpenAI API
        result_image_path = await _perform_text_repair(
            ctx=ctx,
            analysis_result_json=analysis_result,
            cosine_sim=similarity_check,
            base_image=base_image
        )
        
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
        
        logger.info(f"Text repair completed: {result_image_path}")
        
    except Exception as e:
        error_msg = f"Error in text repair stage: {str(e)}"
        logger.error(error_msg)
        raise  # Re-raise the error to be caught by the executor


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
        # TODO: If any part of the analysis is not englsih then suggest improvements under corrections section
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
        - `object_description`: visible text inside the reference object, but excluding the brand name itself. Do not include repeated instances of the brand name. 
        - If no text is found, return an empty string (`""`) for the text fields.

        3. Text Correction and Language Handling:
        - If any extracted text (from background or object) contains:
            - Spelling mistakes, grammatical errors, or broken phrasing
            - Text that is not in English (either fully or partially)
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

        logger.info(f"Text analysis result: {response.data.__dict__}")
        return response.data.__dict__

    except Exception as e:
        error_msg = f"Error in text analysis: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg) from e


def _perform_similarity_check(ctx: PipelineContext, analysis_result: Dict):
    
    # Load Model
    logger.info("-----Performing similarity check-----")
    model = SentenceTransformer('distiluse-base-multilingual-cased-v2')

    detected_img_txt = analysis_result.get('main_text', '')
    task_description = ctx.original_pipeline_data.get('user_inputs').get('task_description')
    
    # Pre processing before passing to embedding model
    task_description = task_description.lower() if task_description else ""
    detected_img_txt = detected_img_txt.lower() if detected_img_txt else ""
    
    # Remove special characters
    task_description = re.sub(r'[^a-z0-9\s]', '', task_description)
    detected_img_txt = re.sub(r'[^a-z0-9\s]', '', detected_img_txt)
    
    logger.info(f"Task Desc = {task_description}")
    logger.info(f"Detected Main Text = {detected_img_txt}")

    emb1 = model.encode(task_description, convert_to_tensor=True)
    emb2 = model.encode(detected_img_txt, convert_to_tensor=True)

    cosine_sim = util.pytorch_cos_sim(emb1, emb2).item()
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
    

async def _perform_text_repair(ctx: PipelineContext, analysis_result_json: Dict, cosine_sim: float, base_image) -> Optional[str]:
    logger.info("-----Performing text repair-----")
    
    # Get main object
    _, main_obj = get_image_ctx_and_main_object(ctx)

    # Check User Inputs
    user_inputs = ctx.original_pipeline_data.get('user_inputs')
    is_render_text = user_inputs.get('render_text')
    is_apply_branding = user_inputs.get('apply_branding')
    task_description = user_inputs.get('task_description')
    branding_elements = user_inputs.get('branding_elements')
    
    logger.info("User Inputs:")
    logger.info(f"- Render Text : {is_render_text}")
    logger.info(f"- Task Describtion : {task_description}")
    logger.info(f"- Apply Branding : {is_apply_branding}")
    logger.info(f"- Branding Elements : {branding_elements}")
    
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
        detected_brand = analysis_result_json.get('brand_name', '')
        detected_desc = analysis_result_json.get('object_description', '')  
        corrections = analysis_result_json.get('corrections', '')
        corrected_desc = corrections.get('object_description', '')

        logger.info(f"Detected Brand Name : {detected_brand}")
        logger.info(f"Detected Object Description : {detected_desc}")
        logger.info(f"Corrections : {corrections}")

        # If brand name is empty
        if detected_brand == '':
            print(f"!!! Render Branding FAILED - Empty Brand Name Detected from Image.")
            prompt_replace_brand = f"Add the brand name '{branding_elements}' clearly to the main object ('{main_obj}') in a professional and visually integrated manner." 
        
        # Apply branding True but brand name is not found in image
        if branding_elements.lower() not in detected_brand.lower():
            print(f"!!! Brand Name - ({branding_elements}) not found in generated image. ")   
            
            # Perform text rephrasing
            rephrased_brand = await _perform_text_rephrase(ctx, analysis_result_json)
            
            # Create prompt for brand name replacement
            # (Optional)  Create prompt for object description replacement if corrections are suggested by agent
            prompt_replace_brand = f"""Replace the current brand name '{detected_brand}' on the main object ('{main_obj}') with '{rephrased_brand}', preserving the original placement, style, and formatting."""
            if corrected_desc: 
                prompt_fixed_spelling = f"""Replace the current object description '{detected_desc}' on the main object  ('{main_obj}') with '{corrected_desc}', preserve the orignal placement, style, and formatting."""
    
    
    # Check if render text is true
    if is_render_text:
        logger.info("-----Enhanced Type : Task Description-----")
        detected_img_txt = analysis_result_json.get('main_text', '')
        # detected_img_txt = str(detected_img_txt).replace('\\n', ', ').replace('\n', ', ')
    
        # If no text generated in image although provided by user
        if not detected_img_txt:
            print("!!! Render Text FAILED - Empty Text Detected from Image")
            prompt_replace_text = _prepare_render_text_prompt(ctx)
            
        
        # If Generated text does not match the user input
        elif task_description and task_description.lower() not in str(detected_img_txt).lower() and cosine_sim < 0.6:
            print(f"!!! Task description text ('{task_description}') not found in generated image. \n")
            prompt_replace_text = _prepare_text_repair_prompt(
                detected_txt=detected_img_txt, 
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
    
    logger.info(f"Final Prompt: {final_prompt}")
    

    # Determine image size using shared utility
    image_size = determine_api_image_size(base_image.size)
    logger.info(f"Base Image Size: {image_size}")
    
    # Call OpenAI API using shared utility (no mask for global text repair)
    # Only call if prompt exists 
    if final_prompt:
        result_image_path = await call_openai_images_edit(
            ctx=ctx,
            enhanced_prompt=final_prompt,
            image_size=image_size,
            mask_path=None,  # Text repair uses global editing
            image_gen_client=image_gen_client
        )
    else:
        result_image_path = None
        logger.info("No final prompt generated. Skipping text repair.")
    
    return result_image_path


def _prepare_text_repair_prompt(detected_txt: str, expected_txt: str) -> str:
    
    prompt = f"""
    You are editing an image that might contains visible branding and text description. 

    Instructions:
    1. Replace every instance of “{detected_txt}” with “{expected_txt}”,  preserving the original casing style — if the existing text is in all uppercase, the replacement must also appear in all uppercase.
    2. Maintain the original font style, size, color, positioning, and alignment exactly as seen in the source image. The updated text must seamlessly match the formatting and spatial layout of the original.
    3. Ensure the new text blends naturally with the surrounding design — matching textures, shadows, lighting, and perspective.
    4. Do not alter any other elements of the image or introduce additional text.
    5. Return only the edited image with the updated text.
    """

    return prompt

def _prepare_render_text_prompt(ctx: PipelineContext) -> str:
    
    # Get main object
    _, main_obj = get_image_ctx_and_main_object(ctx)

    # Get image ctx
    processing_context = ctx.original_pipeline_data.get('processing_context')
    image_ctx_json = processing_context.get('generated_image_prompts')[ctx.generation_index]
    
    prompt_render = f"""
    You are editing an image to render promotional text onto it based on the following precise visual specification.

    **Contextual References**:
    - Main Object : {main_obj}
    - Text Styling Details: {image_ctx_json['visual_concept']['promotional_text_visuals']}
    
    **Instructions**:
    1. Carefully study the Text Styling Details to guide the appearance and placement of the promotional text.
    - These details serve as **style inspiration**, not fixed spatial rules.
    - You may adapt **positioning or layout** of the text to suit the image without compromising legibility or aesthetics.
    2. **Do not alter, shrink, resize, reposition, or visually obstruct** the main object (“{main_obj}”) in any way.
    - The object must remain visually dominant and unchanged in size, scale, and placement.
    - Preserve all existing content and composition in the image.
    3. **Flexibly adjust** the position of the promotional text to maintain:
    - Visual harmony with the scene
    - Clear readability without disrupting important visual elements
    - Balance in the overall composition (e.g., avoid crowding or overlapping)
    4. Do not generate or introduce any additional visual elements, effects, or annotations beyond what is required to render the described text.
    5. The final result should be clean, cohesive, and professionally styled — as if the text was originally designed into the image.
    6. Return only the final edited image with the rendered promotional text. Do not include design overlays, reference images, or explanatory labels.
    """
    return prompt_render