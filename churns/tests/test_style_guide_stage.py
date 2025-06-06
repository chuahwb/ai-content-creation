"""
Test suite for the Style Guide stage.

Tests style guidance generation with various inputs, creativity levels,
client injection, error handling, and parsing functionality.
"""

import pytest
import json
from unittest.mock import Mock, MagicMock
from churns.stages.style_guide import run
from churns.pipeline.context import PipelineContext
from churns.models import StyleGuidance, StyleGuidanceList


class TestStyleGuideStage:
    """Test the style guide stage functionality."""

    def create_test_context(self, strategies=None, creativity_level=2, task_type="1. Product Photography"):
        """Create a test context with sample strategies."""
        if strategies is None:
            strategies = [
                {
                    "target_audience": "Young Professionals (25-35)",
                    "target_niche": "Cafe/Coffee Shop",
                    "target_objective": "Drive Foot Traffic",
                    "target_voice": "Friendly & Casual"
                },
                {
                    "target_audience": "Foodies/Bloggers",
                    "target_niche": "Fine Dining",
                    "target_objective": "Increase Brand Awareness",
                    "target_voice": "Sophisticated & Elegant"
                },
                {
                    "target_audience": "Families with Children",
                    "target_niche": "Family Restaurant",
                    "target_objective": "Drive Short-Term Sales",
                    "target_voice": "Warm & Welcoming"
                }
            ]
        
        ctx = PipelineContext()
        ctx.creativity_level = creativity_level
        ctx.task_type = task_type
        ctx.prompt = "Create social media content for our restaurant"
        
        # Set context properties directly
        ctx.suggested_marketing_strategies = strategies
        ctx.image_analysis_result = {"main_subject": "Coffee Cup"}
        
        return ctx

    def create_mock_client(self, response_data, usage_info=None):
        """Create a mock LLM client that returns test data."""
        if usage_info is None:
            usage_info = {
                "prompt_tokens": 150,
                "completion_tokens": 300,
                "total_tokens": 450
            }
        
        # Create mock response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = json.dumps(response_data)
        
        # Add usage info
        mock_response._raw_response = Mock()
        mock_response._raw_response.usage = Mock()
        mock_response._raw_response.usage.model_dump.return_value = usage_info
        
        # Create mock client
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        
        return mock_client

    def test_successful_style_guidance_generation(self):
        """Test successful style guidance generation with mock client."""
        ctx = self.create_test_context()
        
        # Create mock response data
        response_data = {
            "style_guidance_sets": [
                {
                    "style_keywords": ["modern", "minimalist", "clean"],
                    "style_description": "A clean, modern aesthetic with bright lighting and minimal props. Focus on crisp lines and negative space to emphasize the coffee's quality.",
                    "marketing_impact": "Clean aesthetics resonate with professionals seeking quality, enhancing Instagram engagement.",
                    "source_strategy_index": 0
                },
                {
                    "style_keywords": ["cinematic", "dramatic", "moody"],
                    "style_description": "Dramatic lighting with rich shadows and warm tones. Employ shallow depth of field to create an intimate, upscale dining atmosphere.",
                    "marketing_impact": "Cinematic quality appeals to food bloggers and creates shareable, memorable content for social media.",
                    "source_strategy_index": 1
                },
                {
                    "style_keywords": ["bright", "colorful", "welcoming"],
                    "style_description": "Bright, cheerful lighting with vibrant colors and family-friendly compositions. Use warm tones and inclusive imagery to create an inviting atmosphere.",
                    "marketing_impact": "Bright, welcoming visuals attract families and convey a friendly, approachable brand personality.",
                    "source_strategy_index": 2
                }
            ]
        }
        
        mock_client = self.create_mock_client(response_data)
        ctx.style_guide_client = mock_client
        
        # Run the stage
        run(ctx)
        
        # Verify the stage completed successfully
        assert ctx.style_guidance_sets is not None
        style_guidance = ctx.style_guidance_sets
        assert len(style_guidance) == 3
        
        # Verify structure of first style guidance
        first_style = style_guidance[0]
        assert "style_keywords" in first_style
        assert "style_description" in first_style
        assert "marketing_impact" in first_style
        assert "source_strategy_index" in first_style
        
        # Verify content
        assert first_style["style_keywords"] == ["modern", "minimalist", "clean"]
        assert "clean, modern aesthetic" in first_style["style_description"]
        assert first_style["source_strategy_index"] == 0
        
        # Verify usage tracking
        assert "style_guider" in ctx.llm_usage
        usage = ctx.llm_usage["style_guider"]
        assert usage["total_tokens"] == 450

    def test_different_creativity_levels(self):
        """Test style guidance generation with different creativity levels."""
        for creativity_level in [1, 2, 3]:
            ctx = self.create_test_context(creativity_level=creativity_level)
            
            response_data = {
                "style_guidance_sets": [
                    {
                        "style_keywords": ["photorealistic", "studio", "professional"] if creativity_level == 1 
                                        else ["impressionistic", "stylized", "cinematic"] if creativity_level == 2
                                        else ["abstract", "surreal", "artistic"],
                        "style_description": f"Style description for creativity level {creativity_level}",
                        "marketing_impact": f"Marketing impact for level {creativity_level}",
                        "source_strategy_index": 0
                    }
                ]
            }
            
            mock_client = self.create_mock_client(response_data)
            ctx.style_guide_client = mock_client
            
            run(ctx)
            
            # Verify the call was made with correct creativity level
            mock_client.chat.completions.create.assert_called_once()
            call_args = mock_client.chat.completions.create.call_args
            system_prompt = call_args[1]["messages"][0]["content"]
            
            if creativity_level == 1:
                assert "Focused & Photorealistic" in system_prompt
                assert "photorealistic, or minimally stylized" in system_prompt
            elif creativity_level == 2:
                assert "Impressionistic & Stylized" in system_prompt
                assert "impressionistic or cinematic qualities" in system_prompt
            elif creativity_level == 3:
                assert "Abstract & Illustrative" in system_prompt
                assert "abstract, or illustrative styles" in system_prompt

    def test_different_task_types(self):
        """Test style guidance generation with different task types."""
        task_types = [
            "1. Product Photography",
            "2. Promotional Graphics & Announcements", 
            "3. Store Atmosphere & Decor",
            "6. Recipes & Food Tips"
        ]
        
        for task_type in task_types:
            ctx = self.create_test_context(task_type=task_type)
            
            response_data = {
                "style_guidance_sets": [
                    {
                        "style_keywords": ["task-specific", "style", "keywords"],
                        "style_description": f"Style description for {task_type}",
                        "marketing_impact": f"Marketing impact for {task_type}",
                        "source_strategy_index": 0
                    }
                ]
            }
            
            mock_client = self.create_mock_client(response_data)
            ctx.style_guide_client = mock_client
            
            run(ctx)
            
            # Verify the call included correct task type
            mock_client.chat.completions.create.assert_called_once()
            call_args = mock_client.chat.completions.create.call_args
            system_prompt = call_args[1]["messages"][0]["content"]
            user_prompt = call_args[1]["messages"][1]["content"]
            
            assert task_type in system_prompt
            assert task_type in user_prompt

    def test_json_extraction_from_markdown(self):
        """Test JSON extraction from markdown-formatted LLM responses."""
        ctx = self.create_test_context()
        
        # Test markdown-wrapped JSON
        markdown_response = """
```json
{
    "style_guidance_sets": [
        {
            "style_keywords": ["extracted", "from", "markdown"],
            "style_description": "Successfully extracted from markdown code block.",
            "marketing_impact": "Tests JSON extraction capability.",
            "source_strategy_index": 0
        }
    ]
}
```
        """
        
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = markdown_response
        mock_response._raw_response = Mock()
        mock_response._raw_response.usage = Mock()
        mock_response._raw_response.usage.model_dump.return_value = {"total_tokens": 100}
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        ctx.style_guide_client = mock_client
        
        run(ctx)
        
        # Verify extraction worked
        style_guidance = ctx.style_guidance_sets
        assert len(style_guidance) == 1
        assert style_guidance[0]["style_keywords"] == ["extracted", "from", "markdown"]

    def test_json_extraction_with_extra_text(self):
        """Test JSON extraction when LLM includes extra text."""
        ctx = self.create_test_context()
        
        # Response with extra text
        response_with_extra = """
Here are the style guidance sets for your marketing strategies:

{
    "style_guidance_sets": [
        {
            "style_keywords": ["clean", "professional"],
            "style_description": "Clean professional style extracted despite extra text.",
            "marketing_impact": "Professional appeal for target audience.",
            "source_strategy_index": 0
        }
    ]
}

I hope this helps with your marketing campaign!
        """
        
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = response_with_extra
        mock_response._raw_response = Mock()
        mock_response._raw_response.usage = Mock()
        mock_response._raw_response.usage.model_dump.return_value = {"total_tokens": 150}
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        ctx.style_guide_client = mock_client
        
        run(ctx)
        
        # Verify extraction worked despite extra text
        style_guidance = ctx.style_guidance_sets
        assert len(style_guidance) == 1
        assert style_guidance[0]["style_keywords"] == ["clean", "professional"]

    def test_no_strategies_provided(self):
        """Test behavior when no marketing strategies are provided."""
        ctx = self.create_test_context(strategies=[])
        mock_client = Mock()
        ctx.style_guide_client = mock_client
        
        run(ctx)
        
        # Should return empty list, not call LLM
        assert ctx.style_guidance_sets == []
        mock_client.chat.completions.create.assert_not_called()

    def test_no_client_provided(self):
        """Test behavior when no LLM client is provided."""
        ctx = self.create_test_context()
        # Don't set style_guide_client
        
        run(ctx)
        
        # Should set style_guidance_sets to None
        assert ctx.style_guidance_sets is None

    def test_llm_api_error_handling(self):
        """Test handling of LLM API errors."""
        ctx = self.create_test_context()
        
        # Mock client that raises an exception
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        ctx.style_guide_client = mock_client
        
        run(ctx)
        
        # Should handle error gracefully
        assert ctx.style_guidance_sets is None

    def test_invalid_json_response(self):
        """Test handling of invalid JSON responses."""
        ctx = self.create_test_context()
        
        # Mock response with invalid JSON
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message.content = "This is not valid JSON at all!"
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        ctx.style_guide_client = mock_client
        
        run(ctx)
        
        # Should handle invalid JSON gracefully
        assert ctx.style_guidance_sets is None

    def test_image_analysis_integration(self):
        """Test integration with image analysis results."""
        ctx = self.create_test_context()
        ctx.image_analysis_result = {
            "main_subject": "Gourmet Burger"
        }
        
        response_data = {
            "style_guidance_sets": [
                {
                    "style_keywords": ["burger", "gourmet", "appetizing"],
                    "style_description": "Style that complements the gourmet burger subject.",
                    "marketing_impact": "Burger-focused styling for food photography.",
                    "source_strategy_index": 0
                }
            ]
        }
        
        mock_client = self.create_mock_client(response_data)
        ctx.style_guide_client = mock_client
        
        run(ctx)
        
        # Verify image subject was included in prompt
        call_args = mock_client.chat.completions.create.call_args
        user_prompt = call_args[1]["messages"][1]["content"]
        assert "Gourmet Burger" in user_prompt

    def test_instructor_parsing_compatibility(self):
        """Test compatibility with instructor-based parsing."""
        ctx = self.create_test_context()
        
        # Create mock instructor response (different structure)
        mock_style_guidance = Mock()
        mock_style_guidance.style_keywords = ["instructor", "parsed"]
        mock_style_guidance.style_description = "Parsed via instructor"
        mock_style_guidance.marketing_impact = "Instructor parsing test"
        mock_style_guidance.source_strategy_index = 0
        mock_style_guidance.model_dump.return_value = {
            "style_keywords": ["instructor", "parsed"],
            "style_description": "Parsed via instructor", 
            "marketing_impact": "Instructor parsing test",
            "source_strategy_index": 0
        }
        
        mock_response = Mock()
        mock_response.style_guidance_sets = [mock_style_guidance]
        mock_response._raw_response = Mock()
        mock_response._raw_response.usage = Mock()
        mock_response._raw_response.usage.model_dump.return_value = {"total_tokens": 200}
        
        mock_client = Mock()
        mock_client.chat.completions.create.return_value = mock_response
        ctx.style_guide_client = mock_client
        
        # Temporarily patch the problem models list to enable instructor parsing
        from churns.stages.style_guide import INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS
        original_problem_models = INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS.copy()
        INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS.clear()
        
        try:
            run(ctx)
            
            # Verify results structure
            style_guidance = ctx.style_guidance_sets
            assert len(style_guidance) == 1
        finally:
            # Restore original problem models
            INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS.clear()
            INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS.extend(original_problem_models)

    def test_logging_functionality(self):
        """Test that appropriate log messages are generated."""
        ctx = self.create_test_context()
        
        response_data = {
            "style_guidance_sets": [
                {
                    "style_keywords": ["test"],
                    "style_description": "Test description",
                    "marketing_impact": "Test impact",
                    "source_strategy_index": 0
                }
            ]
        }
        
        mock_client = self.create_mock_client(response_data)
        ctx.style_guide_client = mock_client
        
        initial_log_count = len(ctx.logs)
        run(ctx)
        
        # Verify logs were added
        assert len(ctx.logs) > initial_log_count
        
        # Check for specific log messages
        log_messages = " ".join(ctx.logs)
        assert "Starting Style Guide stage" in log_messages
        assert "Successfully generated" in log_messages
        assert "Style Guide stage completed successfully" in log_messages 