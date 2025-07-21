"""
Test suite for StyleAdaptation stage.

Tests the style adaptation logic, precedence rules, token budget management,
and edge case handling for STYLE_RECIPE presets.
"""

import pytest
import json
from unittest.mock import Mock, patch, AsyncMock
from churns.stages import style_adaptation
from churns.pipeline.context import PipelineContext
from churns.api.database import PresetType

class TestStyleAdaptationStage:
    """Test suite for StyleAdaptation stage functionality."""
    
    @pytest.fixture
    def mock_client(self):
        """Mock LLM client for testing."""
        from churns.models import VisualConceptDetails
        mock_client = Mock()
        mock_response = VisualConceptDetails(
            main_subject="A gourmet pizza",
            composition_and_framing="Close-up shot with shallow depth of field",
            background_environment="Dark wooden table with subtle lighting",
            lighting_and_mood="Warm, appetizing lighting",
            color_palette="Rich browns, golden yellows, deep reds",
            visual_style="Professional food photography",
            suggested_alt_text="Gourmet pizza with melted cheese"
        )
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        return mock_client

    @pytest.fixture
    def base_style_recipe(self):
        """Base style recipe for testing."""
        return {
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
            }
        }

    @pytest.fixture
    def pipeline_context(self, base_style_recipe):
        """Pipeline context with STYLE_RECIPE preset."""
        ctx = PipelineContext(
            run_id="test_run",
            prompt="A delicious pizza",
            task_type="1. Product Photography",
            target_platform={"name": "Instagram Post (1:1 Square)"},
            marketing_goals={
                "audience": "Foodies/Bloggers",
                "niche": "Casual Dining",
                "objective": "Create Appetite Appeal",
                "voice": "Mouth-watering & Descriptive",
            },
            image_analysis_result={}
        )
        ctx.preset_type = PresetType.STYLE_RECIPE
        ctx.preset_data = base_style_recipe
        ctx.overrides = {"prompt": "A delicious pizza"}
        return ctx

    @pytest.fixture
    def setup_stage_globals(self, mock_client):
        """Setup global variables for the stage."""
        style_adaptation.instructor_client_style_adaptation = mock_client
        style_adaptation.base_llm_client_style_adaptation = mock_client
        style_adaptation.STYLE_ADAPTATION_MODEL_ID = "openai/gpt-4o"
        style_adaptation.STYLE_ADAPTATION_MODEL_PROVIDER = "OpenRouter"
        style_adaptation.FORCE_MANUAL_JSON_PARSE = False
        style_adaptation.INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS = []
        yield
        # Cleanup
        style_adaptation.instructor_client_style_adaptation = None
        style_adaptation.base_llm_client_style_adaptation = None
        style_adaptation.STYLE_ADAPTATION_MODEL_ID = None
        style_adaptation.STYLE_ADAPTATION_MODEL_PROVIDER = None
        style_adaptation.FORCE_MANUAL_JSON_PARSE = False
        style_adaptation.INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS = []

    @pytest.mark.asyncio
    async def test_style_adaptation_execution(self, pipeline_context, setup_stage_globals, mock_client):
        """Test normal style adaptation execution."""
        await style_adaptation.run(pipeline_context)
        
        # Verify LLM was called
        mock_client.chat.completions.create.assert_called_once()
        call_args = mock_client.chat.completions.create.call_args
        
        # Verify model configuration
        assert call_args[1]["model"] == "openai/gpt-4o"
        assert call_args[1]["temperature"] == 0.7
        assert call_args[1]["max_tokens"] == 4000
        
        # Verify messages structure
        messages = call_args[1]["messages"]
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "Creative Director" in messages[0]["content"]
        assert "A delicious pizza" in messages[1]["content"]
        
        # Verify context was updated
        assert "visual_concept" in pipeline_context.preset_data
        assert "main_subject" in pipeline_context.preset_data["visual_concept"]
        assert pipeline_context.preset_data["visual_concept"]["main_subject"] == "A gourmet pizza"

    @pytest.mark.asyncio
    async def test_skipped_for_input_template(self, setup_stage_globals):
        """Test that StyleAdaptation is skipped for INPUT_TEMPLATE presets."""
        ctx = PipelineContext(
            run_id="test_run",
            prompt="A delicious pizza",
            task_type="1. Product Photography",
            target_platform={"name": "Instagram Post (1:1 Square)"},
            marketing_goals={
                "audience": "Foodies/Bloggers",
                "niche": "Casual Dining",
                "objective": "Create Appetite Appeal",
                "voice": "Mouth-watering & Descriptive",
            },
            image_analysis_result={}
        )
        ctx.preset_type = PresetType.INPUT_TEMPLATE
        
        await style_adaptation.run(ctx)
        
        # Verify clients were not called
        assert not style_adaptation.instructor_client_style_adaptation.chat.completions.create.called
        assert not style_adaptation.base_llm_client_style_adaptation.chat.completions.create.called

    @pytest.mark.asyncio
    async def test_skipped_for_no_new_prompt(self, base_style_recipe, setup_stage_globals):
        """Test that StyleAdaptation is skipped when no new prompt is provided."""
        ctx = PipelineContext(
            run_id="test_run",
            prompt="A delicious burger",  # Same as original
            task_type="1. Product Photography",
            target_platform={"name": "Instagram Post (1:1 Square)"},
            marketing_goals={
                "audience": "Foodies/Bloggers",
                "niche": "Casual Dining",
                "objective": "Create Appetite Appeal",
                "voice": "Mouth-watering & Descriptive",
            },
            image_analysis_result={}
        )
        ctx.preset_type = PresetType.STYLE_RECIPE
        ctx.preset_data = base_style_recipe
        ctx.overrides = {}  # No new prompt override
        
        await style_adaptation.run(ctx)
        
        # Verify clients were not called
        assert not style_adaptation.instructor_client_style_adaptation.chat.completions.create.called
        assert not style_adaptation.base_llm_client_style_adaptation.chat.completions.create.called

    @pytest.mark.asyncio
    async def test_handles_missing_preset_data(self, setup_stage_globals):
        """Test error handling when preset data is missing."""
        ctx = PipelineContext(
            run_id="test_run",
            prompt="A delicious pizza",
            task_type="1. Product Photography",
            target_platform={"name": "Instagram Post (1:1 Square)"},
            marketing_goals={
                "audience": "Foodies/Bloggers",
                "niche": "Casual Dining",
                "objective": "Create Appetite Appeal",
                "voice": "Mouth-watering & Descriptive",
            },
            image_analysis_result={}
        )
        ctx.preset_type = PresetType.STYLE_RECIPE
        ctx.preset_data = None  # Missing preset data
        ctx.overrides = {"prompt": "A delicious pizza"}
        
        await style_adaptation.run(ctx)
        
        # Verify clients were not called
        assert not style_adaptation.instructor_client_style_adaptation.chat.completions.create.called
        assert not style_adaptation.base_llm_client_style_adaptation.chat.completions.create.called

    @pytest.mark.asyncio
    async def test_handles_missing_client(self, pipeline_context):
        """Test error handling when client is not configured."""
        style_adaptation.instructor_client_style_adaptation = None
        style_adaptation.base_llm_client_style_adaptation = None
        
        await style_adaptation.run(pipeline_context)
        
        # Should not raise exception, just log error and continue

    @pytest.mark.asyncio
    async def test_handles_llm_error(self, pipeline_context, setup_stage_globals, mock_client):
        """Test error handling when LLM call fails."""
        # Make the LLM call fail
        mock_client.chat.completions.create.side_effect = Exception("LLM Error")
        
        await style_adaptation.run(pipeline_context)
        
        # Should not raise exception, just log error and continue
        # Original preset data should remain unchanged

    @pytest.mark.asyncio
    async def test_handles_invalid_json_response(self, pipeline_context, setup_stage_globals, mock_client):
        """Test error handling when LLM returns invalid JSON."""
        # Make the LLM return invalid JSON
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "Invalid JSON response"
        mock_client.chat.completions.create.return_value = mock_response
        
        await style_adaptation.run(pipeline_context)
        
        # Should not raise exception, just log error and continue
        # Original preset data should remain unchanged

    @pytest.mark.asyncio
    async def test_handles_invalid_visual_concept_structure(self, pipeline_context, setup_stage_globals, mock_client):
        """Test error handling when LLM returns invalid visual concept structure."""
        # Make the LLM return invalid structure
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps({
            "main_subject": "A pizza",
            # Missing required fields
        })
        mock_client.chat.completions.create.return_value = mock_response
        
        await style_adaptation.run(pipeline_context)
        
        # Should not raise exception, just log error and continue
        # Original preset data should remain unchanged

    @pytest.mark.asyncio
    async def test_user_prompt_precedence(self, pipeline_context, setup_stage_globals, mock_client):
        """Test that new user prompts take precedence over saved recipe data."""
        # Setup mock to return adapted concept
        from churns.models import VisualConceptDetails
        mock_response = VisualConceptDetails(
            main_subject="A delicious pizza",  # Changed from burger to pizza
            composition_and_framing="Close-up shot with shallow depth of field",
            background_environment="Dark wooden table with subtle lighting",
            lighting_and_mood="Warm, appetizing lighting",
            color_palette="Rich browns, golden yellows, deep reds",
            visual_style="Professional food photography",
            suggested_alt_text="Delicious pizza slice"
        )
        mock_client.chat.completions.create.return_value = mock_response
        
        await style_adaptation.run(pipeline_context)
        
        # Verify the subject was adapted but style elements preserved
        visual_concept = pipeline_context.preset_data["visual_concept"]
        assert visual_concept["main_subject"] == "A delicious pizza"
        assert visual_concept["lighting_and_mood"] == "Warm, appetizing lighting"  # Style preserved
        assert visual_concept["color_palette"] == "Rich browns, golden yellows, deep reds"  # Style preserved

    @pytest.mark.asyncio
    async def test_with_image_analysis(self, pipeline_context, setup_stage_globals, mock_client):
        """Test style adaptation with new image analysis data."""
        # Add image analysis to context
        pipeline_context.image_analysis_result = {
            "objects_detected": ["pizza", "cheese", "pepperoni"],
            "style_analysis": "Modern food photography with natural lighting"
        }
        
        await style_adaptation.run(pipeline_context)
        
        # Verify image analysis was included in the prompt
        call_args = mock_client.chat.completions.create.call_args
        user_message = call_args[1]["messages"][1]["content"]
        assert "new_image_analysis" in user_message
        assert "pizza" in user_message

    @pytest.mark.asyncio
    async def test_override_merging(self, pipeline_context, setup_stage_globals, mock_client):
        """Test that additional overrides are merged after adaptation."""
        # Add additional overrides
        pipeline_context.overrides = {
            "prompt": "A delicious pizza",
            "style_prompt": "Rustic photography style"
        }
        
        with patch('churns.stages.style_adaptation.merge_recipe_with_overrides') as mock_merge:
            mock_merge.return_value = pipeline_context.preset_data
            
            await style_adaptation.run(pipeline_context)
            
            # Verify merge was called with overrides
            mock_merge.assert_called_once_with(
                pipeline_context.preset_data,
                pipeline_context.overrides
            )

    def test_token_budget_mitigation(self):
        """Test token budget mitigation function."""
        verbose_concept = {
            "main_subject": "A pizza",
            "composition_and_framing": "Close-up shot",
            "background_environment": "Kitchen counter",
            "lighting_and_mood": "Warm lighting",
            "color_palette": "Warm colors",
            "visual_style": "Food photography",
            "suggested_alt_text": "Delicious pizza",
            "creative_reasoning": "A" * 500,  # Very long reasoning
            "texture_and_details": "B" * 300,  # Long details
            "negative_elements": "C" * 200,  # Long negative elements
        }
        
        pruned_concept = style_adaptation._apply_token_budget_mitigation(verbose_concept)
        
        # Verify creative_reasoning was removed
        assert "creative_reasoning" not in pruned_concept
        
        # Verify texture_and_details was truncated
        assert len(pruned_concept["texture_and_details"]) <= 203  # 200 + "..."
        
        # Verify negative_elements was truncated
        assert len(pruned_concept["negative_elements"]) <= 103  # 100 + "..."

    def test_token_count_estimation(self):
        """Test token count estimation function."""
        text = "This is a test string"
        token_count = style_adaptation._estimate_token_count(text)
        
        # Should be approximately text length / 4
        expected_tokens = len(text) // 4
        assert token_count == expected_tokens

    def test_token_budget_check(self):
        """Test token budget checking function."""
        short_text = "Short text"
        long_text = "A" * 10000  # Very long text
        
        # Short text should be under budget
        assert style_adaptation._check_token_budget(short_text, short_text) is True
        
        # Long text should exceed budget
        assert style_adaptation._check_token_budget(long_text, long_text, limit=2000) is False

    def test_build_system_prompt(self):
        """Test system prompt building."""
        system_prompt = style_adaptation._build_system_prompt()
        
        # Verify key elements are present
        assert "Creative Director" in system_prompt
        assert "base_style_recipe" in system_prompt
        assert "new_user_request" in system_prompt
        assert "visual_concept" in system_prompt
        assert "JSON" in system_prompt

    def test_build_user_prompt(self):
        """Test user prompt building."""
        original_concept = {
            "main_subject": "A burger",
            "lighting_and_mood": "Warm lighting"
        }
        
        new_request = "A delicious pizza"
        
        # Test without image analysis
        user_prompt = style_adaptation._build_user_prompt(original_concept, new_request)
        
        assert "base_style_recipe" in user_prompt
        assert "new_user_request" in user_prompt
        assert "A delicious pizza" in user_prompt
        assert "burger" in user_prompt
        
        # Test with image analysis
        image_analysis = {"objects": ["pizza", "cheese"]}
        user_prompt_with_image = style_adaptation._build_user_prompt(
            original_concept, new_request, image_analysis
        )
        
        assert "new_image_analysis" in user_prompt_with_image
        assert "pizza" in user_prompt_with_image

if __name__ == "__main__":
    pytest.main([__file__]) 