"""
Pipeline Executor - Orchestrates running pipeline stages in order.

This replaces the monolithic run_full_pipeline() function with a modular,
configurable stage-based executor.
"""

import time
import yaml
import importlib
from pathlib import Path
import logging
from typing import List, Dict, Any, Optional, Callable, Awaitable
from .context import PipelineContext
from .preset_loader import PresetLoader
from ..core.client_config import get_configured_clients
from ..api.database import StageStatus

# Setup Logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("executor")

class PipelineExecutor:
    """Executes pipeline stages in configurable order."""
    
    def __init__(self, mode: str = "generation", stages_config_path: Optional[str] = None, env_path: Optional[str] = None):
        """Initialize executor with stage configuration and API clients."""
        self.mode = mode  # "generation" or "refinement"
        
        if stages_config_path is None:
            # Default to stage_order.yml in configs directory
            self.config_path = Path(__file__).parent.parent / "configs" / "stage_order.yml"
        else:
            self.config_path = Path(stages_config_path)
        
        self.stages = self._load_stage_config()
        
        # Load and configure API clients
        from ..core.client_config import _client_config
        was_already_configured = _client_config is not None
        
        self.clients = get_configured_clients(env_path)
        
        configured_count = len([k for k, v in self.clients.items() if v is not None and k not in ['model_config', 'force_manual_json_parse', 'instructor_tool_mode_problem_models']])
        
        if was_already_configured:
            print(f"🔧 Pipeline executor initialized for {mode} mode with {len(self.stages)} stages (sharing {configured_count} configured clients)")
        else:
            print(f"🔧 Pipeline executor initialized for {mode} mode with {len(self.stages)} stages and {configured_count} configured clients")
    
    def _load_stage_config(self) -> List[str]:
        """Load stage execution order from YAML config based on mode."""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
                
                # Try to get stages for specific mode first
                if self.mode in config:
                    return config[self.mode]
                
                # Fallback to legacy 'stages' key (for generation mode)
                if 'stages' in config:
                    return config['stages']
                
                # Final fallback to hardcoded order
                return self._get_fallback_stages()
                
        except Exception as e:
            print(f"Warning: Could not load stage config from {self.config_path}: {e}")
            return self._get_fallback_stages()
    
    def _get_fallback_stages(self) -> List[str]:
        """Get fallback stage order based on mode."""
        if self.mode == "refinement":
            return ['load_base_image', 'conditional_stage', 'save_outputs']
        else:
            # Default generation stages
            return ['image_eval', 'strategy', 'style_guide', 'creative_expert', 'prompt_assembly', 'image_generation']
    
    def get_client_summary(self) -> Dict[str, str]:
        """Get a summary of configured clients."""
        summary = {}
        for client_name, client in self.clients.items():
            if client_name in ['model_config', 'force_manual_json_parse', 'instructor_tool_mode_problem_models']:
                continue  # Skip configuration items
            
            if client is not None:
                summary[client_name] = "✅ Configured"
            else:
                summary[client_name] = "❌ Not configured"
        
        return summary
    
    def _inject_clients_into_stage(self, stage_module, ctx: Optional[PipelineContext] = None) -> None:
        """Inject clients and configuration into a specific stage module."""
        # Inject image evaluation clients
        if hasattr(stage_module, 'instructor_client_img_eval'):
            stage_module.instructor_client_img_eval = self.clients.get('instructor_client_img_eval')
        if hasattr(stage_module, 'base_llm_client_img_eval'):
            stage_module.base_llm_client_img_eval = self.clients.get('base_llm_client_img_eval')
        
        # Inject strategy clients
        if hasattr(stage_module, 'instructor_client_strategy'):
            stage_module.instructor_client_strategy = self.clients.get('instructor_client_strategy')
        if hasattr(stage_module, 'base_llm_client_strategy'):
            stage_module.base_llm_client_strategy = self.clients.get('base_llm_client_strategy')
        
        # Inject style guide clients
        if hasattr(stage_module, 'instructor_client_style_guide'):
            stage_module.instructor_client_style_guide = self.clients.get('instructor_client_style_guide')
        if hasattr(stage_module, 'base_llm_client_style_guide'):
            stage_module.base_llm_client_style_guide = self.clients.get('base_llm_client_style_guide')
        
        # Inject creative expert clients
        if hasattr(stage_module, 'instructor_client_creative_expert'):
            stage_module.instructor_client_creative_expert = self.clients.get('instructor_client_creative_expert')
        if hasattr(stage_module, 'base_llm_client_creative_expert'):
            stage_module.base_llm_client_creative_expert = self.clients.get('base_llm_client_creative_expert')
        
        # Inject image generation client
        if hasattr(stage_module, 'image_gen_client'):
            stage_module.image_gen_client = self.clients.get('image_gen_client')
        
        # Inject image assessment clients (dedicated clients)
        if hasattr(stage_module, 'instructor_client_image_assessment'):
            stage_module.instructor_client_image_assessment = self.clients.get('instructor_client_image_assessment')
        if hasattr(stage_module, 'base_llm_client_image_assessment'):
            stage_module.base_llm_client_image_assessment = self.clients.get('base_llm_client_image_assessment')
        
        # Inject caption clients
        if hasattr(stage_module, 'instructor_client_caption'):
            stage_module.instructor_client_caption = self.clients.get('instructor_client_caption')
        if hasattr(stage_module, 'base_llm_client_caption'):
            stage_module.base_llm_client_caption = self.clients.get('base_llm_client_caption')
        
        # Inject style adaptation clients
        if hasattr(stage_module, 'instructor_client_style_adaptation'):
            stage_module.instructor_client_style_adaptation = self.clients.get('instructor_client_style_adaptation')
        if hasattr(stage_module, 'base_llm_client_style_adaptation'):
            stage_module.base_llm_client_style_adaptation = self.clients.get('base_llm_client_style_adaptation')
        
        # Inject model configuration and parsing flags
        model_config = self.clients.get('model_config', {})
        if hasattr(stage_module, 'IMG_EVAL_MODEL_ID'):
            stage_module.IMG_EVAL_MODEL_ID = model_config.get('IMG_EVAL_MODEL_ID')
            stage_module.IMG_EVAL_MODEL_PROVIDER = model_config.get('IMG_EVAL_MODEL_PROVIDER')
        if hasattr(stage_module, 'STRATEGY_MODEL_ID'):
            stage_module.STRATEGY_MODEL_ID = model_config.get('STRATEGY_MODEL_ID')
            stage_module.STRATEGY_MODEL_PROVIDER = model_config.get('STRATEGY_MODEL_PROVIDER')
        if hasattr(stage_module, 'STYLE_GUIDER_MODEL_ID'):
            stage_module.STYLE_GUIDER_MODEL_ID = model_config.get('STYLE_GUIDER_MODEL_ID')
            stage_module.STYLE_GUIDER_MODEL_PROVIDER = model_config.get('STYLE_GUIDER_MODEL_PROVIDER')
        if hasattr(stage_module, 'CREATIVE_EXPERT_MODEL_ID'):
            stage_module.CREATIVE_EXPERT_MODEL_ID = model_config.get('CREATIVE_EXPERT_MODEL_ID')
            stage_module.CREATIVE_EXPERT_MODEL_PROVIDER = model_config.get('CREATIVE_EXPERT_MODEL_PROVIDER')
        if hasattr(stage_module, 'IMAGE_ASSESSMENT_MODEL_ID'):
            stage_module.IMAGE_ASSESSMENT_MODEL_ID = model_config.get('IMAGE_ASSESSMENT_MODEL_ID')
            stage_module.IMAGE_ASSESSMENT_MODEL_PROVIDER = model_config.get('IMAGE_ASSESSMENT_MODEL_PROVIDER')
        if hasattr(stage_module, 'IMAGE_GENERATION_MODEL_ID'):
            stage_module.IMAGE_GENERATION_MODEL_ID = model_config.get('IMAGE_GENERATION_MODEL_ID')
        if hasattr(stage_module, 'CAPTION_MODEL_ID'):
            # Use dynamic model from context if available, otherwise use default from config
            if ctx and hasattr(ctx, 'caption_model_id') and ctx.caption_model_id:
                stage_module.CAPTION_MODEL_ID = ctx.caption_model_id
                # Extract provider from model ID (e.g., "openai/gpt-4.1" -> "openai")
                if "/" in ctx.caption_model_id:
                    stage_module.CAPTION_MODEL_PROVIDER = ctx.caption_model_id.split("/")[0]
                else:
                    stage_module.CAPTION_MODEL_PROVIDER = model_config.get('CAPTION_MODEL_PROVIDER')
            else:
                stage_module.CAPTION_MODEL_ID = model_config.get('CAPTION_MODEL_ID')
                stage_module.CAPTION_MODEL_PROVIDER = model_config.get('CAPTION_MODEL_PROVIDER')
        if hasattr(stage_module, 'STYLE_ADAPTATION_MODEL_ID'):
            stage_module.STYLE_ADAPTATION_MODEL_ID = model_config.get('STYLE_ADAPTATION_MODEL_ID')
            stage_module.STYLE_ADAPTATION_MODEL_PROVIDER = model_config.get('STYLE_ADAPTATION_MODEL_PROVIDER')
        
        # Inject parsing configuration
        if hasattr(stage_module, 'FORCE_MANUAL_JSON_PARSE'):
            stage_module.FORCE_MANUAL_JSON_PARSE = self.clients.get('force_manual_json_parse', False)
        if hasattr(stage_module, 'INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS'):
            stage_module.INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS = self.clients.get('instructor_tool_mode_problem_models', [])
    
    def run(self, ctx: PipelineContext) -> PipelineContext:
        """Execute all stages in order."""
        ctx.log(f"Starting {self.mode} pipeline execution with {len(self.stages)} stages")
        
        overall_start_time = time.time()
        
        for stage_name in self.stages:
            stage_start_time = time.time()
            ctx.log(f"--- Stage: {stage_name} ---")
            
            try:
                # Handle conditional stage execution for refinements
                if stage_name == "conditional_stage" and self.mode == "refinement":
                    actual_stage_name = self._resolve_conditional_stage(ctx)
                    if actual_stage_name:
                        stage_module = importlib.import_module(f"churns.stages.{actual_stage_name}")
                        ctx.log(f"Resolved conditional stage to: {actual_stage_name}")
                    else:
                        ctx.log(f"Warning: Could not resolve conditional stage for refinement type: {getattr(ctx, 'refinement_type', 'unknown')}")
                        continue
                else:
                    # Regular stage import
                    stage_module = importlib.import_module(f"churns.stages.{stage_name}")
                
                # Inject clients into stage
                self._inject_clients_into_stage(stage_module, ctx)
                
                # Execute stage
                stage_module.run(ctx)
                
                stage_duration = time.time() - stage_start_time
                ctx.log(f"Stage {stage_name} completed in {stage_duration:.2f}s")
                
            except Exception as e:
                stage_duration = time.time() - stage_start_time
                ctx.log(f"ERROR in stage {stage_name}: {e}")
                ctx.log(f"Stage {stage_name} failed after {stage_duration:.2f}s")
                # For now, continue with next stage rather than stopping
                # In production, you might want to halt on critical failures
        
        overall_duration = time.time() - overall_start_time
        ctx.log(f"{self.mode.capitalize()} pipeline execution completed in {overall_duration:.2f}s")
        
        return ctx
    
    def _resolve_conditional_stage(self, ctx: PipelineContext) -> Optional[str]:
        """Resolve conditional_stage to actual stage name based on refinement type."""
        refinement_type = getattr(ctx, 'refinement_type', None)
        
        if refinement_type == "subject":
            return "subject_repair"
        elif refinement_type == "text":
            return "text_repair"
        elif refinement_type == "prompt":
            return "prompt_refine"
        else:
            return None
    
    def _needs_style_adaptation(self, ctx: PipelineContext) -> bool:
        """Check if StyleAdaptation stage is needed."""
        from churns.api.database import PresetType
        
        # A new image is provided if image_reference is populated for this run.
        has_new_image = ctx.image_reference is not None
        has_new_prompt = bool(ctx.adaptation_prompt)

        return (
            ctx.preset_type == PresetType.STYLE_RECIPE and
            (has_new_image or has_new_prompt)
        )
    
    async def _run_style_adaptation_stage(self, ctx: PipelineContext, progress_callback: Optional[Callable] = None, stage_order: float = 0) -> None:
        """Run the StyleAdaptation stage."""
        stage_name = "style_adaptation"
        stage_start_time = time.time()
        
        logger.info(f"--- Stage {stage_order}: {stage_name} ---")
        
        # Send stage starting notification
        if progress_callback:
            await progress_callback(
                stage_name, int(stage_order), StageStatus.RUNNING, 
                f"Starting stage {stage_name}...", None, None, None
            )
        
        try:
            # Dynamically import and run the style adaptation stage
            stage_module = importlib.import_module(f"churns.stages.{stage_name}")
            
            # Inject clients into stage
            self._inject_clients_into_stage(stage_module, ctx)
            
            # Run the stage
            await stage_module.run(ctx)
            
            stage_duration = time.time() - stage_start_time
            
            # Check if the stage set an error state
            if hasattr(ctx, 'stage_error') and ctx.stage_error:
                error_msg = ctx.stage_error
                logger.error(f"Stage {stage_name} failed: {error_msg}")
                
                # Send stage error notification
                if progress_callback:
                    await progress_callback(
                        stage_name, int(stage_order), StageStatus.FAILED, 
                        f"Stage {stage_name} failed", 
                        None, error_msg, stage_duration
                    )
                # Clear the error state for next stages
                ctx.stage_error = None
            else:
                logger.info(f"Stage {stage_name} completed in {stage_duration:.2f}s")
                
                # Extract output data for the completed stage
                output_data = self._extract_stage_output(ctx, stage_name)
                
                # Send stage completion notification
                if progress_callback:
                    await progress_callback(
                        stage_name, int(stage_order), StageStatus.COMPLETED, 
                        f"Stage {stage_name} completed successfully", 
                        output_data, None, stage_duration
                    )
            
        except Exception as e:
            stage_duration = time.time() - stage_start_time
            error_msg = f"ERROR in stage {stage_name}: {e}"
            logger.error(error_msg)
            
            # Send stage error notification
            if progress_callback:
                await progress_callback(
                    stage_name, int(stage_order), StageStatus.FAILED, 
                    f"Stage {stage_name} failed", 
                    None, error_msg, stage_duration
                )
            
            # Don't raise exception - let the pipeline continue
    
    async def run_async(
        self, 
        ctx: PipelineContext, 
        progress_callback: Optional[Callable[[str, int, StageStatus, str, Optional[Dict], Optional[str], Optional[float]], Awaitable[None]]] = None,
        session: Optional[Any] = None
    ) -> PipelineContext:
        """Execute all stages in order with async support and progress callbacks."""
        logger.info(f"Starting async {self.mode} pipeline execution with {len(self.stages)} stages : {self.stages}")
        
        # Handle preset loading if preset_id is provided
        if ctx.preset_id and session:
            try:
                logger.info(f"Loading preset {ctx.preset_id} with template_overrides: {ctx.template_overrides}")
                preset_loader = PresetLoader(session)
                await preset_loader.load_and_apply_preset(
                    ctx, 
                    ctx.preset_id, 
                    user_id="dev_user_1",  # TODO: Get from auth context
                    template_overrides=ctx.template_overrides
                )
                logger.info(f"Preset {ctx.preset_id} loaded and applied to context")
            except Exception as e:
                logger.error(f"Failed to load preset {ctx.preset_id}: {str(e)}")
                logger.error(f"Error details: {type(e).__name__}: {str(e)}")
                logger.warning("Continuing pipeline execution without preset")
                # Clear preset information to prevent further issues
                ctx.preset_id = None
                ctx.preset_type = None
                ctx.template_overrides = {}
                ctx.adaptation_prompt = None
        elif ctx.preset_id and not session:
            logger.warning(f"Preset {ctx.preset_id} specified but no database session provided")
        else:
            logger.info("No preset specified, continuing with normal pipeline execution")
        
        overall_start_time = time.time()
        
        for stage_order, stage_name in enumerate(self.stages, 1):
            stage_start_time = time.time()
            logger.info(f"--- Stage {stage_order}: {stage_name} ---")
            
            # Handle conditional stage resolution for refinements
            actual_stage_name = stage_name
            if stage_name == "conditional_stage" and self.mode == "refinement":
                resolved_stage = self._resolve_conditional_stage(ctx)
                if resolved_stage:
                    actual_stage_name = resolved_stage
                    logger.info(f"Resolved conditional stage to: {actual_stage_name}")
                else:
                    logger.warning(f"Warning: Could not resolve conditional stage for refinement type: {getattr(ctx, 'refinement_type', 'unknown')}")
                    continue
            
            # Check if stage should be skipped due to preset configuration
            if actual_stage_name in ctx.skip_stages:
                logger.info(f"Skipping stage {actual_stage_name} due to preset configuration")
                if progress_callback:
                    await progress_callback(
                        actual_stage_name, stage_order, StageStatus.SKIPPED, 
                        f"Stage {actual_stage_name} skipped due to preset configuration", 
                        None, None, 0.0
                    )
                continue
            
            # Check if we need to run StyleAdaptation before prompt_assembly
            if actual_stage_name == "prompt_assembly" and self._needs_style_adaptation(ctx):
                logger.info("Running StyleAdaptation stage before prompt_assembly")
                await self._run_style_adaptation_stage(ctx, progress_callback, stage_order - 0.5)
            
            # Send stage starting notification
            if progress_callback:
                await progress_callback(
                    actual_stage_name, stage_order, StageStatus.RUNNING, 
                    f"Starting stage {actual_stage_name}...", None, None, None
                )
                
                # Small delay to ensure database update is committed before stage execution
                import asyncio
                await asyncio.sleep(0.05)
            
            try:
                # Dynamically import stage module
                stage_module = importlib.import_module(f"churns.stages.{actual_stage_name}")
                
                # Inject clients into stage
                self._inject_clients_into_stage(stage_module, ctx)
                
                # Stage is async, call directly (all stages should be async)
                
                await stage_module.run(ctx)
                
                stage_duration = time.time() - stage_start_time
                logger.info(f"Stage {actual_stage_name} completed in {stage_duration:.2f}s")
                
                # Send stage completion notification
                if progress_callback:
                    # Extract output data based on stage
                    output_data = self._extract_stage_output(ctx, actual_stage_name)
                    await progress_callback(
                        actual_stage_name, stage_order, StageStatus.COMPLETED, 
                        f"Stage {actual_stage_name} completed successfully", 
                        output_data, None, stage_duration
                    )
                
            except Exception as e:
                stage_duration = time.time() - stage_start_time
                error_msg = f"ERROR in stage {actual_stage_name}: {e}"
                logger.error(error_msg)
                logger.info(f"Stage {actual_stage_name} failed after {stage_duration:.2f}s")
                
                # Send stage error notification
                if progress_callback:
                    await progress_callback(
                        actual_stage_name, stage_order, StageStatus.FAILED, 
                        f"Stage {actual_stage_name} failed", 
                        None, str(e), stage_duration
                    )
                
                # For now, continue with next stage rather than stopping
                # In production, you might want to halt on critical failures
        
        overall_duration = time.time() - overall_start_time
        logger.info(f"{self.mode.capitalize()} pipeline execution completed in {overall_duration:.2f}s")
        
        return ctx
    
    def _extract_stage_output(self, ctx: PipelineContext, stage_name: str) -> Optional[Dict[str, Any]]:
        """Extract relevant output data for a completed stage."""
        # Extract stage-specific outputs using context properties
        if stage_name == "image_eval":
            return {"image_analysis": ctx.image_analysis_result}
        elif stage_name == "strategy":
            return {"marketing_strategies": ctx.suggested_marketing_strategies}
        elif stage_name == "style_guide":
            return {"style_guidance": ctx.style_guidance_sets}
        elif stage_name == "creative_expert":
            return {"visual_concepts": ctx.generated_image_prompts}
        elif stage_name == "prompt_assembly":
            return {"final_prompts": ctx.final_assembled_prompts}
        elif stage_name == "image_generation":
            return {"generated_images": ctx.generated_image_results}
        elif stage_name == "image_assessment":
            return {"image_assessments": ctx.image_assessments}
        elif stage_name == "style_adaptation":
            # Extract style adaptation outputs following same pattern as other stages
            return {
                # Primary outputs (same as what other stages produce)
                "adapted_visual_concept": getattr(ctx, 'preset_data', {}).get('visual_concept') if hasattr(ctx, 'preset_data') else None,
                "generated_image_prompts": getattr(ctx, 'generated_image_prompts', []),
                "suggested_marketing_strategies": getattr(ctx, 'suggested_marketing_strategies', []),
                "style_guidance_sets": getattr(ctx, 'style_guidance_sets', []),
                
                # Adaptation-specific metadata
                "adaptation_metadata": {
                    "parent_preset_id": getattr(ctx, 'preset_id', None),
                    "adaptation_trigger": "new_subject_image" if getattr(ctx, 'image_reference', None) else "prompt_override",
                    "original_subject": getattr(ctx, 'original_subject', None),
                    "new_subject": getattr(ctx, 'image_analysis_result', {}).get('main_subject') if hasattr(ctx, 'image_analysis_result') else None,
                    "stages_skipped": getattr(ctx, 'skip_stages', []),
                    "adaptation_success": not bool(getattr(ctx, 'stage_error', None)),
                    "adaptation_reasoning": getattr(ctx, 'adaptation_context', {}).get('adaptation_reasoning') if hasattr(ctx, 'adaptation_context') else None
                },
                
                # Error information (if any)
                "error_details": getattr(ctx, 'stage_error', None)
            }
        elif stage_name in ["load_base_image", "subject_repair", "text_repair", "prompt_refine", "save_outputs"]:
            # Refinement stages - extract relevant data
            return {
                "refinement_result": getattr(ctx, 'refinement_result', None),
                "base_image_loaded": getattr(ctx, 'base_image_path', None) is not None
            }
        else:
            return None
    
    def run_single_stage(self, ctx: PipelineContext, stage_name: str) -> PipelineContext:
        """Execute a single stage by name (useful for testing)."""
        ctx.log(f"Running single stage: {stage_name}")
        
        try:
            stage_module = importlib.import_module(f"churns.stages.{stage_name}")
            self._inject_clients_into_stage(stage_module, ctx)
            stage_module.run(ctx)
            ctx.log(f"Stage {stage_name} completed successfully")
        except Exception as e:
            ctx.log(f"ERROR in stage {stage_name}: {e}")
        
        return ctx

def load_stage_order(mode: str = "generation") -> List[str]:
    """Load stage execution order from YAML config (standalone function for compatibility)."""
    config_path = Path(__file__).parent.parent / "configs" / "stage_order.yml"
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            
            # Try to get stages for specific mode first
            if mode in config:
                return config[mode]
            
            # Fallback to legacy 'stages' key (for generation mode)
            if 'stages' in config:
                return config['stages']
            
            # Final fallback to hardcoded order
            if mode == "refinement":
                return ['load_base_image', 'conditional_stage', 'save_outputs']
            else:
                return ['image_eval', 'strategy', 'style_guide', 'creative_expert', 'prompt_assembly', 'image_generation']
                
    except Exception as e:
        print(f"Warning: Could not load stage config from {config_path}: {e}")
        # Fallback to hardcoded order
        if mode == "refinement":
            return ['load_base_image', 'conditional_stage', 'save_outputs']
        else:
            return ['image_eval', 'strategy', 'style_guide', 'creative_expert', 'prompt_assembly', 'image_generation'] 