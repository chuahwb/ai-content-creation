"""
Test suite for Pipeline Preset Integration.

Tests pipeline execution with presets, stage skipping, and preset loading
functionality.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from churns.pipeline.context import PipelineContext
from churns.pipeline.executor import PipelineExecutor
from churns.pipeline.preset_loader import PresetLoader
from churns.api.database import PresetType, BrandPreset

class TestPipelinePresetIntegration:
    """Test suite for pipeline preset integration."""
    
    @pytest.fixture
    def sample_input_template(self):
        """Sample INPUT_TEMPLATE preset."""
        return {
            "id": "template_123",
            "name": "Test Template",
            "preset_type": PresetType.INPUT_TEMPLATE,
            "model_id": "gpt-image-1",
            "preset_data": {
                "prompt": "A delicious burger",
                "task_type": "1. Product Photography",
                "platform": "Instagram Post (1:1 Square)",
                "audience": "Foodies/Bloggers",
                "niche": "Casual Dining",
                "objective": "Create Appetite Appeal",
                "voice": "Mouth-watering & Descriptive",
                "style_prompt": "Professional food photography",
                "image_analysis_result": {},
                "brand_kit": {
                    "colors": {
                        "primary": "#FF6B35",
                        "secondary": "#004E89",
                        "accent": "#F7931E"
                    },
                    "logo_analysis": {
                        "has_logo": True,
                        "logo_position": "top-right",
                        "logo_style": "modern"
                    }
                }
            },
            "version": 1,
            "user_id": "test_user"
        }
    
    @pytest.fixture
    def sample_style_recipe(self):
        """Sample STYLE_RECIPE preset."""
        return {
            "id": "recipe_123",
            "name": "Test Recipe",
            "preset_type": PresetType.STYLE_RECIPE,
            "model_id": "gpt-image-1",
            "preset_data": {
                "visual_concept": {
                    "main_subject": "A gourmet burger",
                    "composition_and_framing": "Close-up shot with shallow depth of field",
                    "background_environment": "Dark wooden table with subtle lighting",
                    "lighting_and_mood": "Warm, appetizing lighting",
                    "color_palette": "Rich browns, golden yellows, deep reds",
                    "visual_style": "Professional food photography",
                    "suggested_alt_text": "Gourmet burger with crispy bacon"
                },
                "generation_config": {
                    "quality": "high",
                    "style": "photographic",
                    "aspect_ratio": "1:1"
                },
                "brand_kit": {
                    "colors": {
                        "primary": "#FF6B35",
                        "secondary": "#004E89",
                        "accent": "#F7931E"
                    },
                    "logo_analysis": {
                        "has_logo": True,
                        "logo_position": "top-right",
                        "logo_style": "modern"
                    }
                }
            },
            "version": 1,
            "user_id": "test_user"
        }
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session."""
        mock_db = Mock()
        mock_db.query.return_value.filter.return_value.first.return_value = None
        return mock_db
    
    @pytest.fixture
    def pipeline_context(self):
        """Base pipeline context."""
        return PipelineContext(
            run_id="test_run",
            user_id="test_user",
            prompt="A delicious burger",
            task_type="1. Product Photography",
            platform="Instagram Post (1:1 Square)",
            audience="Foodies/Bloggers",
            niche="Casual Dining",
            objective="Create Appetite Appeal",
            voice="Mouth-watering & Descriptive",
            style_prompt="Professional food photography",
            image_analysis_result={}
        )

    @pytest.mark.asyncio
    async def test_template_loading(self, pipeline_context, sample_input_template, mock_db_session):
        """Test loading INPUT_TEMPLATE preset."""
        # Mock database query to return template
        mock_preset = Mock()
        mock_preset.id = sample_input_template["id"]
        mock_preset.name = sample_input_template["name"]
        mock_preset.preset_type = sample_input_template["preset_type"]
        mock_preset.preset_data = sample_input_template["preset_data"]
        mock_preset.version = sample_input_template["version"]
        mock_preset.user_id = sample_input_template["user_id"]
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_preset
        
        # Load preset
        loader = PresetLoader(mock_db_session)
        await loader.load_preset(pipeline_context, "template_123")
        
        # Verify context was updated
        assert pipeline_context.preset_id == "template_123"
        assert pipeline_context.preset_type == PresetType.INPUT_TEMPLATE
        assert pipeline_context.preset_data == sample_input_template["preset_data"]
        assert pipeline_context.prompt == "A delicious burger"
        assert pipeline_context.task_type == "1. Product Photography"
        assert pipeline_context.platform == "Instagram Post (1:1 Square)"

    @pytest.mark.asyncio
    async def test_recipe_loading(self, pipeline_context, sample_style_recipe, mock_db_session):
        """Test loading STYLE_RECIPE preset."""
        # Mock database query to return recipe
        mock_preset = Mock()
        mock_preset.id = sample_style_recipe["id"]
        mock_preset.name = sample_style_recipe["name"]
        mock_preset.preset_type = sample_style_recipe["preset_type"]
        mock_preset.preset_data = sample_style_recipe["preset_data"]
        mock_preset.version = sample_style_recipe["version"]
        mock_preset.user_id = sample_style_recipe["user_id"]
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_preset
        
        # Load preset
        loader = PresetLoader(mock_db_session)
        await loader.load_preset(pipeline_context, "recipe_123")
        
        # Verify context was updated
        assert pipeline_context.preset_id == "recipe_123"
        assert pipeline_context.preset_type == PresetType.STYLE_RECIPE
        assert pipeline_context.preset_data == sample_style_recipe["preset_data"]
        
        # Verify stage skipping is configured
        expected_skip_stages = ["image_eval", "strategy", "style_guide", "creative_expert"]
        assert pipeline_context.skip_stages == expected_skip_stages

    @pytest.mark.asyncio
    async def test_recipe_with_overrides(self, pipeline_context, sample_style_recipe, mock_db_session):
        """Test loading STYLE_RECIPE with overrides."""
        # Mock database query to return recipe
        mock_preset = Mock()
        mock_preset.id = sample_style_recipe["id"]
        mock_preset.name = sample_style_recipe["name"]
        mock_preset.preset_type = sample_style_recipe["preset_type"]
        mock_preset.preset_data = sample_style_recipe["preset_data"]
        mock_preset.version = sample_style_recipe["version"]
        mock_preset.user_id = sample_style_recipe["user_id"]
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_preset
        
        # Set overrides
        pipeline_context.overrides = {
            "prompt": "A delicious pizza",
            "style_prompt": "Rustic photography style"
        }
        
        # Load preset
        loader = PresetLoader(mock_db_session)
        await loader.load_preset(pipeline_context, "recipe_123", overrides=pipeline_context.overrides)
        
        # Verify context was updated with overrides
        assert pipeline_context.preset_id == "recipe_123"
        assert pipeline_context.preset_type == PresetType.STYLE_RECIPE
        assert pipeline_context.overrides == {
            "prompt": "A delicious pizza",
            "style_prompt": "Rustic photography style"
        }

    @pytest.mark.asyncio
    async def test_preset_not_found(self, pipeline_context, mock_db_session):
        """Test handling of non-existent preset."""
        # Mock database query to return None
        mock_db_session.query.return_value.filter.return_value.first.return_value = None
        
        loader = PresetLoader(mock_db_session)
        
        with pytest.raises(ValueError, match="Preset not found"):
            await loader.load_preset(pipeline_context, "nonexistent_preset")

    @pytest.mark.asyncio
    async def test_user_access_control(self, pipeline_context, sample_input_template, mock_db_session):
        """Test that users can only access their own presets."""
        # Mock database query to return preset for different user
        mock_preset = Mock()
        mock_preset.user_id = "different_user"
        mock_preset.id = sample_input_template["id"]
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_preset
        
        loader = PresetLoader(mock_db_session)
        
        with pytest.raises(ValueError, match="Preset not found"):
            await loader.load_preset(pipeline_context, "template_123")

    @pytest.mark.asyncio
    async def test_brand_kit_application(self, pipeline_context, sample_input_template, mock_db_session):
        """Test that brand kit is properly applied."""
        # Mock database query to return template
        mock_preset = Mock()
        mock_preset.id = sample_input_template["id"]
        mock_preset.name = sample_input_template["name"]
        mock_preset.preset_type = sample_input_template["preset_type"]
        mock_preset.preset_data = sample_input_template["preset_data"]
        mock_preset.version = sample_input_template["version"]
        mock_preset.user_id = sample_input_template["user_id"]
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_preset
        
        # Load preset
        loader = PresetLoader(mock_db_session)
        await loader.load_preset(pipeline_context, "template_123")
        
        # Verify brand kit is applied
        assert hasattr(pipeline_context, 'brand_kit')
        assert pipeline_context.brand_kit['colors']['primary'] == '#FF6B35'
        assert pipeline_context.brand_kit['logo_analysis']['has_logo'] is True

    @pytest.mark.asyncio
    async def test_stage_skipping_logic(self, pipeline_context, sample_style_recipe, mock_db_session):
        """Test that stage skipping works correctly for STYLE_RECIPE."""
        # Mock database query to return recipe
        mock_preset = Mock()
        mock_preset.id = sample_style_recipe["id"]
        mock_preset.name = sample_style_recipe["name"]
        mock_preset.preset_type = sample_style_recipe["preset_type"]
        mock_preset.preset_data = sample_style_recipe["preset_data"]
        mock_preset.version = sample_style_recipe["version"]
        mock_preset.user_id = sample_style_recipe["user_id"]
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_preset
        
        # Load preset
        loader = PresetLoader(mock_db_session)
        await loader.load_preset(pipeline_context, "recipe_123")
        
        # Verify skip_stages is set correctly
        expected_skip_stages = ["image_eval", "strategy", "style_guide", "creative_expert"]
        assert pipeline_context.skip_stages == expected_skip_stages

    @pytest.mark.asyncio
    async def test_pipeline_executor_with_template(self, sample_input_template, mock_db_session):
        """Test pipeline executor with INPUT_TEMPLATE preset."""
        # Create context with preset
        ctx = PipelineContext(
            run_id="test_run",
            user_id="test_user",
            prompt="A delicious burger",
            task_type="1. Product Photography",
            platform="Instagram Post (1:1 Square)",
            audience="Foodies/Bloggers",
            niche="Casual Dining",
            objective="Create Appetite Appeal",
            voice="Mouth-watering & Descriptive",
            style_prompt="Professional food photography",
            image_analysis_result={}
        )
        ctx.preset_id = "template_123"
        ctx.preset_type = PresetType.INPUT_TEMPLATE
        ctx.preset_data = sample_input_template["preset_data"]
        
        # Mock executor and stage modules
        with patch('churns.pipeline.executor.importlib.import_module') as mock_import, \
             patch('churns.pipeline.executor.get_configured_clients') as mock_clients:
            
            mock_clients.return_value = {'model_config': {}}
            
            # Mock stage modules
            mock_stage = Mock()
            mock_stage.run = AsyncMock()
            mock_import.return_value = mock_stage
            
            # Create executor
            executor = PipelineExecutor(mode="generation")
            
            # Run pipeline
            result_ctx = executor.run(ctx)
            
            # Verify all stages were attempted (no skipping for templates)
            assert mock_stage.run.call_count >= 5  # At least 5 stages should be called

    @pytest.mark.asyncio
    async def test_pipeline_executor_with_recipe(self, sample_style_recipe, mock_db_session):
        """Test pipeline executor with STYLE_RECIPE preset."""
        # Create context with preset
        ctx = PipelineContext(
            run_id="test_run",
            user_id="test_user",
            prompt="A delicious burger",
            task_type="1. Product Photography",
            platform="Instagram Post (1:1 Square)",
            audience="Foodies/Bloggers",
            niche="Casual Dining",
            objective="Create Appetite Appeal",
            voice="Mouth-watering & Descriptive",
            style_prompt="Professional food photography",
            image_analysis_result={}
        )
        ctx.preset_id = "recipe_123"
        ctx.preset_type = PresetType.STYLE_RECIPE
        ctx.preset_data = sample_style_recipe["preset_data"]
        ctx.skip_stages = ["image_eval", "strategy", "style_guide", "creative_expert"]
        
        # Mock executor and stage modules
        with patch('churns.pipeline.executor.importlib.import_module') as mock_import, \
             patch('churns.pipeline.executor.get_configured_clients') as mock_clients:
            
            mock_clients.return_value = {'model_config': {}}
            
            # Mock stage modules
            mock_stage = Mock()
            mock_stage.run = AsyncMock()
            mock_import.return_value = mock_stage
            
            # Create executor
            executor = PipelineExecutor(mode="generation")
            
            # Run pipeline
            result_ctx = executor.run(ctx)
            
            # Verify some stages were skipped
            # Should only call prompt_assembly and image_generation (2 stages)
            assert mock_stage.run.call_count <= 3  # Fewer stages called due to skipping

    @pytest.mark.asyncio
    async def test_preset_usage_tracking(self, pipeline_context, sample_input_template, mock_db_session):
        """Test that preset usage is tracked correctly."""
        # Mock database query to return template
        mock_preset = Mock()
        mock_preset.id = sample_input_template["id"]
        mock_preset.name = sample_input_template["name"]
        mock_preset.preset_type = sample_input_template["preset_type"]
        mock_preset.preset_data = sample_input_template["preset_data"]
        mock_preset.version = sample_input_template["version"]
        mock_preset.user_id = sample_input_template["user_id"]
        mock_preset.usage_count = 0
        mock_preset.last_used_at = None
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_preset
        
        # Load preset
        loader = PresetLoader(mock_db_session)
        await loader.load_preset(pipeline_context, "template_123")
        
        # Simulate usage tracking
        await loader.track_usage(pipeline_context)
        
        # Verify usage was tracked
        assert mock_preset.usage_count == 1
        assert mock_preset.last_used_at is not None
        mock_db_session.commit.assert_called()

    @pytest.mark.asyncio
    async def test_recipe_override_merging(self, pipeline_context, sample_style_recipe, mock_db_session):
        """Test that recipe overrides are merged correctly."""
        # Mock database query to return recipe
        mock_preset = Mock()
        mock_preset.id = sample_style_recipe["id"]
        mock_preset.name = sample_style_recipe["name"]
        mock_preset.preset_type = sample_style_recipe["preset_type"]
        mock_preset.preset_data = sample_style_recipe["preset_data"]
        mock_preset.version = sample_style_recipe["version"]
        mock_preset.user_id = sample_style_recipe["user_id"]
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_preset
        
        # Set overrides
        overrides = {
            "prompt": "A delicious pizza",
            "style_prompt": "Rustic photography style"
        }
        
        with patch('churns.pipeline.preset_loader.merge_recipe_with_overrides') as mock_merge:
            mock_merge.return_value = sample_style_recipe["preset_data"]
            
            # Load preset
            loader = PresetLoader(mock_db_session)
            await loader.load_preset(pipeline_context, "recipe_123", overrides=overrides)
            
            # Verify merge was called
            mock_merge.assert_called_once_with(
                sample_style_recipe["preset_data"],
                overrides
            )

    @pytest.mark.asyncio
    async def test_model_id_consistency(self, pipeline_context, sample_input_template, mock_db_session):
        """Test that model_id is consistent between preset and context."""
        # Mock database query to return template
        mock_preset = Mock()
        mock_preset.id = sample_input_template["id"]
        mock_preset.name = sample_input_template["name"]
        mock_preset.preset_type = sample_input_template["preset_type"]
        mock_preset.preset_data = sample_input_template["preset_data"]
        mock_preset.model_id = "gpt-image-1"
        mock_preset.version = sample_input_template["version"]
        mock_preset.user_id = sample_input_template["user_id"]
        
        mock_db_session.query.return_value.filter.return_value.first.return_value = mock_preset
        
        # Load preset
        loader = PresetLoader(mock_db_session)
        await loader.load_preset(pipeline_context, "template_123")
        
        # Verify model_id is consistent
        assert pipeline_context.model_id == "gpt-image-1"

if __name__ == "__main__":
    pytest.main([__file__]) 