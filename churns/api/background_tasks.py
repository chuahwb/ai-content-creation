import asyncio
import json
import traceback
import base64
import os
from datetime import datetime
from typing import Dict, Any, Optional
import logging
from pathlib import Path

from sqlmodel import Session, select
from churns.api.database import (
    get_session, PipelineRun, PipelineStage, RefinementJob,
    RunStatus, StageStatus, engine
)
from churns.api.schemas import (
    PipelineRunRequest, StageProgressUpdate, 
    GeneratedImageResult, PipelineResults
)
from churns.api.websocket import connection_manager
from churns.pipeline.context import PipelineContext
from churns.pipeline.executor import PipelineExecutor
from churns.core.constants import (
    MODEL_PRICING, 
    IMAGE_ASSESSMENT_MODEL_ID,
    IMG_EVAL_MODEL_ID,
    STRATEGY_MODEL_ID, 
    STYLE_GUIDER_MODEL_ID,
    CREATIVE_EXPERT_MODEL_ID,
    IMAGE_GENERATION_MODEL_ID
)
from churns.core.token_cost_manager import get_token_cost_manager, calculate_stage_cost_from_usage

logger = logging.getLogger(__name__)


def get_model_pricing(model_id: str, fallback_input_rate: float = 0.001, fallback_output_rate: float = 0.001):
    """
    Get pricing for a model from centralized MODEL_PRICING with fallback protection.
    
    Args:
        model_id: The model identifier 
        fallback_input_rate: Fallback input rate per 1M tokens
        fallback_output_rate: Fallback output rate per 1M tokens
        
    Returns:
        Dict with 'input_rate' and 'output_rate' keys
    """
    pricing = MODEL_PRICING.get(model_id)
    if not pricing:
        logger.warning(f"No pricing found for model {model_id}, using fallback rates")
        return {
            "input_rate": fallback_input_rate,
            "output_rate": fallback_output_rate
        }
    
    return {
        "input_rate": pricing["input_cost_per_mtok"],
        "output_rate": pricing["output_cost_per_mtok"]
    }


class PipelineTaskProcessor:
    """Processes pipeline runs in background with real-time updates"""
    
    def __init__(self):
        self.active_tasks: Dict[str, asyncio.Task] = {}
        self.run_timeouts: Dict[str, asyncio.Task] = {}
        self.PIPELINE_TIMEOUT_SECONDS = 3600  # 1 hour timeout
        
    async def _check_run_timeout(self, run_id: str):
        """Check if a run has exceeded the timeout limit"""
        try:
            await asyncio.sleep(self.PIPELINE_TIMEOUT_SECONDS)
            if run_id in self.active_tasks:
                logger.warning(f"Pipeline run {run_id} exceeded timeout limit of {self.PIPELINE_TIMEOUT_SECONDS}s")
                await self._handle_timeout(run_id)
        except asyncio.CancelledError:
            pass
        finally:
            self.run_timeouts.pop(run_id, None)
    
    async def _handle_timeout(self, run_id: str):
        """Handle a timed out pipeline run"""
        if run_id in self.active_tasks:
            task = self.active_tasks[run_id]
            task.cancel()
            self.active_tasks.pop(run_id, None)
            
            # Update database
            with Session(engine) as session:
                run = session.get(PipelineRun, run_id)
                if run and run.status == RunStatus.RUNNING:
                    run.status = RunStatus.FAILED
                    run.completed_at = datetime.utcnow()
                    run.error_message = f"Pipeline execution timed out after {self.PIPELINE_TIMEOUT_SECONDS} seconds"
                    if run.started_at:
                        run.total_duration_seconds = (run.completed_at - run.started_at).total_seconds()
                    session.add(run)
                    session.commit()
            
            # Notify clients
            await connection_manager.send_run_error(
                run_id, 
                f"Pipeline execution timed out after {self.PIPELINE_TIMEOUT_SECONDS} seconds",
                {"type": "timeout"}
            )

    async def start_pipeline_run(self, run_id: str, request: PipelineRunRequest, image_data: Optional[bytes] = None):
        """Start a pipeline run in the background"""
        # First check if there's a stalled run
        with Session(engine) as session:
            run = session.get(PipelineRun, run_id)
            if not run:
                logger.error(f"Run {run_id} not found in database")
                return
            
            # If run exists but shows as running and not in active tasks, it's stalled
            if run.status == RunStatus.RUNNING and run_id not in self.active_tasks:
                run.status = RunStatus.FAILED
                run.completed_at = datetime.utcnow()
                run.error_message = "Pipeline execution was interrupted unexpectedly"
                if run.started_at:
                    run.total_duration_seconds = (run.completed_at - run.started_at).total_seconds()
                session.add(run)
                session.commit()
                
                await connection_manager.send_run_error(
                    run_id,
                    "Pipeline execution was interrupted unexpectedly",
                    {"type": "stalled"}
                )
                return
            
            # If run is already active, don't start again
            if run_id in self.active_tasks:
                logger.warning(f"Pipeline run {run_id} is already running")
                return
            
            # Start the run
            run.status = RunStatus.RUNNING
            run.started_at = datetime.utcnow()
            run.error_message = None  # Clear any previous error
            session.add(run)
            session.commit()
        
        # Create and start the background task
        task = asyncio.create_task(self._execute_pipeline(run_id, request, image_data))
        self.active_tasks[run_id] = task
        
        # Start timeout monitor
        timeout_task = asyncio.create_task(self._check_run_timeout(run_id))
        self.run_timeouts[run_id] = timeout_task
        
        # Clean up completed tasks
        def cleanup_tasks(t):
            self.active_tasks.pop(run_id, None)
            if run_id in self.run_timeouts:
                self.run_timeouts[run_id].cancel()
        
        task.add_done_callback(cleanup_tasks)
        
        logger.info(f"Started background pipeline task for run {run_id}")
    
    async def _execute_pipeline(self, run_id: str, request: PipelineRunRequest, image_data: Optional[bytes] = None):
        """Execute the complete pipeline with progress updates"""
        try:
            # Update run status to running
            with Session(engine) as session:
                run = session.get(PipelineRun, run_id)
                if not run:
                    logger.error(f"Run {run_id} not found in database")
                    return
                
                run.status = RunStatus.RUNNING
                run.started_at = datetime.utcnow()
                session.add(run)
                session.commit()
            
            # Create output directory
            output_dir = Path(f"./data/runs/{run_id}")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Save uploaded image if provided
            image_path = None
            if image_data and request.image_reference:
                image_filename = f"input_{request.image_reference.filename}"
                image_path = output_dir / image_filename
                with open(image_path, "wb") as f:
                    f.write(image_data)
                logger.info(f"Saved input image to {image_path}")
            
            # Convert request to pipeline context format (matching original notebook)
            pipeline_data = self._convert_request_to_pipeline_data(request, str(output_dir), image_path, image_data)
            
            # Create pipeline context
            context = PipelineContext.from_dict(pipeline_data)
            
            # Set the output directory for stages to use
            context.output_directory = str(output_dir)
            
            # Initialize cost tracking
            total_cost = 0.0
            stage_costs = []
            
            # Set up progress callback
            async def progress_callback(stage_name: str, stage_order: int, status: StageStatus, 
                                      message: str, output_data: Optional[Dict] = None, 
                                      error_message: Optional[str] = None,
                                      duration_seconds: Optional[float] = None):
                
                # Calculate cost using centralized token cost manager
                nonlocal total_cost, stage_costs
                if status == StageStatus.COMPLETED and duration_seconds:
                    stage_cost = 0.0
                    
                    # Try to get actual cost from real API usage data in context
                    try:
                        processing_context = (context.data or {}).get("processing_context", {})
                        llm_usage = processing_context.get("llm_call_usage", {})
                        
                        # Use centralized cost calculation system
                        if stage_name == "image_generation":
                            # Handle image generation separately as it has different structure
                            image_results = processing_context.get("generated_image_results", [])
                            actual_images = len([r for r in image_results if r.get("status") == "success"])
                            total_prompt_tokens = sum(r.get("prompt_tokens", 0) for r in image_results if r.get("prompt_tokens"))
                            
                            if actual_images > 0 and total_prompt_tokens > 0:
                                # Use the token cost manager for image generation
                                token_manager = get_token_cost_manager()
                                from churns.core.token_cost_manager import TokenUsage
                                
                                usage = TokenUsage(
                                    prompt_tokens=total_prompt_tokens,
                                    completion_tokens=0,  # Image generation doesn't have completion tokens
                                    total_tokens=total_prompt_tokens,
                                    model=IMAGE_GENERATION_MODEL_ID,
                                    provider="openai"
                                )
                                
                                image_details = {
                                    "count": actual_images,
                                    "resolution": "1024x1024",  # Assume standard resolution
                                    "quality": "medium"  # Assume medium quality
                                }
                                
                                cost_breakdown = token_manager.calculate_cost(usage, image_details)
                                stage_cost = cost_breakdown.total_cost
                                logger.info(f"Image generation cost: ${stage_cost:.6f} using {IMAGE_GENERATION_MODEL_ID} - {cost_breakdown.notes}")
                            else:
                                stage_cost = 0.0  # No successful generation
                                
                        elif stage_name == "image_eval":
                            # Use centralized cost calculation
                            cost_result = calculate_stage_cost_from_usage(
                                stage_name, llm_usage, ["image_eval"], IMG_EVAL_MODEL_ID
                            )
                            stage_cost = cost_result.get("total_cost", 0.0)
                            if stage_cost > 0:
                                logger.info(f"Image eval cost: ${stage_cost:.6f} using {IMG_EVAL_MODEL_ID}")
                                
                        elif stage_name == "strategy":
                            # Use centralized cost calculation for multiple keys
                            cost_result = calculate_stage_cost_from_usage(
                                stage_name, llm_usage, ["strategy_niche_id", "strategy_goal_gen"], STRATEGY_MODEL_ID
                            )
                            stage_cost = cost_result.get("total_cost", 0.0)
                            if stage_cost > 0:
                                logger.info(f"Strategy cost: ${stage_cost:.6f} using {STRATEGY_MODEL_ID}")
                            
                        elif stage_name == "style_guide":
                            # Use centralized cost calculation
                            cost_result = calculate_stage_cost_from_usage(
                                stage_name, llm_usage, ["style_guider"], STYLE_GUIDER_MODEL_ID
                            )
                            stage_cost = cost_result.get("total_cost", 0.0)
                            if stage_cost > 0:
                                logger.info(f"Style guide cost: ${stage_cost:.6f} using {STYLE_GUIDER_MODEL_ID}")
                                
                        elif stage_name == "creative_expert":
                            # Use centralized cost calculation for multiple strategy keys
                            creative_keys = [key for key in llm_usage.keys() if key.startswith("creative_expert_strategy_")]
                            cost_result = calculate_stage_cost_from_usage(
                                stage_name, llm_usage, creative_keys, CREATIVE_EXPERT_MODEL_ID
                            )
                            stage_cost = cost_result.get("total_cost", 0.0)
                            if stage_cost > 0:
                                logger.info(f"Creative expert cost: ${stage_cost:.6f} using {CREATIVE_EXPERT_MODEL_ID}")
                            
                        elif stage_name == "image_assessment":
                            # Use centralized cost calculation with detailed logging
                            cost_result = calculate_stage_cost_from_usage(
                                stage_name, llm_usage, ["image_assessment"], IMAGE_ASSESSMENT_MODEL_ID
                            )
                            stage_cost = cost_result.get("total_cost", 0.0)
                            
                            if stage_cost > 0 and "image_assessment" in llm_usage:
                                assessment_usage = llm_usage["image_assessment"]
                                total_prompt_tokens = assessment_usage.get("prompt_tokens", 0)
                                completion_tokens = assessment_usage.get("completion_tokens", 0)
                                image_tokens = assessment_usage.get("image_tokens", 0)
                                text_tokens = assessment_usage.get("text_tokens", 0)
                                assessment_count = assessment_usage.get("assessment_count", 0)
                                
                                logger.info(f"Image assessment cost: ${stage_cost:.6f} using {IMAGE_ASSESSMENT_MODEL_ID}")
                                logger.info(f"  Detailed breakdown:")
                                logger.info(f"    Total prompt tokens: {total_prompt_tokens:,}")
                                logger.info(f"      └─ Image tokens: {image_tokens:,}")
                                logger.info(f"      └─ Text tokens: {text_tokens:,}")
                                logger.info(f"    Completion tokens: {completion_tokens:,}")
                                logger.info(f"    Assessments completed: {assessment_count}")
                            elif stage_cost == 0:
                                stage_cost = 0.0001  # Minimal cost if no usage data
                            
                        else:
                            # Other stages - minimal cost
                            stage_cost = 0.0001
                            
                    except Exception as e:
                        logger.warning(f"Failed to calculate cost for stage {stage_name}: {e}")
                        # Fallback to minimal cost
                        stage_cost = 0.0001
                    
                    if stage_cost > 0:
                        total_cost += stage_cost
                        stage_costs.append({
                            "stage_name": stage_name,
                            "cost_usd": stage_cost,
                            "duration_seconds": duration_seconds
                        })
                        logger.info(f"Stage {stage_name} actual cost: ${stage_cost:.6f}")
                        
                        # Update context with cost information directly on the context object
                        cost_summary_data = {
                            "total_pipeline_cost_usd": total_cost,
                            "stage_costs": stage_costs,
                            "total_pipeline_duration_seconds": sum(c["duration_seconds"] for c in stage_costs)
                        }
                        
                        # Set cost_summary on the context object directly (not via data property)
                        context.cost_summary = cost_summary_data
                        
                        logger.debug(f"Updated context cost_summary in data structure: ${total_cost:.6f} total, {len(stage_costs)} stages")
                
                # Enhance message for image processing issues
                enhanced_message = message
                if stage_name == "image_eval" and output_data and "image_analysis" in output_data:
                    image_analysis = output_data["image_analysis"]
                    if image_analysis is None and request.image_reference:
                        enhanced_message = f"IMPORTANT: Your uploaded image '{request.image_reference.filename}' could not be analyzed. Using generic fallback instead. This may affect result quality."
                        error_message = "Image analysis failed - using simulation mode"
                
                await self._send_stage_update(
                    run_id, stage_name, stage_order, status, 
                    enhanced_message, output_data, error_message, duration_seconds
                )
            
            # Execute pipeline
            executor = PipelineExecutor()
            await executor.run_async(context, progress_callback)
            
            # Calculate final cost summary using actual LLM usage data
            await self._calculate_final_cost_summary(context)
            
            # Process results
            await self._process_pipeline_results(run_id, context, str(output_dir))
            
            # Mark as completed
            with Session(engine) as session:
                run = session.get(PipelineRun, run_id)
                if run:
                    run.status = RunStatus.COMPLETED
                    run.completed_at = datetime.utcnow()
                    run.total_duration_seconds = (run.completed_at - run.started_at).total_seconds()
                    run.output_directory = str(output_dir)
                    
                    # Extract cost information from context
                    extracted_cost = None
                    try:
                        # Access cost_summary directly from context object (not via data property)
                        cost_summary = context.cost_summary
                        if cost_summary and isinstance(cost_summary, dict):
                            extracted_cost = cost_summary.get("total_pipeline_cost_usd")
                            logger.info(f"Extracted cost from context: ${extracted_cost}")
                            logger.debug(f"Cost summary structure: {cost_summary}")
                        else:
                            logger.warning(f"Cost summary not found or not dict: {type(cost_summary)}")
                            # Fallback: try accessing via data property
                            try:
                                processing_context = (context.data or {}).get("processing_context", {})
                                if processing_context and isinstance(processing_context, dict):
                                    fallback_cost_summary = processing_context.get("cost_summary", {})
                                    if fallback_cost_summary and isinstance(fallback_cost_summary, dict):
                                        extracted_cost = fallback_cost_summary.get("total_pipeline_cost_usd")
                                        logger.info(f"Extracted cost from context via fallback: ${extracted_cost}")
                            except Exception as fallback_e:
                                logger.warning(f"Fallback cost extraction also failed: {fallback_e}")
                    except Exception as e:
                        logger.warning(f"Failed to extract cost from context: {e}")
                        logger.warning(f"Context cost_summary type: {type(getattr(context, 'cost_summary', None))}")
                    
                    # Fallback: try to calculate from stage costs if context cost failed
                    if extracted_cost is None or extracted_cost == 0.0:
                        try:
                            # Calculate total from stage costs
                            calculated_cost = sum(c["cost_usd"] for c in stage_costs)
                            if calculated_cost > 0:
                                extracted_cost = calculated_cost
                                logger.info(f"Calculated cost from stage costs: ${extracted_cost}")
                        except Exception as e:
                            logger.warning(f"Failed to calculate cost from stage costs: {e}")
                    
                    # Set the final cost
                    if extracted_cost is not None and extracted_cost > 0:
                        run.total_cost_usd = extracted_cost
                        logger.info(f"Set run total cost to: ${run.total_cost_usd}")
                    else:
                        logger.warning(f"No valid cost found for run {run_id}")
                    
                    session.add(run)
                    session.commit()
                    
            # Send completion notification
            results = self._extract_pipeline_results(context)
            await connection_manager.send_run_complete(run_id, results.model_dump())
            
            logger.info(f"Pipeline run {run_id} completed successfully")
            
        except Exception as e:
            error_message = f"Pipeline execution failed: {str(e)}"
            error_traceback = traceback.format_exc()
            logger.error(f"Pipeline run {run_id} failed: {error_message}\n{error_traceback}")
            
            # Update database with error
            with Session(engine) as session:
                run = session.get(PipelineRun, run_id)
                if run:
                    run.status = RunStatus.FAILED
                    run.completed_at = datetime.utcnow()
                    run.error_message = error_message
                    if run.started_at:
                        run.total_duration_seconds = (run.completed_at - run.started_at).total_seconds()
                    session.add(run)
                    session.commit()
            
            # Send error notification
            await connection_manager.send_run_error(run_id, error_message, {"traceback": error_traceback})

    async def start_refinement_job(self, job_id: str, refinement_data: Dict[str, Any]):
        """Start a refinement job in the background"""
        # Check if there's a stalled refinement job
        with Session(engine) as session:
            job = session.get(RefinementJob, job_id)
            if not job:
                logger.error(f"Refinement job {job_id} not found in database")
                return
            
            # If job exists but shows as running and not in active tasks, it's stalled
            if job.status == RunStatus.RUNNING and job_id not in self.active_tasks:
                job.status = RunStatus.FAILED
                job.completed_at = datetime.utcnow()
                job.error_message = "Refinement execution was interrupted unexpectedly"
                session.add(job)
                session.commit()
                
                await connection_manager.send_run_error(
                    job_id,
                    "Refinement execution was interrupted unexpectedly",
                    {"type": "stalled"}
                )
                return
            
            # If job is already active, don't start again
            if job_id in self.active_tasks:
                logger.warning(f"Refinement job {job_id} is already running")
                return
            
            # Start the job
            job.status = RunStatus.RUNNING
            job.created_at = datetime.utcnow()
            job.error_message = None  # Clear any previous error
            session.add(job)
            session.commit()
        
        # Create and start the background task
        task = asyncio.create_task(self._execute_refinement(job_id, refinement_data))
        self.active_tasks[job_id] = task
        
        # Start timeout monitor (shorter timeout for refinements)
        refinement_timeout = 1800  # 30 minutes for refinements
        timeout_task = asyncio.create_task(self._check_refinement_timeout(job_id, refinement_timeout))
        self.run_timeouts[job_id] = timeout_task
        
        # Clean up completed tasks
        def cleanup_tasks(t):
            self.active_tasks.pop(job_id, None)
            if job_id in self.run_timeouts:
                self.run_timeouts[job_id].cancel()
        
        task.add_done_callback(cleanup_tasks)
        
        logger.info(f"Started background refinement task for job {job_id}")

    async def _check_refinement_timeout(self, job_id: str, timeout_seconds: int):
        """Check if a refinement job has exceeded the timeout limit"""
        try:
            await asyncio.sleep(timeout_seconds)
            if job_id in self.active_tasks:
                logger.warning(f"Refinement job {job_id} exceeded timeout limit of {timeout_seconds}s")
                await self._handle_refinement_timeout(job_id)
        except asyncio.CancelledError:
            pass
        finally:
            self.run_timeouts.pop(job_id, None)

    async def _handle_refinement_timeout(self, job_id: str):
        """Handle a timed out refinement job"""
        if job_id in self.active_tasks:
            task = self.active_tasks[job_id]
            task.cancel()
            self.active_tasks.pop(job_id, None)
            
            # Update database
            with Session(engine) as session:
                job = session.get(RefinementJob, job_id)
                if job and job.status == RunStatus.RUNNING:
                    job.status = RunStatus.FAILED
                    job.completed_at = datetime.utcnow()
                    job.error_message = "Refinement execution timed out"
                    session.add(job)
                    session.commit()
            
            # Notify clients
            await connection_manager.send_run_error(
                job_id, 
                "Refinement execution timed out",
                {"type": "timeout"}
            )

    async def _execute_refinement(self, job_id: str, refinement_data: Dict[str, Any]):
        """Execute the refinement pipeline with progress updates"""
        try:
            # DEBUG: Log refinement data being processed in background task
            logger.info(f"Starting refinement execution - Job ID: {job_id}")
            logger.info(f"Refinement data in background processor: {refinement_data}")
            
            # Get job details from database
            with Session(engine) as session:
                job = session.get(RefinementJob, job_id)
                if not job:
                    logger.error(f"Refinement job {job_id} not found in database")
                    return
                
                job.status = RunStatus.RUNNING
                job.created_at = datetime.utcnow()
                session.add(job)
                session.commit()
                
                # Get parent run details for context
                parent_run = session.get(PipelineRun, job.parent_run_id)
                if not parent_run:
                    raise ValueError(f"Parent run {job.parent_run_id} not found")
            
            # Set up directories
            parent_run_dir = Path(f"./data/runs/{job.parent_run_id}")
            refinements_dir = parent_run_dir / "refinements"
            refinements_dir.mkdir(exist_ok=True)
            
            # Create pipeline context
            context = PipelineContext()
            context.parent_run_id = job.parent_run_id
            context.parent_image_id = job.parent_image_id
            context.parent_image_type = job.parent_image_type
            context.generation_index = job.generation_index
            context.refinement_type = job.refinement_type
    
            context.base_run_dir = str(parent_run_dir)
            
            # Set refinement-specific inputs
            if job.refinement_type == "subject":
                context.instructions = refinement_data.get("instructions")
                context.reference_image_path = refinement_data.get("reference_image_path")
            elif job.refinement_type == "text":
                context.instructions = refinement_data.get("instructions")
            elif job.refinement_type == "prompt":
                context.prompt = refinement_data.get("prompt")
                context.mask_coordinates = refinement_data.get("mask_coordinates")
            
            # Load parent run metadata for context enhancement
            metadata_path = parent_run_dir / "pipeline_metadata.json"
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    context.original_pipeline_data = json.load(f)
            
            # Initialize cost tracking
            total_cost = 0.0
            stage_costs = []
            
            # Set up progress callback for refinement
            async def refinement_progress_callback(stage_name: str, stage_order: int, status: StageStatus, 
                                                  message: str, output_data: Optional[Dict] = None, 
                                                  error_message: Optional[str] = None,
                                                  duration_seconds: Optional[float] = None):
                
                # Calculate cost for refinement stages
                nonlocal total_cost, stage_costs
                if status == StageStatus.COMPLETED and duration_seconds:
                    stage_cost = 0.0
                    
                    # Calculate refinement-specific costs
                    if stage_name in ["subject_repair", "text_repair", "prompt_refine"]:
                        # Get cost from context if calculated by stage
                        stage_cost = getattr(context, 'refinement_cost', 0.0)
                        if stage_cost == 0.0:
                            # Fallback estimation
                            stage_cost = 0.040  # Typical DALL-E edit cost
                    else:
                        stage_cost = 0.001  # Minimal cost for utility stages
                    
                    if stage_cost > 0:
                        total_cost += stage_cost
                        stage_costs.append({
                            "stage_name": stage_name,
                            "cost_usd": stage_cost,
                            "duration_seconds": duration_seconds
                        })
                        logger.info(f"Refinement stage {stage_name} cost: ${stage_cost:.6f}")
                
                # Send WebSocket progress update
                await self._send_stage_update(
                    job_id, stage_name, stage_order, status, 
                    message, output_data, error_message, duration_seconds
                )
            
            # Execute refinement pipeline
            executor = PipelineExecutor(mode="refinement")
            await executor.run_async(context, refinement_progress_callback)
            
            # Update job with results
            # The updated context will be passed down from above
            with Session(engine) as session:
                job = session.get(RefinementJob, job_id)
                if job:
                    job.status = RunStatus.COMPLETED
                    job.completed_at = datetime.utcnow()
                    job.cost_usd = total_cost
                    if job.refinement_type == "subject":
                        job.refinement_summary = "Subject replaced = False" 
                    elif job.refinement_type == "text":
                        job.refinement_summary = "Text repaired = False" 
                    elif job.refinement_type == "prompt":
                        job.refinement_summary = "Prompt refined = False"

                    # Set result path from context
                    # If has refinement_result indicates the subject repair is success
                    if hasattr(context, 'refinement_result') and context.refinement_result:
                        job.image_path = context.refinement_result.get("output_path")
                        if job.refinement_type == "subject":
                            job.refinement_summary = "Subject replaced = " + str(context.refinement_result.get("modifications")['subject_replaced']) 
                        elif job.refinement_type == "text":
                            job.refinement_summary = "Text repaired = " + str(context.refinement_result.get("modifications")['text_corrected']) 
                        elif job.refinement_type == "prompt":
                            job.refinement_summary = "Prompt refined = " + str(context.refinement_result.get("modifications")['prompt_refined']) 
                    session.add(job)
                    session.commit()
            
                
                # Send completion notification with refinement-specific data
                refinement_result = {
                    "job_id": job_id,
                    "type": job.refinement_type,
                    "parent_run_id": job.parent_run_id,
                    "parent_image_type": job.parent_image_type,
                    "parent_image_path": self._get_parent_image_path(job),
                    "reference_image_path": context.reference_image_path, 
                    "image_path": job.image_path,
                    "cost_usd": job.cost_usd,
                    "summary": job.refinement_summary,
                    "created_at": job.created_at.isoformat() if job.created_at else None
                }
                
                # Update refinements.json index
                await self._update_refinements_index(refinement_result)
                
                await connection_manager.send_run_complete(job_id, refinement_result)
                logger.info(f"Refinement job {job_id} completed successfully")
            
        except Exception as e:
            error_message = f"Refinement execution failed: {str(e)}"
            error_traceback = traceback.format_exc()
            logger.error(f"Refinement job {job_id} failed: {error_message}\n{error_traceback}")
            
            # Update database with error
            with Session(engine) as session:
                job = session.get(RefinementJob, job_id)
                if job:
                    job.status = RunStatus.FAILED
                    job.completed_at = datetime.utcnow()
                    job.error_message = error_message
                    session.add(job)
                    session.commit()
            
            # Send error notification
            await connection_manager.send_run_error(job_id, error_message, {"traceback": error_traceback})

    async def _update_refinements_index(self, refinement_result):
        """Update the refinements.json index file"""
        try:
            parent_run_dir = Path(f"./data/runs/{refinement_result['parent_run_id']}")
            refinements_file = parent_run_dir / "refinements.json"
            
            # Load existing refinements or create new structure
            if refinements_file.exists():
                with open(refinements_file, 'r') as f:
                    refinements_data = json.load(f)
            else:
                logger.info(f"Refinements file {refinements_file} does not exist, creating new")
                refinements_data = {
                    "refinements": [],
                    "total_cost": 0.0,
                    "total_refinements": 0
                }
            
            refinements_data["refinements"].append(refinement_result)
            refinements_data["total_cost"] += refinement_result["cost_usd"]
            refinements_data["total_refinements"] = len(refinements_data["refinements"])
            
            # Save updated index
            with open(refinements_file, 'w') as f:
                json.dump(refinements_data, f, indent=2)
            
            logger.info(f"Updated refinements index for run {refinement_result['job_id']}")
            
        except Exception as e:
            logger.error(f"Failed to update refinements index: {e}")

    def _get_parent_image_path(self, job: RefinementJob) -> str:
        """Get the relative path to the parent image"""
        if job.parent_image_type == "original":
            return f"edit_image_strategy_{job.generation_index}.png"
        else:
            # It's a refinement, need to look up the path
            return f"refinements/{job.parent_image_id}_from_{job.generation_index}.png"
    
    async def _send_stage_update(self, run_id: str, stage_name: str, stage_order: int, 
                                status: StageStatus, message: str, 
                                output_data: Optional[Dict] = None,
                                error_message: Optional[str] = None,
                                duration_seconds: Optional[float] = None):
        """Send stage progress update via WebSocket"""
        
        # Update database and capture values for WebSocket
        stage_started_at = None
        stage_completed_at = None
        stage_duration_seconds = duration_seconds
        
        with Session(engine) as session:
            # Find or create stage record
            stage = session.exec(
                select(PipelineStage).where(
                    PipelineStage.run_id == run_id,
                    PipelineStage.stage_name == stage_name
                )
            ).first()
            
            if not stage:
                stage = PipelineStage(
                    run_id=run_id,
                    stage_name=stage_name,
                    stage_order=stage_order,
                    status=status
                )
            
            # Update stage status and timing
            stage.status = status
            if status == StageStatus.RUNNING and not stage.started_at:
                stage.started_at = datetime.utcnow()
            elif status in [StageStatus.COMPLETED, StageStatus.FAILED] and not stage.completed_at:
                stage.completed_at = datetime.utcnow()
                if stage.started_at:
                    stage.duration_seconds = (stage.completed_at - stage.started_at).total_seconds()
            
            if duration_seconds is not None:
                stage.duration_seconds = duration_seconds
            
            if output_data:
                stage.output_data = json.dumps(output_data)
            
            if error_message:
                stage.error_message = error_message
                
            session.add(stage)
            session.commit()
            
            # Capture values while still in session
            stage_started_at = stage.started_at
            stage_completed_at = stage.completed_at
            stage_duration_seconds = stage.duration_seconds
        
        # Send WebSocket update using captured values
        update = StageProgressUpdate(
            stage_name=stage_name,
            stage_order=stage_order,
            status=status,
            started_at=stage_started_at,
            completed_at=stage_completed_at,
            duration_seconds=stage_duration_seconds,
            message=message,
            output_data=output_data,
            error_message=error_message
        )
        
        await connection_manager.send_stage_update(run_id, update)
    
    def _convert_request_to_pipeline_data(self, request: PipelineRunRequest, 
                                        output_dir: str, image_path: Optional[Path] = None, 
                                        image_data: Optional[bytes] = None) -> Dict[str, Any]:
        """Convert API request to pipeline data format (matching original notebook)"""
        
        # Build pipeline_data structure matching the original notebook format
        pipeline_data = {
            "pipeline_settings": {
                "run_timestamp": datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f"),
                "creativity_level_selected": request.creativity_level,
                "num_variants": request.num_variants
            },
            "request_details": {
                "mode": request.mode,
                "task_type": request.task_type,
                "target_platform": {
                    "name": request.platform_name,
                    "resolution_details": self._get_platform_resolution(request.platform_name)
                }
            },
            "user_inputs": {
                "prompt": request.prompt,
                "image_reference": None,
                "render_text": request.render_text,
                "apply_branding": request.apply_branding,
                "branding_elements": request.branding_elements,
                "task_description": request.task_description,
                "marketing_goals": None
            },
            "processing_context": {
                "initial_json_valid": True,
                "image_analysis_result": None,
                "suggested_marketing_strategies": None,
                "style_guidance_sets": None,
                "generated_image_prompts": [],
                "final_assembled_prompts": [],
                "generated_image_results": [],
                "llm_call_usage": {},
                "cost_summary": {"stage_costs": [], "total_pipeline_cost_usd": 0.0}
            }
        }
        
        # Add image reference if provided
        if request.image_reference and image_path and image_data:
            # Convert image data to base64 for VLM analysis
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            pipeline_data["user_inputs"]["image_reference"] = {
                "filename": request.image_reference.filename,
                "content_type": request.image_reference.content_type,
                "size_bytes": request.image_reference.size_bytes,
                "instruction": request.image_reference.instruction,
                "saved_image_path_in_run_dir": str(image_path),
                "image_content_base64": image_base64  # This is what VLM analysis needs!
            }
        
        # Add marketing goals if provided
        if request.marketing_goals:
            pipeline_data["user_inputs"]["marketing_goals"] = {
                "target_audience": request.marketing_goals.target_audience,
                "objective": request.marketing_goals.objective,
                "voice": request.marketing_goals.voice,
                "niche": request.marketing_goals.niche
            }
        
        return pipeline_data
    
    def _get_platform_resolution(self, platform_name: str) -> Dict[str, Any]:
        """Get platform resolution details (from original constants)"""
        platform_map = {
            'Instagram Post (1:1 Square)': {'width': 1080, 'height': 1080, 'aspect_ratio': '1:1'},
            'Instagram Story/Reel (9:16 Vertical)': {'width': 1080, 'height': 1920, 'aspect_ratio': '9:16'},
            'Facebook Post (Mixed)': {'width': 1200, 'height': 630, 'aspect_ratio': '1.91:1'},
            'Pinterest Pin (2:3 Vertical)': {'width': 1024, 'height': 1536, 'aspect_ratio': '2:3'},
            'Xiaohongshu (Red Note) (3:4 Vertical)': {'width': 1080, 'height': 1440, 'aspect_ratio': '3:4'},
        }
        return platform_map.get(platform_name, {'width': 1080, 'height': 1080, 'aspect_ratio': '1:1'})
    
    async def _process_pipeline_results(self, run_id: str, context: PipelineContext, output_dir: str):
        """Process and save pipeline results"""
        try:
            # Save complete pipeline metadata as JSON
            metadata_path = Path(output_dir) / "pipeline_metadata.json"
            
            # Ensure context has valid data
            if not context or not context.data:
                logger.warning(f"Pipeline context data is empty for run {run_id}, creating minimal structure")
                if not context:
                    context = PipelineContext()
                context.data = {"processing_context": {}, "pipeline_settings": {}, "user_inputs": {}}
            
            # Create a sanitized version for saving (remove base64 data)
            try:
                sanitized_data = json.loads(json.dumps(context.data, default=str))
            except Exception as e:
                logger.error(f"Failed to serialize context data for run {run_id}: {e}")
                sanitized_data = {"error": "Failed to serialize pipeline data", "processing_context": {}}
            
            # Add safety check for None data
            if (sanitized_data and 
                isinstance(sanitized_data, dict) and 
                sanitized_data.get("user_inputs", {}) and
                isinstance(sanitized_data.get("user_inputs"), dict) and
                sanitized_data["user_inputs"].get("image_reference", {}) and
                isinstance(sanitized_data["user_inputs"].get("image_reference"), dict) and
                sanitized_data["user_inputs"]["image_reference"].get("image_content_base64")):
                sanitized_data["user_inputs"]["image_reference"]["image_content_base64"] = "[[Removed for save]]"
            
            with open(metadata_path, 'w') as f:
                json.dump(sanitized_data, f, indent=2)
            
            # Update database with metadata path
            with Session(engine) as session:
                run = session.get(PipelineRun, run_id)
                if run:
                    run.metadata_file_path = str(metadata_path)
                    session.add(run)
                    session.commit()
            
            logger.info(f"Saved pipeline metadata to {metadata_path}")
            
        except Exception as e:
            logger.error(f"Failed to process pipeline results for run {run_id}: {e}")
            logger.error(f"Error details: {traceback.format_exc()}")
    
    def _extract_pipeline_results(self, context: PipelineContext) -> PipelineResults:
        """Extract results for API response"""
        try:
            # Add comprehensive safety checks
            if not context:
                logger.warning("Context is None in _extract_pipeline_results")
                context = PipelineContext()
                context.data = {}
            
            data = context.data or {}
            processing_context = data.get("processing_context") if isinstance(data, dict) else {}
            
            if not isinstance(processing_context, dict):
                logger.warning(f"processing_context is not a dict: {type(processing_context)}")
                processing_context = {}
            
            # Extract generated images
            generated_images = []
            image_results = processing_context.get("generated_image_results", []) or []
            
            if not isinstance(image_results, list):
                logger.warning(f"generated_image_results is not a list: {type(image_results)}")
                image_results = []
            
            for result in image_results:
                if result and isinstance(result, dict):  # Enhanced safety check
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
            cost_summary = processing_context.get("cost_summary") if isinstance(processing_context, dict) else {}
            if not isinstance(cost_summary, dict):
                logger.warning(f"cost_summary is not a dict: {type(cost_summary)}")
                cost_summary = {}
        
        except Exception as e:
            logger.error(f"Error in _extract_pipeline_results: {e}")
            logger.error(f"Context type: {type(context)}, Context.data type: {type(getattr(context, 'data', None))}")
            # Return minimal safe structure
            generated_images = []
            cost_summary = {}
            data = {}
            processing_context = {}
        
        # Safe extraction of fields with defaults
        pipeline_settings = data.get("pipeline_settings") if isinstance(data, dict) else {}
        if not isinstance(pipeline_settings, dict):
            pipeline_settings = {}
        
        run_id = pipeline_settings.get("run_timestamp", "unknown")
        
        return PipelineResults(
            run_id=run_id,
            status=RunStatus.COMPLETED,
            image_analysis=processing_context.get("image_analysis_result") if isinstance(processing_context, dict) else None,
            marketing_strategies=processing_context.get("suggested_marketing_strategies") if isinstance(processing_context, dict) else None,
            style_guidance=processing_context.get("style_guidance_sets") if isinstance(processing_context, dict) else None,
            visual_concepts=processing_context.get("generated_image_prompts") if isinstance(processing_context, dict) else None,
            final_prompts=processing_context.get("final_assembled_prompts") if isinstance(processing_context, dict) else None,
            generated_images=generated_images,
            total_cost_usd=cost_summary.get("total_pipeline_cost_usd") if isinstance(cost_summary, dict) else None,
            total_duration_seconds=cost_summary.get("total_pipeline_duration_seconds") if isinstance(cost_summary, dict) else None,
            stage_costs=cost_summary.get("stage_costs") if isinstance(cost_summary, dict) else None
        )
    
    def cancel_run(self, run_id: str) -> bool:
        """Cancel a running pipeline"""
        if run_id not in self.active_tasks:
            # Check if run exists but is stalled
            with Session(engine) as session:
                run = session.get(PipelineRun, run_id)
                if run and run.status == RunStatus.RUNNING:
                    run.status = RunStatus.CANCELLED
                    run.completed_at = datetime.utcnow()
                    run.error_message = "Pipeline execution was cancelled"
                    if run.started_at:
                        run.total_duration_seconds = (run.completed_at - run.started_at).total_seconds()
                    session.add(run)
                    session.commit()
                    
                    asyncio.create_task(connection_manager.send_run_error(
                        run_id,
                        "Pipeline execution was cancelled",
                        {"type": "cancelled"}
                    ))
                    return True
            return False
        
        # Cancel active task
        task = self.active_tasks[run_id]
        task.cancel()
        
        # Cancel timeout task if exists
        if run_id in self.run_timeouts:
            self.run_timeouts[run_id].cancel()
        
        # Update database
        with Session(engine) as session:
            run = session.get(PipelineRun, run_id)
            if run:
                run.status = RunStatus.CANCELLED
                run.completed_at = datetime.utcnow()
                run.error_message = "Pipeline execution was cancelled"
                if run.started_at:
                    run.total_duration_seconds = (run.completed_at - run.started_at).total_seconds()
                session.add(run)
                session.commit()
        
        logger.info(f"Cancelled pipeline run {run_id}")
        return True

    def cancel_refinement(self, job_id: str) -> bool:
        """Cancel a running refinement job"""
        if job_id not in self.active_tasks:
            # Check if job exists but is stalled
            with Session(engine) as session:
                job = session.get(RefinementJob, job_id)
                if job and job.status == RunStatus.RUNNING:
                    job.status = RunStatus.CANCELLED
                    job.completed_at = datetime.utcnow()
                    job.error_message = "Refinement execution was cancelled"
                    session.add(job)
                    session.commit()
                    
                    asyncio.create_task(connection_manager.send_run_error(
                        job_id,
                        "Refinement execution was cancelled",
                        {"type": "cancelled"}
                    ))
                    return True
            return False
        
        # Cancel active task
        task = self.active_tasks[job_id]
        task.cancel()
        
        # Cancel timeout task if exists
        if job_id in self.run_timeouts:
            self.run_timeouts[job_id].cancel()
        
        # Update database
        with Session(engine) as session:
            job = session.get(RefinementJob, job_id)
            if job:
                job.status = RunStatus.CANCELLED
                job.completed_at = datetime.utcnow()
                job.error_message = "Refinement execution was cancelled"
                session.add(job)
                session.commit()
        
        logger.info(f"Cancelled refinement job {job_id}")
        return True
    
    def get_active_runs(self) -> list[str]:
        """Get list of currently running pipeline tasks"""
        return list(self.active_tasks.keys())
    
    def _estimate_stage_cost(self, stage_name: str, duration_seconds: float) -> float:
        """
        DEPRECATED: This method used hardcoded estimates and caused duplicate costs.
        Cost calculation now uses actual API usage data in progress_callback.
        """
        logger.warning("_estimate_stage_cost is deprecated and should not be called")
        return 0.0
        
        # OLD HARDCODED LOGIC (COMMENTED OUT):
        # """Estimate cost for a stage based on model pricing and typical usage"""
        # # More realistic cost estimation based on model pricing from constants
        # if stage_name == "image_generation":
        #     # For gpt-image-1, estimate based on token-based pricing
        #     # Assume medium quality 1024x1024 images (most common)
        #     # Text input: ~100 tokens, Image output: ~1056 tokens per image
        #     # Assume 3 images generated per run (typical)
        #     text_tokens = 100  # Estimated prompt tokens
        #     image_output_tokens = 1056 * 3  # 3 medium quality images
        #     
        #     text_cost = (text_tokens / 1_000_000) * 5.00  # $5/1M tokens
        #     image_cost = (image_output_tokens / 1_000_000) * 40.00  # $40/1M tokens
        #     
        #     total_cost = text_cost + image_cost
        #     logger.info(f"Image generation cost: ${text_cost:.6f} (text) + ${image_cost:.6f} (images) = ${total_cost:.6f}")
        #     return total_cost
        #     
        # elif stage_name == "image_eval":
        #     # Vision model: gpt-4.1-mini with image input
        #     # Estimate ~500 text tokens input + image processing
        #     text_tokens = 500
        #     output_tokens = 200
        #     cost = (text_tokens / 1_000_000) * 0.40 + (output_tokens / 1_000_000) * 1.20
        #     return cost
        #     
        # elif stage_name in ["strategy", "style_guide", "creative_expert"]:
        #     # Text generation models
        #     if stage_name == "creative_expert":
        #         # More complex generation - gemini-2.5-pro-preview
        #         input_tokens = 1000
        #         output_tokens = 800
        #         cost = (input_tokens / 1_000_000) * 1.25 + (output_tokens / 1_000_000) * 10.00
        #     else:
        #         # Simpler generation - gpt-4.1-mini 
        #         input_tokens = 600
        #         output_tokens = 400
        #         cost = (input_tokens / 1_000_000) * 0.40 + (output_tokens / 1_000_000) * 1.20
        #     return cost
        #     
        # else:
        #     # prompt_assembly and other stages - minimal cost
        #     base_cost = 0.0001
        #     
        # # Apply duration factor for very long runs (unusual cases)  
        # if duration_seconds > 120:  # More than 2 minutes is unusual
        #     duration_multiplier = min(1.5, 1 + (duration_seconds - 120) / 600)  # Cap at 1.5x
        #     base_cost *= duration_multiplier
        #     
        # return base_cost

    async def _calculate_final_cost_summary(self, context: PipelineContext):
        """Calculate final cost summary using actual LLM usage data and preserve real stage durations"""
        try:
            logger.info("🔧 _calculate_final_cost_summary: Starting final cost calculation")
            
            # Check if we already have a valid cost summary with durations from progress_callback
            if hasattr(context, 'cost_summary') and context.cost_summary:
                existing_summary = context.cost_summary
                if isinstance(existing_summary, dict) and existing_summary.get("stage_costs"):
                    # We already have cost data from progress tracking, just verify and return
                    total_cost = existing_summary.get("total_pipeline_cost_usd", 0.0)
                    stage_count = len(existing_summary.get("stage_costs", []))
                    logger.info(f"✅ Using existing cost summary from progress tracking: ${total_cost:.6f} across {stage_count} stages")
                    return
            
            # Ensure context has valid data
            if not context or not context.data:
                logger.warning("Pipeline context data is empty in _calculate_final_cost_summary")
                logger.warning(f"Context: {context}, Context.data: {getattr(context, 'data', None)}")
                return
            
            data = context.data or {}
            processing_context = data.get("processing_context") if isinstance(data, dict) else {}
            
            if not isinstance(processing_context, dict):
                logger.warning(f"processing_context is not a dict: {type(processing_context)}")
                return
            
            llm_usage = processing_context.get("llm_call_usage", {})
            if not isinstance(llm_usage, dict):
                logger.warning(f"llm_call_usage is not a dict: {type(llm_usage)}")
                return
            
            if not llm_usage:
                logger.info("No LLM usage data found, skipping cost calculation")
                return
            
            logger.info(f"🔧 Found LLM usage data with {len(llm_usage)} keys: {list(llm_usage.keys())}")
            
            # Get actual stage durations from database 
            actual_durations = await self._get_actual_stage_durations(context.run_id)
            
            # Calculate costs for each stage using the same logic as background_tasks.py
            total_cost = 0.0
            stage_costs = []
            
            # Define stage mappings (same as progress callback logic)
            stage_mappings = [
                ("image_eval", ["image_eval"], IMG_EVAL_MODEL_ID),
                ("strategy", ["strategy_niche_id", "strategy_goal_gen"], STRATEGY_MODEL_ID),
                ("style_guide", ["style_guider"], STYLE_GUIDER_MODEL_ID),
                ("creative_expert", [key for key in llm_usage.keys() if key.startswith("creative_expert_strategy_")], CREATIVE_EXPERT_MODEL_ID),
                ("image_assessment", ["image_assessment"], IMAGE_ASSESSMENT_MODEL_ID),
            ]
            
            logger.info(f"🔧 Processing {len(stage_mappings)} stage mappings")
            
            # Handle image generation separately (different structure)
            image_results = processing_context.get("generated_image_results", [])
            if image_results:
                actual_images = len([r for r in image_results if r.get("status") == "success"])
                total_prompt_tokens = sum(r.get("prompt_tokens", 0) for r in image_results if r.get("prompt_tokens"))
                
                logger.info(f"🔧 Image generation: {actual_images} images, {total_prompt_tokens} tokens")
                
                if actual_images > 0 and total_prompt_tokens > 0:
                    try:
                        token_manager = get_token_cost_manager()
                        from churns.core.token_cost_manager import TokenUsage
                        
                        usage = TokenUsage(
                            prompt_tokens=total_prompt_tokens,
                            completion_tokens=0,
                            total_tokens=total_prompt_tokens,
                            model=IMAGE_GENERATION_MODEL_ID,
                            provider="openai"
                        )
                        
                        image_details = {
                            "count": actual_images,
                            "resolution": "1024x1024",
                            "quality": "medium"
                        }
                        
                        cost_breakdown = token_manager.calculate_cost(usage, image_details)
                        stage_cost = cost_breakdown.total_cost
                        
                        # Use actual duration if available, otherwise estimate
                        actual_duration = actual_durations.get("image_generation", 25.0)  # Default to 25s for image gen
                        
                        stage_costs.append({
                            "stage_name": "image_generation",
                            "cost_usd": stage_cost,
                            "duration_seconds": actual_duration
                        })
                        total_cost += stage_cost
                        
                        logger.info(f"🔧 Final calculation - Image generation: ${stage_cost:.6f} (duration: {actual_duration:.1f}s)")
                        
                    except Exception as e:
                        logger.warning(f"Failed to calculate image generation cost: {e}")
            
            # Calculate costs for other stages
            for stage_name, usage_keys, model_id in stage_mappings:
                try:
                    logger.debug(f"🔧 Calculating {stage_name} with keys {usage_keys}")
                    
                    cost_result = calculate_stage_cost_from_usage(
                        stage_name, llm_usage, usage_keys, model_id
                    )
                    stage_cost = cost_result.get("total_cost", 0.0)
                    
                    if stage_cost > 0:
                        # Use actual duration if available, otherwise estimate based on stage type
                        actual_duration = actual_durations.get(stage_name)
                        if actual_duration is None:
                            # Provide realistic estimates based on stage complexity
                            duration_estimates = {
                                "image_eval": 3.0,
                                "strategy": 12.0, 
                                "style_guide": 20.0,
                                "creative_expert": 30.0,
                                "image_assessment": 45.0,
                                "prompt_assembly": 1.0
                            }
                            actual_duration = duration_estimates.get(stage_name, 5.0)
                        
                        stage_costs.append({
                            "stage_name": stage_name,
                            "cost_usd": stage_cost,
                            "duration_seconds": actual_duration
                        })
                        total_cost += stage_cost
                        
                        logger.info(f"🔧 Final calculation - {stage_name}: ${stage_cost:.6f} (duration: {actual_duration:.1f}s)")
                        
                except Exception as e:
                    logger.warning(f"Failed to calculate cost for stage {stage_name}: {e}")
            
            logger.info(f"🔧 Calculated total cost: ${total_cost:.6f} across {len(stage_costs)} stages")
            
            # Store the cost summary directly on the context object
            cost_summary_data = {
                "total_pipeline_cost_usd": total_cost,
                "stage_costs": stage_costs,
                "total_pipeline_duration_seconds": sum(c["duration_seconds"] for c in stage_costs)
            }
            
            # Set cost_summary on the context object directly (not via data property)
            context.cost_summary = cost_summary_data
            
            logger.info(f"🔧 Updated context.data cost_summary: {cost_summary_data}")
            logger.info(f"✅ Final cost calculation complete: ${total_cost:.6f} total across {len(stage_costs)} stages")
            
            # Verify the update was applied - use the cost_summary_data directly since we just set it
            logger.info(f"🔧 Verification - cost_summary successfully updated: total=${cost_summary_data.get('total_pipeline_cost_usd', 0):.6f}, stages={len(cost_summary_data.get('stage_costs', []))}")
            
        except Exception as e:
            logger.error(f"Failed to calculate final cost summary: {e}")
            logger.error(f"Error details: {traceback.format_exc()}")

    async def _get_actual_stage_durations(self, run_id: str) -> Dict[str, float]:
        """Retrieve actual stage durations from database."""
        durations = {}
        try:
            with Session(engine) as session:
                stages = session.exec(
                    select(PipelineStage).where(PipelineStage.run_id == run_id)
                ).all()
                
                for stage in stages:
                    if stage.duration_seconds is not None:
                        durations[stage.stage_name] = stage.duration_seconds
                        logger.debug(f"Retrieved duration for {stage.stage_name}: {stage.duration_seconds:.1f}s")
                
                logger.info(f"Retrieved {len(durations)} actual stage durations from database")
                
        except Exception as e:
            logger.warning(f"Failed to retrieve stage durations from database: {e}")
        
        return durations


# Global task processor instance
task_processor = PipelineTaskProcessor() 