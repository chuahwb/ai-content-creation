"""
Prompt Refine Stage - Refinement Pipeline

This stage performs prompt-based image refinement with optional masking.
Combines regional editing (with masks) and general refinement capabilities.

IMPLEMENTATION GUIDANCE:
- Use user prompt to guide image modifications
- Support optional mask-based regional editing
- Leverage original generation context for consistency
- Consider using: Stable Diffusion Inpainting/Img2Img, DALL-E Edit, etc.
"""

import os
import json
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from PIL import Image, ImageDraw
from ..pipeline.context import PipelineContext
from ..models import CostDetail


def run(ctx: PipelineContext) -> None:
    """
    Perform prompt-based image refinement with optional masking.
    
    REQUIRED CONTEXT INPUTS:
    - ctx.base_image_path: Path to the base image to modify
    - ctx.prompt: User refinement prompt
    - ctx.refinement_type: Should be "prompt"
    - ctx.creativity_level: 1-3 for modification intensity
    - ctx.mask_coordinates: Optional mask coordinates for regional editing
    - ctx.original_pipeline_data: Original generation metadata for context
    
    SETS CONTEXT OUTPUTS:
    - ctx.refinement_result: Dict with result information
    - ctx.refinement_cost: Cost of the operation
    
    IMPLEMENTATION REQUIREMENTS:
    1. Load base image and parse mask (if provided)
    2. Prepare refinement prompt with context
    3. Apply regional or global image modification
    4. Maintain consistency with original generation
    5. Save result and update context
    """
    
    ctx.log("Starting prompt refinement stage...")
    
    # Validate required inputs
    _validate_inputs(ctx)
    
    # Load base image
    base_image = _load_base_image(ctx)
    
    # Parse and create mask if provided
    mask = _create_mask_from_coordinates(ctx, base_image.size)
    
    # Prepare refinement prompt with context
    refined_prompt = _prepare_refinement_prompt(ctx)
    
    # TODO: IMPLEMENT ACTUAL PROMPT REFINEMENT LOGIC
    result_image = _perform_prompt_refinement(ctx, base_image, refined_prompt, mask)
    
    # Save result
    output_path = _save_result_image(ctx, result_image)
    
    # Update context with results
    ctx.refinement_result = {
        "type": "prompt_refinement",
        "status": "completed",
        "output_path": output_path,
        "modifications": {
            "prompt_used": refined_prompt,
            "mask_applied": mask is not None,
            "regional_edit": mask is not None,
            "creativity_level": ctx.creativity_level
        }
    }
    
    # Track costs
    ctx.refinement_cost = _calculate_cost(ctx, mask is not None)
    
    ctx.log(f"Prompt refinement completed: {output_path}")


def _validate_inputs(ctx: PipelineContext) -> None:
    """Validate required inputs for prompt refinement."""
    
    if not ctx.base_image_path or not os.path.exists(ctx.base_image_path):
        raise ValueError("Base image path is required and must exist")
    
    if ctx.refinement_type != "prompt":
        raise ValueError(f"Invalid refinement type for prompt refinement: {ctx.refinement_type}")
    
    if not ctx.prompt:
        raise ValueError("Refinement prompt is required for prompt refinement")


def _load_base_image(ctx: PipelineContext) -> Image.Image:
    """Load and validate the base image for prompt refinement."""
    
    try:
        image = Image.open(ctx.base_image_path)
        ctx.log(f"Loaded base image: {image.size} {image.mode}")
        
        # Ensure RGB mode for processing
        if image.mode != 'RGB':
            image = image.convert('RGB')
            ctx.log(f"Converted image to RGB mode")
        
        return image
        
    except Exception as e:
        raise ValueError(f"Failed to load base image: {e}")


def _create_mask_from_coordinates(ctx: PipelineContext, image_size: Tuple[int, int]) -> Optional[Image.Image]:
    """
    Create a mask image from coordinate data for regional editing.
    
    IMPLEMENTATION NOTES:
    - Parse mask_coordinates JSON string
    - Support multiple shapes: rectangles, circles, polygons
    - Create binary mask (white = edit region, black = preserve)
    - Handle coordinate normalization and scaling
    
    MASK COORDINATE FORMATS:
    1. Rectangle: {"type": "rectangle", "x1": 0.1, "y1": 0.1, "x2": 0.9, "y2": 0.9}
    2. Circle: {"type": "circle", "cx": 0.5, "cy": 0.5, "radius": 0.3}
    3. Polygon: {"type": "polygon", "points": [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]}
    4. Freehand: {"type": "freehand", "strokes": [[[x1,y1], [x2,y2], ...], ...]}
    """
    
    if not ctx.mask_coordinates:
        ctx.log("No mask coordinates provided, performing global refinement")
        return None
    
    try:
        # Parse mask coordinates
        mask_data = json.loads(ctx.mask_coordinates) if isinstance(ctx.mask_coordinates, str) else ctx.mask_coordinates
        ctx.log(f"Creating mask from coordinates: {mask_data.get('type', 'unknown')}")
        
        # Create blank mask (black = preserve, white = edit)
        mask = Image.new('L', image_size, 0)
        draw = ImageDraw.Draw(mask)
        
        width, height = image_size
        
        if mask_data.get('type') == 'rectangle':
            # Convert normalized coordinates to pixels
            x1 = int(mask_data['x1'] * width)
            y1 = int(mask_data['y1'] * height)
            x2 = int(mask_data['x2'] * width)
            y2 = int(mask_data['y2'] * height)
            
            draw.rectangle([x1, y1, x2, y2], fill=255)
            ctx.log(f"Created rectangular mask: ({x1}, {y1}) to ({x2}, {y2})")
            
        elif mask_data.get('type') == 'circle':
            # Convert normalized coordinates to pixels
            cx = int(mask_data['cx'] * width)
            cy = int(mask_data['cy'] * height)
            radius = int(mask_data['radius'] * min(width, height))
            
            draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=255)
            ctx.log(f"Created circular mask: center ({cx}, {cy}), radius {radius}")
            
        elif mask_data.get('type') == 'polygon':
            # Convert normalized coordinates to pixels
            points = []
            for point in mask_data['points']:
                x = int(point[0] * width)
                y = int(point[1] * height)
                points.append((x, y))
            
            draw.polygon(points, fill=255)
            ctx.log(f"Created polygon mask with {len(points)} points")
            
        else:
            ctx.log(f"Warning: Unsupported mask type: {mask_data.get('type')}")
            return None
        
        return mask
        
    except Exception as e:
        ctx.log(f"Warning: Failed to create mask from coordinates: {e}")
        return None


def _prepare_refinement_prompt(ctx: PipelineContext) -> str:
    """
    Prepare the refinement prompt with additional context.
    
    CONTEXT ENHANCEMENT:
    - Incorporate original generation context
    - Add style and aesthetic guidance
    - Include marketing strategy context
    - Enhance prompt for better results
    """
    
    base_prompt = ctx.prompt
    
    # Add context from original generation if available
    if ctx.original_pipeline_data:
        processing_context = ctx.original_pipeline_data.get("processing_context", {})
        
        # Extract style guidance
        style_guidance = processing_context.get("style_guidance_sets", [])
        if style_guidance:
            style_keywords = []
            for guidance in style_guidance:
                if isinstance(guidance, dict) and "style_keywords" in guidance:
                    style_keywords.extend(guidance["style_keywords"])
            
            if style_keywords:
                style_context = f", maintaining {', '.join(style_keywords[:3])} style"
                base_prompt += style_context
        
        # Extract marketing context
        strategies = processing_context.get("suggested_marketing_strategies", [])
        if strategies and len(strategies) > 0:
            strategy = strategies[0]  # Use first strategy
            if isinstance(strategy, dict):
                audience = strategy.get("target_audience", "")
                if audience:
                    base_prompt += f", appealing to {audience}"
    
    # Add creativity level guidance
    creativity_guidance = {
        1: "subtle, conservative changes",
        2: "moderate adjustments", 
        3: "creative, bold modifications"
    }
    
    guidance = creativity_guidance.get(ctx.creativity_level, "moderate adjustments")
    enhanced_prompt = f"{base_prompt}, applying {guidance}"
    
    ctx.log(f"Enhanced refinement prompt: {enhanced_prompt}")
    return enhanced_prompt


def _perform_prompt_refinement(ctx: PipelineContext, base_image: Image.Image, prompt: str, mask: Optional[Image.Image]) -> Image.Image:
    """
    PLACEHOLDER: Perform the actual prompt-based refinement.
    
    IMPLEMENTATION STRATEGY:
    
    1. CHOOSE REFINEMENT METHOD:
       - Global editing (no mask): Use img2img with prompt
       - Regional editing (with mask): Use inpainting with prompt
       - Consider model capabilities and image requirements
    
    2. GLOBAL REFINEMENT (NO MASK):
       - Use Stable Diffusion img2img pipeline
       - Set appropriate strength based on creativity level
       - Maintain image composition and main elements
       - Options: SDXL, SD 1.5, or custom trained models
    
    3. REGIONAL REFINEMENT (WITH MASK):
       - Use Stable Diffusion inpainting pipeline
       - Apply mask to limit changes to specific regions
       - Blend seamlessly with unchanged areas
       - Consider mask feathering for smooth transitions
    
    4. ADVANCED TECHNIQUES:
       - Use ControlNet for better structure preservation
       - Apply IP-Adapter for style consistency
       - Use depth maps or edge detection for guidance
       - Consider multiple passes for complex changes
    
    5. POST-PROCESSING:
       - Apply color correction if needed
       - Enhance details and sharpness
       - Ensure consistency with original style
    
    RECOMMENDED TOOLS/APIS:
    - Stable Diffusion WebUI API
    - Hugging Face Diffusers library
    - Replicate API for hosted models
    - OpenAI DALL-E Edit API
    - Custom fine-tuned models for specific domains
    
    RETURN:
    - Refined image based on prompt and optional mask
    """
    
    ctx.log("PLACEHOLDER: Performing prompt refinement...")
    ctx.log(f"Prompt: {prompt}")
    ctx.log(f"Has mask: {mask is not None}")
    ctx.log(f"Creativity level: {ctx.creativity_level}")
    
    # TODO: Replace with actual implementation
    
    # IMPLEMENTATION PSEUDOCODE:
    """
    if mask is not None:
        # Regional editing with inpainting
        result = stable_diffusion_inpaint(
            image=base_image,
            mask=mask,
            prompt=prompt,
            strength=_get_strength_from_creativity(ctx.creativity_level),
            guidance_scale=7.5,
            num_inference_steps=50
        )
    else:
        # Global editing with img2img
        result = stable_diffusion_img2img(
            image=base_image,
            prompt=prompt,
            strength=_get_strength_from_creativity(ctx.creativity_level),
            guidance_scale=7.5,
            num_inference_steps=50
        )
    
    # Apply post-processing
    result = apply_post_processing(result, base_image, ctx.creativity_level)
    
    return result
    """
    
    # PLACEHOLDER: Apply simple filter for demonstration
    result_image = base_image.copy()
    
    if mask:
        # Simulate regional editing by drawing on masked area
        draw = ImageDraw.Draw(result_image)
        # Convert mask to get white regions
        mask_array = list(mask.getdata())
        width, height = mask.size
        
        for y in range(height):
            for x in range(width):
                if mask_array[y * width + x] > 128:  # White mask areas
                    # Apply slight color shift as placeholder
                    try:
                        r, g, b = result_image.getpixel((x, y))
                        new_r = min(255, r + 10)  # Slight red shift
                        result_image.putpixel((x, y), (new_r, g, b))
                    except:
                        pass
        
        ctx.log("PLACEHOLDER: Applied regional color shift to masked areas")
    else:
        # Simulate global editing
        # Apply slight brightness adjustment
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Brightness(result_image)
        brightness_factor = 1.0 + (ctx.creativity_level - 2) * 0.1  # -0.1 to +0.1
        result_image = enhancer.enhance(brightness_factor)
        
        ctx.log(f"PLACEHOLDER: Applied global brightness adjustment ({brightness_factor:.2f})")
    
    ctx.log("WARNING: Using placeholder - returning modified image")
    return result_image


def _save_result_image(ctx: PipelineContext, result_image: Image.Image) -> str:
    """Save the result image to the appropriate location."""
    
    # Create output directory
    output_dir = Path(f"./data/runs/{ctx.parent_run_id}/refinements")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate filename
    parent_id = ctx.parent_image_id
    if ctx.parent_image_type == "original":
        parent_id = f"{ctx.generation_index}"
    
    filename = f"{ctx.run_id}_from_{parent_id}.png"
    output_path = output_dir / filename
    
    # Save image
    try:
        result_image.save(output_path, format='PNG', optimize=True)
        ctx.log(f"Saved result image: {output_path}")
        return str(output_path)
        
    except Exception as e:
        raise RuntimeError(f"Failed to save result image: {e}")


def _calculate_cost(ctx: PipelineContext, has_mask: bool) -> float:
    """
    Calculate cost for prompt refinement operation.
    
    COST FACTORS:
    - Type of operation (global vs regional)
    - Image resolution and processing complexity
    - Number of inference steps
    - Model used (SD 1.5 vs SDXL vs custom)
    - Creativity level (affects inference steps)
    """
    
    # Base costs (these are estimates, adjust based on actual providers)
    if has_mask:
        # Inpainting typically costs more due to complexity
        base_cost = 0.04
    else:
        # img2img operation
        base_cost = 0.03
    
    # Adjust based on creativity level (higher = more inference steps)
    creativity_multiplier = {1: 0.8, 2: 1.0, 3: 1.4}
    total_cost = base_cost * creativity_multiplier.get(ctx.creativity_level, 1.0)
    
    # Additional cost for high-resolution images (if needed)
    # This would be determined by actual image dimensions
    
    ctx.log(f"Estimated prompt refinement cost: ${total_cost:.3f} ({'regional' if has_mask else 'global'} edit)")
    return total_cost


def _track_stage_cost(ctx: PipelineContext) -> None:
    """Track detailed cost information for this stage."""
    
    try:
        has_mask = ctx.mask_coordinates is not None
        operation_type = "inpainting" if has_mask else "img2img"
        
        cost_detail = CostDetail(
            stage_name="prompt_refine",
            model_id="stable_diffusion_refinement",
            provider="sd_api_provider",
            duration_seconds=8.0,  # Typical SD inference time
            total_stage_cost_usd=ctx.refinement_cost or 0.0,
            cost_calculation_notes=f"Prompt-based {operation_type} refinement"
        )
        
        # Add to context cost summary
        if ctx.cost_summary and 'stage_costs' in ctx.cost_summary:
            ctx.cost_summary['stage_costs'].append(cost_detail.model_dump())
            
    except Exception as e:
        ctx.log(f"Warning: Could not track cost for prompt_refine stage: {e}") 