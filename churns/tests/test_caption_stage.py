"""
Unit tests for the Caption Stage.

Tests the caption generation functionality including both Analyst and Writer LLMs.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone

from churns.stages.caption import run, _get_analyst_system_prompt, _get_writer_system_prompt
from churns.models import CaptionBrief, CaptionSettings, CaptionResult
from churns.pipeline.context import PipelineContext


class TestCaptionStage:
    
    def setup_method(self):
        """Set up test fixtures."""
        self.mock_ctx = Mock(spec=PipelineContext)
        self.mock_ctx.log = Mock()
        self.mock_ctx.llm_usage = {}
        
        # Mock pipeline data
        self.mock_ctx.generated_image_prompts = [{
            'source_strategy_index': 0,
            'visual_concept': {
                'main_subject': 'Artisan coffee cup',
                'lighting_and_mood': 'Warm, cozy morning light',
                'visual_style': 'Photorealistic with soft focus',
                'suggested_alt_text': 'Steaming coffee cup on wooden table',
                'promotional_text_visuals': 'FRESH BREW'
            }
        }]
        
        self.mock_ctx.marketing_strategies = [{
            'target_audience': 'Coffee enthusiasts aged 25-40',
            'target_objective': 'Increase brand awareness',
            'target_voice': 'Friendly and approachable',
            'target_niche': 'Specialty Coffee'
        }]
        
        self.mock_ctx.target_platform = {'name': 'Instagram Post (1:1 Square)'}
        
        # Mock settings
        self.mock_ctx.caption_settings = {
            'tone': None,  # Auto mode
            'call_to_action': None,  # Auto mode
            'include_emojis': True,
            'hashtag_strategy': None  # Auto mode
        }
    
    def test_analyst_system_prompt_generation(self):
        """Test that the analyst system prompt is properly formatted."""
        prompt = _get_analyst_system_prompt()
        
        assert "master social media strategist" in prompt
        assert "Caption Brief" in prompt
        assert "Auto Mode Logic" in prompt
        assert "Platform Optimizations" in prompt
    
    def test_writer_system_prompt_generation(self):
        """Test that the writer system prompt is properly formatted."""
        prompt = _get_writer_system_prompt()
        
        assert "expert social media copywriter" in prompt
        assert "authentic and human" in prompt
        assert "Style Guidelines" in prompt
    
    @patch('churns.stages.caption.should_use_manual_parsing')
    @patch('churns.stages.caption._run_analyst')
    @patch('churns.stages.caption._run_writer')
    def test_run_success_flow(self, mock_writer, mock_analyst, mock_parsing):
        """Test successful caption generation flow."""
        # Setup mocks
        mock_parsing.return_value = False
        
        mock_brief = CaptionBrief(
            core_message="Showcase artisan coffee quality",
            key_themes_to_include=["craftsmanship", "morning ritual", "quality"],
            seo_keywords=["artisan coffee", "specialty brew", "morning coffee"],
            target_emotion="Warm and inviting",
            platform_optimizations={"Instagram Post": {"structure": "Hook + value + CTA"}},
            primary_call_to_action="Try our signature blend today!",
            hashtags=["#artisancoffee", "#specialtybrew", "#morningcoffee"],
            emoji_suggestions=["☕", "✨", "🌅"]
        )
        mock_analyst.return_value = mock_brief
        mock_writer.return_value = "Start your morning right ☕\n\nOur artisan coffee is crafted with care for the perfect specialty brew. Every cup tells a story of quality and craftsmanship.\n\nTry our signature blend today!\n\n#artisancoffee #specialtybrew #morningcoffee"
        
        # Run the stage
        run(self.mock_ctx)
        
        # Verify calls
        assert mock_analyst.called
        assert mock_writer.called
        
        # Verify results stored in context
        assert hasattr(self.mock_ctx, 'generated_captions')
        assert len(self.mock_ctx.generated_captions) == 1
        
        caption_data = self.mock_ctx.generated_captions[0]
        assert 'text' in caption_data
        assert 'version' in caption_data
        assert 'settings_used' in caption_data
        assert 'brief_used' in caption_data
        
        # Verify logging
        self.mock_ctx.log.assert_any_call("Starting caption generation stage")
        self.mock_ctx.log.assert_any_call("Caption generation stage completed. Generated 1 captions")
    
    def test_run_missing_image_prompts(self):
        """Test handling when no image prompts are available."""
        self.mock_ctx.generated_image_prompts = None
        
        run(self.mock_ctx)
        
        self.mock_ctx.log.assert_any_call("ERROR: No generated image prompts available for caption generation")
    
    def test_run_missing_marketing_strategies(self):
        """Test handling when no marketing strategies are available."""
        self.mock_ctx.marketing_strategies = None
        
        run(self.mock_ctx)
        
        self.mock_ctx.log.assert_any_call("ERROR: No marketing strategies available for caption generation")
    
    def test_caption_settings_parsing(self):
        """Test that caption settings are properly parsed."""
        # Test with custom settings
        self.mock_ctx.caption_settings = {
            'tone': 'Professional & Polished',
            'call_to_action': 'Shop now!',
            'include_emojis': False,
            'hashtag_strategy': 'Niche & Specific'
        }
        
        with patch('churns.stages.caption._run_analyst') as mock_analyst, \
             patch('churns.stages.caption._run_writer') as mock_writer:
            
            mock_analyst.return_value = CaptionBrief(
                core_message="Test message",
                key_themes_to_include=["test"],
                seo_keywords=["test"],
                target_emotion="Test",
                platform_optimizations={"test": {"test": "test"}},
                primary_call_to_action="Test CTA",
                hashtags=["#test"],
                emoji_suggestions=["✨"]
            )
            mock_writer.return_value = "Test caption"
            
            run(self.mock_ctx)
            
            # Verify analyst was called with the correct settings
            assert mock_analyst.called
            args, kwargs = mock_analyst.call_args_list[0]
            settings = args[1]  # Second argument is settings
            
            assert settings.tone == 'Professional & Polished'
            assert settings.call_to_action == 'Shop now!'
            assert settings.include_emojis == False
            assert settings.hashtag_strategy == 'Niche & Specific'

    def test_main_subject_extraction_from_image_analysis(self):
        """Test main subject extraction when visual concept has null main_subject."""
        # Set up visual concept with null main_subject
        visual_concept = {
            "main_subject": None,
            "lighting_and_mood": "bright",
            "visual_style": "modern"
        }
        
        # Set up image analysis with main subject
        self.mock_ctx.image_analysis_result = {
            "main_subject": "Artisan Coffee Cup"
        }
        
        from churns.stages.caption import _extract_main_subject
        
        result = _extract_main_subject(self.mock_ctx, visual_concept)
        assert result == "Artisan Coffee Cup"
        
    def test_main_subject_extraction_missing_data(self):
        """Test main subject extraction when both sources are missing."""
        visual_concept = {"main_subject": None}
        self.mock_ctx.image_analysis_result = None
        
        from churns.stages.caption import _extract_main_subject
        
        with pytest.raises(ValueError, match="No valid main subject found"):
            _extract_main_subject(self.mock_ctx, visual_concept)
    
    def test_safe_data_extraction_without_defaults(self):
        """Test that safe extraction doesn't provide misleading defaults."""
        from churns.stages.caption import _safe_extract_strategy_data, _safe_extract_visual_data
        
        # Test strategy extraction with missing data
        incomplete_strategy = {"target_audience": "Young professionals"}
        strategy_data = _safe_extract_strategy_data(incomplete_strategy)
        
        assert strategy_data["target_audience"] == "Young professionals"
        assert strategy_data["target_objective"] is None  # No default
        assert strategy_data["target_voice"] is None  # No default
        assert strategy_data["target_niche"] is None  # No default
        
        # Test visual extraction with missing data
        incomplete_visual = {"lighting_and_mood": "dramatic"}
        visual_data = _safe_extract_visual_data(incomplete_visual)
        
        assert visual_data["lighting_mood"] == "dramatic"
        assert visual_data["visual_style"] is None  # No default
        assert visual_data["promotional_text"] is None  # No default
        
    def test_validation_missing_required_data(self):
        """Test validation fails when required data is missing."""
        from churns.stages.caption import _validate_required_data
        
        # Missing target_audience
        strategy_data = {
            "target_audience": None,
            "target_objective": "Increase engagement",
            "target_voice": "Friendly",
            "target_niche": "Coffee"
        }
        visual_data = {"lighting_mood": "bright"}
        
        with pytest.raises(ValueError, match="Missing required target_audience"):
            _validate_required_data(strategy_data, visual_data, "Coffee Cup")
        
        # Missing target_objective
        strategy_data["target_audience"] = "Coffee lovers"
        strategy_data["target_objective"] = None
        
        with pytest.raises(ValueError, match="Missing required target_objective"):
            _validate_required_data(strategy_data, visual_data, "Coffee Cup")
            
    def test_caption_generation_with_incomplete_data(self):
        """Test caption generation fails gracefully with incomplete data."""
        # Create incomplete strategy data
        self.mock_ctx.marketing_strategies = [{
            "target_audience": "Food lovers"
            # Missing target_objective
        }]
        
        self.mock_ctx.generated_image_prompts = [{
            "visual_concept": {
                "main_subject": "Gourmet Burger",
                "lighting_and_mood": "appetizing"
            },
            "source_strategy_index": 0
        }]
        
        # Mock the LLM calls (won't be reached due to validation error)
        self.mock_ctx.instructor_client_caption = Mock()
        self.mock_ctx.base_llm_client_caption = Mock()
        
        from churns.stages.caption import run
        
        # Should handle the error gracefully and not generate captions
        run(self.mock_ctx)
        
        # Verify no captions were generated due to missing data
        assert not hasattr(self.mock_ctx, 'generated_captions') or len(self.mock_ctx.generated_captions) == 0


@pytest.fixture
def sample_caption_brief():
    """Sample caption brief for testing."""
    return CaptionBrief(
        core_message="Showcase artisan coffee quality and morning ritual",
        key_themes_to_include=["craftsmanship", "morning ritual", "quality", "warmth"],
        seo_keywords=["artisan coffee", "specialty brew", "morning coffee", "handcrafted"],
        target_emotion="Warm and inviting",
        platform_optimizations={
            "Instagram Post": {
                "caption_structure": "Start with engaging hook, use line breaks, end with CTA",
                "mentionable_elements": ["Reference the morning light in the image"]
            }
        },
        primary_call_to_action="What's your perfect morning brew? Tell us below! ☕",
        hashtags=["#artisancoffee", "#specialtybrew", "#morningcoffee", "#handcrafted", "#coffeelover"],
        emoji_suggestions=["☕", "✨", "🌅"]
    )


def test_caption_brief_model_validation(sample_caption_brief):
    """Test that CaptionBrief model validates correctly."""
    assert sample_caption_brief.core_message == "Showcase artisan coffee quality and morning ritual"
    assert len(sample_caption_brief.key_themes_to_include) == 4
    assert len(sample_caption_brief.seo_keywords) == 4
    assert len(sample_caption_brief.hashtags) == 5
    assert len(sample_caption_brief.emoji_suggestions) == 3


def test_caption_settings_model_defaults():
    """Test CaptionSettings model with default values."""
    settings = CaptionSettings()
    
    assert settings.tone is None
    assert settings.call_to_action is None
    assert settings.include_emojis == True  # Default to True
    assert settings.hashtag_strategy is None


def test_caption_result_model():
    """Test CaptionResult model creation."""
    settings = CaptionSettings(tone="Friendly & Casual")
    brief = CaptionBrief(
        core_message="Test message",
        key_themes_to_include=["test"],
        seo_keywords=["test"],
        target_emotion="Happy",
        platform_optimizations={"Instagram": {"structure": "test"}},
        primary_call_to_action="Test CTA",
        hashtags=["#test"],
        emoji_suggestions=["😊"]
    )
    
    result = CaptionResult(
        text="This is a test caption! 😊 #test",
        version=1,
        settings_used=settings,
        brief_used=brief,
        created_at=datetime.now(timezone.utc).isoformat()
    )
    
    assert result.text == "This is a test caption! 😊 #test"
    assert result.version == 1
    assert result.settings_used.tone == "Friendly & Casual"
    assert result.brief_used.core_message == "Test message" 