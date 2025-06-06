"""
Pipeline Executor - Orchestrates running pipeline stages in order.

This replaces the monolithic run_full_pipeline() function with a modular,
configurable stage-based executor.
"""

import time
import yaml
import importlib
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable, Awaitable
from .context import PipelineContext
from ..core.client_config import get_configured_clients
from ..api.database import StageStatus

class PipelineExecutor:
    """Executes pipeline stages in configurable order."""
    
    def __init__(self, stages_config_path: Optional[str] = None, env_path: Optional[str] = None):
        """Initialize executor with stage configuration and API clients."""
        if stages_config_path is None:
            # Default to stage_order.yml in configs directory
            self.config_path = Path(__file__).parent.parent / "configs" / "stage_order.yml"
        else:
            self.config_path = Path(stages_config_path)
        
        self.stages = self._load_stage_config()
        
        # Load and configure API clients
        self.clients = get_configured_clients(env_path)
        print(f"🔧 Pipeline executor initialized with {len(self.stages)} stages and {len([k for k, v in self.clients.items() if v is not None and k not in ['model_config', 'force_manual_json_parse', 'instructor_tool_mode_problem_models']])} configured clients")
    
    def _load_stage_config(self) -> List[str]:
        """Load stage execution order from YAML config."""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)
                return config.get('stages', [])
        except Exception as e:
            print(f"Warning: Could not load stage config from {self.config_path}: {e}")
            # Fallback to hardcoded order
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
    
    def _inject_clients_into_stage(self, stage_module) -> None:
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
        if hasattr(stage_module, 'IMAGE_GENERATION_MODEL_ID'):
            stage_module.IMAGE_GENERATION_MODEL_ID = model_config.get('IMAGE_GENERATION_MODEL_ID')
        
        # Inject parsing configuration
        if hasattr(stage_module, 'FORCE_MANUAL_JSON_PARSE'):
            stage_module.FORCE_MANUAL_JSON_PARSE = self.clients.get('force_manual_json_parse', False)
        if hasattr(stage_module, 'INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS'):
            stage_module.INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS = self.clients.get('instructor_tool_mode_problem_models', [])
    
    def run(self, ctx: PipelineContext) -> PipelineContext:
        """Execute all stages in order."""
        ctx.log(f"Starting pipeline execution with {len(self.stages)} stages")
        
        overall_start_time = time.time()
        
        for stage_name in self.stages:
            stage_start_time = time.time()
            ctx.log(f"--- Stage: {stage_name} ---")
            
            try:
                # Dynamically import stage module
                stage_module = importlib.import_module(f"ai_marketing.stages.{stage_name}")
                
                # Inject clients into stage
                self._inject_clients_into_stage(stage_module)
                
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
        ctx.log(f"Pipeline execution completed in {overall_duration:.2f}s")
        
        return ctx
    
    async def run_async(
        self, 
        ctx: PipelineContext, 
        progress_callback: Optional[Callable[[str, int, StageStatus, str, Optional[Dict], Optional[str], Optional[float]], Awaitable[None]]] = None
    ) -> PipelineContext:
        """Execute all stages in order with async support and progress callbacks."""
        ctx.log(f"Starting async pipeline execution with {len(self.stages)} stages")
        
        overall_start_time = time.time()
        
        for stage_order, stage_name in enumerate(self.stages, 1):
            stage_start_time = time.time()
            ctx.log(f"--- Stage {stage_order}: {stage_name} ---")
            
            # Send stage starting notification
            if progress_callback:
                await progress_callback(
                    stage_name, stage_order, StageStatus.RUNNING, 
                    f"Starting stage {stage_name}...", None, None, None
                )
            
            try:
                # Dynamically import stage module
                stage_module = importlib.import_module(f"ai_marketing.stages.{stage_name}")
                
                # Inject clients into stage
                self._inject_clients_into_stage(stage_module)
                
                # Execute stage in thread pool to avoid blocking
                def run_stage():
                    return stage_module.run(ctx)
                
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, run_stage)
                
                stage_duration = time.time() - stage_start_time
                ctx.log(f"Stage {stage_name} completed in {stage_duration:.2f}s")
                
                # Send stage completion notification
                if progress_callback:
                    # Extract output data based on stage
                    output_data = self._extract_stage_output(ctx, stage_name)
                    await progress_callback(
                        stage_name, stage_order, StageStatus.COMPLETED, 
                        f"Stage {stage_name} completed successfully", 
                        output_data, None, stage_duration
                    )
                
            except Exception as e:
                stage_duration = time.time() - stage_start_time
                error_msg = f"ERROR in stage {stage_name}: {e}"
                ctx.log(error_msg)
                ctx.log(f"Stage {stage_name} failed after {stage_duration:.2f}s")
                
                # Send stage error notification
                if progress_callback:
                    await progress_callback(
                        stage_name, stage_order, StageStatus.FAILED, 
                        f"Stage {stage_name} failed", 
                        None, str(e), stage_duration
                    )
                
                # For now, continue with next stage rather than stopping
                # In production, you might want to halt on critical failures
        
        overall_duration = time.time() - overall_start_time
        ctx.log(f"Pipeline execution completed in {overall_duration:.2f}s")
        
        return ctx
    
    def _extract_stage_output(self, ctx: PipelineContext, stage_name: str) -> Optional[Dict[str, Any]]:
        """Extract relevant output data for a completed stage."""
        processing_context = ctx.data.get("processing_context", {})
        
        # Extract stage-specific outputs
        if stage_name == "image_eval":
            return {"image_analysis": processing_context.get("image_analysis_result")}
        elif stage_name == "strategy":
            return {"marketing_strategies": processing_context.get("suggested_marketing_strategies")}
        elif stage_name == "style_guide":
            return {"style_guidance": processing_context.get("style_guidance_sets")}
        elif stage_name == "creative_expert":
            return {"visual_concepts": processing_context.get("generated_image_prompts")}
        elif stage_name == "prompt_assembly":
            return {"final_prompts": processing_context.get("final_assembled_prompts")}
        elif stage_name == "image_generation":
            return {"generated_images": processing_context.get("generated_image_results")}
        else:
            return None
    
    def run_single_stage(self, ctx: PipelineContext, stage_name: str) -> PipelineContext:
        """Execute a single stage by name (useful for testing)."""
        ctx.log(f"Running single stage: {stage_name}")
        
        try:
            stage_module = importlib.import_module(f"ai_marketing.stages.{stage_name}")
            self._inject_clients_into_stage(stage_module)
            stage_module.run(ctx)
            ctx.log(f"Stage {stage_name} completed successfully")
        except Exception as e:
            ctx.log(f"ERROR in stage {stage_name}: {e}")
        
        return ctx

def load_stage_order() -> List[str]:
    """Load stage execution order from YAML config (standalone function for compatibility)."""
    config_path = Path(__file__).parent.parent / "configs" / "stage_order.yml"
    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            return config.get('stages', [])
    except Exception as e:
        print(f"Warning: Could not load stage config from {config_path}: {e}")
        # Fallback to hardcoded order
        return ['image_eval', 'strategy', 'style_guide', 'creative_expert', 'prompt_assembly', 'image_generation'] 