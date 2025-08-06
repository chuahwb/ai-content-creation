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


def _get_prompt_prefix(is_style_adaptation: bool, has_reference: bool, has_logo: bool, has_instruction: bool, instruction_text: str) -> str:
    """Determines the correct prompt prefix based on the scenario using clear, readable conditions."""

    # Style adaptation is a distinct mode that overrides other scenarios.
    # if is_style_adaptation:
    #     logo_integration_phrase = ", integrating the provided logo," if has_logo else ""
    #     return (
    #         f"Adapt the provided reference image{logo_integration_phrase} to match the following detailed visual concept. "
    #         "Focus on applying the stylistic elements (lighting, color, mood, texture) from the description to the composition of the reference image: "
    #     )

    # Scenarios with a reference image
    if has_reference:
        if has_logo:  # Complex Edit (Reference + Logo)
            if has_instruction:
                return f"Based on the provided primary reference image and the secondary image as a logo, modify it according to the user instruction '{instruction_text}' to achieve the following detailed visual concept: "
            else:
                return "Using the provided primary reference image and the secondary logo image, create a composition that integrates both elements according to the following detailed visual concept: "
        else:  # Reference Image Only
            if has_instruction: # Instructed Edit
                return f"Based on the provided reference image, modify it according to the user instruction '{instruction_text}' to achieve the following detailed visual concept: "
            else: # Default Edit (Preserve Subject)
                return "Edit the provided image. Preserve the main subject exactly as it is in the original image. Modify only the surrounding context (background, lighting, style, composition, etc.) to match this description: "

    # Scenarios without a reference image
    if has_logo:  # Logo Only
        if has_instruction:
            return f"Using the provided logo, adapt it according to the user instruction '{instruction_text}' to achieve the following detailed visual concept: "
        else:
            return "Integrate the provided logo into the following detailed visual concept: "

    # Full Generation (no reference, no logo)
    return "Create an image based on the following detailed visual concept: "


def _assemble_core_description(vc: Dict[str, Any], user_inputs: Dict[str, Any], include_main_subject: bool) -> str:
    """Assembles the core descriptive parts of the prompt."""
    parts = []
    
    if include_main_subject:
        parts.append(vc.get("main_subject"))
        
    parts.append(f"Composition and Framing: {vc.get('composition_and_framing')}")
    parts.append(f"Background: {vc.get('background_environment')}")
    
    if vc.get("foreground_elements"):
        parts.append(f"Foreground elements: {vc.get('foreground_elements')}")
        
    parts.append(f"Lighting & Mood: {vc.get('lighting_and_mood')}")
    parts.append(f"Color Palette: {vc.get('color_palette')}")
    parts.append(f"Visual Style: {vc.get('visual_style')}")
    
    if vc.get("texture_and_details"):
        parts.append(f"Textures & Details: {vc.get('texture_and_details')}")
        
    if user_inputs.get("render_text", False) and vc.get("promotional_text_visuals"):
        parts.append(f"Promotional Text Visuals: {vc.get('promotional_text_visuals')}")
        
    if user_inputs.get("apply_branding", False) and vc.get("branding_visuals"):
        parts.append(f"Branding Visuals: {vc.get('branding_visuals')}")
        
    if vc.get("negative_elements"):
        parts.append(f"Negative Elements to Avoid: {vc.get('negative_elements')}")
        
    return " ".join(filter(None, parts))


def assemble_final_prompt(structured_prompt_data: Dict[str, Any], user_inputs: Dict[str, Any], platform_aspect_ratio: str) -> str:
    """Assembles the final text prompt string from the structured visual concept details."""
    if not structured_prompt_data:
        return "Error: Invalid structured prompt data for assembly."

    # Extract visual concept - now consistent for both regular and style adaptation runs
    vc = structured_prompt_data.get("visual_concept")
    
    if not vc:
        return "Error: 'visual_concept' not found in structured prompt data."

    image_reference = user_inputs.get("image_reference")
    brand_kit = user_inputs.get("brand_kit")
    is_style_adaptation_run = user_inputs.get("is_style_adaptation_run", False)

    # Determine context from inputs
    has_reference = image_reference is not None
    has_logo = brand_kit is not None and brand_kit.get("saved_logo_path_in_run_dir") is not None
    has_instruction = has_reference and image_reference.get("instruction")
    instruction_text = image_reference.get("instruction", "") if has_instruction else ""
    
    # Determine the appropriate prompt prefix
    prefix = _get_prompt_prefix(
        is_style_adaptation=is_style_adaptation_run,
        has_reference=has_reference,
        has_logo=has_logo,
        has_instruction=has_instruction,
        instruction_text=instruction_text
    )

    # The main subject is only needed if there's no reference image to define it.
    include_main_subject = not has_reference
    
    core_description = _assemble_core_description(
        vc=vc,
        user_inputs=user_inputs,
        include_main_subject=include_main_subject
    )

    supported_aspect_ratio_for_prompt = map_to_supported_aspect_ratio_for_prompt(platform_aspect_ratio)
    
    suffix = f" IMPORTANT: Ensure the image strictly adheres to a {supported_aspect_ratio_for_prompt} aspect ratio."
    
    final_prompt_str = f"{prefix}{core_description}{suffix}"
    
    return final_prompt_str


async def run(ctx: PipelineContext) -> None:
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
    is_style_adaptation_run = hasattr(ctx, 'adaptation_context') and ctx.adaptation_context is not None
    
    # Build user_inputs dict from context fields for compatibility with assemble_final_prompt
    user_inputs = {
        "image_reference": ctx.image_reference,
        "brand_kit": ctx.brand_kit,
        "render_text": ctx.render_text,
        "apply_branding": ctx.apply_branding,
        "is_style_adaptation_run": is_style_adaptation_run,
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
        has_logo = ctx.brand_kit is not None and ctx.brand_kit.get("saved_logo_path_in_run_dir") is not None
        has_instruction = has_reference and ctx.image_reference.get("instruction")
        
        # Determine assembly type
        assembly_type = "full_generation"  # Default
        if is_style_adaptation_run:
            assembly_type = "style_adaptation_edit"
            ctx.log("   (Assembling prompt for style adaptation edit)")
        elif has_reference and has_logo:
            assembly_type = "complex_edit"
            ctx.log("   (Assembling complex prompt for reference image + logo editing)")
        elif has_logo and not has_reference:
            assembly_type = "logo_only_edit"
            ctx.log("   (Assembling prompt for logo-only editing)")
        elif has_reference and not has_instruction:
            assembly_type = "default_edit"
            ctx.log("   (Assembling simplified prompt for default image edit - preserving subject)")
        elif has_reference and has_instruction:
            assembly_type = "instructed_edit"
            ctx.log("   (Assembling prompt for instructed image edit)")
        else:
            ctx.log("   (Assembling full prompt for generation)")
        
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
            "assembly_type": assembly_type,
            "platform_aspect_ratio": platform_aspect_ratio,
            "supported_aspect_ratio": map_to_supported_aspect_ratio_for_prompt(platform_aspect_ratio),
            "has_reference": has_reference,
            "has_logo": has_logo,
            "has_instruction": has_instruction,
            "is_style_adaptation": is_style_adaptation_run,
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
    
    # Log summary with new assembly types
    for prompt_data in assembled_prompts:
        ctx.log(f"   Strategy {prompt_data['index']}: {prompt_data['assembly_type']} ({len(prompt_data['prompt'])} chars)") 