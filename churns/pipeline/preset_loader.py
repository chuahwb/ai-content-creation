"""
Preset Loader - Handles loading and applying brand presets in the pipeline.
"""

import json
import logging
from typing import Dict, Any, Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from churns.api.database import BrandPreset, PresetType
from churns.pipeline.context import PipelineContext
from churns.models.presets import PipelineInputSnapshot, StyleRecipeData

logger = logging.getLogger(__name__)


class PresetLoader:
    """Handles loading and applying brand presets to pipeline context."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def load_and_apply_preset(
        self, 
        ctx: PipelineContext, 
        preset_id: str, 
        user_id: str,
        overrides: Optional[Dict[str, Any]] = None
    ) -> None:
        """Load a brand preset and apply it to the pipeline context."""
        try:
            logger.info(f"Loading preset {preset_id} for user {user_id}")
            
            # Load the preset from database
            result = await self.session.execute(
                select(BrandPreset)
                .where(BrandPreset.id == preset_id)
                .where(BrandPreset.user_id == user_id)
            )
            preset = result.scalar_one_or_none()
            
            if not preset:
                logger.error(f"Brand preset {preset_id} not found or not accessible")
                raise ValueError(f"Brand preset {preset_id} not found or not accessible")
            
            logger.info(f"Found preset '{preset.name}' of type {preset.preset_type}")
            
            # Store preset information in context
            ctx.preset_id = preset_id
            ctx.preset_type = preset.preset_type
            ctx.overrides = overrides or {}
            
            logger.info(f"Applying preset with overrides: {ctx.overrides}")
            
            # Apply preset based on type
            if preset.preset_type == PresetType.INPUT_TEMPLATE:
                await self._apply_input_template(ctx, preset)
            elif preset.preset_type == PresetType.STYLE_RECIPE:
                await self._apply_style_recipe(ctx, preset)
            else:
                logger.error(f"Unknown preset type: {preset.preset_type}")
                raise ValueError(f"Unknown preset type: {preset.preset_type}")
            
            # Update usage tracking
            preset.usage_count += 1
            from datetime import datetime
            preset.last_used_at = datetime.utcnow()
            await self.session.commit()
            
            logger.info(f"Successfully applied {preset.preset_type} preset '{preset.name}' to pipeline context")
            
        except Exception as e:
            logger.error(f"Error loading preset {preset_id}: {str(e)}")
            logger.error(f"Error details: {type(e).__name__}: {str(e)}")
            # Don't re-raise the exception, just log it and continue
            # This allows the pipeline to continue without the preset
            logger.warning(f"Continuing pipeline execution without preset {preset_id}")
            ctx.preset_id = None
            ctx.preset_type = None
            ctx.overrides = {}
    
    async def _apply_input_template(self, ctx: PipelineContext, preset: BrandPreset) -> None:
        """Apply an INPUT_TEMPLATE preset to the pipeline context."""
        try:
            if not preset.input_snapshot:
                logger.error("INPUT_TEMPLATE preset missing input_snapshot data")
                raise ValueError("INPUT_TEMPLATE preset missing input_snapshot data")
            
            # Parse the input snapshot
            try:
                input_data = json.loads(preset.input_snapshot)
                logger.info(f"Parsed input snapshot with keys: {list(input_data.keys())}")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse input_snapshot JSON: {e}")
                raise ValueError(f"Failed to parse input_snapshot JSON: {e}")
            
            # Apply template data to context, allowing overrides
            overrides = ctx.overrides or {}
            
            # Core fields
            if 'prompt' not in overrides:
                ctx.prompt = input_data.get('prompt', ctx.prompt)
            else:
                ctx.prompt = overrides['prompt']
            
            if 'creativity_level' not in overrides:
                ctx.creativity_level = input_data.get('creativity_level', ctx.creativity_level)
            else:
                ctx.creativity_level = overrides['creativity_level']
            
            if 'num_variants' not in overrides:
                ctx.num_variants = input_data.get('num_variants', ctx.num_variants)
            else:
                ctx.num_variants = overrides['num_variants']
            
            # Apply other template fields
            ctx.mode = input_data.get('mode', ctx.mode)
            # Apply platform_name if present in template
            if input_data.get('platform_name'):
                if not ctx.target_platform:
                    ctx.target_platform = {}
                ctx.target_platform['name'] = input_data.get('platform_name')
            ctx.task_type = input_data.get('task_type', ctx.task_type)
            ctx.render_text = input_data.get('render_text', ctx.render_text)
            ctx.apply_branding = input_data.get('apply_branding', ctx.apply_branding)
            ctx.task_description = input_data.get('task_description', ctx.task_description)
            ctx.language = input_data.get('language', ctx.language)
            
            # Apply brand kit from input snapshot if present
            if input_data.get('brand_kit'):
                logger.info(f"Applying brand kit from input snapshot: {input_data.get('brand_kit')}")
                ctx.brand_kit = input_data.get('brand_kit')
            
            # Marketing goals
            if input_data.get('marketing_audience') or input_data.get('marketing_objective'):
                ctx.marketing_goals = {
                    'target_audience': input_data.get('marketing_audience'),
                    'objective': input_data.get('marketing_objective'),
                    'voice': input_data.get('marketing_voice'),
                    'niche': input_data.get('marketing_niche')
                }
            
            # Apply brand kit from preset (this will merge with any brand_kit from input_snapshot)
            await self._apply_brand_kit(ctx, preset)
            
            # INPUT_TEMPLATE runs full pipeline (no stages skipped)
            ctx.skip_stages = []
            
            logger.info(f"Successfully applied INPUT_TEMPLATE preset with {len(overrides)} overrides")
            
        except Exception as e:
            logger.error(f"Error applying INPUT_TEMPLATE preset: {e}")
            raise
    
    async def _apply_style_recipe(self, ctx: PipelineContext, preset: BrandPreset) -> None:
        """Apply a STYLE_RECIPE preset to the pipeline context."""
        try:
            if not preset.style_recipe:
                logger.error("STYLE_RECIPE preset missing style_recipe data")
                raise ValueError("STYLE_RECIPE preset missing style_recipe data")
            
            # Parse the style recipe data
            try:
                style_data = json.loads(preset.style_recipe)
                logger.info(f"Parsed style recipe with keys: {list(style_data.keys())}")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse style_recipe JSON: {e}")
                raise ValueError(f"Failed to parse style_recipe JSON: {e}")
            
            # Store the style recipe data in context
            ctx.preset_data = style_data
            
            # Apply brand kit from preset
            await self._apply_brand_kit(ctx, preset)
            
            # Determine which stages to skip for STYLE_RECIPE
            # We skip the creative stages since we're reusing their output
            ctx.skip_stages = ['strategy', 'style_guide', 'creative_expert']
            
            # Check if we need StyleAdaptation based on overrides
            if ctx.overrides and ctx.overrides.get('prompt'):
                # User provided a new prompt, so we need StyleAdaptation
                ctx.skip_stages = ['strategy', 'style_guide', 'creative_expert']
                # StyleAdaptation will be handled by the executor
                logger.info("Style adaptation will be triggered due to prompt override")
            
            logger.info(f"Successfully applied STYLE_RECIPE preset, skipping stages: {ctx.skip_stages}")
            
        except Exception as e:
            logger.error(f"Error applying STYLE_RECIPE preset: {e}")
            raise
    
    async def _apply_brand_kit(self, ctx: PipelineContext, preset: BrandPreset) -> None:
        """Apply brand kit data from preset to context."""
        try:
            # Initialize brand kit if not present
            if ctx.brand_kit is None:
                ctx.brand_kit = {}
            
            # Apply brand kit data from preset's unified brand_kit field
            if preset.brand_kit:
                try:
                    preset_brand_kit = json.loads(preset.brand_kit)
                    logger.info(f"Parsed brand kit from preset: {preset_brand_kit}")
                    
                    # Apply brand colors
                    if preset_brand_kit.get('colors'):
                        ctx.brand_kit['colors'] = preset_brand_kit['colors']
                        logger.info(f"Applied brand colors from preset: {preset_brand_kit['colors']}")
                    
                    # Apply brand voice
                    if preset_brand_kit.get('brand_voice_description'):
                        ctx.brand_kit['brand_voice_description'] = preset_brand_kit['brand_voice_description']
                        logger.info(f"Applied brand voice from preset: {preset_brand_kit['brand_voice_description']}")
                    
                    # Apply logo analysis
                    if preset_brand_kit.get('logo_analysis'):
                        ctx.brand_kit['logo_analysis'] = preset_brand_kit['logo_analysis']
                        logger.info(f"Applied logo analysis from preset: {preset_brand_kit['logo_analysis']}")
                    
                    # Apply logo file path if present
                    if preset_brand_kit.get('saved_logo_path_in_run_dir'):
                        ctx.brand_kit['saved_logo_path_in_run_dir'] = preset_brand_kit['saved_logo_path_in_run_dir']
                        logger.info(f"Applied logo path from preset: {preset_brand_kit['saved_logo_path_in_run_dir']}")
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse brand_kit JSON: {e}")
                    logger.warning("Skipping brand kit data from preset")
            
            logger.info("Successfully applied brand kit data to context")
            
        except Exception as e:
            logger.error(f"Error applying brand kit data: {e}")
            # Don't raise the exception, just log it and continue
            logger.warning("Continuing without brand kit data from preset")
    
    def should_skip_stage(self, ctx: PipelineContext, stage_name: str) -> bool:
        """Check if a stage should be skipped based on preset configuration."""
        return stage_name in ctx.skip_stages
    
    def get_style_recipe_data(self, ctx: PipelineContext) -> Optional[Dict[str, Any]]:
        """Get the style recipe data from context if available."""
        if ctx.preset_type == PresetType.STYLE_RECIPE:
            return ctx.preset_data
        return None
    
    def needs_style_adaptation(self, ctx: PipelineContext) -> bool:
        """Check if StyleAdaptation stage is needed."""
        return (
            ctx.preset_type == PresetType.STYLE_RECIPE and
            ctx.overrides and 
            ctx.overrides.get('prompt')
        )


def merge_recipe_with_overrides(recipe: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge user overrides with style recipe data.
    User overrides take precedence over recipe data.
    """
    merged = recipe.copy()
    
    # Apply overrides with precedence rules
    for key, value in overrides.items():
        if key in ['prompt', 'creativity_level', 'num_variants']:
            # These are handled at the context level
            continue
        elif key == 'visual_concept':
            # Deep merge visual concept fields
            if 'visual_concept' in merged and isinstance(merged['visual_concept'], dict):
                merged['visual_concept'].update(value)
            else:
                merged['visual_concept'] = value
        else:
            # Direct override
            merged[key] = value
    
    return merged 