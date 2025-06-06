from typing import List, Optional
import os
from pathlib import Path
import mimetypes
import logging

from fastapi import APIRouter, HTTPException, Depends, WebSocket, UploadFile, File, Form
from fastapi.responses import FileResponse
from sqlmodel import Session, select
from sqlalchemy import desc

from churns.api.database import (
    get_session, PipelineRun, PipelineStage, 
    RunStatus, StageStatus, create_db_and_tables
)
from churns.api.schemas import (
    PipelineRunRequest, PipelineRunResponse, PipelineRunDetail, 
    RunListResponse, RunListItem, PipelineResults,
    ImageReferenceInput, MarketingGoalsInput, GeneratedImageResult
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
@runs_router.post("/", response_model=PipelineRunResponse)
async def create_pipeline_run(
    # Required fields
    mode: str = Form(..., description="Pipeline mode"),
    platform_name: str = Form(..., description="Target platform"),
    creativity_level: int = Form(2, description="Creativity level 1-3"),
    
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


@runs_router.post("/{run_id}/cancel")
async def cancel_pipeline_run(
    run_id: str,
    session: Session = Depends(get_session)
):
    """Cancel a running pipeline"""
    
    run = session.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    
    if run.status not in [RunStatus.PENDING, RunStatus.RUNNING]:
        raise HTTPException(status_code=400, detail="Cannot cancel completed pipeline")
    
    success = task_processor.cancel_run(run_id)
    if not success:
        raise HTTPException(status_code=400, detail="Pipeline not currently running")
    
    return {"message": "Pipeline cancelled successfully"}


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


# Include routers in main API router
api_router.include_router(runs_router)
api_router.include_router(files_router)
api_router.include_router(ws_router) 