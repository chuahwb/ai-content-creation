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
from churns.models.presets import PipelineInputSnapshot, StyleRecipeData, StyleRecipeEnvelope

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
        template_overrides: Optional[Dict[str, Any]] = None
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
            ctx.template_overrides = template_overrides or {}
            
            logger.info(f"Applying preset with template_overrides: {ctx.template_overrides}")
            
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
            ctx.template_overrides = {}
            ctx.adaptation_prompt = None
    
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
            
            # Apply template data to context, allowing template overrides
            template_overrides = ctx.template_overrides or {}
            
            # Core fields with clean override logic
            ctx.prompt = template_overrides.get('prompt', input_data.get('prompt', ctx.prompt))
            ctx.creativity_level = template_overrides.get('creativity_level', input_data.get('creativity_level', ctx.creativity_level))
            ctx.num_variants = template_overrides.get('num_variants', input_data.get('num_variants', ctx.num_variants))
            
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
            
            logger.info(f"Successfully applied INPUT_TEMPLATE preset with {len(template_overrides)} template_overrides")
            
        except Exception as e:
            logger.error(f"Error applying INPUT_TEMPLATE preset: {e}")
            raise
    
    async def _apply_style_recipe(self, ctx: PipelineContext, preset: BrandPreset) -> None:
        """Apply a STYLE_RECIPE preset to the pipeline context."""
        try:
            if not preset.style_recipe:
                logger.error("STYLE_RECIPE preset missing style_recipe data")
                raise ValueError("STYLE_RECIPE preset missing style_recipe data")

            # Parse the style recipe envelope
            try:
                envelope_data = json.loads(preset.style_recipe)
                style_envelope = StyleRecipeEnvelope(**envelope_data)
                logger.info(f"Parsed style recipe envelope. Platform: {style_envelope.source_platform}, Language: {style_envelope.language}")
            except Exception as e:
                logger.error(f"Failed to parse or validate StyleRecipeEnvelope JSON: {e}")
                raise ValueError(f"Invalid StyleRecipeEnvelope data: {e}")

            # Store the core recipe data in context for the adaptation stage
            ctx.preset_data = style_envelope.recipe_data.model_dump()

            # Apply rendering flags and context from the envelope
            # These can be overridden by the user's explicit submission flags
            ctx.render_text = style_envelope.render_text
            ctx.apply_branding = style_envelope.apply_branding
            ctx.language = style_envelope.language
            if not ctx.target_platform or not ctx.target_platform.get('name'):
                 if not ctx.target_platform:
                    ctx.target_platform = {}
                 ctx.target_platform['name'] = style_envelope.source_platform

            # Apply brand kit from the top-level of the preset
            await self._apply_brand_kit(ctx, preset)

            # --- BEGIN ENHANCEMENT: Brand Kit Override Detection ---
            original_brand_kit = preset.brand_kit
            current_run_brand_kit = ctx.brand_kit
            is_override = False

            if ctx.apply_branding:
                # A simple and effective deep comparison for dictionaries by comparing their JSON string representations
                original_kit_str = json.dumps(original_brand_kit, sort_keys=True) if original_brand_kit else "{}"
                current_kit_str = json.dumps(current_run_brand_kit, sort_keys=True) if current_run_brand_kit else "{}"
                
                if original_kit_str != current_kit_str:
                    is_override = True
                    logger.info("Brand kit override detected. The provided brand kit differs from the one in the saved recipe.")
                
            # Set a new, explicit flag on the context for downstream stages to use
            ctx.brand_kit_is_override = is_override
            # --- END ENHANCEMENT ---

            # Determine which stages to skip for STYLE_RECIPE
            # We skip the creative stages since we're reusing their output
            ctx.skip_stages = ['strategy', 'style_guide', 'creative_expert']
            
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
                    
                    # Create a sanitized version for logging (hide base64 data)
                    sanitized_brand_kit = preset_brand_kit.copy()
                    if 'logo_base64' in sanitized_brand_kit:
                        sanitized_brand_kit['logo_base64'] = "[HIDDEN]"
                    if 'image_content_base64' in sanitized_brand_kit:
                        sanitized_brand_kit['image_content_base64'] = "[HIDDEN]"
                    if 'logo_file_base64' in sanitized_brand_kit:
                        sanitized_brand_kit['logo_file_base64'] = "[HIDDEN]"
                    # Also check nested structures
                    if 'logo_analysis' in sanitized_brand_kit and isinstance(sanitized_brand_kit['logo_analysis'], dict):
                        if 'logo_base64' in sanitized_brand_kit['logo_analysis']:
                            sanitized_brand_kit['logo_analysis']['logo_base64'] = "[HIDDEN]"
                        if 'image_content_base64' in sanitized_brand_kit['logo_analysis']:
                            sanitized_brand_kit['logo_analysis']['image_content_base64'] = "[HIDDEN]"
                        if 'logo_file_base64' in sanitized_brand_kit['logo_analysis']:
                            sanitized_brand_kit['logo_analysis']['logo_file_base64'] = "[HIDDEN]"
                    
                    logger.info(f"Parsed brand kit from preset: {sanitized_brand_kit}")
                    
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
                        # Create sanitized version for logging
                        sanitized_logo_analysis = preset_brand_kit['logo_analysis'].copy() if isinstance(preset_brand_kit['logo_analysis'], dict) else preset_brand_kit['logo_analysis']
                        if isinstance(sanitized_logo_analysis, dict):
                            if 'logo_base64' in sanitized_logo_analysis:
                                sanitized_logo_analysis['logo_base64'] = "[HIDDEN]"
                            if 'image_content_base64' in sanitized_logo_analysis:
                                sanitized_logo_analysis['image_content_base64'] = "[HIDDEN]"
                            if 'logo_file_base64' in sanitized_logo_analysis:
                                sanitized_logo_analysis['logo_file_base64'] = "[HIDDEN]"
                        logger.info(f"Applied logo analysis from preset: {sanitized_logo_analysis}")
                    
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
        if ctx.preset_type == PresetType.STYLE_RECIPE and ctx.preset_data:
            # preset_data should now be the core recipe_data dictionary
            return ctx.preset_data
        return None
    
    def needs_style_adaptation(self, ctx: PipelineContext) -> bool:
        """Check if StyleAdaptation stage is needed."""
        return (
            ctx.preset_type == PresetType.STYLE_RECIPE and
            bool(ctx.adaptation_prompt)
        ) 