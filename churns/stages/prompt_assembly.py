"""
Stage 5: Prompt Assembly

Assembles the final text prompt strings from structured visual concept details
for image generation. Handles different scenarios including default edits,
instructed edits, and full generation.

Extracted from original monolith: assemble_final_prompt function (~line 2063)
"""

from typing import Dict, Any, Optional, List
from ..pipeline.context import PipelineContext


def map_to_supported_aspect_ratio_for_prompt(aspect_ratio: str, ctx: Optional[PipelineContext] = None) -> str:
    """Maps input aspect ratio to a supported aspect ratio string (1:1, 2:3, 3:2) for use in the image generation prompt."""
    # This mapping is for the textual prompt, not necessarily the API size parameter
    if aspect_ratio == "1:1": 
        return "1:1"
    elif aspect_ratio in ["9:16", "3:4", "2:3"]: 
        return "2:3"  # Vertical
    elif aspect_ratio == "16:9" or aspect_ratio == "1.91:1": 
        return "3:2"  # Horizontal
    else:
        warning_msg = f"WARNING: Unsupported aspect ratio '{aspect_ratio}' for prompt text. Defaulting to '1:1'."
        if ctx:
            ctx.log(warning_msg)
        else:
            print(warning_msg)
        return "1:1"


def assemble_final_prompt(structured_prompt_data: Dict[str, Any], user_inputs: Dict[str, Any], platform_aspect_ratio: str) -> str:
    """Assembles the final text prompt string from the structured visual concept details."""
    if not structured_prompt_data or "visual_concept" not in structured_prompt_data:
        return "Error: Invalid structured prompt data for assembly."
    
    vc = structured_prompt_data["visual_concept"]
    image_reference = user_inputs.get("image_reference")
    has_reference = image_reference is not None
    has_instruction = has_reference and image_reference.get("instruction")
    instruction_text = image_reference.get("instruction", "") if has_instruction else ""
    supported_aspect_ratio_for_prompt = map_to_supported_aspect_ratio_for_prompt(platform_aspect_ratio)
    is_default_edit_scenario = has_reference and not has_instruction and vc.get("main_subject") is None

    final_prompt_str = ""
    
    if is_default_edit_scenario:
        # Assembling simplified prompt for default image edit - preserving subject
        prefix = "Edit the provided image. Preserve the main subject exactly as it is in the original image. Modify only the surrounding context (background, lighting, style, composition, etc.) to match this description: "
        context_parts = [
            vc.get("composition_and_framing"), 
            f"Background: {vc.get('background_environment')}",
            f"Foreground elements: {vc.get('foreground_elements')}" if vc.get("foreground_elements") else None,
            f"Lighting & Mood: {vc.get('lighting_and_mood')}", 
            f"Color Palette: {vc.get('color_palette')}",
            f"Visual Style: {vc.get('visual_style')}",
            f"Textures & Details: {vc.get('texture_and_details')}" if vc.get("texture_and_details") else None,
            f"Promotional Text Visuals: {vc.get('promotional_text_visuals')}" if user_inputs.get("render_text", False) and vc.get("promotional_text_visuals") else None,
            f"Branding Visuals: {vc.get('branding_visuals')}" if user_inputs.get("apply_branding", False) and vc.get("branding_visuals") else None,
            f"Avoid the following elements: {vc.get('negative_elements')}" if vc.get("negative_elements") else None,
        ]
        context_description = " ".join(filter(None, context_parts))
        final_prompt_str = f"{prefix}{context_description} IMPORTANT: Ensure the image strictly adheres to a {supported_aspect_ratio_for_prompt} aspect ratio."
    else:
        # Assembling full prompt for generation or instructed edit
        core_description_parts = [
            vc.get("main_subject"), 
            vc.get("composition_and_framing"),
            f"Background: {vc.get('background_environment')}",
            f"Foreground elements: {vc.get('foreground_elements')}" if vc.get("foreground_elements") else None,
            f"Lighting & Mood: {vc.get('lighting_and_mood')}", 
            f"Color Palette: {vc.get('color_palette')}",
            f"Visual Style: {vc.get('visual_style')}",
            f"Textures & Details: {vc.get('texture_and_details')}" if vc.get("texture_and_details") else None,
            f"Promotional Text Visuals: {vc.get('promotional_text_visuals')}" if user_inputs.get("render_text", False) and vc.get("promotional_text_visuals") else None,
            f"Branding Visuals: {vc.get('branding_visuals')}" if user_inputs.get("apply_branding", False) and vc.get("branding_visuals") else None,
            f"Avoid the following elements: {vc.get('negative_elements')}" if vc.get("negative_elements") else None,
        ]
        core_description = " ".join(filter(None, core_description_parts))
        prefix = ""
        if has_reference and has_instruction: 
            prefix = f"Based on the provided reference image, modify it according to the user instruction '{instruction_text}' to achieve the following detailed visual concept: "
        final_prompt_str = f"{prefix}{core_description} IMPORTANT: Ensure the image strictly adheres to a {supported_aspect_ratio_for_prompt} aspect ratio."
    
    return final_prompt_str


def run(ctx: PipelineContext) -> None:
    """
    Stage 5: Prompt Assembly
    
    Assembles final text prompts from structured visual concepts for image generation.
    Processes all generated image prompts and creates final assembled prompts.
    
    Input: ctx.generated_image_prompts (list of ImageGenerationPrompt dicts)
    Output: ctx.final_assembled_prompts (list of assembled prompt strings)
    """
    ctx.log("Starting Prompt Assembly stage...")
    
    # Get data from previous stages
    structured_prompts = ctx.generated_image_prompts or []
    
    # Build user_inputs dict from context fields for compatibility with assemble_final_prompt
    user_inputs = {
        "image_reference": ctx.image_reference,
        "render_text": ctx.render_text,
        "apply_branding": ctx.apply_branding
    }
    
    # Get platform aspect ratio
    platform_info = ctx.target_platform or {}
    platform_aspect_ratio = platform_info.get("resolution_details", {}).get("aspect_ratio", "1:1")
    
    if not structured_prompts:
        ctx.log("WARNING: No structured prompts available for assembly")
        ctx.final_assembled_prompts = []
        return
    
    ctx.log(f"Assembling {len(structured_prompts)} final prompts...")
    
    assembled_prompts = []
    
    for i, struct_prompt in enumerate(structured_prompts):
        strategy_index = struct_prompt.get("source_strategy_index", i)
        
        ctx.log(f"Assembling prompt for Strategy {strategy_index}...")
        
        # Determine assembly type based on context
        has_reference = ctx.image_reference is not None
        has_instruction = has_reference and ctx.image_reference.get("instruction")
        
        if has_reference and not has_instruction:
            ctx.log("   (Assembling simplified prompt for default image edit - preserving subject)")
        else:
            ctx.log("   (Assembling full prompt for generation or instructed edit)")
        
        # Assemble the final prompt
        final_prompt = assemble_final_prompt(
            struct_prompt, 
            user_inputs, 
            platform_aspect_ratio
        )
        
        # Store the assembled prompt with metadata
        assembled_prompt_data = {
            "index": strategy_index,
            "prompt": final_prompt,
            "assembly_type": "default_edit" if (has_reference and not has_instruction) else "full_generation",
            "platform_aspect_ratio": platform_aspect_ratio,
            "supported_aspect_ratio": map_to_supported_aspect_ratio_for_prompt(platform_aspect_ratio)
        }
        
        assembled_prompts.append(assembled_prompt_data)
        
        # Log preview of assembled prompt
        prompt_preview = final_prompt[:200] + "..." if len(final_prompt) > 200 else final_prompt
        ctx.log(f"   Assembled prompt preview: {prompt_preview}")
        
        # Check for assembly errors
        if final_prompt.startswith("Error:"):
            ctx.log(f"   ERROR assembling prompt for Strategy {strategy_index}: {final_prompt}")
    
    # Store results in context
    ctx.final_assembled_prompts = assembled_prompts
    
    ctx.log(f"✅ Successfully assembled {len(assembled_prompts)} final prompts")
    
    # Log summary
    for prompt_data in assembled_prompts:
        ctx.log(f"   Strategy {prompt_data['index']}: {prompt_data['assembly_type']} ({len(prompt_data['prompt'])} chars)") 