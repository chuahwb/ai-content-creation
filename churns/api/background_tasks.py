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
    get_session, PipelineRun, PipelineStage, 
    RunStatus, StageStatus, engine
)
from churns.api.schemas import (
    PipelineRunRequest, StageProgressUpdate, 
    GeneratedImageResult, PipelineResults
)
from churns.api.websocket import connection_manager
from churns.pipeline.context import PipelineContext
from churns.pipeline.executor import PipelineExecutor

logger = logging.getLogger(__name__)


class PipelineTaskProcessor:
    """Processes pipeline runs in background with real-time updates"""
    
    def __init__(self):
        self.active_tasks: Dict[str, asyncio.Task] = {}
        
    async def start_pipeline_run(self, run_id: str, request: PipelineRunRequest, image_data: Optional[bytes] = None):
        """Start a pipeline run in the background"""
        if run_id in self.active_tasks:
            logger.warning(f"Pipeline run {run_id} is already running")
            return
        
        # Create and start the background task
        task = asyncio.create_task(self._execute_pipeline(run_id, request, image_data))
        self.active_tasks[run_id] = task
        
        # Clean up completed tasks
        task.add_done_callback(lambda t: self.active_tasks.pop(run_id, None))
        
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
                
                # Calculate cost based on actual API usage data, not estimates
                nonlocal total_cost, stage_costs
                if status == StageStatus.COMPLETED and duration_seconds:
                    stage_cost = 0.0
                    
                    # Try to get actual cost from real API usage data in context
                    try:
                        processing_context = (context.data or {}).get("processing_context", {})
                        llm_usage = processing_context.get("llm_call_usage", {})
                        
                        # Calculate cost based on actual token usage for this stage
                        if stage_name == "image_generation":
                            # Use actual image generation results
                            image_results = processing_context.get("generated_image_results", [])
                            actual_images = len([r for r in image_results if r.get("status") == "success"])
                            total_prompt_tokens = sum(r.get("prompt_tokens", 0) for r in image_results if r.get("prompt_tokens"))
                            
                            if actual_images > 0 and total_prompt_tokens > 0:
                                # Use actual usage data
                                text_cost = (total_prompt_tokens / 1_000_000) * 5.00  # $5/1M tokens
                                image_cost = (1056 * actual_images / 1_000_000) * 40.00  # $40/1M tokens per image
                                stage_cost = text_cost + image_cost
                                logger.info(f"Image generation actual cost: ${text_cost:.6f} (text) + ${image_cost:.6f} ({actual_images} images) = ${stage_cost:.6f}")
                            else:
                                stage_cost = 0.0  # No successful generation
                                
                        elif stage_name == "image_eval":
                            # Use actual VLM usage
                            if "image_eval" in llm_usage:
                                usage = llm_usage["image_eval"]
                                input_tokens = usage.get("prompt_tokens", 0)
                                output_tokens = usage.get("completion_tokens", 0)
                                stage_cost = (input_tokens / 1_000_000) * 0.40 + (output_tokens / 1_000_000) * 1.20
                                
                        elif stage_name == "strategy":
                            # Use actual strategy generation usage
                            total_strategy_cost = 0.0
                            for key in ["strategy_niche_id", "strategy_goal_gen"]:
                                if key in llm_usage:
                                    usage = llm_usage[key]
                                    input_tokens = usage.get("prompt_tokens", 0)
                                    output_tokens = usage.get("completion_tokens", 0)
                                    total_strategy_cost += (input_tokens / 1_000_000) * 0.40 + (output_tokens / 1_000_000) * 1.20
                            stage_cost = total_strategy_cost
                            
                        elif stage_name == "style_guide":
                            # Use actual style guidance usage
                            if "style_guider" in llm_usage:
                                usage = llm_usage["style_guider"]
                                input_tokens = usage.get("prompt_tokens", 0)
                                output_tokens = usage.get("completion_tokens", 0)
                                stage_cost = (input_tokens / 1_000_000) * 1.25 + (output_tokens / 1_000_000) * 10.00  # Gemini pricing
                                
                        elif stage_name == "creative_expert":
                            # Use actual creative expert usage (multiple strategy calls)
                            total_creative_cost = 0.0
                            for key in llm_usage:
                                if key.startswith("creative_expert_strategy_"):
                                    usage = llm_usage[key]
                                    input_tokens = usage.get("prompt_tokens", 0)
                                    output_tokens = usage.get("completion_tokens", 0)
                                    total_creative_cost += (input_tokens / 1_000_000) * 1.25 + (output_tokens / 1_000_000) * 10.00  # Gemini pricing
                            stage_cost = total_creative_cost
                            
                        else:
                            # Other stages - minimal cost
                            stage_cost = 0.0001
                            
                    except Exception as e:
                        logger.warning(f"Failed to calculate actual cost for stage {stage_name}: {e}")
                        # Fallback to minimal cost, not hardcoded estimates
                        stage_cost = 0.0001
                    
                    if stage_cost > 0:
                        total_cost += stage_cost
                        stage_costs.append({
                            "stage_name": stage_name,
                            "cost_usd": stage_cost,
                            "duration_seconds": duration_seconds
                        })
                        logger.info(f"Stage {stage_name} actual cost: ${stage_cost:.6f}")
                        
                        # Update context with cost information
                        if not context.data:
                            context.data = {}
                        if not context.data.get("processing_context"):
                            context.data["processing_context"] = {}
                        context.data["processing_context"]["cost_summary"] = {
                            "total_pipeline_cost_usd": total_cost,
                            "stage_costs": stage_costs,
                            "total_pipeline_duration_seconds": sum(c["duration_seconds"] for c in stage_costs)
                        }
                
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
                        processing_context = (context.data or {}).get("processing_context", {})
                        if processing_context and isinstance(processing_context, dict):
                            cost_summary = processing_context.get("cost_summary", {})
                            if cost_summary and isinstance(cost_summary, dict):
                                extracted_cost = cost_summary.get("total_pipeline_cost_usd")
                                logger.info(f"Extracted cost from context: ${extracted_cost}")
                    except Exception as e:
                        logger.warning(f"Failed to extract cost from context: {e}")
                    
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
            return False
        
        task = self.active_tasks[run_id]
        task.cancel()
        
        # Update database
        with Session(engine) as session:
            run = session.get(PipelineRun, run_id)
            if run:
                run.status = RunStatus.CANCELLED
                run.completed_at = datetime.utcnow()
                session.add(run)
                session.commit()
        
        logger.info(f"Cancelled pipeline run {run_id}")
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


# Global task processor instance
task_processor = PipelineTaskProcessor() 