from typing import List, Optional
import os
import json
from pathlib import Path
import mimetypes
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Depends, WebSocket, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlmodel import Session, select
from sqlalchemy import desc

from churns.api.database import (
    get_session, PipelineRun, PipelineStage, RefinementJob, RefinementType,
    RunStatus, StageStatus, create_db_and_tables
)
from churns.api.schemas import (
    PipelineRunRequest, PipelineRunResponse, PipelineRunDetail, 
    RunListResponse, RunListItem, PipelineResults,
    ImageReferenceInput, MarketingGoalsInput, GeneratedImageResult,
    RefinementResponse, RefinementListResponse, RefinementResult,
    CaptionRequest, CaptionResponse, CaptionRegenerateRequest, CaptionSettings
)
from churns.api.websocket import websocket_endpoint
from churns.api.background_tasks import task_processor
from churns.core.constants import SOCIAL_MEDIA_PLATFORMS, TASK_TYPES

# Create logger
logger = logging.getLogger(__name__)

# Create routers
api_router = APIRouter(prefix="/api/v1")
runs_router = APIRouter(prefix="/runs", tags=["Pipeline Runs"])
files_router = APIRouter(prefix="/files", tags=["File Operations"])
ws_router = APIRouter(prefix="/ws", tags=["WebSocket"])


@api_router.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    create_db_and_tables()
    # Ensure data directories exist
    os.makedirs("./data/runs", exist_ok=True)


# Pipeline Run Endpoints
@runs_router.post("", response_model=PipelineRunResponse)
async def create_pipeline_run(
    # Required fields
    mode: str = Form(..., description="Pipeline mode"),
    platform_name: str = Form(..., description="Target platform"),
    creativity_level: int = Form(2, description="Creativity level 1-3"),
    num_variants: int = Form(3, description="Number of variants to generate"),
    
    # Optional text fields
    prompt: Optional[str] = Form(None, description="User prompt"),
    task_type: Optional[str] = Form(None, description="Task type"),
    task_description: Optional[str] = Form(None, description="Task description"),
    branding_elements: Optional[str] = Form(None, description="Branding elements"),
    
    # Boolean flags
    render_text: bool = Form(False, description="Render text flag"),
    apply_branding: bool = Form(False, description="Apply branding flag"),
    
    # Marketing goals (optional)
    marketing_audience: Optional[str] = Form(None, description="Marketing audience"),
    marketing_objective: Optional[str] = Form(None, description="Marketing objective"),
    marketing_voice: Optional[str] = Form(None, description="Marketing voice"),
    marketing_niche: Optional[str] = Form(None, description="Marketing niche"),
    
    # Image instruction
    image_instruction: Optional[str] = Form(None, description="Image instruction"),
    
    # File upload
    image_file: Optional[UploadFile] = File(None, description="Reference image"),
    
    session: Session = Depends(get_session)
):
    """Create a new pipeline run"""
    
    # Validate inputs
    if mode not in ["easy_mode", "custom_mode", "task_specific_mode"]:
        raise HTTPException(status_code=400, detail=f"Invalid mode: {mode}")
    
    if platform_name not in SOCIAL_MEDIA_PLATFORMS:
        raise HTTPException(status_code=400, detail=f"Invalid platform: {platform_name}")
    
    if creativity_level not in [1, 2, 3]:
        raise HTTPException(status_code=400, detail=f"Creativity level must be 1, 2, or 3")
    
    if num_variants < 1 or num_variants > 6:
        raise HTTPException(status_code=400, detail=f"Number of variants must be between 1 and 6")
    
    if mode == "task_specific_mode" and not task_type:
        raise HTTPException(status_code=400, detail="Task type required for task_specific_mode")
    
    if task_type and task_type not in TASK_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid task type: {task_type}")
    
    # Basic validation for required inputs
    if mode in ["easy_mode", "custom_mode"] and not prompt and not image_file:
        raise HTTPException(status_code=400, detail=f"{mode} requires either prompt or image")
    
    # Process image file if provided
    image_data = None
    image_reference = None
    if image_file:
        # Validate image file
        if not image_file.content_type or not image_file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="Uploaded file must be an image")
        
        # Read image data
        image_data = await image_file.read()
        if len(image_data) > 10 * 1024 * 1024:  # 10MB limit
            raise HTTPException(status_code=400, detail="Image file too large (max 10MB)")
        
        image_reference = ImageReferenceInput(
            filename=image_file.filename or "uploaded_image",
            content_type=image_file.content_type,
            size_bytes=len(image_data),
            instruction=image_instruction
        )
    
    # Build marketing goals if any provided
    marketing_goals = None
    if any([marketing_audience, marketing_objective, marketing_voice, marketing_niche]):
        marketing_goals = MarketingGoalsInput(
            target_audience=marketing_audience,
            objective=marketing_objective,
            voice=marketing_voice,
            niche=marketing_niche
        )
    
    # Create pipeline run request
    request = PipelineRunRequest(
        mode=mode,
        platform_name=platform_name,
        creativity_level=creativity_level,
        num_variants=num_variants,
        prompt=prompt,
        task_type=task_type,
        task_description=task_description,
        branding_elements=branding_elements,
        image_reference=image_reference,
        render_text=render_text,
        apply_branding=apply_branding,
        marketing_goals=marketing_goals
    )
    
    # Create database record
    run = PipelineRun(
        status=RunStatus.PENDING,
        mode=request.mode,
        platform_name=request.platform_name,
        task_type=request.task_type,
        prompt=request.prompt,
        creativity_level=request.creativity_level,
        render_text=request.render_text,
        apply_branding=request.apply_branding,
        has_image_reference=image_reference is not None,
        image_filename=image_reference.filename if image_reference else None,
        image_instruction=image_reference.instruction if image_reference else None,
        branding_elements=request.branding_elements,
        task_description=request.task_description,
        marketing_audience=marketing_goals.target_audience if marketing_goals else None,
        marketing_objective=marketing_goals.objective if marketing_goals else None,
        marketing_voice=marketing_goals.voice if marketing_goals else None,
        marketing_niche=marketing_goals.niche if marketing_goals else None
    )
    
    session.add(run)
    session.commit()
    session.refresh(run)
    
    # Start background pipeline execution
    await task_processor.start_pipeline_run(run.id, request, image_data)
    
    return PipelineRunResponse(
        id=run.id,
        status=run.status,
        mode=run.mode,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        total_duration_seconds=run.total_duration_seconds,
        total_cost_usd=run.total_cost_usd,
        error_message=run.error_message,
        output_directory=run.output_directory,
        metadata_file_path=run.metadata_file_path
    )


# === REFINEMENT ENDPOINTS ===
@runs_router.post("/{run_id}/refine", response_model=RefinementResponse)
async def create_refinement(
    run_id: str,
    # Required fields
    refine_type: str = Form(..., description="Type of refinement: subject, text, or prompt"),
    parent_image_id: str = Form(..., description="ID of the image to refine"),
    parent_image_type: str = Form("original", description="'original' or 'refinement'"),
    generation_index: Optional[int] = Form(None, description="Which of N original images (0-based)"),
    
    # Optional refinement inputs
    prompt: Optional[str] = Form(None, description="Refinement prompt"),
    instructions: Optional[str] = Form(None, description="Specific instructions"),
    mask_data: Optional[str] = Form(None, description="JSON string of mask coordinates"),
    
    # File upload for subject repair
    reference_image: Optional[UploadFile] = File(None, description="Reference image for subject repair"),
    
    session: Session = Depends(get_session)
):
    """Create a new image refinement job"""
    
    # Validate parent run exists
    run = session.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Parent pipeline run not found")
    
    if run.status != RunStatus.COMPLETED:
        raise HTTPException(status_code=400, detail=f"Parent pipeline must be completed. Current status: {run.status}")
    
    # Validate refinement type
    try:
        refinement_type = RefinementType(refine_type)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid refinement type: {refine_type}. Must be 'subject', 'text', or 'prompt'")
    
    # Process reference image if provided
    reference_image_data = None
    reference_image_path = None
    if reference_image:
        # Validate image file
        if not reference_image.content_type or not reference_image.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="Reference file must be an image")
        
        # Read image data
        reference_image_data = await reference_image.read()
        if len(reference_image_data) > 10 * 1024 * 1024:  # 10MB limit
            raise HTTPException(status_code=400, detail="Reference image file too large (max 10MB)")
    
    # Generate refinement summary
    refinement_summary = _generate_refinement_summary(refinement_type, prompt, instructions)
    
    # Create refinement job record
    refinement_job = RefinementJob(
        parent_run_id=run_id,
        parent_image_id=parent_image_id,
        parent_image_type=parent_image_type,
        generation_index=generation_index,
        refinement_type=refinement_type,
        status=RunStatus.PENDING,
        refinement_summary=refinement_summary,
        prompt=prompt,
        instructions=instructions,
        mask_data=mask_data
    )
    
    session.add(refinement_job)
    session.commit()
    session.refresh(refinement_job)
    
    # Prepare refinement data for background processing
    refinement_data = {
        "refinement_type": refinement_type,
        "prompt": prompt,
        "instructions": instructions,
        "mask_coordinates": mask_data,
        "reference_image_data": reference_image_data
    }
    
    # Save reference image if provided
    if reference_image_data:
        parent_run_dir = Path(f"./data/runs/{run_id}")
        parent_run_dir.mkdir(parents=True, exist_ok=True)
        ref_image_path = parent_run_dir / f"ref_{refinement_job.id}_{reference_image.filename}"
        with open(ref_image_path, "wb") as f:
            f.write(reference_image_data)
        refinement_data["reference_image_path"] = str(ref_image_path)
    
    # DEBUG: Log refinement data received from frontend
    logger.info(f"Refinement request received - Job ID: {refinement_job.id}")
    logger.info(f"Refinement data from frontend: {refinement_data}")
    logger.info(f"Parent image details - ID: {parent_image_id}, Type: {parent_image_type}, Index: {generation_index}")
    
    # Start background refinement execution
    await task_processor.start_refinement_job(refinement_job.id, refinement_data)
    
    return RefinementResponse(
        job_id=refinement_job.id,
        parent_run_id=run_id,
        refinement_type=refinement_type,
        status=RunStatus.PENDING,
        created_at=refinement_job.created_at,
        refinement_summary=refinement_summary
    )


@runs_router.get("/{run_id}/refinements", response_model=RefinementListResponse)
async def list_refinements(
    run_id: str,
    session: Session = Depends(get_session)
):
    """List all refinements for a pipeline run"""
    
    # Validate parent run exists
    run = session.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    
    # Get refinements for this run
    refinements_query = select(RefinementJob).where(
        RefinementJob.parent_run_id == run_id
    ).order_by(RefinementJob.created_at)
    
    refinements = session.exec(refinements_query).all()
    
    # Convert to response format
    refinement_results = []
    total_cost = 0.0
    
    for refinement in refinements:
        refinement_results.append(RefinementResult(
            job_id=refinement.id,
            parent_run_id=refinement.parent_run_id,
            refinement_type=refinement.refinement_type,
            status=refinement.status,
            parent_image_id=refinement.parent_image_id,
            parent_image_type=refinement.parent_image_type,
            generation_index=refinement.generation_index,
            image_path=refinement.image_path,
            cost_usd=refinement.cost_usd,
            refinement_summary=refinement.refinement_summary,
            created_at=refinement.created_at,
            completed_at=refinement.completed_at,
            error_message=refinement.error_message
        ))
        
        if refinement.cost_usd:
            total_cost += refinement.cost_usd
    
    return RefinementListResponse(
        refinements=refinement_results,
        total_cost=total_cost,
        total_refinements=len(refinement_results)
    )


@api_router.post("/refinements/{job_id}/cancel")
async def cancel_refinement(
    job_id: str,
    session: Session = Depends(get_session)
):
    """Cancel a refinement job"""
    
    refinement = session.get(RefinementJob, job_id)
    if not refinement:
        raise HTTPException(status_code=404, detail="Refinement job not found")
    
    if refinement.status in [RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED]:
        return {"message": f"Refinement is already in final state: {refinement.status}"}
    
    # Attempt to cancel
    cancelled = task_processor.cancel_refinement(job_id)
    
    if cancelled:
        return {"message": "Refinement cancelled successfully"}
    else:
        # If not cancelled but status is RUNNING, it means the job is stalled
        if refinement.status == RunStatus.RUNNING:
            refinement.status = RunStatus.CANCELLED
            refinement.completed_at = datetime.now(timezone.utc)
            refinement.error_message = "Refinement execution was cancelled (stalled job)"
            session.add(refinement)
            session.commit()
            return {"message": "Stalled refinement marked as cancelled"}
        else:
            return {"message": "Refinement is not currently running"}


def _generate_refinement_summary(refinement_type: RefinementType, prompt: Optional[str], instructions: Optional[str]) -> str:
    """Generate a brief summary of the refinement for UI display"""
    if refinement_type == RefinementType.SUBJECT:
        return f"Subject repair: {instructions or 'Replace main subject'}"
    elif refinement_type == RefinementType.TEXT:
        return f"Text repair: {instructions or 'Fix text elements'}"
    elif refinement_type == RefinementType.PROMPT:
        return f"Prompt refinement: {prompt or instructions or 'Refine image'}"
    else:
        return "Unknown refinement"


@runs_router.get("/", response_model=RunListResponse)
async def list_pipeline_runs(
    page: int = 1,
    page_size: int = 20,
    status: Optional[RunStatus] = None,
    mode: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """List pipeline runs with pagination and filtering"""
    
    # Build query
    query = select(PipelineRun).order_by(desc(PipelineRun.created_at))
    
    if status:
        query = query.where(PipelineRun.status == status)
    
    if mode:
        query = query.where(PipelineRun.mode == mode)
    
    # Get total count
    total_query = select(PipelineRun)
    if status:
        total_query = total_query.where(PipelineRun.status == status)
    if mode:
        total_query = total_query.where(PipelineRun.mode == mode)
    
    total = len(session.exec(total_query).all())
    
    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    
    runs = session.exec(query).all()
    
    # Convert to response format
    run_items = [
        RunListItem(
            id=run.id,
            status=run.status,
            mode=run.mode,
            platform_name=run.platform_name,
            task_type=run.task_type,
            created_at=run.created_at,
            completed_at=run.completed_at,
            total_cost_usd=run.total_cost_usd
        )
        for run in runs
    ]
    
    return RunListResponse(
        runs=run_items,
        total=total,
        page=page,
        page_size=page_size
    )


@runs_router.get("/{run_id}", response_model=PipelineRunDetail)
async def get_pipeline_run(
    run_id: str,
    session: Session = Depends(get_session)
):
    """Get detailed information about a specific pipeline run"""
    
    run = session.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    
    # Get stages for this run
    stages_query = select(PipelineStage).where(
        PipelineStage.run_id == run_id
    ).order_by(PipelineStage.stage_order)
    
    stages = session.exec(stages_query).all()
    
    # Convert stages to response format
    stage_updates = []
    for stage in stages:
        # Parse output data if present
        output_data = None
        if stage.output_data:
            try:
                import json
                output_data = json.loads(stage.output_data)
            except:
                pass
        
        stage_updates.append({
            "stage_name": stage.stage_name,
            "stage_order": stage.stage_order,
            "status": stage.status,
            "started_at": stage.started_at,
            "completed_at": stage.completed_at,
            "duration_seconds": stage.duration_seconds,
            "message": f"Stage {stage.stage_name} {stage.status.value}",
            "output_data": output_data,
            "error_message": stage.error_message
        })
    
    return PipelineRunDetail(
        id=run.id,
        status=run.status,
        mode=run.mode,
        created_at=run.created_at,
        started_at=run.started_at,
        completed_at=run.completed_at,
        total_duration_seconds=run.total_duration_seconds,
        total_cost_usd=run.total_cost_usd,
        error_message=run.error_message,
        output_directory=run.output_directory,
        metadata_file_path=run.metadata_file_path,
        stages=stage_updates,
        
        # Form input data
        platform_name=run.platform_name,
        task_type=run.task_type,
        prompt=run.prompt,
        creativity_level=run.creativity_level,
        render_text=run.render_text,
        apply_branding=run.apply_branding,
        has_image_reference=run.has_image_reference,
        image_filename=run.image_filename,
        image_instruction=run.image_instruction,
        branding_elements=run.branding_elements,
        task_description=run.task_description,
        marketing_audience=run.marketing_audience,
        marketing_objective=run.marketing_objective,
        marketing_voice=run.marketing_voice,
        marketing_niche=run.marketing_niche
    )


@runs_router.get("/{run_id}/status", response_model=dict)
async def get_run_status(
    run_id: str,
    session: Session = Depends(get_session)
):
    """Get detailed status information about a pipeline run"""
    run = session.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    
    # Get stages for this run
    stages_query = select(PipelineStage).where(
        PipelineStage.run_id == run_id
    ).order_by(PipelineStage.stage_order)
    
    stages = session.exec(stages_query).all()
    
    # Check if run is actually running
    is_active = run_id in task_processor.active_tasks
    
    # If status is RUNNING but task is not active, it's stalled
    actual_status = run.status
    if run.status == RunStatus.RUNNING and not is_active:
        actual_status = RunStatus.FAILED
        
        # Update the database
        run.status = RunStatus.FAILED
        run.error_message = "Pipeline execution was interrupted unexpectedly"
        run.completed_at = datetime.now(timezone.utc)
        if run.started_at:
            run.total_duration_seconds = (run.completed_at - run.started_at).total_seconds()
        session.add(run)
        session.commit()
    
    return {
        "id": run.id,
        "status": actual_status,
        "is_active": is_active,
        "created_at": run.created_at,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "error_message": run.error_message,
        "total_duration_seconds": run.total_duration_seconds,
        "current_stage": stages[-1].stage_name if stages else None,
        "stage_count": len(stages),
        "completed_stages": len([s for s in stages if s.status == StageStatus.COMPLETED]),
        "failed_stages": len([s for s in stages if s.status == StageStatus.FAILED])
    }


@runs_router.post("/{run_id}/cancel")
async def cancel_pipeline_run(
    run_id: str,
    session: Session = Depends(get_session)
):
    """Cancel a running pipeline"""
    run = session.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    
    if run.status in [RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED]:
        return {"message": f"Pipeline is already in final state: {run.status}"}
    
    # Attempt to cancel
    cancelled = task_processor.cancel_run(run_id)
    
    if cancelled:
        return {"message": "Pipeline cancelled successfully"}
    else:
        # If not cancelled but status is RUNNING, it means the run is stalled
        if run.status == RunStatus.RUNNING:
            run.status = RunStatus.CANCELLED
            run.completed_at = datetime.now(timezone.utc)
            run.error_message = "Pipeline execution was cancelled (stalled run)"
            if run.started_at:
                run.total_duration_seconds = (run.completed_at - run.started_at).total_seconds()
            session.add(run)
            session.commit()
            return {"message": "Stalled pipeline marked as cancelled"}
        else:
            return {"message": "Pipeline is not currently running"}


@runs_router.get("/{run_id}/results", response_model=PipelineResults)
async def get_pipeline_results(
    run_id: str,
    session: Session = Depends(get_session)
):
    """Get the final results of a completed pipeline run"""
    try:
        run = session.get(PipelineRun, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Pipeline run not found")
        
        if run.status != RunStatus.COMPLETED:
            raise HTTPException(status_code=400, detail=f"Pipeline not completed yet. Current status: {run.status}")
        
        if not run.metadata_file_path or not os.path.exists(run.metadata_file_path):
            raise HTTPException(status_code=404, detail=f"Pipeline results not found. Metadata path: {run.metadata_file_path}")
        
        # Load pipeline metadata
        import json
        try:
            with open(run.metadata_file_path, 'r') as f:
                pipeline_data = json.load(f)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to load pipeline metadata: {str(e)}")
        
        # Extract results from pipeline data
        processing_context = pipeline_data.get("processing_context", {})
        
        # Extract generated images
        generated_images = []
        image_results = processing_context.get("generated_image_results", [])
        
        if not isinstance(image_results, list):
            logger.warning(f"generated_image_results is not a list: {type(image_results)}")
            image_results = []
        
        for result in image_results:
            if result and isinstance(result, dict):
                # Ensure we store just the filename for frontend compatibility
                result_path = result.get("result_path")
                if result_path and "/" in result_path:
                    # Extract just the filename if a full path was stored
                    result_path = os.path.basename(result_path)
                    
                generated_images.append(GeneratedImageResult(
                    strategy_index=result.get("index", 0),
                    status=result.get("status", "unknown"),
                    image_path=result_path,
                    error_message=result.get("error_message"),
                    prompt_used=None  # Could extract from final_assembled_prompts
                ))
        
        # Get refinements for this run
        refinements_query = select(RefinementJob).where(
            RefinementJob.parent_run_id == run_id
        ).order_by(RefinementJob.created_at)
        refinements = session.exec(refinements_query).all()
        
        refinement_results = []
        for refinement in refinements:
            refinement_results.append(RefinementResult(
                job_id=refinement.id,
                parent_run_id=refinement.parent_run_id,
                refinement_type=refinement.refinement_type,
                status=refinement.status,
                parent_image_id=refinement.parent_image_id,
                parent_image_type=refinement.parent_image_type,
                generation_index=refinement.generation_index,
                image_path=refinement.image_path,
                cost_usd=refinement.cost_usd,
                refinement_summary=refinement.refinement_summary,
                created_at=refinement.created_at,
                completed_at=refinement.completed_at,
                error_message=refinement.error_message
            ))
        
        # Extract cost information
        cost_summary = processing_context.get("cost_summary", {})
        
        return PipelineResults(
            run_id=run_id,
            status=run.status,
            image_analysis=processing_context.get("image_analysis_result"),
            marketing_strategies=processing_context.get("suggested_marketing_strategies"),
            style_guidance=processing_context.get("style_guidance_sets"),
            visual_concepts=processing_context.get("generated_image_prompts"),
            final_prompts=processing_context.get("final_assembled_prompts"),
            generated_images=generated_images,
            # NEW: Include image assessments
            image_assessments=processing_context.get("image_assessment"),
            # NEW: Include refinements
            refinements=refinement_results,
            total_cost_usd=cost_summary.get("total_pipeline_cost_usd"),
            total_duration_seconds=cost_summary.get("total_pipeline_duration_seconds"),
            stage_costs=cost_summary.get("stage_costs")
        )
    
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        import traceback
        logger.error(f"Error in get_pipeline_results for run {run_id}: {str(e)}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


# File serving endpoints
@files_router.get("/{run_id}/{filename}")
async def get_run_file(
    run_id: str,
    filename: str,
    session: Session = Depends(get_session)
):
    """Serve files from a pipeline run (images, metadata, etc.)"""
    
    run = session.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    
    # Construct file path safely
    file_path = Path(f"./data/runs/{run_id}") / filename
    
    # Security check: ensure file is within the run directory
    try:
        file_path = file_path.resolve()
        run_dir = Path(f"./data/runs/{run_id}").resolve()
        file_path.relative_to(run_dir)  # Will raise ValueError if outside
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    # Determine media type
    media_type, _ = mimetypes.guess_type(str(file_path))
    if not media_type:
        media_type = "application/octet-stream"
    
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=filename
    )


# Configuration endpoints
@api_router.get("/config/platforms")
async def get_platforms():
    """Get available social media platforms"""
    platforms = []
    for name, details in SOCIAL_MEDIA_PLATFORMS.items():
        if name != "Select Platform...":  # Skip placeholder
            platforms.append({
                "name": name,
                "details": details
            })
    return {"platforms": platforms}


@api_router.get("/config/task-types")
async def get_task_types():
    """Get available task types"""
    task_types = []
    for task_type in TASK_TYPES:
        if not task_type.startswith("Select"):  # Skip placeholder
            task_types.append(task_type)
    return {"task_types": task_types}


@api_router.get("/status")
async def get_api_status():
    """Get API status and stats"""
    active_runs = task_processor.get_active_runs()
    
    return {
        "status": "healthy",
        "active_runs": len(active_runs),
        "active_run_ids": active_runs
    }


# WebSocket endpoint
@ws_router.websocket("/{run_id}")
async def websocket_run_updates(websocket: WebSocket, run_id: str):
    """WebSocket endpoint for real-time pipeline updates"""
    await websocket_endpoint(websocket, run_id)


# === CAPTION ENDPOINTS ===

def _get_next_caption_version(run_id: str, image_id: str) -> int:
    """Calculate the next version number for a caption by checking existing files"""
    caption_dir = Path(f"./data/runs/{run_id}/captions/{image_id}")
    next_version = 0  # Default for first caption
    
    if caption_dir.exists():
        # Find existing version files and get the highest version number
        existing_files = list(caption_dir.glob("v*_result.json"))
        if existing_files:
            versions = []
            for file in existing_files:
                try:
                    # Extract version number from filename (e.g., "v2_result.json" -> 2)
                    version_str = file.stem.split('_')[0][1:]  # Remove 'v' prefix
                    versions.append(int(version_str))
                except (ValueError, IndexError):
                    continue
            
            if versions:
                next_version = max(versions) + 1
    
    return next_version
@runs_router.post("/{run_id}/images/{image_id}/caption", response_model=CaptionResponse)
async def generate_caption(
    run_id: str,
    image_id: str,
    request: CaptionRequest,
    session: Session = Depends(get_session)
):
    """Generate a caption for a specific image"""
    
    # Validate parent run exists and is completed
    run = session.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    
    if run.status != RunStatus.COMPLETED:
        raise HTTPException(status_code=400, detail=f"Pipeline must be completed. Current status: {run.status}")
    
    # Validate image exists in run results
    # This would normally check against generated images, but for now we'll trust the image_id
    
    # Generate unique caption ID
    import uuid
    caption_id = str(uuid.uuid4())
    
    # Calculate the next version by checking existing files
    next_version = _get_next_caption_version(run_id, image_id)
    
    # Prepare caption generation data
    caption_data = {
        "run_id": run_id,
        "image_id": image_id,
        "caption_id": caption_id,
        "settings": request.settings.model_dump() if request.settings else {},
        "version": next_version
    }
    
    # Start background caption generation
    await task_processor.start_caption_generation(caption_id, caption_data)
    
    # Return immediate response (actual generation happens in background)
    return CaptionResponse(
        caption_id=caption_id,
        image_id=image_id,
        text="Caption generation in progress...",
        version=next_version,
        settings_used=request.settings or CaptionSettings(),
        created_at=datetime.now(timezone.utc),
        status="PENDING"
    )


@runs_router.post("/{run_id}/images/{image_id}/caption/{caption_version}/regenerate", response_model=CaptionResponse)
async def regenerate_caption(
    run_id: str,
    image_id: str,
    caption_version: int,
    request: CaptionRegenerateRequest,
    session: Session = Depends(get_session)
):
    """Regenerate a caption with new settings or just new creativity"""
    
    # Validate parent run exists and is completed
    run = session.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    
    if run.status != RunStatus.COMPLETED:
        raise HTTPException(status_code=400, detail=f"Pipeline must be completed. Current status: {run.status}")
    
    # Generate new caption ID and calculate next version
    import uuid
    new_caption_id = str(uuid.uuid4())
    
    # Calculate the next version by checking existing files
    new_version = _get_next_caption_version(run_id, image_id)
    
    # Prepare caption regeneration data
    caption_data = {
        "run_id": run_id,
        "image_id": image_id,
        "caption_id": new_caption_id,
        "settings": request.settings.model_dump() if request.settings else {},
        "version": new_version,
        "writer_only": request.writer_only and not request.settings,  # Only writer if no new settings
        "previous_version": caption_version
    }
    
    # Start background caption regeneration
    await task_processor.start_caption_generation(new_caption_id, caption_data)
    
    # Return immediate response
    return CaptionResponse(
        caption_id=new_caption_id,
        image_id=image_id,
        text="Caption regeneration in progress...",
        version=new_version,
        settings_used=request.settings or CaptionSettings(),
        created_at=datetime.now(timezone.utc),
        status="PENDING"
    )


@runs_router.get("/{run_id}/images/{image_id}/captions")
async def list_captions(
    run_id: str,
    image_id: str,
    session: Session = Depends(get_session)
):
    """List all caption versions for a specific image"""
    
    # Validate parent run exists
    run = session.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    
    # Load captions from file system
    captions = []
    try:
        caption_dir = Path(f"./data/runs/{run_id}/captions/{image_id}")
        if caption_dir.exists():
            # Find all caption result files and sort by version number
            result_files = list(caption_dir.glob("v*_result.json"))
            
            # Sort files by version number for consistent ordering
            def get_version_from_filename(file_path):
                try:
                    version_str = file_path.stem.split('_')[0][1:]  # Remove 'v' prefix
                    return int(version_str)
                except (ValueError, IndexError):
                    return 0
            
            result_files.sort(key=get_version_from_filename)
            
            for result_file in result_files:
                try:
                    with open(result_file, 'r', encoding='utf-8') as f:
                        caption_data = json.load(f)
                    
                    # Convert to frontend format
                    captions.append({
                        "version": caption_data.get("version", 0),
                        "text": caption_data.get("text", ""),
                        "settings_used": caption_data.get("settings_used", {}),
                        "brief_used": caption_data.get("brief_used", {}),
                        "created_at": caption_data.get("created_at", ""),
                        "llm_usage": caption_data.get("llm_usage", {})
                    })
                except Exception as e:
                    logger.warning(f"Failed to load caption from {result_file}: {e}")
                    continue
    
    except Exception as e:
        logger.error(f"Failed to load captions for {run_id}/{image_id}: {e}")
    
    return {
        "run_id": run_id,
        "image_id": image_id,
        "captions": captions,
        "total_versions": len(captions)
    }


# Include routers in main API router
api_router.include_router(runs_router)
api_router.include_router(files_router)
api_router.include_router(ws_router) 