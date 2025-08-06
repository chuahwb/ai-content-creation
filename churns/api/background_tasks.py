import asyncio
import json
import traceback
import base64
import os
from datetime import datetime
from typing import Dict, Any, Optional
import logging
from pathlib import Path
from copy import deepcopy

from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from churns.api.database import (
    get_session, PipelineRun, PipelineStage, RefinementJob,
    RunStatus, StageStatus, engine, async_session_factory,
    retry_db_operation
)
from churns.pipeline.executor import PipelineExecutor
from churns.api.schemas import (
    PipelineRunRequest, StageProgressUpdate, 
    GeneratedImageResult, PipelineResults, WebSocketMessage
)
from churns.api.websocket import connection_manager
from churns.pipeline.context import PipelineContext
from churns.core.constants import (
    MODEL_PRICING, 
    IMAGE_ASSESSMENT_MODEL_ID,
    IMG_EVAL_MODEL_ID,
    STRATEGY_MODEL_ID, 
    STYLE_GUIDER_MODEL_ID,
    CREATIVE_EXPERT_MODEL_ID,
    IMAGE_GENERATION_MODEL_ID,
    CAPTION_MODEL_ID,
    CAPTION_MODEL_PROVIDER,
    STYLE_ADAPTATION_MODEL_ID
)
from churns.core.model_selector import get_caption_model_for_processing_mode
from churns.core.token_cost_manager import get_token_cost_manager, calculate_stage_cost_from_usage
from churns.stages.image_assessment import ImageAssessor

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
            async with async_session_factory() as session:
                run = await session.get(PipelineRun, run_id)
                if run and run.status == RunStatus.RUNNING:
                    run.status = RunStatus.FAILED
                    run.completed_at = datetime.utcnow()
                    run.error_message = f"Pipeline execution timed out after {self.PIPELINE_TIMEOUT_SECONDS} seconds"
                    if run.started_at:
                        run.total_duration_seconds = (run.completed_at - run.started_at).total_seconds()
                    session.add(run)
                    await session.commit()
            
            # Notify clients
            await connection_manager.send_run_error(
                run_id, 
                f"Pipeline execution timed out after {self.PIPELINE_TIMEOUT_SECONDS} seconds",
                {"type": "timeout"}
            )

    async def start_pipeline_run(self, run_id: str, request: PipelineRunRequest, image_data: Optional[bytes] = None, executor: Optional[PipelineExecutor] = None):
        """Start a pipeline run in the background"""
        logger.info(f"start_pipeline_run called with run_id: {run_id}")
        logger.info(f"Request details: mode={request.mode}, platform={request.platform_name}, preset_id={request.preset_id}")
        
        # First check if there's a stalled run - use retry logic
        async def check_and_handle_stalled_run():
            async with async_session_factory() as session:
                run = await session.get(PipelineRun, run_id)
                if not run:
                    logger.error(f"Run {run_id} not found in database")
                    return False
                
                # If run exists but shows as running and not in active tasks, it's stalled
                if run.status == RunStatus.RUNNING and run_id not in self.active_tasks:
                    run.status = RunStatus.FAILED
                    run.completed_at = datetime.utcnow()
                    run.error_message = "Pipeline execution was interrupted unexpectedly"
                    if run.started_at:
                        run.total_duration_seconds = (run.completed_at - run.started_at).total_seconds()
                    session.add(run)
                    await session.commit()
                    
                    await connection_manager.send_run_error(
                        run_id,
                        "Pipeline execution was interrupted unexpectedly",
                        {"type": "stalled"}
                    )
                    return False  # Indicates we should not continue
                
                # If run is already active, don't start again
                if run_id in self.active_tasks:
                    logger.warning(f"Pipeline run {run_id} is already running")
                    return False
                
                return True  # All good, continue with execution
        
        should_continue = await retry_db_operation(
            check_and_handle_stalled_run,
            operation_name=f"check stalled run {run_id}"
        )
        
        if not should_continue:
            return
        
        # Create and start the background task (don't update status to RUNNING here)
        task = asyncio.create_task(self._execute_pipeline(run_id, request, image_data, executor))
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
        
        logger.info(f"Started background pipeline task for run {run_id} - task in active_tasks: {run_id in self.active_tasks}")
    
    async def _execute_pipeline(self, run_id: str, request: PipelineRunRequest, image_data: Optional[bytes] = None, executor: Optional[PipelineExecutor] = None):
        """Execute the complete pipeline with progress updates"""
        logger.info(f"_execute_pipeline called for run {run_id}")
        
        try:
            # Update run status to running - use retry logic
            async def update_run_status_to_running():
                async with async_session_factory() as session:
                    run = await session.get(PipelineRun, run_id)
                    if not run:
                        logger.error(f"Run {run_id} not found in database")
                        return False
                    
                    run.status = RunStatus.RUNNING
                    run.started_at = datetime.utcnow()
                    session.add(run)
                    await session.commit()
                    
                    logger.info(f"Updated run {run_id} status to RUNNING")
                    return True
            
            status_updated = await retry_db_operation(
                update_run_status_to_running,
                operation_name=f"update run {run_id} status to RUNNING"
            )
            
            if not status_updated:
                return
            
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
            logger.info(f"Converting request to pipeline data for run {run_id}")
            pipeline_data = self._convert_request_to_pipeline_data(request, str(output_dir), image_path, image_data)
            
            # Create pipeline context
            logger.info(f"Creating pipeline context for run {run_id}")
            context = PipelineContext.from_dict(pipeline_data)
            
            # Set the output directory for stages to use
            context.output_directory = str(output_dir)
            
            logger.info(f"Pipeline context created for run {run_id}: preset_id={context.preset_id}, preset_type={context.preset_type}")
            
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
                            
                            if actual_images > 0:
                                # Use the token cost manager for image generation
                                token_manager = get_token_cost_manager()
                                from churns.core.token_cost_manager import TokenUsage
                                
                                # Extract comprehensive token breakdown from stored metadata
                                total_text_tokens = 0
                                total_input_image_tokens = 0
                                total_tokens_including_images = 0
                                num_input_images = 0
                                
                                for result in image_results:
                                    if result.get("status") == "success":
                                        # Use enhanced token breakdown if available (new format)
                                        token_breakdown = result.get("token_breakdown", {})
                                        if token_breakdown:
                                            total_text_tokens += token_breakdown.get("text_tokens", 0)
                                            total_input_image_tokens += token_breakdown.get("input_image_tokens", 0)
                                            total_tokens_including_images += token_breakdown.get("total_tokens", 0)
                                            # Use max to handle multiple images with same input images
                                            num_input_images = max(num_input_images, token_breakdown.get("num_input_images", 0))
                                        else:
                                            # Fallback to legacy prompt_tokens (old format)
                                            legacy_tokens = result.get("prompt_tokens", 0)
                                            total_text_tokens += legacy_tokens
                                            total_tokens_including_images += legacy_tokens
                                
                                # Log comprehensive token usage
                                if total_input_image_tokens > 0:
                                    logger.info(f"Multi-modal image generation tokens: {total_text_tokens} text + {total_input_image_tokens} input images = {total_tokens_including_images} total")
                                else:
                                    logger.info(f"Text-to-image generation tokens: {total_tokens_including_images} total")
                                
                                usage = TokenUsage(
                                    prompt_tokens=total_tokens_including_images,
                                    completion_tokens=0,  # Image generation doesn't have completion tokens
                                    total_tokens=total_tokens_including_images,
                                    image_tokens=total_input_image_tokens,
                                    text_tokens=total_text_tokens,
                                    image_count=num_input_images,
                                    model=IMAGE_GENERATION_MODEL_ID,
                                    provider="openai"
                                )
                                
                                image_details = {
                                    "count": actual_images,
                                    "resolution": "1024x1024",  # Assume standard resolution for output
                                    "quality": "medium",  # Assume medium quality
                                    "input_images": num_input_images
                                }
                                
                                cost_breakdown = token_manager.calculate_cost(usage, image_details)
                                stage_cost = cost_breakdown.total_cost
                                
                                # Enhanced logging for multi-modal scenarios
                                if num_input_images > 1:
                                    logger.info(f"Multi-modal image generation cost: ${stage_cost:.6f} using {IMAGE_GENERATION_MODEL_ID}")
                                    logger.info(f"  - Text tokens: {total_text_tokens}, Input image tokens: {total_input_image_tokens} ({num_input_images} images)")
                                    logger.info(f"  - {cost_breakdown.notes}")
                                elif num_input_images == 1:
                                    logger.info(f"Single-input image generation cost: ${stage_cost:.6f} using {IMAGE_GENERATION_MODEL_ID}")
                                    logger.info(f"  - Text tokens: {total_text_tokens}, Input image tokens: {total_input_image_tokens}")
                                    logger.info(f"  - {cost_breakdown.notes}")
                                else:
                                    logger.info(f"Text-to-image generation cost: ${stage_cost:.6f} using {IMAGE_GENERATION_MODEL_ID} - {cost_breakdown.notes}")
                            else:
                                stage_cost = 0.0  # No successful generation
                                
                        elif stage_name == "image_eval":
                            # Use centralized cost calculation, including logo_eval
                            cost_result = calculate_stage_cost_from_usage(
                                stage_name, llm_usage, ["image_eval", "logo_eval"], IMG_EVAL_MODEL_ID
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
                                
                        elif stage_name == "style_adaptation":
                            # Use centralized cost calculation
                            cost_result = calculate_stage_cost_from_usage(
                                stage_name, llm_usage, ["style_adaptation"], STYLE_ADAPTATION_MODEL_ID
                            )
                            stage_cost = cost_result.get("total_cost", 0.0)
                            if stage_cost > 0:
                                logger.info(f"Style adaptation cost: ${stage_cost:.6f} using {STYLE_ADAPTATION_MODEL_ID}")
                                
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
            
            # Execute pipeline - use provided executor or create fallback
            if executor is None:
                logger.warning("No executor provided, creating new instance (this should not happen in production)")
                from churns.pipeline.executor import PipelineExecutor
                executor = PipelineExecutor()
            
            # Pass database session to executor for preset loading
            async with async_session_factory() as session:
                await executor.run_async(context, progress_callback, session)
            
            # Calculate final cost summary using actual LLM usage data
            await self._calculate_final_cost_summary(context)
            
            # Process results
            await self._process_pipeline_results(run_id, context, str(output_dir))
            
            # Mark as completed - use retry logic
            async def mark_pipeline_completed():
                async with async_session_factory() as session:
                    run = await session.get(PipelineRun, run_id)
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
                        
                        # Update brand kit data from final context (important for preset-loaded data)
                        # Only store if branding was enabled
                        if context.brand_kit and context.apply_branding:
                            import json
                            run.brand_kit = json.dumps(context.brand_kit)
                            logger.info(f"Updated database with final brand kit data: {len(str(context.brand_kit))} characters")
                        
                        session.add(run)
                        await session.commit()
                        return True
                    return False
            
            await retry_db_operation(
                mark_pipeline_completed,
                operation_name=f"mark pipeline {run_id} completed"
            )
            
            # Send completion notification
            results = self._extract_pipeline_results(context)
            await connection_manager.send_run_complete(run_id, results.model_dump())
            
            logger.info(f"Pipeline run {run_id} completed successfully")
            
        except Exception as e:
            error_message = f"Pipeline execution failed: {str(e)}"
            error_traceback = traceback.format_exc()
            logger.error(f"Pipeline run {run_id} failed: {error_message}\n{error_traceback}")
            
            # Update database with error - use retry logic
            async def mark_pipeline_failed():
                async with async_session_factory() as session:
                    run = await session.get(PipelineRun, run_id)
                    if run:
                        run.status = RunStatus.FAILED
                        run.completed_at = datetime.utcnow()
                        run.error_message = error_message
                        if run.started_at:
                            run.total_duration_seconds = (run.completed_at - run.started_at).total_seconds()
                        session.add(run)
                        await session.commit()
                        return True
                    return False
            
            await retry_db_operation(
                mark_pipeline_failed,
                operation_name=f"mark pipeline {run_id} failed"
            )
            
            # Send error notification
            await connection_manager.send_run_error(run_id, error_message, {"traceback": error_traceback})

    async def start_refinement_job(self, job_id: str, refinement_data: Dict[str, Any], executor: Optional[PipelineExecutor] = None):
        """Start a refinement job in the background"""
        # Check if there's a stalled refinement job - use retry logic
        async def check_and_handle_stalled_refinement():
            async with async_session_factory() as session:
                job = await session.get(RefinementJob, job_id)
                if not job:
                    logger.error(f"Refinement job {job_id} not found in database")
                    return False
                
                # If job exists but shows as running and not in active tasks, it's stalled
                if job.status == RunStatus.RUNNING and job_id not in self.active_tasks:
                    job.status = RunStatus.FAILED
                    job.completed_at = datetime.utcnow()
                    job.error_message = "Refinement execution was interrupted unexpectedly"
                    session.add(job)
                    await session.commit()
                    
                    await connection_manager.send_run_error(
                        job_id,
                        "Refinement execution was interrupted unexpectedly",
                        {"type": "stalled"}
                    )
                    return False
                
                # If job is already active, don't start again
                if job_id in self.active_tasks:
                    logger.warning(f"Refinement job {job_id} is already running")
                    return False
                
                # Start the job
                job.status = RunStatus.RUNNING
                job.created_at = datetime.utcnow()
                job.error_message = None  # Clear any previous error
                session.add(job)
                await session.commit()
                return True
        
        should_continue = await retry_db_operation(
            check_and_handle_stalled_refinement,
            operation_name=f"check and start refinement job {job_id}"
        )
        
        if not should_continue:
            return
        
        # Create and start the background task
        task = asyncio.create_task(self._execute_refinement(job_id, refinement_data, executor))
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
            
            # Update database - use retry logic
            async def mark_refinement_timeout():
                async with async_session_factory() as session:
                    job = await session.get(RefinementJob, job_id)
                    if job and job.status == RunStatus.RUNNING:
                        job.status = RunStatus.FAILED
                        job.completed_at = datetime.utcnow()
                        job.error_message = "Refinement execution timed out"
                        session.add(job)
                        await session.commit()
                        return True
                    return False
            
            await retry_db_operation(
                mark_refinement_timeout,
                operation_name=f"mark refinement {job_id} timeout"
            )
            
            # Notify clients
            await connection_manager.send_run_error(
                job_id, 
                "Refinement execution timed out",
                {"type": "timeout"}
            )

    async def _execute_refinement(self, job_id: str, refinement_data: Dict[str, Any], executor: Optional[PipelineExecutor] = None):
        """Execute the refinement pipeline with progress updates"""
        try:
            logger.info(f"Starting refinement execution - Job ID: {job_id}")
            logger.debug(f"Refinement data: {refinement_data}")
            
            # Get job details from database - use retry logic
            parent_run = None
            job = None
            async def get_refinement_job_details():
                nonlocal parent_run, job
                async with async_session_factory() as session:
                    job = await session.get(RefinementJob, job_id)
                    if not job:
                        logger.error(f"Refinement job {job_id} not found in database")
                        return False
                    
                    job.status = RunStatus.RUNNING
                    job.created_at = datetime.utcnow()
                    session.add(job)
                    await session.commit()
                    
                    # Get parent run details for context
                    parent_run = await session.get(PipelineRun, job.parent_run_id)
                    if not parent_run:
                        raise ValueError(f"Parent run {job.parent_run_id} not found")
                    return True
            
            details_loaded = await retry_db_operation(
                get_refinement_job_details,
                operation_name=f"get refinement job {job_id} details"
            )
            
            if not details_loaded:
                return
            
            # Set up directories
            parent_run_dir = Path(f"./data/runs/{job.parent_run_id}").resolve()  # Make absolute
            refinements_dir = parent_run_dir / "refinements"
            refinements_dir.mkdir(exist_ok=True)
            
            # Create pipeline context
            context = PipelineContext()
            context.run_id = job_id  # Set the current refinement job ID
            context.parent_run_id = job.parent_run_id
            context.parent_image_id = job.parent_image_id
            context.parent_image_type = job.parent_image_type
            context.generation_index = job.generation_index
            context.refinement_type = job.refinement_type
            context.pipeline_mode = "refinement"  # Set pipeline mode for executor

            context.base_run_dir = str(parent_run_dir)
            
            # Set refinement-specific inputs
            if job.refinement_type == "subject":
                context.instructions = refinement_data.get("instructions")
                # Handle reference image path 
                reference_image_path = refinement_data.get("reference_image_path")
                if reference_image_path:
                    # Check if path is already absolute
                    if os.path.isabs(reference_image_path):
                        context.reference_image_path = reference_image_path
                        logger.info(f"Using absolute reference image path: {reference_image_path}")
                    else:
                        # For relative paths, check if they already contain the full path
                        if reference_image_path.startswith("data/runs/"):
                            # Path is already complete, just make it absolute
                            context.reference_image_path = os.path.abspath(reference_image_path)
                            logger.info(f"Converted relative to absolute path: {reference_image_path} -> {context.reference_image_path}")
                        else:
                            # Legacy relative path handling
                            context.reference_image_path = str(parent_run_dir / reference_image_path)
                            logger.info(f"Converted legacy relative path: {reference_image_path} -> {context.reference_image_path}")
                else:
                    context.reference_image_path = None
                    logger.warning(f"No reference image path found in refinement data: {refinement_data}")
            elif job.refinement_type == "prompt":
                context.prompt = refinement_data.get("prompt")
                context.mask_coordinates = refinement_data.get("mask_coordinates")  # Legacy support
                context.mask_file_path = refinement_data.get("mask_file_path")  # New mask file support
                
                # Handle optional reference image for prompt refinement
                reference_image_path = refinement_data.get("reference_image_path")
                if reference_image_path:
                    if os.path.isabs(reference_image_path):
                        context.reference_image_path = reference_image_path
                    else:
                        context.reference_image_path = str(parent_run_dir / reference_image_path)
            
            # Load parent run metadata for context enhancement
            metadata_path = parent_run_dir / "pipeline_metadata.json"
            if metadata_path.exists():
                with open(metadata_path, 'r') as f:
                    context.original_pipeline_data = json.load(f)
            else:
                logger.warning(f"No pipeline metadata found at {metadata_path}")
                context.original_pipeline_data = {"processing_context": {}, "user_inputs": {}}
            
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
                    
                    # Get actual cost from context if calculated by stage
                    if stage_name in ["subject_repair", "prompt_refine"]:
                        # Check if stage calculated its own cost
                        stage_cost = getattr(context, 'refinement_cost', 0.0)
                        if stage_cost == 0.0:
                            # Use more accurate estimation based on OpenAI pricing
                            stage_cost = 0.042  # Current gpt-image-1 model pricing for 1024x1024
                    elif stage_name in ["load_base_image", "save_outputs"]:
                        stage_cost = 0.0  # No external API costs for utility stages
                    else:
                        stage_cost = 0.001  # Minimal cost for other utility stages
                    
                    if stage_cost > 0:
                        total_cost += stage_cost
                        stage_costs.append({
                            "stage_name": stage_name,
                            "cost_usd": stage_cost,
                            "duration_seconds": duration_seconds,
                            "model_used": "gpt-image-1" if stage_name in ["subject_repair", "prompt_refine"] else "local"
                        })
                        logger.info(f"Refinement stage {stage_name} cost: ${stage_cost:.6f}")
                
                # Send WebSocket progress update
                await self._send_stage_update(
                    job_id, stage_name, stage_order, status, 
                    message, output_data, error_message, duration_seconds
                )
            
            # Execute refinement pipeline - use shared executor if available
            if executor is None:
                logger.warning("No executor provided, creating new refinement instance (this should not happen in production)")
                from churns.pipeline.executor import PipelineExecutor
                executor = PipelineExecutor(mode="refinement")
            
            await executor.run_async(context, refinement_progress_callback)
            
            # Update job with results using database_updates from save_outputs stage
            async with async_session_factory() as session:
                job = await session.get(RefinementJob, job_id)
                if job:
                    # Use database_updates prepared by save_outputs stage if available
                    if hasattr(context, 'database_updates') and context.database_updates:
                        db_updates = context.database_updates
                        
                        # Set status based on save_outputs analysis
                        if db_updates["status"] == "completed":
                            job.status = RunStatus.COMPLETED
                        else:
                            job.status = RunStatus.FAILED
                        
                        job.completed_at = datetime.utcnow()
                        job.cost_usd = total_cost
                        job.image_path = db_updates.get("image_path")
                        job.refinement_summary = db_updates.get("refinement_summary", "Refinement processed")
                        job.error_message = db_updates.get("error_message")
                        
                        logger.info(f"Updated job {job_id} with save_outputs database_updates: status={job.status}, summary={job.refinement_summary}")
                    else:
                        # Fallback to old logic if database_updates not available
                        logger.warning(f"No database_updates found in context for job {job_id}, using fallback logic")
                        job.status = RunStatus.COMPLETED
                        job.completed_at = datetime.utcnow()
                        job.cost_usd = total_cost
                        
                        # Check if refinement actually succeeded
                        if hasattr(context, 'refinement_result') and context.refinement_result:
                            output_path = context.refinement_result.get("output_path")
                            if output_path and os.path.exists(output_path):
                                # Convert to relative path for database storage
                                try:
                                    job.image_path = str(Path(output_path).relative_to(parent_run_dir))
                                except ValueError:
                                    job.image_path = f"refinements/{os.path.basename(output_path)}"
                                job.refinement_summary = f"{job.refinement_type.title()} enhancement: Successful"
                            else:
                                job.refinement_summary = f"{job.refinement_type.title()} enhancement: No changes made"
                        else:
                            job.refinement_summary = f"{job.refinement_type.title()} enhancement: No changes made"
                    
                    session.add(job)
                    await session.commit()
            
                
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
                
                # Send completion notification to the parent run (not the job ID)
                await connection_manager.send_run_complete(job.parent_run_id, refinement_result)
                logger.info(f"Refinement job {job_id} completed successfully")
            
        except Exception as e:
            error_message = f"Refinement execution failed: {str(e)}"
            error_traceback = traceback.format_exc()
            logger.error(f"Refinement job {job_id} failed: {error_message}\n{error_traceback}")
            
            # Update database with error - use retry logic
            async def mark_refinement_failed():
                async with async_session_factory() as session:
                    job = await session.get(RefinementJob, job_id)
                    if job:
                        job.status = RunStatus.FAILED
                        job.completed_at = datetime.utcnow()
                        job.error_message = error_message
                        session.add(job)
                        await session.commit()
                        return True
                    return False
            
            await retry_db_operation(
                mark_refinement_failed,
                operation_name=f"mark refinement {job_id} failed"
            )
            
            # Send error notification - only if we have job details
            if job and hasattr(job, 'parent_run_id'):
                await connection_manager.send_run_error(job.parent_run_id, error_message, {"traceback": error_traceback, "job_id": job_id})
            else:
                logger.warning(f"Cannot send error notification for refinement {job_id} - job details not available")

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
            # Directory where originals are stored
            originals_dir = Path(f"./data/runs/{job.parent_run_id}").resolve()
            if not os.path.exists(originals_dir):
                raise FileNotFoundError(f"Originals directory does not exist: {originals_dir}")
            # Patterns: with and without timestamp
            patterns = [
                f"edited_image_strategy_{job.generation_index}.png",
                f"edited_image_strategy_{job.generation_index}_*.png"
            ]
            matches = []
            for pattern in patterns:
                matches.extend(originals_dir.glob(pattern))
            matches = list(set(matches))  # Remove duplicates if any

            logger.info(f"Searching for parent image with patterns {patterns} in {originals_dir}")
            if not matches:
                raise FileNotFoundError(f"No image found for patterns: {patterns} in {originals_dir}")
            matches.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            logger.info(f"Found parent image: {matches[0]}")
            return str(matches[0].relative_to(originals_dir))
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
        
        # Check if this is a refinement job by trying to find it in refinement_jobs table
        is_refinement_job = False
        parent_run_id = None
        
        async with async_session_factory() as session:
            # Check if run_id is a refinement job
            refinement_result = await session.execute(
                select(RefinementJob).where(RefinementJob.id == run_id)
            )
            refinement_job = refinement_result.scalars().first()
            
            if refinement_job:
                is_refinement_job = True
                parent_run_id = refinement_job.parent_run_id
                # For refinements, skip pipeline stage creation to avoid foreign key constraint
                # Refinement progress is tracked separately in the RefinementJob table
                logger.debug(f"Skipping pipeline stage creation for refinement job {run_id}")
            else:
                # This is a regular pipeline run - proceed with stage tracking
                # Find or create stage record
                result = await session.execute(
                    select(PipelineStage).where(
                        PipelineStage.run_id == run_id,
                        PipelineStage.stage_name == stage_name
                    )
                )
                stage = result.scalars().first()
                
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
                await session.commit()
                
                # Capture values while still in session
                stage_started_at = stage.started_at
                stage_completed_at = stage.completed_at
                stage_duration_seconds = stage.duration_seconds
        
        # Small delay to ensure database consistency before WebSocket update
        await asyncio.sleep(0.1)
        
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
        
        # For refinements, send WebSocket updates to the parent run
        websocket_run_id = parent_run_id if is_refinement_job else run_id
        await connection_manager.send_stage_update(websocket_run_id, update)
    
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
                },
                "language": request.language or 'en'
            },
            "user_inputs": {
                "prompt": request.prompt,
                "image_reference": None,
                "render_text": request.render_text,
                "apply_branding": request.apply_branding,
                "task_description": request.task_description,
                "marketing_goals": None,
                "preset_id": request.preset_id,
                "preset_type": request.preset_type,
                "template_overrides": request.template_overrides,
                "adaptation_prompt": request.adaptation_prompt,
                # NEW: Unified brand_kit object - only include if branding is enabled
                "brand_kit": request.brand_kit.model_dump() if (request.brand_kit and request.apply_branding) else None,
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
        
        # Add image reference if provided (defer base64 encoding)
        if request.image_reference and image_path:
            pipeline_data["user_inputs"]["image_reference"] = {
                "filename": request.image_reference.filename,
                "content_type": request.image_reference.content_type,
                "size_bytes": request.image_reference.size_bytes,
                "instruction": request.image_reference.instruction,
                "saved_image_path_in_run_dir": str(image_path),
                "image_content_base64": None,  # Will be populated when needed
                "_image_data_bytes": image_data  # Store raw bytes temporarily
            }
        
        # Add marketing goals if provided
        if request.marketing_goals:
            pipeline_data["user_inputs"]["marketing_goals"] = {
                "target_audience": request.marketing_goals.target_audience,
                "objective": request.marketing_goals.objective,
                "voice": request.marketing_goals.voice,
                "niche": request.marketing_goals.niche
            }

        # Add brand kit and handle logo upload - only if branding is enabled
        if pipeline_data["user_inputs"]["brand_kit"] and pipeline_data["user_inputs"]["brand_kit"].get("logo_file_base64") and request.apply_branding:
            brand_kit_data = pipeline_data["user_inputs"]["brand_kit"]
            try:
                # Decode the base64 string
                header, encoded = brand_kit_data["logo_file_base64"].split(",", 1)
                logo_bytes = base64.b64decode(encoded)
                
                # Save the logo file
                logo_filename = "logo.png"
                logo_path = Path(output_dir) / logo_filename
                with open(logo_path, "wb") as f:
                    f.write(logo_bytes)
                
                # Add the saved path to the context data
                brand_kit_data["saved_logo_path_in_run_dir"] = str(logo_path)
                logger.info(f"Saved brand logo to {logo_path}")

            except Exception as e:
                logger.error(f"Failed to decode or save brand logo: {e}")
                brand_kit_data["saved_logo_path_in_run_dir"] = None
            
            # Remove base64 from context to avoid oversized metadata
            brand_kit_data.pop("logo_file_base64", None)
        
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
            
            # Add style adaptation context if this is a style adaptation run
            if (context and hasattr(context, 'preset_type') and 
                context.preset_type and str(context.preset_type) == "PresetType.STYLE_RECIPE"):
                
                # Ensure processing_context exists
                if "processing_context" not in sanitized_data:
                    sanitized_data["processing_context"] = {}
                
                # Add style adaptation context
                style_adaptation_context = {
                    "parent_preset": {
                        "id": getattr(context, 'preset_id', None),
                        "adaptation_trigger": getattr(context, 'adaptation_context', {}).get('adaptation_trigger', 'unknown'),
                        "original_subject": getattr(context, 'original_subject', 'unknown_from_recipe'),
                        "new_subject": getattr(context, 'image_analysis_result', {}).get('main_subject') if hasattr(context, 'image_analysis_result') else None,
                        "adaptation_reasoning": getattr(context, 'adaptation_context', {}).get('adaptation_reasoning', 'Style adapted to new context'),
                        "stages_skipped": getattr(context, 'skip_stages', []),
                        "stages_executed": self._get_executed_stages_list(context)
                    }
                }
                
                sanitized_data["processing_context"]["style_adaptation_context"] = style_adaptation_context
                
                # Update pipeline mode to indicate style adaptation
                if "pipeline_settings" in sanitized_data:
                    sanitized_data["pipeline_settings"]["pipeline_mode"] = "style_adaptation"
                    sanitized_data["pipeline_settings"]["adaptation_type"] = "subject_substitution" if getattr(context, 'image_reference', None) else "prompt_override"
            
            with open(metadata_path, 'w') as f:
                json.dump(sanitized_data, f, indent=2)
            
            # Update database with metadata path
            async with async_session_factory() as session:
                run = await session.get(PipelineRun, run_id)
                if run:
                    run.metadata_file_path = str(metadata_path)
                    session.add(run)
                    await session.commit()
            
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
    
    async def cancel_run(self, run_id: str) -> bool:
        """Cancel a running pipeline"""
        if run_id not in self.active_tasks:
            # Check if run exists but is stalled, use retry logic
            async def cancel_stalled_run():
                async with async_session_factory() as session:
                    run = await session.get(PipelineRun, run_id)
                    if run and run.status == RunStatus.RUNNING:
                        run.status = RunStatus.CANCELLED
                        run.completed_at = datetime.utcnow()
                        run.error_message = "Pipeline execution was cancelled"
                        if run.started_at:
                            run.total_duration_seconds = (run.completed_at - run.started_at).total_seconds()
                        session.add(run)
                        await session.commit()
                        
                        asyncio.create_task(connection_manager.send_run_error(
                            run_id,
                            "Pipeline execution was cancelled",
                            {"type": "cancelled"}
                        ))
                        return True
                    return False
            
            return await retry_db_operation(
                cancel_stalled_run,
                operation_name=f"cancel stalled pipeline run {run_id}"
            )
        
        # Cancel active task
        task = self.active_tasks[run_id]
        task.cancel()
        
        # Cancel timeout task if exists
        if run_id in self.run_timeouts:
            self.run_timeouts[run_id].cancel()
        
        # Update database with retry logic
        async def update_cancelled_run():
            async with async_session_factory() as session:
                run = await session.get(PipelineRun, run_id)
                if run:
                    run.status = RunStatus.CANCELLED
                    run.completed_at = datetime.utcnow()
                    run.error_message = "Pipeline execution was cancelled"
                    if run.started_at:
                        run.total_duration_seconds = (run.completed_at - run.started_at).total_seconds()
                    session.add(run)
                    await session.commit()
                    return True
                return False
        
        await retry_db_operation(
            update_cancelled_run,
            operation_name=f"update cancelled pipeline run {run_id}"
        )
        
        logger.info(f"Cancelled pipeline run {run_id}")
        return True

    async def cancel_refinement(self, job_id: str) -> bool:
        """Cancel a running refinement job"""
        if job_id not in self.active_tasks:
            # Check if job exists but is stalled, use retry logic
            async def cancel_stalled_refinement():
                async with async_session_factory() as session:
                    job = await session.get(RefinementJob, job_id)
                    if job and job.status == RunStatus.RUNNING:
                        job.status = RunStatus.CANCELLED
                        job.completed_at = datetime.utcnow()
                        job.error_message = "Refinement execution was cancelled"
                        session.add(job)
                        await session.commit()
                        
                        asyncio.create_task(connection_manager.send_run_error(
                            job_id,
                            "Refinement execution was cancelled",
                            {"type": "cancelled"}
                        ))
                        return True
                    return False
            
            return await retry_db_operation(
                cancel_stalled_refinement,
                operation_name=f"cancel stalled refinement job {job_id}"
            )
        
        # Cancel active task
        task = self.active_tasks[job_id]
        task.cancel()
        
        # Cancel timeout task if exists
        if job_id in self.run_timeouts:
            self.run_timeouts[job_id].cancel()
        
        # Update database with retry logic
        async def update_cancelled_refinement():
            async with async_session_factory() as session:
                job = await session.get(RefinementJob, job_id)
                if job:
                    job.status = RunStatus.CANCELLED
                    job.completed_at = datetime.utcnow()
                    job.error_message = "Refinement execution was cancelled"
                    session.add(job)
                    await session.commit()
                    return True
                return False
        
        await retry_db_operation(
            update_cancelled_refinement,
            operation_name=f"update cancelled refinement job {job_id}"
        )
        
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

    def _get_executed_stages_list(self, context: PipelineContext) -> list:
        """Get list of stages that were actually executed (not skipped)."""
        try:
            # Get all possible stages from the executor
            all_stages = ["image_eval", "strategy", "style_guide", "creative_expert", "style_adaptation", 
                         "prompt_assembly", "image_generation", "image_assessment", "caption"]
            
            # Get skipped stages
            skip_stages = getattr(context, 'skip_stages', [])
            
            # Return stages that weren't skipped
            executed_stages = [stage for stage in all_stages if stage not in skip_stages]
            
            # Add style_adaptation if it was triggered
            if (hasattr(context, 'preset_type') and 
                str(context.preset_type) == "PresetType.STYLE_RECIPE" and
                "style_adaptation" not in executed_stages):
                executed_stages.insert(-3, "style_adaptation")  # Insert before prompt_assembly
                
            return executed_stages
        except Exception as e:
            logger.warning(f"Could not determine executed stages: {e}")
            return ["unknown"]

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
                ("image_eval", ["image_eval", "logo_eval"], IMG_EVAL_MODEL_ID),
                ("strategy", ["strategy_niche_id", "strategy_goal_gen"], STRATEGY_MODEL_ID),
                ("style_guide", ["style_guider"], STYLE_GUIDER_MODEL_ID),
                ("creative_expert", [key for key in llm_usage.keys() if key.startswith("creative_expert_strategy_")], CREATIVE_EXPERT_MODEL_ID),
                ("style_adaptation", ["style_adaptation"], STYLE_ADAPTATION_MODEL_ID),
                ("image_assessment", ["image_assessment"], IMAGE_ASSESSMENT_MODEL_ID),
                ("caption", ["caption_analyst", "caption_writer"], CAPTION_MODEL_ID),
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
            async with async_session_factory() as session:
                result = await session.execute(
                    select(PipelineStage).where(PipelineStage.run_id == run_id)
                )
                stages = result.all()
                
                for stage in stages:
                    if stage.duration_seconds is not None:
                        durations[stage.stage_name] = stage.duration_seconds
                        logger.debug(f"Retrieved duration for {stage.stage_name}: {stage.duration_seconds:.1f}s")
                
                logger.info(f"Retrieved {len(durations)} actual stage durations from database")
                
        except Exception as e:
            logger.warning(f"Failed to retrieve stage durations from database: {e}")
        
        return durations

    async def start_caption_generation(self, caption_id: str, caption_data: Dict[str, Any], executor: Optional[PipelineExecutor] = None):
        """Start caption generation in the background"""
        # Create and start the background task
        task = asyncio.create_task(self._execute_caption_generation(caption_id, caption_data, executor))
        self.active_tasks[caption_id] = task
        
        # Clean up completed tasks
        def cleanup_tasks(t):
            self.active_tasks.pop(caption_id, None)
        
        task.add_done_callback(cleanup_tasks)
        
        logger.info(f"Started background caption generation task for {caption_id}")

    async def _execute_caption_generation(self, caption_id: str, caption_data: Dict[str, Any], executor: Optional[PipelineExecutor] = None):
        """Execute caption generation with real-time updates"""
        try:
            run_id = caption_data["run_id"]
            image_id = caption_data["image_id"]
            settings = caption_data.get("settings", {})
            version = caption_data.get("version", 0)
            writer_only = caption_data.get("writer_only", False)
            # Determine model_id based on processing_mode or explicit model_id
            settings = caption_data.get("settings", {})
            processing_mode = settings.get("processing_mode")
            
            if processing_mode:
                # Use processing_mode to select appropriate model
                model_id = get_caption_model_for_processing_mode(processing_mode)
                logger.info(f"Selected model {model_id} for processing_mode: {processing_mode}")
            else:
                # Fallback to explicitly provided model_id or default
                model_id = caption_data.get("model_id", CAPTION_MODEL_ID)
                logger.info(f"Using model {model_id} (no processing_mode specified)")
            
            logger.info(f"Starting caption generation for image {image_id} in run {run_id} using model {model_id}")
            
            # Load the original pipeline context to get metadata - use retry logic
            run = None
            async def load_caption_run_metadata():
                nonlocal run
                async with async_session_factory() as session:
                    run = await session.get(PipelineRun, run_id)
                    if not run:
                        raise Exception(f"Pipeline run {run_id} not found")
                    
                    if not run.output_directory:
                        raise Exception(f"No output directory found for run {run_id}")
                    return True
            
            await retry_db_operation(
                load_caption_run_metadata,
                operation_name=f"load run metadata for caption {caption_id}"
            )
            
            # Load metadata from the original run
            metadata_path = Path(run.output_directory) / "pipeline_metadata.json"
            if not metadata_path.exists():
                raise Exception(f"Metadata file not found: {metadata_path}")
            
            with open(metadata_path, 'r') as f:
                metadata = json.load(f)
            
            # Create a pipeline context from the metadata for caption generation
            context = PipelineContext.from_dict(metadata)
            
            # Add caption-specific settings to context
            context.caption_settings = settings
            context.caption_version = version
            context.regenerate_writer_only = writer_only
            
            # Load cached brief for writer-only regeneration
            if writer_only and "previous_version" in caption_data:
                previous_version = caption_data["previous_version"]
                brief_file = Path(run.output_directory) / "captions" / image_id / f"v{previous_version}_brief.json"
                if brief_file.exists():
                    try:
                        with open(brief_file, 'r', encoding='utf-8') as f:
                            brief_data = json.load(f)
                        
                        # Import CaptionBrief model to recreate the object
                        from churns.models import CaptionBrief
                        context.cached_caption_brief = CaptionBrief(**brief_data)
                        logger.info(f"Loaded cached brief from {brief_file} for writer-only regeneration")
                    except Exception as e:
                        logger.warning(f"Failed to load cached brief from {brief_file}: {e}")
                        logger.warning("Will proceed with full pipeline regeneration")
                else:
                    logger.warning(f"Brief file {brief_file} not found for writer-only regeneration")
                    logger.warning("Will proceed with full pipeline regeneration")
            
            # Set target image index for single-image processing
            # Extract image index from image_id (e.g., "image_0" -> 0, "image_1" -> 1)
            try:
                if image_id.startswith("image_"):
                    target_index = int(image_id.split("_")[1])
                    context.target_image_index = target_index
                    logger.info(f"Set target image index to {target_index} for image {image_id}")
                else:
                    logger.warning(f"Could not parse image index from {image_id}, will process all images")
            except (IndexError, ValueError) as e:
                logger.warning(f"Could not parse image index from {image_id}: {e}, will process all images")
            
            # Send progress update
            from churns.api.websocket import WebSocketMessage, WSMessageType
            message = WebSocketMessage(
                type=WSMessageType.CAPTION_UPDATE,
                run_id=run_id,
                data={
                    "caption_id": caption_id,
                    "image_id": image_id,
                    "status": "RUNNING",
                    "message": f"Generating caption using {model_id}..."
                }
            )
            await connection_manager.send_message_to_run(run_id, message)
            
            # Execute caption pipeline using shared executor if available
            if executor is None:
                logger.warning("No executor provided, creating new caption instance (this should not happen in production)")
                from churns.pipeline.executor import PipelineExecutor
                executor = PipelineExecutor(mode="caption")
            
            # Set up progress callback for caption generation
            async def caption_progress_callback(stage_name: str, stage_order: int, status: StageStatus, 
                                              message: str, output_data: Optional[Dict] = None, 
                                              error_message: Optional[str] = None,
                                              duration_seconds: Optional[float] = None):
                
                # Send WebSocket progress update
                from churns.api.websocket import WebSocketMessage, WSMessageType
                progress_message = WebSocketMessage(
                    type=WSMessageType.CAPTION_UPDATE,
                    run_id=run_id,
                    data={
                        "caption_id": caption_id,
                        "image_id": image_id,
                        "status": status.value if hasattr(status, 'value') else str(status),
                        "message": message,
                        "stage_name": stage_name,
                        "stage_order": stage_order,
                        "duration_seconds": duration_seconds
                    }
                )
                await connection_manager.send_message_to_run(run_id, progress_message)
            
            # Set the selected model ID in context for the caption stage to use
            context.caption_model_id = model_id
            
            # Run the caption stage through the executor
            await executor.run_async(context, caption_progress_callback)
            
            # Extract the generated caption
            if hasattr(context, 'generated_captions') and context.generated_captions:
                # For single-image processing, there should be exactly one caption
                if len(context.generated_captions) == 1:
                    caption_result = context.generated_captions[0]
                    caption_text = caption_result["text"]
                else:
                    # This shouldn't happen with single-image processing, but handle gracefully
                    logger.warning(f"Expected 1 caption, got {len(context.generated_captions)}. Using first one.")
                    caption_result = context.generated_captions[0]
                    caption_text = caption_result["text"]
                
                # Save caption to file (following data/runs/{run_id}/ structure)
                caption_dir = Path(run.output_directory) / "captions" / image_id
                caption_dir.mkdir(parents=True, exist_ok=True)
                
                caption_file = caption_dir / f"v{version}.txt"
                with open(caption_file, 'w', encoding='utf-8') as f:
                    f.write(caption_text)
                
                brief_file = caption_dir / f"v{version}_brief.json"
                with open(brief_file, 'w', encoding='utf-8') as f:
                    json.dump(caption_result["brief_used"], f, indent=2)
                
                # Create streamlined usage summary
                analyst_usage = context.llm_usage.get("caption_analyst", {})
                writer_usage = context.llm_usage.get("caption_writer", {})
                
                # Calculate totals
                total_cost = 0.0
                total_latency = 0.0
                
                analyst_cost = 0.0
                writer_cost = 0.0
                analyst_latency = 0.0
                writer_latency = 0.0
                
                if analyst_usage.get("cost_breakdown"):
                    analyst_cost = analyst_usage["cost_breakdown"]["total_cost"]
                    total_cost += analyst_cost
                    analyst_latency = analyst_usage.get("latency_seconds", 0)
                    total_latency += analyst_latency
                
                if writer_usage.get("cost_breakdown"):
                    writer_cost = writer_usage["cost_breakdown"]["total_cost"]
                    total_cost += writer_cost
                    writer_latency = writer_usage.get("latency_seconds", 0)
                    total_latency += writer_latency
                
                usage_summary = {
                    "total_cost_usd": round(total_cost, 6),
                    "total_latency_seconds": round(total_latency, 3),
                    "model_id": model_id,
                    "analyst": {
                        "tokens": {
                            "prompt": analyst_usage.get("prompt_tokens", 0),
                            "completion": analyst_usage.get("completion_tokens", 0),
                            "cached": analyst_usage.get("cached_tokens", 0)
                        },
                        "cost": round(analyst_cost, 6),
                        "latency": round(analyst_latency, 3)
                    } if analyst_usage else {},
                    "writer": {
                        "tokens": {
                            "prompt": writer_usage.get("prompt_tokens", 0),
                            "completion": writer_usage.get("completion_tokens", 0),
                            "cached": writer_usage.get("cached_tokens", 0)
                        },
                        "cost": round(writer_cost, 6),
                        "latency": round(writer_latency, 3)
                    } if writer_usage else {}
                }

                # Also save caption result with metadata to match pipeline pattern
                result_file = caption_dir / f"v{version}_result.json"
                with open(result_file, 'w', encoding='utf-8') as f:
                    json.dump({
                        "text": caption_text,
                        "version": version,
                        "settings_used": caption_result.get("settings_used", {}),
                        "brief_used": caption_result["brief_used"],
                        "created_at": caption_result.get("created_at"),
                        "model_id": model_id,  # Save the model used
                        "usage_summary": usage_summary
                    }, f, indent=2)
                
                # Send success update
                success_message = WebSocketMessage(
                    type=WSMessageType.CAPTION_COMPLETE,
                    run_id=run_id,
                    data={
                        "caption_id": caption_id,
                        "image_id": image_id,
                        "status": "COMPLETED",
                        "text": caption_text,
                        "version": version,
                        "model_id": model_id,
                        "file_path": str(caption_file)
                    }
                )
                await connection_manager.send_message_to_run(run_id, success_message)
                
                logger.info(f"Caption generation completed for {caption_id} using model {model_id}")
                
            else:
                raise Exception("Caption generation failed - no caption produced")
                
        except Exception as e:
            error_message = f"Caption generation failed: {str(e)}"
            error_traceback = traceback.format_exc()
            logger.error(f"Caption generation {caption_id} failed: {error_message}\n{error_traceback}")
            
            # Send error notification
            error_message_obj = WebSocketMessage(
                type=WSMessageType.CAPTION_ERROR,
                run_id=run_id,
                data={
                    "caption_id": caption_id,
                    "image_id": image_id,
                    "status": "FAILED",
                    "error_message": error_message
                }
            )
            await connection_manager.send_message_to_run(run_id, error_message_obj)

    async def run_noise_assessment_for_refinement(self, job_id: str, executor: Optional[PipelineExecutor] = None):
        """Run noise assessment for a completed refinement job"""
        try:
            logger.info(f"Starting noise assessment for refinement job: {job_id}")
            
            # Get refinement details from database
            async with async_session_factory() as session:
                refinement = await session.get(RefinementJob, job_id)
                if not refinement:
                    logger.error(f"Refinement job {job_id} not found")
                    return
                
                if refinement.status != RunStatus.COMPLETED:
                    logger.error(f"Refinement {job_id} is not completed (status: {refinement.status})")
                    return
                
                if not refinement.image_path:
                    logger.error(f"Refinement {job_id} has no image path")
                    return
                
                if refinement.needs_noise_reduction is not None:
                    logger.info(f"Refinement {job_id} already has noise assessment result: {refinement.needs_noise_reduction}")
                    return
                
                # Construct full image path
                from pathlib import Path
                parent_run_dir = Path(f"./data/runs/{refinement.parent_run_id}")
                refinements_dir = parent_run_dir / "refinements"
                image_path = refinements_dir / refinement.image_path
                
                if not image_path.exists():
                    # Try alternative path without refinements subdirectory
                    image_path = parent_run_dir / refinement.image_path
                    if not image_path.exists():
                        logger.error(f"Refinement image not found at {image_path}")
                        return
                
                # Send WebSocket notification that assessment is starting
                await connection_manager.send_message_to_run(
                    refinement.parent_run_id,
                    WebSocketMessage(
                        type="noise_assessment_started",
                        run_id=refinement.parent_run_id,
                        data={
                            "job_id": job_id,
                            "message": "Starting noise assessment..."
                        }
                    )
                )
                
                # Access pre-configured client from shared executor
                if executor is None:
                    logger.error("No executor provided for noise assessment")
                    await connection_manager.send_message_to_run(
                        refinement.parent_run_id,
                        WebSocketMessage(
                            type="noise_assessment_error",
                            run_id=refinement.parent_run_id,
                            data={
                                "job_id": job_id,
                                "error": "Executor not provided",
                                "message": "Noise assessment failed: no executor"
                            }
                        )
                    )
                    return
                
                # Access pre-configured client from shared executor
                image_assessment_client = executor.clients.get('base_llm_client_image_assessment')
                model_config = executor.clients.get('model_config', {})
                
                if not image_assessment_client:
                    logger.error("Image assessment client not configured")
                    await connection_manager.send_message_to_run(
                        refinement.parent_run_id,
                        WebSocketMessage(
                            type="noise_assessment_error",
                            run_id=refinement.parent_run_id,
                            data={
                                "job_id": job_id,
                                "error": "Client not configured",
                                "message": "Noise assessment failed: client not configured"
                            }
                        )
                    )
                    return
                
                # Create assessor with shared pre-configured client
                model_id = model_config.get('IMAGE_ASSESSMENT_MODEL_ID', IMAGE_ASSESSMENT_MODEL_ID)
                assessor = ImageAssessor(model_id=model_id, client=image_assessment_client)
                
                # Run noise assessment
                needs_noise_reduction = await assessor.assess_noise_only_async(str(image_path))
                
                # Update database with fresh session to avoid detached object issues
                async with async_session_factory() as update_session:
                    fresh_refinement = await update_session.get(RefinementJob, job_id)
                    if fresh_refinement:
                        fresh_refinement.needs_noise_reduction = needs_noise_reduction
                        update_session.add(fresh_refinement)
                        await update_session.commit()
                    else:
                        logger.error(f"Could not find refinement {job_id} for database update")
                        return
                
                # Send completion notification
                await connection_manager.send_message_to_run(
                    refinement.parent_run_id,
                    WebSocketMessage(
                        type="noise_assessment_completed",
                        run_id=refinement.parent_run_id,
                        data={
                            "job_id": job_id,
                            "needs_noise_reduction": needs_noise_reduction,
                            "message": f"Assessment complete: {'Noise detected' if needs_noise_reduction else 'Image is clean'}"
                        }
                    )
                )
                
        except Exception as e:
            logger.error(f"Noise assessment failed for job {job_id}: {str(e)}")
            
            # Send error notification
            try:
                async with async_session_factory() as session:
                    refinement = await session.get(RefinementJob, job_id)
                    if refinement:
                        await connection_manager.send_message_to_run(
                            refinement.parent_run_id,
                            WebSocketMessage(
                                type="noise_assessment_error",
                                run_id=refinement.parent_run_id,
                                data={
                                    "job_id": job_id,
                                    "error": str(e),
                                    "message": "Noise assessment failed"
                                }
                            )
                        )
            except Exception as cleanup_error:
                logger.error(f"Error sending failure notification for job {job_id}: {str(cleanup_error)}")


# Global task processor instance
task_processor = PipelineTaskProcessor() 