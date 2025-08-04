from typing import List, Optional, Dict, Any
import os
import json
from pathlib import Path
import mimetypes
import logging
import time
import asyncio
from datetime import datetime, timezone
import traceback
import base64

from fastapi import APIRouter, HTTPException, Depends, WebSocket, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse
from sqlmodel import select
from sqlalchemy import desc, and_
from sqlalchemy.ext.asyncio import AsyncSession

from churns.api.database import (
    get_session, PipelineRun, PipelineStage, RefinementJob, RefinementType,
    RunStatus, StageStatus, create_db_and_tables, BrandPreset, PresetType,
    retry_db_operation
)
from churns.api.dependencies import get_executor, get_refinement_executor, get_caption_executor
from churns.pipeline.executor import PipelineExecutor
from churns.api.schemas import (
    PipelineRunRequest, PipelineRunResponse, PipelineRunDetail, 
    RunListResponse, RunListItem, PipelineResults,
    ImageReferenceInput, MarketingGoalsInput, GeneratedImageResult,
    RefinementResponse, RefinementListResponse, RefinementResult,
    CaptionRequest, CaptionResponse, CaptionRegenerateRequest, CaptionSettings,
    CaptionModelsResponse, CaptionModelOption,
    BrandPresetCreateRequest, BrandPresetUpdateRequest, BrandPresetResponse,
    BrandPresetListResponse, SavePresetFromResultRequest, ParentPresetInfo
)
from churns.api.websocket import websocket_endpoint
from churns.api.background_tasks import task_processor
from churns.core.constants import (
    SOCIAL_MEDIA_PLATFORMS, TASK_TYPES, PLATFORM_DISPLAY_NAMES,
    CAPTION_MODEL_OPTIONS, CAPTION_MODEL_ID
)
from churns.models.presets import StyleRecipeEnvelope, StyleRecipeData
from churns.models import VisualConceptDetails, MarketingGoalSetFinal, StyleGuidance

# Create logger
logger = logging.getLogger(__name__)

# Create routers
api_router = APIRouter(prefix="/api/v1")
runs_router = APIRouter(prefix="/runs", tags=["Pipeline Runs"])
files_router = APIRouter(prefix="/files", tags=["File Operations"])
ws_router = APIRouter(prefix="/ws", tags=["WebSocket"])
presets_router = APIRouter(prefix="/brand-presets", tags=["Brand Presets"])


@api_router.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    await create_db_and_tables()
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
    
    # Boolean flags
    render_text: bool = Form(False, description="Render text flag"),
    apply_branding: bool = Form(False, description="Apply branding flag"),
    
    # Language control
    language: Optional[str] = Form('en', description="Output language ISO-639-1 code"),
    
    # Marketing goals (optional)
    marketing_audience: Optional[str] = Form(None, description="Marketing audience"),
    marketing_objective: Optional[str] = Form(None, description="Marketing objective"),
    marketing_voice: Optional[str] = Form(None, description="Marketing voice"),
    marketing_niche: Optional[str] = Form(None, description="Marketing niche"),
    
    # Image instruction
    image_instruction: Optional[str] = Form(None, description="Image instruction"),
    
    # File upload
    image_file: Optional[UploadFile] = File(None, description="Reference image"),
    
    # Brand Preset support
    preset_id: Optional[str] = Form(None, description="Brand preset ID to apply"),
    preset_type: Optional[str] = Form(None, description="Type of preset being applied"),
    template_overrides: Optional[str] = Form(None, description="JSON string of template field overrides"),
    adaptation_prompt: Optional[str] = Form(None, description="New prompt for style recipe adaptation"),
    
    # Brand Kit data
    brand_kit: Optional[str] = Form(None, description="JSON string of BrandKitInput"),
    
    session: AsyncSession = Depends(get_session),
    executor: PipelineExecutor = Depends(get_executor)
):
    """Create a new pipeline run"""
    
    try:
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
        
        # Language validation
        if language:
            # Common ISO-639-1 language codes
            VALID_LANGUAGE_CODES = {
                'en', 'zh', 'es', 'fr', 'de', 'it', 'ja', 'ko', 'pt', 'ru', 
                'ar', 'hi', 'th', 'vi', 'nl', 'sv', 'no', 'da', 'fi', 'pl',
                'tr', 'he', 'cs', 'hu', 'ro', 'bg', 'hr', 'sk', 'sl', 'et',
                'lv', 'lt', 'mt', 'ga', 'cy', 'eu', 'ca', 'gl', 'is', 'fo'
            }
            if len(language) != 2 or language.lower() not in VALID_LANGUAGE_CODES:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Invalid language code: '{language}'. Must be a valid 2-letter ISO-639-1 code (e.g., es, fr, ja, de, it)"
                )
            # Normalize to lowercase
            language = language.lower()
        
        # Basic validation for required inputs
        if mode in ["easy_mode", "custom_mode"] and not prompt and not image_file:
            raise HTTPException(status_code=400, detail=f"{mode} requires either prompt or image")
        
        logger.info("✅ Input validation passed")
        
        # Process image file if provided
        image_data = None
        image_reference = None
        if image_file:
            logger.info(f"📷 Processing image file: {image_file.filename}")
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
        
        # Parse template overrides if provided
        parsed_template_overrides = None
        if template_overrides:
            try:
                parsed_template_overrides = json.loads(template_overrides)
                logger.info(f"📝 Parsed template_overrides: {parsed_template_overrides}")
            except json.JSONDecodeError as e:
                logger.error(f"❌ Failed to parse template_overrides JSON: {e}")
                raise HTTPException(status_code=400, detail="Invalid JSON format for template_overrides")
        
        # Parse brand kit if provided
        parsed_brand_kit = None
        if brand_kit:
            try:
                parsed_brand_kit = json.loads(brand_kit)
                logger.info(f"🎨 Parsed brand_kit: {len(str(parsed_brand_kit))} characters")
            except json.JSONDecodeError as e:
                logger.error(f"❌ Failed to parse brand_kit JSON: {e}")
                raise HTTPException(status_code=400, detail="Invalid JSON format for brand_kit")
        
        # Create pipeline run request
        request = PipelineRunRequest(
            mode=mode,
            platform_name=platform_name,
            creativity_level=creativity_level,
            num_variants=num_variants,
            prompt=prompt,
            task_type=task_type,
            task_description=task_description,
            image_reference=image_reference,
            render_text=render_text,
            apply_branding=apply_branding,
            marketing_goals=marketing_goals,
            language=language,
            preset_id=preset_id,
            preset_type=preset_type,
            template_overrides=parsed_template_overrides,
            adaptation_prompt=adaptation_prompt,
            brand_kit=parsed_brand_kit
        )
        
        logger.info(f"📋 Created pipeline run request object")
        
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
            task_description=request.task_description,
            marketing_audience=marketing_goals.target_audience if marketing_goals else None,
            marketing_objective=marketing_goals.objective if marketing_goals else None,
            marketing_voice=marketing_goals.voice if marketing_goals else None,
            marketing_niche=marketing_goals.niche if marketing_goals else None,
            language=language or 'en',
            brand_kit=json.dumps(parsed_brand_kit) if parsed_brand_kit else None,
            
            # NEW: Store preset information
            preset_id=request.preset_id,
            preset_type=request.preset_type,
            template_overrides=json.dumps(parsed_template_overrides) if parsed_template_overrides else None,
            adaptation_prompt=adaptation_prompt
        )
        
        session.add(run)
        await session.commit()
        await session.refresh(run)
        
        # Update base_image_url for style adaptations after run is created
        if image_reference and request.preset_type == "STYLE_RECIPE":
            # Store just the filename - the frontend will construct the full API path
            run.base_image_url = f"input_{image_reference.filename}"
            session.add(run)
            await session.commit()
        
        logger.info(f"💾 Created database record for run {run.id}")
        
        # Start background pipeline execution
        logger.info(f"🎬 Starting background task for run {run.id}")
        asyncio.create_task(task_processor.start_pipeline_run(run.id, request, image_data, executor))
        
        logger.info(f"🚀 Background task started for run {run.id}")
        
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
            metadata_file_path=run.metadata_file_path,
            
            # NEW: Style Adaptation fields
            preset_id=run.preset_id,
            preset_type=run.preset_type,
            base_image_url=run.base_image_url,
            template_overrides=parsed_template_overrides,
            adaptation_prompt=adaptation_prompt,
            parent_preset=None  # Will be populated when run is fetched later
        )
        
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        logger.error(f"❌ Unexpected error in create_pipeline_run: {e}")
        logger.error(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


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
    mask_data: Optional[str] = Form(None, description="JSON string of mask coordinates (legacy)"),
    
    # File uploads
    reference_image: Optional[UploadFile] = File(None, description="Reference image for subject repair or prompt refinement"),
    mask_file: Optional[UploadFile] = File(None, description="Mask PNG file for regional editing"),
    
    session: AsyncSession = Depends(get_session),
    executor: PipelineExecutor = Depends(get_refinement_executor)
):
    """Create a new image refinement job"""
    
    # Validate parent run exists
    run = await session.get(PipelineRun, run_id)
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
    if reference_image:
        # Validate image file
        if not reference_image.content_type or not reference_image.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="Reference file must be an image")
        
        # Read image data
        reference_image_data = await reference_image.read()
        if len(reference_image_data) > 10 * 1024 * 1024:  # 10MB limit
            raise HTTPException(status_code=400, detail="Reference image file too large (max 10MB)")
    
    # Process mask file if provided
    mask_file_data = None
    if mask_file:
        # Validate mask file
        if not mask_file.content_type or mask_file.content_type != 'image/png':
            raise HTTPException(status_code=400, detail="Mask file must be a PNG image")
        
        # Read mask data
        mask_file_data = await mask_file.read()
        if len(mask_file_data) > 4 * 1024 * 1024:  # 4MB limit
            raise HTTPException(status_code=400, detail="Mask file too large (max 4MB)")
        
        # Validate mask dimensions match the base image
        try:
            from PIL import Image
            import io
            
            # Load mask image to validate
            mask_image = Image.open(io.BytesIO(mask_file_data))
            
            # Load base image to compare dimensions (use parent run_id, not current run_id)
            base_image_path = _get_base_image_path(run_id, parent_image_id, parent_image_type, generation_index)
            if not base_image_path or not os.path.exists(base_image_path):
                raise HTTPException(status_code=400, detail="Base image not found for mask validation")
            
            base_image = Image.open(base_image_path)
            
            # Check dimensions match
            if mask_image.size != base_image.size:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Mask dimensions {mask_image.size} must match base image dimensions {base_image.size}"
                )
            
            # Validate mask is grayscale or RGB (can be converted to grayscale)
            if mask_image.mode not in ['L', 'RGB', 'RGBA']:
                raise HTTPException(status_code=400, detail="Mask must be grayscale or RGB format")
                
        except Exception as e:
            if isinstance(e, HTTPException):
                raise
            raise HTTPException(status_code=400, detail=f"Invalid mask file: {str(e)}")
    
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
    await session.commit()
    await session.refresh(refinement_job)
    
    # Prepare refinement data for background processing
    refinement_data = {
        "refinement_type": refinement_type,
        "prompt": prompt,
        "instructions": instructions,
        "mask_coordinates": mask_data,  # Legacy support
        "reference_image_data": reference_image_data,
        "mask_file_data": mask_file_data
    }
    
    # Save reference image if provided (updated for hybrid structure)
    if reference_image_data:
        parent_run_dir = Path(f"./data/runs/{run_id}").resolve()  # Make absolute
        
        # Create job-specific directory for hybrid structure
        job_refinement_dir = parent_run_dir / "refinements" / refinement_job.id
        job_refinement_dir.mkdir(parents=True, exist_ok=True)
        
        # Store reference image directly in job-specific directory
        # Preserve original file extension for better compatibility
        original_extension = Path(reference_image.filename or "reference.png").suffix
        ref_image_filename = f"reference{original_extension}"
        ref_image_path = job_refinement_dir / ref_image_filename
        
        with open(ref_image_path, "wb") as f:
            f.write(reference_image_data)
        
        # Store absolute path for the refinement utilities
        refinement_data["reference_image_path"] = str(ref_image_path)
    
    # Save mask file if provided
    if mask_file_data:
        parent_run_dir = Path(f"./data/runs/{run_id}").resolve()  # Make absolute
        
        # Create job-specific directory for hybrid structure
        job_refinement_dir = parent_run_dir / "refinements" / refinement_job.id
        job_refinement_dir.mkdir(parents=True, exist_ok=True)
        
        # Store mask file directly in job-specific directory
        mask_file_path = job_refinement_dir / "mask.png"
        
        with open(mask_file_path, "wb") as f:
            f.write(mask_file_data)
        
        # Store absolute path for the refinement utilities
        refinement_data["mask_file_path"] = str(mask_file_path)
        logger.info(f"Saved mask file: {mask_file_path}")
    
    logger.info(f"Refinement request received - Job ID: {refinement_job.id}")
    logger.debug(f"Refinement data: {refinement_data}")
    logger.debug(f"Parent image details - ID: {parent_image_id}, Type: {parent_image_type}, Index: {generation_index}")
    
    # Start background refinement execution
    await task_processor.start_refinement_job(refinement_job.id, refinement_data, executor)
    
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
    session: AsyncSession = Depends(get_session)
):
    """List all refinements for a pipeline run"""
    
    # Validate parent run exists
    run = await session.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    
    # Get refinements for this run
    refinements_query = select(RefinementJob).where(
        RefinementJob.parent_run_id == run_id
    ).order_by(RefinementJob.created_at)
    
    result = await session.execute(refinements_query)
    refinements = result.scalars().all()
    
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
            needs_noise_reduction=refinement.needs_noise_reduction,
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


@api_router.get("/refinements/{job_id}/details")
async def get_refinement_details(
    job_id: str,
    session: AsyncSession = Depends(get_session)
):
    """Get detailed metadata for a refinement job"""
    
    refinement = await session.get(RefinementJob, job_id)
    if not refinement:
        raise HTTPException(status_code=404, detail="Refinement job not found")
    
    # Get parent run details for context
    parent_run = await session.get(PipelineRun, refinement.parent_run_id)
    if not parent_run:
        raise HTTPException(status_code=404, detail="Parent pipeline run not found")
    
    # Prepare detailed response based on refinement type
    details = {
        "job_id": refinement.id,
        "parent_run_id": refinement.parent_run_id,
        "refinement_type": refinement.refinement_type,
        "status": refinement.status,
        "created_at": refinement.created_at,
        "completed_at": refinement.completed_at,
        "cost_usd": refinement.cost_usd,
        "duration_seconds": (refinement.completed_at - refinement.created_at).total_seconds() if refinement.completed_at and refinement.created_at else None,
        "error_message": refinement.error_message,
    }
    
    # Type-specific details
    if refinement.refinement_type == "subject":
        details.update({
            "refinement_type_display": "Quick Repair",
            "description": "Automatic subject enhancement using original reference image",
            "user_input_required": False,
            "reference_image_used": refinement.reference_image_path is not None,
            "reference_image_source": "original" if refinement.reference_image_path else None,
        })
    elif refinement.refinement_type == "prompt":
        details.update({
            "refinement_type_display": "Custom Enhancement",
            "description": "Custom prompt-based refinement with optional reference image and regional masking",
            "user_input_required": True,
            "user_prompt": refinement.prompt,
            "instructions": refinement.instructions,
            "mask_used": refinement.mask_data is not None,
            "reference_image_used": refinement.reference_image_path is not None,
            "reference_image_source": "uploaded" if refinement.reference_image_path else None,
        })
    
    # Try to load comprehensive metadata from the job directory
    try:
        parent_run_dir = Path(f"./data/runs/{refinement.parent_run_id}")
        job_metadata_path = parent_run_dir / "refinements" / refinement.id / "metadata.json"
        
        logger.info(f"Attempting to load metadata from: {job_metadata_path}")
        logger.info(f"Parent run dir exists: {parent_run_dir.exists()}")
        logger.info(f"Refinements dir exists: {(parent_run_dir / 'refinements').exists()}")
        logger.info(f"Job dir exists: {(parent_run_dir / 'refinements' / refinement.id).exists()}")
        logger.info(f"Metadata file exists: {job_metadata_path.exists()}")
        
        if job_metadata_path.exists():
            logger.info(f"Loading metadata from: {job_metadata_path}")
            with open(job_metadata_path, 'r') as f:
                job_metadata = json.load(f)
                
            # Extract inputs section
            inputs = job_metadata.get("inputs", {})
            details["original_prompt"] = inputs.get("original_prompt")
            details["ai_refined_prompt"] = inputs.get("refined_prompt")
            details["instructions"] = inputs.get("instructions") or details.get("instructions")
            details["mask_file_path"] = inputs.get("mask_file_path")
            details["creativity_level"] = inputs.get("creativity_level")
            
            # Extract processing information
            processing = job_metadata.get("processing", {})
            details["model_used"] = processing.get("model_used")
            details["api_image_size"] = processing.get("api_image_size")
            details["operation_type"] = processing.get("operation_type", "global_editing")
            
            # Extract results information
            results = job_metadata.get("results", {})
            details["output_generated"] = results.get("output_generated", False)
            details["reference_preserved"] = results.get("reference_preserved", False)
            details["modifications"] = results.get("modifications", {})
            
            # Extract image information
            images = job_metadata.get("images", {})
            details["base_image_metadata"] = images.get("base_image_metadata", {})
            details["reference_image_filename"] = images.get("reference_path")
            
            # Extract context information for better understanding
            context = job_metadata.get("context", {})
            original_pipeline_data = context.get("original_pipeline_data", {})
            if original_pipeline_data:
                user_inputs = original_pipeline_data.get("user_inputs", {})
                processing_context = original_pipeline_data.get("processing_context", {})
                
                # Add original generation context
                details["original_generation"] = {
                    "mode": user_inputs.get("mode"),
                    "platform_name": user_inputs.get("platform_name"),
                    "task_type": user_inputs.get("task_type"),
                    "creativity_level": user_inputs.get("creativity_level"),
                    "has_image_reference": user_inputs.get("image_reference") is not None,
                }
                
                # Add visual concept that led to the original image
                if processing_context:
                    generated_prompts = processing_context.get("generated_image_prompts", [])
                    if generated_prompts and refinement.generation_index is not None:
                        if 0 <= refinement.generation_index < len(generated_prompts):
                            visual_concept = generated_prompts[refinement.generation_index]
                            details["original_visual_concept"] = visual_concept
                            logger.info(f"Added original visual concept for generation index {refinement.generation_index}")
                
            logger.info(f"Successfully loaded metadata for refinement {job_id}")
        else:
            logger.warning(f"Metadata file not found: {job_metadata_path}")
            # Try to load basic metadata from parent run
            parent_metadata_path = parent_run_dir / "pipeline_metadata.json"
            if parent_metadata_path.exists():
                logger.info(f"Loading parent metadata from: {parent_metadata_path}")
                with open(parent_metadata_path, 'r') as f:
                    parent_metadata = json.load(f)
                    
                # Extract what we can from parent metadata
                processing_context = parent_metadata.get("processing_context", {})
                user_inputs = parent_metadata.get("user_inputs", {})
                
                # Add original generation context
                details["original_generation"] = {
                    "mode": user_inputs.get("mode"),
                    "platform_name": user_inputs.get("platform_name"),
                    "task_type": user_inputs.get("task_type"),
                    "creativity_level": user_inputs.get("creativity_level"),
                    "has_image_reference": user_inputs.get("image_reference") is not None,
                }
                
                # Add visual concept if available
                if processing_context and refinement.generation_index is not None:
                    generated_prompts = processing_context.get("generated_image_prompts", [])
                    if generated_prompts and 0 <= refinement.generation_index < len(generated_prompts):
                        visual_concept = generated_prompts[refinement.generation_index]
                        details["original_visual_concept"] = visual_concept
                        logger.info(f"Added original visual concept from parent metadata for generation index {refinement.generation_index}")
                        
                logger.info(f"Loaded fallback metadata from parent run")
            else:
                logger.warning(f"Parent metadata not found: {parent_metadata_path}")
                
    except Exception as e:
        logger.error(f"Error loading metadata for refinement {job_id}: {str(e)}")
        logger.error(f"Exception details: {e.__class__.__name__}: {e}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        
        # Set basic fallback values
        details["original_generation"] = {
            "mode": "unknown",
            "platform_name": "unknown",
            "task_type": "unknown",
            "creativity_level": "unknown",
            "has_image_reference": False,
        }
    
    return details


@api_router.post("/refinements/{job_id}/cancel")
async def cancel_refinement(
    job_id: str,
    session: AsyncSession = Depends(get_session)
):
    """Cancel a refinement job"""
    
    refinement = await session.get(RefinementJob, job_id)
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
            await session.commit()
            return {"message": "Stalled refinement marked as cancelled"}
        else:
            return {"message": "Refinement is not currently running"}


@api_router.post("/refinements/{job_id}/assess-noise")
async def assess_refinement_noise(
    job_id: str,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
    executor: PipelineExecutor = Depends(get_refinement_executor)
):
    """Assess a refined image for noise and grain issues"""
    
    # Validate refinement exists
    refinement = await session.get(RefinementJob, job_id)
    if not refinement:
        raise HTTPException(status_code=404, detail="Refinement job not found")
    
    # Check refinement is completed and has an image
    if refinement.status != RunStatus.COMPLETED:
        raise HTTPException(status_code=400, detail=f"Refinement must be completed. Current status: {refinement.status}")
    
    if not refinement.image_path:
        raise HTTPException(status_code=400, detail="Refinement has no image to assess")
    
    # Check if already assessed
    if refinement.needs_noise_reduction is not None:
        return {
            "message": "Noise assessment already completed",
            "needs_noise_reduction": refinement.needs_noise_reduction
        }
    
    # Start background noise assessment with pre-configured executor
    background_tasks.add_task(
        task_processor.run_noise_assessment_for_refinement,
        job_id,
        executor
    )
    
    return {
        "message": "Noise assessment started",
        "job_id": job_id
    }


def _get_base_image_path(run_id: str, parent_image_id: str, parent_image_type: str, generation_index: Optional[int]) -> Optional[str]:
    """Get the path to the base image for mask validation"""
    try:
        base_run_dir = Path(f"./data/runs/{run_id}")
        
        if parent_image_type == "original":
            # Original generated images are stored directly in the run directory
            # with patterns like: generated_image_strategy_{index}_{timestamp}.png or edited_image_strategy_{index}_{timestamp}.png
            if generation_index is not None:
                # Look for generated images with this index
                patterns = [
                    f"generated_image_strategy_{generation_index}_*.png",
                    f"edited_image_strategy_{generation_index}_*.png",
                    f"image_{generation_index}*.png",  # Fallback pattern
                ]
                
                for pattern in patterns:
                    matches = list(base_run_dir.glob(pattern))
                    if matches:
                        # Sort by modification time (newest first) and return the first match
                        matches.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                        image_path = matches[0]
                        if image_path.exists():
                            logger.info(f"Found original image: {image_path}")
                            return str(image_path)
                
                logger.warning(f"No original image found for generation_index {generation_index} in {base_run_dir}")
                return None
            else:
                # Try to parse generation index from parent_image_id (e.g., "image_0" -> 0)
                if parent_image_id.startswith("image_"):
                    try:
                        index = int(parent_image_id.split("_")[1])
                        return _get_base_image_path(run_id, parent_image_id, parent_image_type, index)
                    except (IndexError, ValueError):
                        pass
                
                logger.warning(f"Cannot determine generation index from parent_image_id: {parent_image_id}")
                return None
        else:
            # Refinement image - look in refinements directory
            refinements_dir = base_run_dir / "refinements"
            
            # Look for the refinement image (could be in various formats)
            possible_patterns = [
                f"{parent_image_id}_from_*.png",
                f"{parent_image_id}.png",
                f"refinement_{parent_image_id}.png",
            ]
            
            for pattern in possible_patterns:
                if '*' in pattern:
                    # Use glob for wildcard patterns
                    matches = list(refinements_dir.glob(pattern))
                    if matches:
                        # Sort by modification time (newest first)
                        matches.sort(key=lambda x: x.stat().st_mtime, reverse=True)
                        image_path = matches[0]
                        if image_path.exists():
                            logger.info(f"Found refinement image: {image_path}")
                            return str(image_path)
                else:
                    # Direct path check
                    image_path = refinements_dir / pattern
                    if image_path.exists():
                        logger.info(f"Found refinement image: {image_path}")
                        return str(image_path)
            
            logger.warning(f"No refinement image found for parent_image_id {parent_image_id} in {refinements_dir}")
            return None
        
    except Exception as e:
        logger.error(f"Error getting base image path: {e}")
        return None


def _generate_refinement_summary(refinement_type: RefinementType, prompt: Optional[str], instructions: Optional[str]) -> str:
    """Generate a brief summary of the refinement for UI display"""
    if refinement_type == RefinementType.SUBJECT:
        return "Quick repair: Automatic subject enhancement using original reference image"
    elif refinement_type == RefinementType.PROMPT:
        return f"Prompt refinement: {prompt or instructions or 'Refine image'}"
    else:
        return "Unknown refinement"


@runs_router.get("", response_model=RunListResponse)
@runs_router.get("/", response_model=RunListResponse)
async def list_pipeline_runs(
    page: int = 1,
    page_size: int = 20,
    status: Optional[RunStatus] = None,
    mode: Optional[str] = None,
    session: AsyncSession = Depends(get_session)
):
    """List pipeline runs with pagination and filtering"""
    
    # Build query with LEFT JOIN for parent preset information
    query = select(
        PipelineRun,
        BrandPreset.name.label("parent_preset_name"),
        BrandPreset.id.label("parent_preset_id")
    ).outerjoin(
        BrandPreset,
        and_(
            PipelineRun.preset_id == BrandPreset.id,
            PipelineRun.preset_type == PresetType.STYLE_RECIPE.value
        )
    ).order_by(desc(PipelineRun.created_at))
    
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
    
    total_result = await session.execute(total_query)
    total = len(total_result.scalars().all())
    
    # Apply pagination
    offset = (page - 1) * page_size
    query = query.offset(offset).limit(page_size)
    
    result = await session.execute(query)
    results = result.all()
    
    # Convert to response format
    run_items = []
    for run, parent_preset_name, parent_preset_id in results:
        # Build parent preset info if available
        parent_preset_info = None
        if parent_preset_name:
            parent_preset_info = ParentPresetInfo(
                id=parent_preset_id,
                name=parent_preset_name,
                image_url=None  # Deferred to detail view for performance
            )
        
        run_items.append(RunListItem(
            id=run.id,
            status=run.status,
            mode=run.mode,
            platform_name=run.platform_name,
            task_type=run.task_type,
            created_at=run.created_at,
            completed_at=run.completed_at,
            total_cost_usd=run.total_cost_usd,
            preset_type=run.preset_type,
            parent_preset=parent_preset_info
        ))
    
    return RunListResponse(
        runs=run_items,
        total=total,
        page=page,
        page_size=page_size
    )


@runs_router.get("/{run_id}", response_model=PipelineRunDetail)
async def get_pipeline_run(
    run_id: str,
    session: AsyncSession = Depends(get_session)
):
    """Get detailed information about a specific pipeline run"""
    
    run = await session.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    
    # Get stages for this run
    stages_query = select(PipelineStage).where(
        PipelineStage.run_id == run_id
    ).order_by(PipelineStage.stage_order)
    
    stages_result = await session.execute(stages_query)
    stages = stages_result.scalars().all()
    
    # Convert stages to response format
    stage_updates = []
    for stage in stages:
        # Parse output data if present - use getattr for safe access
        output_data = None
        stage_output_data = getattr(stage, 'output_data', None)
        if stage_output_data:
            try:
                output_data = json.loads(stage_output_data)
            except:
                pass
        
        stage_updates.append({
            "stage_name": getattr(stage, 'stage_name', ''),
            "stage_order": getattr(stage, 'stage_order', 0),
            "status": getattr(stage, 'status', StageStatus.PENDING),
            "started_at": getattr(stage, 'started_at', None),
            "completed_at": getattr(stage, 'completed_at', None),
            "duration_seconds": getattr(stage, 'duration_seconds', None),
            "message": f"Stage {getattr(stage, 'stage_name', 'unknown')} {getattr(stage, 'status', StageStatus.PENDING).value if hasattr(getattr(stage, 'status', StageStatus.PENDING), 'value') else getattr(stage, 'status', StageStatus.PENDING)}",
            "output_data": output_data,
            "error_message": getattr(stage, 'error_message', None)
        })
    
    # NEW: Handle parent preset for STYLE_RECIPE runs
    parent_preset_info = None
    if run.preset_id and run.preset_type == PresetType.STYLE_RECIPE.value:
        parent_preset_query = select(BrandPreset).where(BrandPreset.id == run.preset_id)
        parent_preset_result = await session.execute(parent_preset_query)
        parent_preset = parent_preset_result.scalar_one_or_none()
        
        if parent_preset:
            # Get the parent preset's reference image from source run and image path
            parent_image_url = None
            if parent_preset.source_run_id and parent_preset.source_image_path:
                # Store just the filename - frontend will construct full path with source_run_id
                parent_image_url = parent_preset.source_image_path
            
            parent_preset_info = ParentPresetInfo(
                id=parent_preset.id,
                name=parent_preset.name,
                image_url=parent_image_url,
                source_run_id=parent_preset.source_run_id
            )
    
    # Parse template overrides if present
    parsed_template_overrides = None
    if run.template_overrides:
        try:
            parsed_template_overrides = json.loads(run.template_overrides)
        except json.JSONDecodeError:
            pass
    
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
        
        # NEW: Style Adaptation fields
        preset_id=run.preset_id,
        preset_type=run.preset_type,
        base_image_url=run.base_image_url,
        template_overrides=parsed_template_overrides,
        adaptation_prompt=run.adaptation_prompt,
        parent_preset=parent_preset_info,
        
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
        task_description=run.task_description,
        marketing_audience=run.marketing_audience,
        marketing_objective=run.marketing_objective,
        marketing_voice=run.marketing_voice,
        marketing_niche=run.marketing_niche,
        language=run.language,
        
        # Brand Kit data (parse JSON if present)
        brand_kit=json.loads(run.brand_kit) if run.brand_kit else None
    )


@runs_router.get("/{run_id}/status", response_model=dict)
async def get_run_status(
    run_id: str,
    session: AsyncSession = Depends(get_session)
):
    """Get detailed status information about a pipeline run"""
    run = await session.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    
    # Get stages for this run
    stages_query = select(PipelineStage).where(
        PipelineStage.run_id == run_id
    ).order_by(PipelineStage.stage_order)
    
    stages_result = await session.execute(stages_query)
    stages = stages_result.scalars().all()
    
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
        await session.commit()
    
    return {
        "id": run.id,
        "status": actual_status,
        "is_active": is_active,
        "created_at": run.created_at,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "error_message": run.error_message,
        "total_duration_seconds": run.total_duration_seconds,
        "current_stage": getattr(stages[-1], 'stage_name', None) if stages else None,
        "stage_count": len(stages),
        "completed_stages": len([s for s in stages if getattr(s, 'status', None) == StageStatus.COMPLETED]),
        "failed_stages": len([s for s in stages if getattr(s, 'status', None) == StageStatus.FAILED])
    }



@runs_router.post("/{run_id}/cancel")
async def cancel_pipeline_run(
    run_id: str,
    session: AsyncSession = Depends(get_session)
):
    """Cancel a running pipeline"""
    
    # Use retry logic for database operations to handle lock contention
    async def get_run_with_retry():
        return await session.get(PipelineRun, run_id)
    
    run = await retry_db_operation(
        get_run_with_retry,
        operation_name=f"get pipeline run {run_id} for cancellation"
    )
    
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    
    if run.status in [RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED]:
        return {"message": f"Pipeline is already in final state: {run.status}"}
    
    # Attempt to cancel through task processor
    cancelled = await task_processor.cancel_run(run_id)
    
    if cancelled:
        return {"message": "Pipeline cancelled successfully"}
    else:
        # If not cancelled but status is RUNNING, it means the run is stalled
        # Use retry logic for the database update
        async def update_stalled_run():
            # Refresh the run to get latest state
            fresh_run = await session.get(PipelineRun, run_id)
            if fresh_run and fresh_run.status == RunStatus.RUNNING:
                fresh_run.status = RunStatus.CANCELLED
                fresh_run.completed_at = datetime.now(timezone.utc)
                fresh_run.error_message = "Pipeline execution was cancelled (stalled run)"
                if fresh_run.started_at:
                    fresh_run.total_duration_seconds = (fresh_run.completed_at - fresh_run.started_at).total_seconds()
                session.add(fresh_run)
                await session.commit()
                return True
            return False
        
        if run.status == RunStatus.RUNNING:
            updated = await retry_db_operation(
                update_stalled_run,
                operation_name=f"update stalled pipeline run {run_id}"
            )
            if updated:
                return {"message": "Stalled pipeline marked as cancelled"}
        
        return {"message": "Pipeline is not currently running"}


@runs_router.get("/{run_id}/results", response_model=PipelineResults)
async def get_pipeline_results(
    run_id: str,
    session: AsyncSession = Depends(get_session)
):
    """Get the final results of a completed pipeline run"""
    try:
        run = await session.get(PipelineRun, run_id)
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
        refinements_result = await session.execute(refinements_query)
        refinements = refinements_result.scalars().all()
        
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
                needs_noise_reduction=refinement.needs_noise_reduction,
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
@files_router.get("/{run_id}/{file_path:path}")
async def get_run_file(
    run_id: str,
    file_path: str,
    session: AsyncSession = Depends(get_session)
):
    """Serve files from a pipeline run (images, metadata, etc.)"""
    
    run = await session.get(PipelineRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    
    # Handle empty file_path (directory access)
    if not file_path or file_path.strip() == "":
        raise HTTPException(status_code=404, detail="File path cannot be empty")
    
    # Construct file path safely - file_path can now include subdirectories
    full_file_path = Path(f"./data/runs/{run_id}") / file_path
    
    # Security check: ensure file is within the run directory
    try:
        full_file_path = full_file_path.resolve()
        run_dir = Path(f"./data/runs/{run_id}").resolve()
        full_file_path.relative_to(run_dir)  # Will raise ValueError if outside
    except ValueError:
        raise HTTPException(status_code=403, detail="Access denied")
    
    if not full_file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    
    # Ensure we're serving a file, not a directory
    if full_file_path.is_dir():
        raise HTTPException(status_code=404, detail="Cannot serve directory as file")
    
    # Determine media type
    media_type, _ = mimetypes.guess_type(str(full_file_path))
    if not media_type:
        media_type = "application/octet-stream"
    
    # Extract just the filename for the download
    filename = full_file_path.name
    
    return FileResponse(
        path=str(full_file_path),
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
    """Get available task types for the frontend"""
    return {
        "task_types": TASK_TYPES,
        "message": "Available task types for pipeline runs"
    }


@api_router.get("/config/caption-models", response_model=CaptionModelsResponse)
async def get_caption_models():
    """Get available caption models with their characteristics"""
    models = [
        CaptionModelOption(
            id=model_info["id"],
            name=model_info["name"],
            description=model_info["description"],
            strengths=model_info["strengths"],
            best_for=model_info["best_for"],
            latency=model_info["latency"],
            creativity=model_info["creativity"]
        )
        for model_info in CAPTION_MODEL_OPTIONS.values()
    ]
    
    return CaptionModelsResponse(
        models=models,
        default_model_id=CAPTION_MODEL_ID
    )


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

def _is_settings_empty(settings):
    """Check if a settings object is effectively empty (all values are defaults)"""
    if settings is None:
        return True
    
    # Create a default CaptionSettings object to compare against
    defaults = CaptionSettings()
    settings_dict = settings.model_dump()
    defaults_dict = defaults.model_dump()
    
    # Compare each field - if any field differs from default, settings are not empty
    for key, value in settings_dict.items():
        if value != defaults_dict.get(key):
            return False
    
    return True

@runs_router.post("/{run_id}/images/{image_id}/caption", response_model=CaptionResponse)
async def generate_caption(
    run_id: str,
    image_id: str,
    request: CaptionRequest,
    session: AsyncSession = Depends(get_session),
    executor: PipelineExecutor = Depends(get_caption_executor)
):
    """Generate a caption for a specific image"""
    
    # Validate parent run exists and is completed - use retry logic
    async def validate_caption_run():
        run = await session.get(PipelineRun, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Pipeline run not found")
        
        if run.status != RunStatus.COMPLETED:
            raise HTTPException(status_code=400, detail=f"Pipeline must be completed. Current status: {run.status}")
        return run
    
    run = await retry_db_operation(
        validate_caption_run,
        operation_name=f"validate run {run_id} for caption generation"
    )
    
    # Validate and set model_id
    model_id = request.model_id or CAPTION_MODEL_ID
    if model_id not in CAPTION_MODEL_OPTIONS:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid model ID: {model_id}. Available models: {list(CAPTION_MODEL_OPTIONS.keys())}"
        )
    
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
        "version": next_version,
        "model_id": model_id
    }
    
    # Start background caption generation
    await task_processor.start_caption_generation(caption_id, caption_data, executor)
    
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
    session: AsyncSession = Depends(get_session),
    executor: PipelineExecutor = Depends(get_caption_executor)
):
    """Regenerate a caption with new settings or just new creativity"""
    
    # Validate parent run exists and is completed - use retry logic
    async def validate_caption_regeneration_run():
        run = await session.get(PipelineRun, run_id)
        if not run:
            raise HTTPException(status_code=404, detail="Pipeline run not found")
        
        if run.status != RunStatus.COMPLETED:
            raise HTTPException(status_code=400, detail=f"Pipeline must be completed. Current status: {run.status}")
        return run
    
    run = await retry_db_operation(
        validate_caption_regeneration_run,
        operation_name=f"validate run {run_id} for caption regeneration"
    )
    
    # Determine model_id to use
    model_id = request.model_id or CAPTION_MODEL_ID
    previous_model_id = None
    
    # If no model specified, try to use the model from the previous version
    if not request.model_id:
        try:
            previous_caption_file = Path(f"./data/runs/{run_id}/captions/{image_id}/v{caption_version}_result.json")
            if previous_caption_file.exists():
                with open(previous_caption_file, 'r', encoding='utf-8') as f:
                    previous_data = json.load(f)
                    previous_model = previous_data.get("model_id")
                    if previous_model and previous_model in CAPTION_MODEL_OPTIONS:
                        model_id = previous_model
                        previous_model_id = previous_model
        except Exception as e:
            logger.warning(f"Could not load previous model from caption {caption_version}: {e}")
    else:
        # If model was explicitly specified, also load the previous model for comparison
        try:
            previous_caption_file = Path(f"./data/runs/{run_id}/captions/{image_id}/v{caption_version}_result.json")
            if previous_caption_file.exists():
                with open(previous_caption_file, 'r', encoding='utf-8') as f:
                    previous_data = json.load(f)
                    previous_model_id = previous_data.get("model_id", CAPTION_MODEL_ID)
        except Exception as e:
            logger.warning(f"Could not load previous model for comparison: {e}")
            previous_model_id = CAPTION_MODEL_ID
    
    # Validate model_id
    if model_id not in CAPTION_MODEL_OPTIONS:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid model ID: {model_id}. Available models: {list(CAPTION_MODEL_OPTIONS.keys())}"
        )
    
    # Generate new caption ID and calculate next version
    import uuid
    new_caption_id = str(uuid.uuid4())
    
    # Calculate the next version by checking existing files
    new_version = _get_next_caption_version(run_id, image_id)
    
    # Check if model has changed
    model_has_changed = previous_model_id and (model_id != previous_model_id)
    
    is_empty = _is_settings_empty(request.settings)
    
    # Determine if we should run writer-only:
    # - Must be requested as writer_only=True
    # - Settings must be empty (no changes to caption settings)
    # - Model must NOT have changed (if model changed, run full pipeline)
    writer_only_result = request.writer_only and is_empty and not model_has_changed
    
    # Prepare caption regeneration data
    caption_data = {
        "run_id": run_id,
        "image_id": image_id,
        "caption_id": new_caption_id,
        "settings": request.settings.model_dump() if request.settings else {},
        "version": new_version,
        "writer_only": writer_only_result,  # Only writer if no settings change AND no model change
        "previous_version": caption_version,
        "model_id": model_id
    }
    
    # Start background caption regeneration
    await task_processor.start_caption_generation(new_caption_id, caption_data, executor)
    
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
    session: AsyncSession = Depends(get_session)
):
    """List all caption versions for a specific image"""
    
    # Validate parent run exists
    run = await session.get(PipelineRun, run_id)
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
                        "model_id": caption_data.get("model_id"),
                        "usage_summary": caption_data.get("usage_summary", {}),
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


# Brand Preset Endpoints
@presets_router.post("", response_model=BrandPresetResponse)
async def create_brand_preset(
    request: BrandPresetCreateRequest,
    session: AsyncSession = Depends(get_session)
):
    """Create a new brand preset"""
    # TODO: Add user authentication and get user_id from auth context
    # For now, using a hardcoded user_id for development
    user_id = "dev_user_1"
    
    # Validate preset type
    if request.preset_type not in [PresetType.INPUT_TEMPLATE, PresetType.STYLE_RECIPE]:
        raise HTTPException(status_code=400, detail=f"Invalid preset type: {request.preset_type}")
    
    # Validate that appropriate data is provided based on preset type
    if request.preset_type == PresetType.INPUT_TEMPLATE and not request.input_snapshot:
        raise HTTPException(status_code=400, detail="input_snapshot is required for INPUT_TEMPLATE presets")
    
    if request.preset_type == PresetType.STYLE_RECIPE and not request.style_recipe:
        raise HTTPException(status_code=400, detail="style_recipe is required for STYLE_RECIPE presets")
    
    # Create the preset
    preset = BrandPreset(
        name=request.name,
        user_id=user_id,
        preset_type=request.preset_type,
        preset_source_type=request.preset_source_type,
        pipeline_version=request.pipeline_version,
        brand_kit=json.dumps(request.brand_kit.model_dump()) if request.brand_kit else None,
        input_snapshot=request.input_snapshot.model_dump_json() if request.input_snapshot else None,
        style_recipe=request.style_recipe.model_dump_json() if request.style_recipe else None,
    )
    
    session.add(preset)
    await session.commit()
    await session.refresh(preset)
    
    return _convert_preset_to_response(preset)


@presets_router.get("", response_model=BrandPresetListResponse)
async def list_brand_presets(
    preset_type: Optional[str] = None,
    session: AsyncSession = Depends(get_session)
):
    """List all brand presets for the authenticated user"""
    # TODO: Add user authentication and get user_id from auth context
    user_id = "dev_user_1"
    
    # Build query
    query = select(BrandPreset).where(BrandPreset.user_id == user_id)
    
    if preset_type:
        if preset_type not in [PresetType.INPUT_TEMPLATE, PresetType.STYLE_RECIPE]:
            raise HTTPException(status_code=400, detail=f"Invalid preset type: {preset_type}")
        query = query.where(BrandPreset.preset_type == preset_type)
    
    # Order by most recently used, then by created date
    query = query.order_by(
        desc(BrandPreset.last_used_at),
        desc(BrandPreset.created_at)
    )
    
    result = await session.execute(query)
    presets = result.scalars().all()
    
    return BrandPresetListResponse(
        presets=[_convert_preset_to_response(p) for p in presets],
        total=len(presets)
    )


@presets_router.get("/{preset_id}", response_model=BrandPresetResponse)
async def get_brand_preset(
    preset_id: str,
    session: AsyncSession = Depends(get_session)
):
    """Get a specific brand preset"""
    # TODO: Add user authentication and get user_id from auth context
    user_id = "dev_user_1"
    
    result = await session.execute(
        select(BrandPreset)
        .where(BrandPreset.id == preset_id)
        .where(BrandPreset.user_id == user_id)
    )
    preset = result.scalar_one_or_none()
    
    if not preset:
        raise HTTPException(status_code=404, detail="Brand preset not found")
    
    return _convert_preset_to_response(preset)


@presets_router.put("/{preset_id}", response_model=BrandPresetResponse)
async def update_brand_preset(
    preset_id: str,
    request: BrandPresetUpdateRequest,
    session: AsyncSession = Depends(get_session)
):
    """Update a brand preset with optimistic locking"""
    # TODO: Add user authentication and get user_id from auth context
    user_id = "dev_user_1"
    
    # Fetch the preset with user authorization
    result = await session.execute(
        select(BrandPreset)
        .where(BrandPreset.id == preset_id)
        .where(BrandPreset.user_id == user_id)
    )
    preset = result.scalar_one_or_none()
    
    if not preset:
        raise HTTPException(status_code=404, detail="Brand preset not found")
    
    # Check version for optimistic locking
    if preset.version != request.version:
        raise HTTPException(
            status_code=409, 
            detail=f"Version mismatch. Current version is {preset.version}, provided version is {request.version}"
        )
    
    # Update fields
    if request.name is not None:
        preset.name = request.name
    if request.brand_kit is not None:
        preset.brand_kit = json.dumps(request.brand_kit.model_dump())
    
    # Increment version
    preset.version += 1
    preset.updated_at = datetime.utcnow()
    
    await session.commit()
    await session.refresh(preset)
    
    return _convert_preset_to_response(preset)


@presets_router.delete("/{preset_id}")
async def delete_brand_preset(
    preset_id: str,
    session: AsyncSession = Depends(get_session)
):
    """Delete a brand preset"""
    # TODO: Add user authentication and get user_id from auth context
    user_id = "dev_user_1"
    
    # Fetch the preset with user authorization
    result = await session.execute(
        select(BrandPreset)
        .where(BrandPreset.id == preset_id)
        .where(BrandPreset.user_id == user_id)
    )
    preset = result.scalar_one_or_none()
    
    if not preset:
        raise HTTPException(status_code=404, detail="Brand preset not found")
    
    await session.delete(preset)
    await session.commit()
    
    return {"message": "Brand preset deleted successfully"}


@presets_router.post("/cleanup-invalid")
async def cleanup_invalid_presets(
    session: AsyncSession = Depends(get_session)
):
    """Clean up presets with invalid data structures"""
    # TODO: Add admin authentication
    
    result = await session.execute(select(BrandPreset))
    presets = result.scalars().all()
    
    invalid_presets = []
    valid_presets = []
    
    for preset in presets:
        try:
            # Try to convert to response format
            _convert_preset_to_response(preset)
            valid_presets.append(preset.id)
        except Exception as e:
            invalid_presets.append({"id": preset.id, "name": preset.name, "error": str(e)})
    
    return {
        "total_presets": len(presets),
        "valid_presets": len(valid_presets),
        "invalid_presets": len(invalid_presets),
        "invalid_details": invalid_presets
    }


@runs_router.post("/{run_id}/save-as-preset", response_model=BrandPresetResponse)
async def save_preset_from_result(
    run_id: str,
    request: SavePresetFromResultRequest,
    session: AsyncSession = Depends(get_session)
):
    """Create a STYLE_RECIPE preset from a completed pipeline run"""
    # TODO: Add user authentication and get user_id from auth context
    user_id = "dev_user_1"
    
    # Get the pipeline run
    result = await session.execute(
        select(PipelineRun).where(PipelineRun.id == run_id)
    )
    run = result.scalar_one_or_none()
    
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    
    if run.status != RunStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Can only save presets from completed runs")
    
    # Load the run metadata to extract the style recipe data
    if not run.metadata_file_path or not os.path.exists(run.metadata_file_path):
        raise HTTPException(status_code=400, detail="Run metadata not found")
    
    try:
        with open(run.metadata_file_path, 'r') as f:
            run_metadata = json.load(f)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load run metadata: {str(e)}")
    
    # Extract style recipe data from the run metadata
    processing_context = run_metadata.get('processing_context', {})
    generated_image_results = processing_context.get('generated_image_results', [])
    
    if request.generation_index >= len(generated_image_results):
        raise HTTPException(status_code=400, detail="Invalid generation index")
    
    # Find the source image path for the specified generation index
    source_image_path = None
    if generated_image_results:
        result = generated_image_results[request.generation_index]
        if result and isinstance(result, dict):
            # Get the image path from the result
            result_path = result.get("result_path")
            if result_path:
                # Extract just the filename if a full path was stored
                if "/" in result_path:
                    source_image_path = os.path.basename(result_path)
                else:
                    source_image_path = result_path
            
    # Build the style recipe from the run metadata
    generated_image_prompts = processing_context.get('generated_image_prompts', [])
    suggested_marketing_strategies = processing_context.get('suggested_marketing_strategies', [])
    style_guidance_sets = processing_context.get('style_guidance_sets', [])
    
    if request.generation_index >= len(generated_image_prompts) or \
       request.generation_index >= len(suggested_marketing_strategies) or \
       request.generation_index >= len(style_guidance_sets):
        raise HTTPException(status_code=400, detail="Incomplete metadata for the selected generation index.")

    try:
        style_recipe_data = StyleRecipeData(
            visual_concept=VisualConceptDetails(**generated_image_prompts[request.generation_index].get('visual_concept', {})),
            strategy=MarketingGoalSetFinal(**suggested_marketing_strategies[request.generation_index]),
            style_guidance=StyleGuidance(**style_guidance_sets[request.generation_index])
        )
    except Exception as e:
        logger.error(f"Error creating StyleRecipeData: {e}")
        raise HTTPException(status_code=500, detail="Failed to construct style recipe from run metadata.")

    # Create the envelope with the complete context
    style_recipe_envelope = StyleRecipeEnvelope(
        recipe_data=style_recipe_data,
        render_text=run.render_text,
        apply_branding=run.apply_branding,
        source_platform=run.platform_name,
        language=run.language or 'en'
    )

    # The brand kit from the PARENT run is the source of truth for the preset's brand kit
    parent_brand_kit_json = run.brand_kit
    
    # Convert logo file path to base64 for frontend compatibility
    if parent_brand_kit_json:
        try:
            parent_brand_kit = json.loads(parent_brand_kit_json)
            
            # Check if we have a logo file path but no base64 data
            if (parent_brand_kit.get('saved_logo_path_in_run_dir') and 
                not parent_brand_kit.get('logo_file_base64')):
                
                logo_path = parent_brand_kit['saved_logo_path_in_run_dir']
                if os.path.exists(logo_path):
                    # Read logo file and convert to base64
                    with open(logo_path, 'rb') as logo_file:
                        logo_data = logo_file.read()
                        logo_base64 = base64.b64encode(logo_data).decode('utf-8')
                        
                        # Determine MIME type
                        mime_type = mimetypes.guess_type(logo_path)[0] or 'image/png'
                        logo_data_uri = f"data:{mime_type};base64,{logo_base64}"
                        
                        # Add base64 data to brand kit
                        parent_brand_kit['logo_file_base64'] = logo_data_uri
                        logger.info(f"Converted logo file to base64 for preset: {logo_path}")
                
            # Update the JSON string
            parent_brand_kit_json = json.dumps(parent_brand_kit)
            
        except Exception as e:
            logger.warning(f"Failed to convert logo to base64: {e}")
            # Continue with original brand_kit if conversion fails
    
    # Create the preset
    preset = BrandPreset(
        name=request.name,
        user_id=user_id,
        preset_type=PresetType.STYLE_RECIPE,
        preset_source_type="style-recipe",
        pipeline_version="1.1.0",  # TODO: Get from run metadata
        source_run_id=run_id,
        source_image_path=source_image_path,
        brand_kit=parent_brand_kit_json, # Now includes base64 logo data
        input_snapshot=None,
        style_recipe=style_recipe_envelope.model_dump_json() # Serialize the envelope
    )
    
    session.add(preset)
    await session.commit()
    await session.refresh(preset)
    
    return _convert_preset_to_response(preset)


def _convert_preset_to_response(preset: BrandPreset) -> BrandPresetResponse:
    """Convert a BrandPreset database model to a response model"""
    try:
        # Parse JSON fields safely
        brand_kit = json.loads(preset.brand_kit) if preset.brand_kit else None
        input_snapshot = json.loads(preset.input_snapshot) if preset.input_snapshot else None
        style_recipe = json.loads(preset.style_recipe) if preset.style_recipe else None
        
        return BrandPresetResponse(
            id=preset.id,
            name=preset.name,
            preset_type=preset.preset_type,
            version=preset.version,
            preset_source_type=preset.preset_source_type,
            pipeline_version=preset.pipeline_version,
            usage_count=preset.usage_count,
            created_at=preset.created_at,
            last_used_at=preset.last_used_at,
            brand_kit=brand_kit,
            input_snapshot=input_snapshot,
            style_recipe=style_recipe
        )
    except Exception as e:
        # Log the error but don't crash the entire listing
        logger.error(f"Failed to convert preset {preset.id} to response: {e}")
        
        # Return a minimal response with just the basic fields
        return BrandPresetResponse(
            id=preset.id,
            name=f"{preset.name} (Error Loading)",
            preset_type=preset.preset_type,
            version=preset.version,
            preset_source_type=preset.preset_source_type,
            pipeline_version=preset.pipeline_version,
            usage_count=preset.usage_count,
            created_at=preset.created_at,
            last_used_at=preset.last_used_at,
            brand_kit=None,
            input_snapshot=None,
            style_recipe=None
        )


# Include routers in main API router
api_router.include_router(runs_router)
api_router.include_router(files_router)
api_router.include_router(ws_router)
api_router.include_router(presets_router) 