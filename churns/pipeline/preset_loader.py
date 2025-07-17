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
        # Load the preset from database
        result = await self.session.execute(
            select(BrandPreset)
            .where(BrandPreset.id == preset_id)
            .where(BrandPreset.user_id == user_id)
        )
        preset = result.scalar_one_or_none()
        
        if not preset:
            raise ValueError(f"Brand preset {preset_id} not found or not accessible")
        
        # Store preset information in context
        ctx.preset_id = preset_id
        ctx.preset_type = preset.preset_type
        ctx.overrides = overrides or {}
        
        # Apply preset based on type
        if preset.preset_type == PresetType.INPUT_TEMPLATE:
            await self._apply_input_template(ctx, preset)
        elif preset.preset_type == PresetType.STYLE_RECIPE:
            await self._apply_style_recipe(ctx, preset)
        else:
            raise ValueError(f"Unknown preset type: {preset.preset_type}")
        
        # Update usage tracking
        preset.usage_count += 1
        from datetime import datetime
        preset.last_used_at = datetime.utcnow()
        await self.session.commit()
        
        logger.info(f"Applied {preset.preset_type} preset '{preset.name}' to pipeline context")
    
    async def _apply_input_template(self, ctx: PipelineContext, preset: BrandPreset) -> None:
        """Apply an INPUT_TEMPLATE preset to the pipeline context."""
        if not preset.input_snapshot:
            raise ValueError("INPUT_TEMPLATE preset missing input_snapshot data")
        
        # Parse the input snapshot
        input_data = json.loads(preset.input_snapshot)
        
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
        ctx.task_type = input_data.get('task_type', ctx.task_type)
        ctx.render_text = input_data.get('render_text', ctx.render_text)
        ctx.apply_branding = input_data.get('apply_branding', ctx.apply_branding)
        ctx.branding_elements = input_data.get('branding_elements', ctx.branding_elements)
        ctx.task_description = input_data.get('task_description', ctx.task_description)
        ctx.language = input_data.get('language', ctx.language)
        
        # Marketing goals
        if input_data.get('marketing_audience') or input_data.get('marketing_objective'):
            ctx.marketing_goals = {
                'target_audience': input_data.get('marketing_audience'),
                'objective': input_data.get('marketing_objective'),
                'voice': input_data.get('marketing_voice'),
                'niche': input_data.get('marketing_niche')
            }
        
        # Apply brand kit from preset
        await self._apply_brand_kit(ctx, preset)
        
        # INPUT_TEMPLATE runs full pipeline (no stages skipped)
        ctx.skip_stages = []
        
        logger.info(f"Applied INPUT_TEMPLATE preset with {len(overrides)} overrides")
    
    async def _apply_style_recipe(self, ctx: PipelineContext, preset: BrandPreset) -> None:
        """Apply a STYLE_RECIPE preset to the pipeline context."""
        if not preset.style_recipe:
            raise ValueError("STYLE_RECIPE preset missing style_recipe data")
        
        # Parse the style recipe data
        style_data = json.loads(preset.style_recipe)
        
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
        
        logger.info(f"Applied STYLE_RECIPE preset, skipping stages: {ctx.skip_stages}")
    
    async def _apply_brand_kit(self, ctx: PipelineContext, preset: BrandPreset) -> None:
        """Apply brand kit data from preset to context."""
        # Apply brand colors
        if preset.brand_colors:
            brand_colors = json.loads(preset.brand_colors)
            # Store brand colors in context for stages to use
            if not hasattr(ctx, 'brand_kit'):
                ctx.brand_kit = {}
            ctx.brand_kit['colors'] = brand_colors
        
        # Apply brand voice
        if preset.brand_voice_description:
            if not hasattr(ctx, 'brand_kit'):
                ctx.brand_kit = {}
            ctx.brand_kit['voice_description'] = preset.brand_voice_description
        
        # Apply logo analysis (if present)
        if preset.logo_asset_analysis:
            logo_data = json.loads(preset.logo_asset_analysis)
            if not hasattr(ctx, 'brand_kit'):
                ctx.brand_kit = {}
            ctx.brand_kit['logo_analysis'] = logo_data
        
        logger.info("Applied brand kit data to context")
    
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