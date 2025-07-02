"""
Load Base Image Stage - Refinement Pipeline

This stage loads the parent image and associated metadata into the context
for refinement operations. It supports loading both original generation
images and previously refined images.
"""

import os
import asyncio
import json
from pathlib import Path
from typing import Dict, Any, Optional
from PIL import Image
from ..pipeline.context import PipelineContext
from ..models import PipelineCostSummary, CostDetail



async def run(ctx: PipelineContext) -> None:
    """
    Load base image and metadata for refinement.
    
    Expected context properties:
    - ctx.parent_run_id: Parent pipeline run ID
    - ctx.parent_image_id: ID of the image to refine
    - ctx.parent_image_type: "original" or "refinement" 
    - ctx.generation_index: Which of N original images (if original)
    - ctx.base_image_path: Path to the base image (if already set)
    
    Sets context properties:
    - ctx.base_image_path: Full path to the loaded image
    - ctx.base_image_metadata: Metadata from the parent run
    - ctx.original_pipeline_data: Original pipeline generation data
    """
    
    ctx.log("Loading base image and metadata for refinement...")
    
    # Validate required context
    if not ctx.parent_run_id:
        raise ValueError("parent_run_id is required for refinement")
    
    if not ctx.parent_image_id:
        raise ValueError("parent_image_id is required for refinement")
    
    # Determine base image path if not already set
    if not ctx.base_image_path:
        ctx.base_image_path = _resolve_base_image_path(ctx)
    
    # Validate image exists
    if not os.path.exists(ctx.base_image_path):
        raise FileNotFoundError(f"Base image not found: {ctx.base_image_path}")
    
    # Load and validate image
    try:
        img = await asyncio.to_thread(Image.open, ctx.base_image_path)
        with img:
            ctx.log(f"Loaded base image: {img.size[0]}x{img.size[1]} {img.mode}")
            # Store basic image info
            ctx.base_image_metadata = {
                "width": img.size[0],
                "height": img.size[1],
                "mode": img.mode,
                "format": img.format,
                "size_bytes": os.path.getsize(ctx.base_image_path)
            }
    except Exception as e:
        raise ValueError(f"Invalid image file: {e}")
    
    # Load original pipeline metadata
    ctx.original_pipeline_data = _load_original_pipeline_metadata(ctx)
    
    ctx.log(f"Successfully loaded base image: {ctx.base_image_path}")


def _resolve_base_image_path(ctx: PipelineContext) -> str:
    """
    Resolve the full path to the base image based on context.
    
    Logic:
    - If parent_image_type is "original", look in originals/ directory
    - If parent_image_type is "refinement", look for specific refinement job
    - Use generation_index for original images
    """
    
    if ctx.parent_image_type == "original":
        # Original generated image
        if ctx.generation_index is None:
            raise ValueError("generation_index required for original image type")
        
        base_path = Path(f"./data/runs/{ctx.parent_run_id}")
        ctx.log(f"Resolving base image path for original image {ctx.generation_index} in {base_path}")
        # Try different naming patterns for original images
        possible_paths = [
            base_path / "originals" / f"image_{ctx.generation_index}.png",
            base_path / f"image_{ctx.generation_index}.png",
            base_path / f"generated_image_{ctx.generation_index}.png",
            base_path / f"edited_image_strategy_{ctx.generation_index}.png"
        ]
        
        for path in possible_paths:
            if path.exists():
                ctx.log(f"Found original image at: {path}")
                return str(path)
        
        raise FileNotFoundError(f"Original image not found for index {ctx.generation_index} in {base_path}")
    
    elif ctx.parent_image_type == "refinement":
        # Previously refined image
        # parent_image_id should be a refinement job ID
        base_path = Path(f"./data/runs/{ctx.parent_run_id}")
        
        # Try different naming patterns for refinement images
        possible_paths = [
            base_path / f"refinement_{ctx.parent_image_id}.png",
        ]
        
        for path in possible_paths:
            if path.exists():
                ctx.log(f"Found refinement image at: {path}")
                return str(path)
        
        raise FileNotFoundError(f"Refinement image not found for job {ctx.parent_image_id} in {base_path}")
    
    else:
        raise ValueError(f"Invalid parent_image_type: {ctx.parent_image_type}")


def _load_original_pipeline_metadata(ctx: PipelineContext) -> Dict[str, Any]:
    """
    Load metadata from the original pipeline run.
    
    This provides context about the original generation including:
    - Marketing strategies
    - Style guidance
    - Visual concepts
    - Generated prompts
    """
    
    # Look for pipeline metadata file
    base_path = Path(f"./data/runs/{ctx.parent_run_id}")
    
    possible_metadata_files = [
        base_path / "pipeline_metadata.json",
        base_path / "metadata.json",
        base_path / f"{ctx.parent_run_id}_metadata.json"
    ]
    
    for metadata_file in possible_metadata_files:
        if metadata_file.exists():
            try:
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                    ctx.log(f"Loaded pipeline metadata from: {metadata_file}")
                    return metadata
            except Exception as e:
                ctx.log(f"Failed to load metadata from {metadata_file}: {e}")
                continue
    
    # If no metadata file found, return minimal context
    ctx.log("Warning: No pipeline metadata found, proceeding with minimal context")
    return {
        "processing_context": {
            "suggested_marketing_strategies": [],
            "style_guidance_sets": [],
            "generated_image_prompts": [],
            "final_assembled_prompts": []
        }
    }


# Cost tracking (minimal for this stage)
def _track_stage_cost(ctx: PipelineContext) -> None:
    """Track cost for load_base_image stage (minimal overhead)."""
    try:
        cost_detail = CostDetail(
            stage_name="load_base_image",
            model_id="file_io",
            provider="local",
            duration_seconds=0.1,  # Minimal file I/O time
            total_stage_cost_usd=0.0,  # No external API costs
            cost_calculation_notes="File I/O operations only"
        )
        
        # Add to context cost summary
        if ctx.cost_summary and 'stage_costs' in ctx.cost_summary:
            ctx.cost_summary['stage_costs'].append(cost_detail.model_dump())
            
    except Exception as e:
        ctx.log(f"Warning: Could not track cost for load_base_image stage: {e}") 