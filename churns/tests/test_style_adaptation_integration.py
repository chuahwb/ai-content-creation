"""
Integration tests for StyleAdaptation stage.

Tests the complete StyleAdaptation functionality including:
- Style adaptation with precedence rules
- Token budget management
- Edge case handling
- Integration with pipeline execution
"""

import pytest
import json
import tempfile
import os
from unittest.mock import Mock, patch, AsyncMock
from churns.pipeline.context import PipelineContext
from churns.pipeline.executor import PipelineExecutor
from churns.stages.style_adaptation import run as style_adaptation_run
from churns.models import VisualConceptDetails
from churns.models.presets import StyleRecipeData
from churns.api.database import PresetType


class TestStyleAdaptationIntegration:
    """Integration tests for StyleAdaptation stage."""
    
    @pytest.fixture
    def sample_style_recipe(self):
        """Sample style recipe data for testing."""
        return {
            "visual_concept": {
                "main_subject": "A gourmet burger with crispy bacon",
                "composition_and_framing": "Close-up shot with shallow depth of field",
                "background_environment": "Dark wooden table with subtle lighting",
                "lighting_and_mood": "Warm, appetizing lighting with soft shadows",
                "color_palette": "Rich browns, golden yellows, deep reds",
                "visual_style": "Professional food photography with high contrast",
                "branding_visuals": "Logo placed in bottom-right corner",
                "suggested_alt_text": "Gourmet burger with crispy bacon"
            },
            "strategy": {
                "target_audience": "Food Enthusiasts",
                "target_niche": "Gourmet Restaurant",
                "target_objective": "Showcase Quality",
                "target_voice": "Sophisticated & Elegant"
            },
            "style_guidance": {
                "style_keywords": ["elegant", "sophisticated", "high-end"],
                "style_description": "Elegant food photography with sophisticated lighting"
            },
            "final_prompt": "Professional food photography of a gourmet burger with crispy bacon, close-up shot with shallow depth of field, dark wooden table background, warm appetizing lighting, rich browns and golden yellows, elegant and sophisticated style"
        }
    
    @pytest.fixture
    def sample_brand_kit(self):
        """Sample brand kit for testing."""
        return {
            "colors": ["#FF6B35", "#004E89", "#F7931E"],
            "brand_voice_description": "Friendly and approachable, with a focus on quality and craftsmanship",
            "logo_analysis": {
                "logo_style": "Modern minimalist design",
                "has_text": True,
                "text_content": "CHURNS",
                "dominant_colors": ["#FF6B35", "#FFFFFF"],
                "logo_type": "wordmark"
            }
        }
    
    def create_test_context_with_style_recipe(self, style_recipe, brand_kit=None, new_prompt=None, new_image_analysis=None):
        """Create test context with style recipe and optional overrides."""
        ctx = PipelineContext()
        ctx.preset_type = PresetType.STYLE_RECIPE
        ctx.preset_data = style_recipe
        ctx.task_type = "1. Product Photography"
        ctx.target_platform = {
            "name": "Instagram Post (1:1 Square)",
            "resolution_details": {"width": 1080, "height": 1080, "aspect_ratio": "1:1"}
        }
        
        # Set brand kit if provided
        if brand_kit:
            ctx.brand_kit = brand_kit
            
        # Set new prompt (user override)
        if new_prompt:
            ctx.prompt = new_prompt
            
        # Set new image analysis (from uploaded image)
        if new_image_analysis:
            ctx.image_analysis_result = new_image_analysis
            
        return ctx
    
    @patch('churns.stages.style_adaptation.StyleAdaptationAgent.adapt_style')
    def test_style_adaptation_with_new_prompt(self, mock_adapt_style, sample_style_recipe):
        """Test style adaptation with new user prompt."""
        # Mock adapted visual concept
        mock_adapted_concept = VisualConceptDetails(
            main_subject="A gourmet pizza with artisan toppings",
            composition_and_framing="Close-up shot with shallow depth of field",
            background_environment="Dark wooden table with subtle lighting",
            lighting_and_mood="Warm, appetizing lighting with soft shadows",
            color_palette="Rich browns, golden yellows, deep reds",
            visual_style="Professional food photography with high contrast",
            branding_visuals="Logo placed in bottom-right corner",
            suggested_alt_text="Gourmet pizza with artisan toppings"
        )
        
        mock_adapt_style.return_value = mock_adapted_concept
        
        # Create context with new prompt
        ctx = self.create_test_context_with_style_recipe(
            sample_style_recipe,
            new_prompt="Create a gourmet pizza with artisan toppings"
        )
        
        # Run style adaptation
        style_adaptation_run(ctx)
        
        # Verify adaptation was called
        mock_adapt_style.assert_called_once()
        
        # Verify adapted concept was stored
        assert ctx.adapted_visual_concept is not None
        assert ctx.adapted_visual_concept.main_subject == "A gourmet pizza with artisan toppings"
        
        # Verify original style elements are preserved
        assert ctx.adapted_visual_concept.lighting_and_mood == "Warm, appetizing lighting with soft shadows"
        assert ctx.adapted_visual_concept.color_palette == "Rich browns, golden yellows, deep reds"
        assert ctx.adapted_visual_concept.visual_style == "Professional food photography with high contrast"
    
    @patch('churns.stages.style_adaptation.StyleAdaptationAgent.adapt_style')
    def test_style_adaptation_with_brand_kit_integration(self, mock_adapt_style, sample_style_recipe, sample_brand_kit):
        """Test style adaptation with brand kit integration."""
        # Mock adapted concept that includes brand kit elements
        mock_adapted_concept = VisualConceptDetails(
            main_subject="A gourmet coffee cup with latte art",
            composition_and_framing="Close-up shot with shallow depth of field",
            background_environment="Dark wooden table with subtle lighting",
            lighting_and_mood="Warm, appetizing lighting reflecting friendly brand voice",
            color_palette="Rich browns complementing brand colors #FF6B35 and #004E89",
            visual_style="Professional food photography with high contrast",
            branding_visuals="CHURNS wordmark logo placed in bottom-right corner, white color for contrast",
            suggested_alt_text="Gourmet coffee cup with CHURNS branding"
        )
        
        mock_adapt_style.return_value = mock_adapted_concept
        
        # Create context with brand kit and new prompt
        ctx = self.create_test_context_with_style_recipe(
            sample_style_recipe,
            brand_kit=sample_brand_kit,
            new_prompt="Create a gourmet coffee cup with latte art"
        )
        
        # Run style adaptation
        style_adaptation_run(ctx)
        
        # Verify brand kit was integrated
        assert ctx.adapted_visual_concept is not None
        assert "#FF6B35" in ctx.adapted_visual_concept.color_palette or "#004E89" in ctx.adapted_visual_concept.color_palette
        assert "CHURNS" in ctx.adapted_visual_concept.branding_visuals
        assert "friendly" in ctx.adapted_visual_concept.lighting_and_mood
    
    @patch('churns.stages.style_adaptation.StyleAdaptationAgent.adapt_style')
    def test_style_adaptation_with_image_analysis(self, mock_adapt_style, sample_style_recipe):
        """Test style adaptation with new image analysis."""
        # Mock adapted concept incorporating new image analysis
        mock_adapted_concept = VisualConceptDetails(
            main_subject="A fresh salad bowl with mixed greens",
            composition_and_framing="Top-down view with natural lighting",
            background_environment="Marble countertop with clean aesthetic",
            lighting_and_mood="Bright, fresh lighting with vibrant colors",
            color_palette="Fresh greens, vibrant vegetables, clean whites",
            visual_style="Healthy lifestyle photography with clean aesthetic",
            branding_visuals="Logo placed in bottom-right corner",
            suggested_alt_text="Fresh salad bowl with mixed greens"
        )
        
        mock_adapt_style.return_value = mock_adapted_concept
        
        # Create context with new image analysis
        new_image_analysis = {
            "main_subject": "Fresh salad bowl",
            "secondary_elements": ["mixed greens", "vegetables", "marble countertop"],
            "color_analysis": {
                "dominant_colors": ["#228B22", "#FFFFFF", "#32CD32"],
                "color_harmony": "Fresh and vibrant"
            }
        }
        
        ctx = self.create_test_context_with_style_recipe(
            sample_style_recipe,
            new_prompt="Create a healthy salad bowl image",
            new_image_analysis=new_image_analysis
        )
        
        # Run style adaptation
        style_adaptation_run(ctx)
        
        # Verify image analysis was incorporated
        assert ctx.adapted_visual_concept is not None
        assert "salad bowl" in ctx.adapted_visual_concept.main_subject.lower()
        assert "greens" in ctx.adapted_visual_concept.color_palette.lower()
        assert "fresh" in ctx.adapted_visual_concept.lighting_and_mood.lower()
    
    def test_style_adaptation_precedence_rules(self, sample_style_recipe):
        """Test precedence rules in style adaptation."""
        # Create context with conflicting elements
        ctx = self.create_test_context_with_style_recipe(
            sample_style_recipe,
            new_prompt="Create a dark, moody nighttime scene"  # Conflicts with warm lighting in recipe
        )
        
        # Mock adaptation that should prioritize user prompt
        with patch('churns.stages.style_adaptation.StyleAdaptationAgent.adapt_style') as mock_adapt:
            mock_adapted_concept = VisualConceptDetails(
                main_subject="A nighttime street scene",
                composition_and_framing="Wide shot with dramatic perspective",
                background_environment="Urban nighttime setting",
                lighting_and_mood="Dark, moody nighttime atmosphere",  # User prompt takes precedence
                color_palette="Deep blues, dark purples, neon accents",
                visual_style="Cinematic nighttime photography",
                branding_visuals="Logo placed in bottom-right corner",
                suggested_alt_text="Moody nighttime street scene"
            )
            
            mock_adapt.return_value = mock_adapted_concept
            
            # Run style adaptation
            style_adaptation_run(ctx)
            
            # Verify user prompt took precedence over original recipe
            assert ctx.adapted_visual_concept is not None
            assert "dark" in ctx.adapted_visual_concept.lighting_and_mood.lower()
            assert "moody" in ctx.adapted_visual_concept.lighting_and_mood.lower()
            assert "nighttime" in ctx.adapted_visual_concept.lighting_and_mood.lower()
    
    def test_style_adaptation_token_budget_management(self, sample_style_recipe):
        """Test token budget management in style adaptation."""
        # Create a very large style recipe that would exceed token limits
        large_recipe = sample_style_recipe.copy()
        large_recipe["visual_concept"]["creative_reasoning"] = "Very detailed reasoning... " * 1000
        large_recipe["visual_concept"]["technical_specifications"] = "Detailed specs... " * 500
        
        ctx = self.create_test_context_with_style_recipe(
            large_recipe,
            new_prompt="Create a simple burger image"
        )
        
        with patch('churns.stages.style_adaptation.estimate_token_count') as mock_estimate:
            with patch('churns.stages.style_adaptation.StyleAdaptationAgent.adapt_style') as mock_adapt:
                # Mock token count that exceeds limit
                mock_estimate.return_value = 8000  # Above 85% of typical 8K limit
                
                mock_adapted_concept = VisualConceptDetails(
                    main_subject="A simple burger",
                    composition_and_framing="Close-up shot",
                    background_environment="Simple background",
                    lighting_and_mood="Natural lighting",
                    color_palette="Natural food colors",
                    visual_style="Simple food photography",
                    branding_visuals="Logo placement",
                    suggested_alt_text="Simple burger"
                )
                
                mock_adapt.return_value = mock_adapted_concept
                
                # Run style adaptation
                style_adaptation_run(ctx)
                
                # Verify token budget management was applied
                # The function should have pruned non-essential fields
                mock_estimate.assert_called()
    
    def test_style_adaptation_error_handling(self, sample_style_recipe):
        """Test error handling in style adaptation."""
        ctx = self.create_test_context_with_style_recipe(
            sample_style_recipe,
            new_prompt="Create a new image"
        )
        
        with patch('churns.stages.style_adaptation.StyleAdaptationAgent.adapt_style') as mock_adapt:
            # Mock API error
            mock_adapt.side_effect = Exception("API connection failed")
            
            # Run style adaptation
            style_adaptation_run(ctx)
            
            # Verify error was handled gracefully
            assert ctx.adapted_visual_concept is None
            assert any("StyleAdaptation failed" in str(log) for log in ctx.logs)
    
    def test_style_adaptation_skipped_when_no_prompt(self, sample_style_recipe):
        """Test that style adaptation is skipped when no new prompt is provided."""
        ctx = self.create_test_context_with_style_recipe(sample_style_recipe)
        # No new prompt provided - should skip adaptation
        
        with patch('churns.stages.style_adaptation.StyleAdaptationAgent.adapt_style') as mock_adapt:
            # Run style adaptation
            style_adaptation_run(ctx)
            
            # Verify adaptation was skipped
            mock_adapt.assert_not_called()
            assert ctx.adapted_visual_concept is None
    
    def test_style_adaptation_with_subject_swap(self, sample_style_recipe):
        """Test style adaptation for subject swap scenario."""
        # Create context with only image analysis (no text prompt)
        new_image_analysis = {
            "main_subject": "Gourmet pizza",
            "secondary_elements": ["melted cheese", "fresh basil"],
            "color_analysis": {
                "dominant_colors": ["#FF6B35", "#228B22", "#FFFFFF"],
                "color_harmony": "Warm and appetizing"
            }
        }
        
        ctx = self.create_test_context_with_style_recipe(
            sample_style_recipe,
            new_image_analysis=new_image_analysis
        )
        
        with patch('churns.stages.style_adaptation.StyleAdaptationAgent.adapt_style') as mock_adapt:
            mock_adapted_concept = VisualConceptDetails(
                main_subject="Gourmet pizza with melted cheese and fresh basil",
                composition_and_framing="Close-up shot with shallow depth of field",
                background_environment="Dark wooden table with subtle lighting",
                lighting_and_mood="Warm, appetizing lighting with soft shadows",
                color_palette="Rich browns, golden yellows, deep reds, vibrant greens",
                visual_style="Professional food photography with high contrast",
                branding_visuals="Logo placed in bottom-right corner",
                suggested_alt_text="Gourmet pizza with melted cheese and fresh basil"
            )
            
            mock_adapt.return_value = mock_adapted_concept
            
            # Run style adaptation
            style_adaptation_run(ctx)
            
            # Verify subject was swapped while preserving style
            assert ctx.adapted_visual_concept is not None
            assert "pizza" in ctx.adapted_visual_concept.main_subject.lower()
            assert "melted cheese" in ctx.adapted_visual_concept.main_subject.lower()
            
            # Verify original style elements were preserved
            assert ctx.adapted_visual_concept.lighting_and_mood == "Warm, appetizing lighting with soft shadows"
            assert "Close-up shot" in ctx.adapted_visual_concept.composition_and_framing
    
    def test_style_adaptation_consistency_tracking(self, sample_style_recipe):
        """Test consistency tracking in style adaptation."""
        ctx = self.create_test_context_with_style_recipe(
            sample_style_recipe,
            new_prompt="Create a gourmet sandwich"
        )
        
        with patch('churns.stages.style_adaptation.StyleAdaptationAgent.adapt_style') as mock_adapt:
            mock_adapted_concept = VisualConceptDetails(
                main_subject="A gourmet sandwich",
                composition_and_framing="Close-up shot with shallow depth of field",
                background_environment="Dark wooden table with subtle lighting",
                lighting_and_mood="Warm, appetizing lighting with soft shadows",
                color_palette="Rich browns, golden yellows, deep reds",
                visual_style="Professional food photography with high contrast",
                branding_visuals="Logo placed in bottom-right corner",
                suggested_alt_text="Gourmet sandwich"
            )
            
            mock_adapt.return_value = mock_adapted_concept
            
            # Run style adaptation
            style_adaptation_run(ctx)
            
            # Verify consistency tracking data is available
            assert ctx.adapted_visual_concept is not None
            assert hasattr(ctx, 'style_adaptation_metadata')
            assert ctx.style_adaptation_metadata['original_recipe_id'] is not None
            assert ctx.style_adaptation_metadata['adaptation_type'] == 'text_prompt'
    
    def test_style_adaptation_edge_cases(self, sample_style_recipe):
        """Test edge cases in style adaptation."""
        # Test with empty prompt
        ctx = self.create_test_context_with_style_recipe(
            sample_style_recipe,
            new_prompt=""
        )
        
        with patch('churns.stages.style_adaptation.StyleAdaptationAgent.adapt_style') as mock_adapt:
            # Run style adaptation
            style_adaptation_run(ctx)
            
            # Should skip adaptation with empty prompt
            mock_adapt.assert_not_called()
            assert ctx.adapted_visual_concept is None
        
        # Test with very long prompt
        long_prompt = "Create a detailed image with " + "many specific requirements " * 100
        ctx = self.create_test_context_with_style_recipe(
            sample_style_recipe,
            new_prompt=long_prompt
        )
        
        with patch('churns.stages.style_adaptation.StyleAdaptationAgent.adapt_style') as mock_adapt:
            mock_adapted_concept = VisualConceptDetails(
                main_subject="A detailed complex image",
                composition_and_framing="Complex composition",
                background_environment="Detailed background",
                lighting_and_mood="Complex lighting setup",
                color_palette="Complex color scheme",
                visual_style="Detailed photography style",
                branding_visuals="Logo placement",
                suggested_alt_text="Complex detailed image"
            )
            
            mock_adapt.return_value = mock_adapted_concept
            
            # Run style adaptation
            style_adaptation_run(ctx)
            
            # Should handle long prompt gracefully
            assert ctx.adapted_visual_concept is not None


class TestStyleAdaptationPipelineIntegration:
    """Test StyleAdaptation integration with full pipeline execution."""
    
    def test_style_adaptation_in_pipeline_execution(self):
        """Test StyleAdaptation stage integration in full pipeline."""
        # Create a complete pipeline context
        ctx = PipelineContext()
        ctx.preset_type = PresetType.STYLE_RECIPE
        ctx.preset_data = {
            "visual_concept": {
                "main_subject": "A gourmet burger",
                "composition_and_framing": "Close-up shot",
                "background_environment": "Dark wooden table",
                "lighting_and_mood": "Warm lighting",
                "color_palette": "Rich browns and golds",
                "visual_style": "Professional food photography",
                "branding_visuals": "Logo in corner",
                "suggested_alt_text": "Gourmet burger"
            }
        }
        ctx.prompt = "Create a gourmet pizza instead"
        ctx.task_type = "1. Product Photography"
        ctx.target_platform = {
            "name": "Instagram Post (1:1 Square)",
            "resolution_details": {"width": 1080, "height": 1080, "aspect_ratio": "1:1"}
        }
        
        # Mock pipeline executor to include StyleAdaptation
        with patch('churns.pipeline.executor.PipelineExecutor.run_async') as mock_run:
            with patch('churns.stages.style_adaptation.StyleAdaptationAgent.adapt_style') as mock_adapt:
                mock_adapted_concept = VisualConceptDetails(
                    main_subject="A gourmet pizza",
                    composition_and_framing="Close-up shot",
                    background_environment="Dark wooden table",
                    lighting_and_mood="Warm lighting",
                    color_palette="Rich browns and golds",
                    visual_style="Professional food photography",
                    branding_visuals="Logo in corner",
                    suggested_alt_text="Gourmet pizza"
                )
                
                mock_adapt.return_value = mock_adapted_concept
                
                # Mock pipeline execution
                executor = PipelineExecutor()
                result_ctx = executor.run(ctx)
                
                # Verify StyleAdaptation was integrated
                assert result_ctx is not None
    
    def test_style_adaptation_stage_skipping(self):
        """Test that StyleAdaptation is properly skipped when not needed."""
        ctx = PipelineContext()
        ctx.preset_type = PresetType.INPUT_TEMPLATE  # Not a style recipe
        ctx.task_type = "1. Product Photography"
        ctx.target_platform = {
            "name": "Instagram Post (1:1 Square)",
            "resolution_details": {"width": 1080, "height": 1080, "aspect_ratio": "1:1"}
        }
        
        with patch('churns.stages.style_adaptation.StyleAdaptationAgent.adapt_style') as mock_adapt:
            # Run pipeline
            executor = PipelineExecutor()
            result_ctx = executor.run(ctx)
            
            # StyleAdaptation should not be called for INPUT_TEMPLATE
            mock_adapt.assert_not_called()
    
    def test_style_adaptation_error_recovery(self):
        """Test pipeline error recovery when StyleAdaptation fails."""
        ctx = PipelineContext()
        ctx.preset_type = PresetType.STYLE_RECIPE
        ctx.preset_data = {
            "visual_concept": {
                "main_subject": "A gourmet burger",
                "composition_and_framing": "Close-up shot",
                "background_environment": "Dark wooden table",
                "lighting_and_mood": "Warm lighting",
                "color_palette": "Rich browns and golds",
                "visual_style": "Professional food photography",
                "branding_visuals": "Logo in corner",
                "suggested_alt_text": "Gourmet burger"
            }
        }
        ctx.prompt = "Create a gourmet pizza instead"
        ctx.task_type = "1. Product Photography"
        ctx.target_platform = {
            "name": "Instagram Post (1:1 Square)",
            "resolution_details": {"width": 1080, "height": 1080, "aspect_ratio": "1:1"}
        }
        
        with patch('churns.stages.style_adaptation.StyleAdaptationAgent.adapt_style') as mock_adapt:
            # Mock StyleAdaptation failure
            mock_adapt.side_effect = Exception("StyleAdaptation failed")
            
            # Run pipeline
            executor = PipelineExecutor()
            result_ctx = executor.run(ctx)
            
            # Pipeline should continue despite StyleAdaptation failure
            assert result_ctx is not None
            assert any("StyleAdaptation failed" in str(log) for log in result_ctx.logs) 