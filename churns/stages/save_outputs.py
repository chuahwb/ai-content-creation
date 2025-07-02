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
    2. Prepare final database record fields
    3. Cleanup temporary files if any
    4. Log completion status
    """
    
    logger.info("Starting save outputs stage...")
    
    # Validate refinement result - allow cases where no result was generated
    if not hasattr(ctx, 'refinement_result') or not ctx.refinement_result:
        logger.info("No refinement result found - this may be normal for failed refinements")
        ctx.refinement_result = {
            "type": ctx.refinement_type,
            "status": "no_changes",
            "output_path": None,
            "modifications": {}
        }
    
    # Extract result information
    output_path = ctx.refinement_result.get("output_path")
    if output_path and os.path.exists(output_path):
        logger.info(f"Refinement output file found: {output_path}")
    else:
        logger.info("No refinement output file generated")
    
    # Prepare final database updates
    _prepare_database_updates(ctx)
    
    # Cleanup temporary files
    _cleanup_temporary_files(ctx)
    
    # Final logging
    refinement_status = "successful" if output_path and os.path.exists(output_path) else "no changes"
    logger.info(f"Refinement outputs processing completed - Status: {refinement_status}")
    if ctx.refinement_cost:
        logger.info(f"Total refinement cost: ${ctx.refinement_cost:.3f}")


def _get_relative_path(absolute_path: str, parent_run_id: str) -> str:
    """Convert absolute path to relative path from run directory."""
    try:
        abs_path = Path(absolute_path)
        run_dir = Path(f"./data/runs/{parent_run_id}")
        relative_path = abs_path.relative_to(run_dir)
        return str(relative_path)
    except ValueError:
        # If can't make relative, return just the filename with refinements prefix
        return f"refinements/{os.path.basename(absolute_path)}"


def _generate_summary(ctx: PipelineContext) -> str:
    """Generate a detailed summary of the refinement for the index."""
    refinement_type = ctx.refinement_type
    refinement_status = ctx.refinement_result.get("status", "unknown") if ctx.refinement_result else "unknown"
    
    # Check if refinement was successful based on output
    has_output = (ctx.refinement_result and 
                  ctx.refinement_result.get("output_path") and 
                  os.path.exists(ctx.refinement_result.get("output_path", "")))
    
    # Get error context for better messaging
    error_context = ctx.refinement_result.get("error_context") if ctx.refinement_result else None
    
    type_labels = {
        "subject": "Subject Enhancement",
        "text": "Text Enhancement", 
        "prompt": "Style Enhancement"
    }
    type_label = type_labels.get(refinement_type, "Refinement")
    
    if refinement_status == "completed" and has_output:
        return f"{type_label}: Successful"
    elif refinement_status == "no_changes_needed":
        return f"{type_label}: No changes needed"
    elif refinement_status == "failed" and error_context:
        error_type = error_context.get("error_type", "unknown")
        if error_type == "connection_error":
            return f"{type_label}: Connection failed"
        elif error_type == "rate_limit":
            return f"{type_label}: Rate limit exceeded"
        elif error_type == "api_error":
            return f"{type_label}: API error"
        elif error_type == "auth_error":
            return f"{type_label}: Authentication failed"
        else:
            return f"{type_label}: Failed"
    else:
        return f"{type_label}: {'Successful' if has_output else 'Failed'}"


def _prepare_database_updates(ctx: PipelineContext) -> None:
    """
    Prepare data for final database record updates.
    
    This sets context properties that will be used by the background
    task processor to update the database record with final results.
    """
    
    # Set the final image path (relative to make it portable)
    output_path = ctx.refinement_result.get("output_path", "")
    relative_path = None
    
    if output_path and os.path.exists(output_path):
        try:
            # Try to make path relative to parent run directory
            relative_path = _get_relative_path(output_path, ctx.parent_run_id)
        except Exception as e:
            logger.warning(f"Could not create relative path for {output_path}: {e}")
            # Fallback to just the filename
            relative_path = f"refinements/{os.path.basename(output_path)}"
    
    # Extract error information from refinement result
    error_message = None
    refinement_status = ctx.refinement_result.get("status", "unknown") if ctx.refinement_result else "unknown"
    error_context = ctx.refinement_result.get("error_context") if ctx.refinement_result else None
    
    if error_context:
        # Use the user-friendly message from error context
        error_message = error_context.get("user_message")
        if error_context.get("suggestion"):
            error_message += f" {error_context.get('suggestion')}"
    elif refinement_status == "failed" and ctx.refinement_result:
        # Fallback to basic error from modifications
        modifications = ctx.refinement_result.get("modifications", {})
        error_message = modifications.get("error", "Refinement failed for unknown reason")
    
    # Determine final status for database
    if refinement_status in ["completed", "no_changes_needed"]:
        db_status = "completed"
    else:
        db_status = "failed"
    
    # Store database update information in context
    ctx.database_updates = {
        "status": db_status,
        "image_path": relative_path,
        "cost_usd": ctx.refinement_cost or 0.0,
        "completed_at": datetime.utcnow(),
        "refinement_summary": _generate_summary(ctx),
        "error_message": error_message
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
    
    # Clean up reference image ONLY if it was temporary AND we've preserved it
    # With the new hybrid approach, reference images are preserved in refinement directories
    if ctx.reference_image_path and "temp" in ctx.reference_image_path:
        # Check if we have successfully preserved the reference image
        refinement_dir = Path(f"./data/runs/{ctx.parent_run_id}/refinements/{ctx.run_id}")
        preserved_reference = refinement_dir / "reference.png"
        
        if preserved_reference.exists():
            # Safe to clean up temp file since it's preserved
            try:
                if os.path.exists(ctx.reference_image_path):
                    os.remove(ctx.reference_image_path)
                    logger.info(f"Cleaned up temporary reference image (preserved in refinement dir): {ctx.reference_image_path}")
                    cleanup_performed = True
            except Exception as e:
                logger.warning(f"Warning: Could not clean up temporary reference image: {e}")
        else:
            logger.info(f"Skipping cleanup of reference image - not preserved in refinement directory: {ctx.reference_image_path}")
    
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