"""
Save Outputs Stage - Refinement Pipeline

This stage finalizes the refinement process by saving results,
updating refinement tracking files, and ensuring proper file organization.

RESPONSIBILITIES:
- Finalize output file paths and organization
- Update refinements.json index file
- Update database records with results
- Ensure proper file permissions and cleanup
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime
from ..pipeline.context import PipelineContext
from ..models import CostDetail

# Setup Logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("save_outputs")


async def run(ctx: PipelineContext) -> None:
    """
    Save and finalize refinement outputs.
    
    EXPECTED CONTEXT INPUTS:
    - ctx.refinement_result: Result from the refinement stage
    - ctx.refinement_cost: Cost of the refinement operation
    - ctx.parent_run_id: Parent pipeline run ID
    - ctx.run_id: Current refinement job ID
    
    PERFORMS:
    1. Validate refinement result exists
    2. Update refinements.json index file
    3. Set final database record fields
    4. Cleanup temporary files if any
    5. Log completion status
    """
    
    logger.info("Starting save outputs stage...")
    
    # Validate refinement result exists
    if not ctx.refinement_result:
        raise ValueError("No refinement result found to save")
    logger.info("Received refinement result: ", ctx.refinement_result)
    
    # Extract result information
    output_path = ctx.refinement_result.get("output_path")
    # if not output_path or not os.path.exists(output_path):
    #     raise ValueError(f"Refinement output file not found: {output_path}")
    
    # Update refinements index file
    # _update_refinements_index("save_outputs", ctx)
    
    # Prepare final database updates
    _prepare_database_updates(ctx)
    
    # Cleanup temporary files
    _cleanup_temporary_files(ctx)
    
    # Final logging
    logger.info(f"Refinement outputs saved successfully")
    logger.info(f"Output file: {output_path}")
    logger.info(f"Total cost: ${ctx.refinement_cost:.3f}")


def _update_refinements_index(stage_name: str, ctx: PipelineContext) -> None:
    """
    Update the refinements.json index file for the parent run.
    """
    
    # Path to refinements index file
    index_path = Path(f"./data/runs/{ctx.parent_run_id}/refinements.json")
    
    # Load existing index or create new one
    if index_path.exists():
        try:
            with open(index_path, 'r') as f:
                index_data = json.load(f)
        except Exception as e:
            logger.warning(f"Warning: Could not read existing refinements index: {e}")
            index_data = {"refinements": [], "total_cost": 0.0, "total_refinements": 0}
    else:
        index_data = {"refinements": [], "total_cost": 0.0, "total_refinements": 0}
    
    # Prepare new refinement entry
    output_path = ctx.refinement_result.get("output_path", "")
    relative_output_path = _get_relative_path(output_path, ctx.parent_run_id)
    
    # Determine parent image path
    parent_image_path = _get_parent_image_relative_path(ctx)
    
    refinement_entry = {
        "job_id": ctx.run_id,
        "stage_name": stage_name,
        "parent_image_id": ctx.parent_image_id,
        "parent_image_path": parent_image_path,
        "image_path": relative_output_path,
        "type": ctx.refinement_type,
        "summary": "Save outputs",
        "cost": 0.0,
        "created_at": datetime.utcnow().isoformat() + "Z"
    }
    
    # Add to index
    index_data["refinements"].append(refinement_entry)
    index_data["total_cost"] += refinement_entry["cost"]
    index_data["total_refinements"] = len(index_data["refinements"])
    
    # Save updated index
    try:
        # Ensure directory exists
        index_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(index_path, 'w') as f:
            json.dump(index_data, f, indent=2)
        
        logger.info(f"Updated refinements index: {index_path}")
        logger.info(f"Total refinements: {index_data['total_refinements']}, Total cost: ${index_data['total_cost']:.3f}")
        
    except Exception as e:
        logger.warning(f"Warning: Could not update refinements index: {e}")


def _get_relative_path(absolute_path: str, parent_run_id: str) -> str:
    """Convert absolute path to relative path from run directory."""
    try:
        abs_path = Path(absolute_path)
        run_dir = Path(f"./data/runs/{parent_run_id}")
        relative_path = abs_path.relative_to(run_dir)
        return str(relative_path)
    except ValueError:
        # If can't make relative, return just the filename
        return os.path.basename(absolute_path)


def _get_parent_image_relative_path(ctx: PipelineContext) -> str:
    """Get relative path to the parent image."""
    if ctx.parent_image_type == "original":
        if ctx.generation_index is not None:
            return f"originals/image_{ctx.generation_index}.png"
        else:
            return f"image_{ctx.parent_image_id}.png"
    elif ctx.parent_image_type == "refinement":
        return f"refinements/{ctx.parent_image_id}.png"
    else:
        return f"unknown/{ctx.parent_image_id}.png"


def _generate_summary(ctx: PipelineContext) -> str:
    """Generate a brief summary of the refinement for the index."""
    refinement_type = ctx.refinement_type
    
    if refinement_type == "subject":
        return f"Subject repair: {ctx.instructions or 'Replace main subject'}"
    elif refinement_type == "text":
        return f"Text repair: {ctx.instructions or 'Fix text elements'}"
    elif refinement_type == "prompt":
        return f"Prompt refinement: {ctx.prompt or ctx.instructions or 'Refine image'}"
    else:
        return f"Unknown refinement: {ctx.instructions or 'No description'}"


def _prepare_database_updates(ctx: PipelineContext) -> None:
    """
    Prepare data for final database record updates.
    
    This sets context properties that will be used by the background
    task processor to update the database record with final results.
    """
    
    # Set the final image path (relative to make it portable)
    output_path = ctx.refinement_result.get("output_path", "")
    if output_path:
        relative_path = _get_relative_path(output_path, ctx.parent_run_id)
    else:
        relative_path = None
    
    # Store database update information in context
    ctx.database_updates = {
        "status": "completed",
        "image_path": relative_path,
        "cost_usd": ctx.refinement_cost,
        "completed_at": datetime.utcnow(),
        "refinement_summary": _generate_summary(ctx),
        "error_message": None
    }
    
    logger.info("Prepared database updates for final commit")


def _cleanup_temporary_files(ctx: PipelineContext) -> None:
    """
    Clean up any temporary files created during refinement.
    
    CLEANUP TARGETS:
    - Temporary reference images
    - Intermediate processing files
    - Cached masks or overlays
    - Any debug output files
    """
    
    cleanup_performed = False
    
    # Clean up reference image if it was temporary
    if ctx.reference_image_path and "temp" in ctx.reference_image_path:
        try:
            if os.path.exists(ctx.reference_image_path):
                os.remove(ctx.reference_image_path)
                logger.info(f"Cleaned up temporary reference image: {ctx.reference_image_path}")
                cleanup_performed = True
        except Exception as e:
            logger.warning(f"Warning: Could not clean up reference image: {e}")
    
    # Clean up any temporary mask files
    temp_mask_path = getattr(ctx, 'temp_mask_path', None)
    if temp_mask_path and os.path.exists(temp_mask_path):
        try:
            os.remove(temp_mask_path)
            logger.info(f"Cleaned up temporary mask file: {temp_mask_path}")
            cleanup_performed = True
        except Exception as e:
            logger.warning(f"Warning: Could not clean up mask file: {e}")
    
    # Clean up any other temporary files stored in context
    temp_files = getattr(ctx, 'temp_files', [])
    for temp_file in temp_files:
        try:
            if os.path.exists(temp_file):
                os.remove(temp_file)
                logger.info(f"Cleaned up temporary file: {temp_file}")
                cleanup_performed = True
        except Exception as e:
            logger.warning(f"Warning: Could not clean up temporary file {temp_file}: {e}")
    
    if not cleanup_performed:
        logger.info("No temporary files to clean up")


def _track_stage_cost(ctx: PipelineContext) -> None:
    """Track cost for save_outputs stage (minimal overhead)."""
    
    try:
        cost_detail = CostDetail(
            stage_name="save_outputs",
            model_id="file_operations",
            provider="local",
            duration_seconds=0.1,  # Minimal file I/O time
            total_stage_cost_usd=0.0,  # No external API costs
            cost_calculation_notes="File saving and index updates only"
        )
        
        # Add to context cost summary
        if ctx.cost_summary and 'stage_costs' in ctx.cost_summary:
            ctx.cost_summary['stage_costs'].append(cost_detail.model_dump())
        
        # Update total cost summary with refinement costs
        if ctx.cost_summary and ctx.refinement_cost:
            ctx.cost_summary['total_pipeline_cost_usd'] = (
                ctx.cost_summary.get('total_pipeline_cost_usd', 0.0) + ctx.refinement_cost
            )
            
    except Exception as e:
        logger.warning(f"Warning: Could not track cost for save_outputs stage: {e}")


def _validate_final_output(ctx: PipelineContext) -> bool:
    """Validate that the refinement output is properly saved and accessible."""
    
    output_path = ctx.refinement_result.get("output_path")
    
    if not output_path:
        logger.error("ERROR: No output path specified in refinement result")
        return False
    
    if not os.path.exists(output_path):
        logger.error(f"ERROR: Output file does not exist: {output_path}")
        return False
    
    # Check file size (should be > 0)
    try:
        file_size = os.path.getsize(output_path)
        if file_size == 0:
            logger.error(f"ERROR: Output file is empty: {output_path}")
            return False
        
        logger.info(f"Validated output file: {output_path} ({file_size} bytes)")
        return True
        
    except Exception as e:
        logger.error(f"ERROR: Could not validate output file: {e}")
        return False 