"""
Test suite for the Creative Expert stage.

Tests visual concept generation with various inputs, creativity levels,
client injection, error handling, and style guidance integration.
"""

import pytest
import json
from unittest.mock import Mock, MagicMock
from churns.stages.creative_expert import run
from churns.pipeline.context import PipelineContext
from churns.models import ImageGenerationPrompt, VisualConceptDetails, StyleGuidance


class TestCreativeExpertStage:
    """Test the creative expert stage functionality."""

    def create_test_context(self, strategies=None, style_guidance=None, creativity_level=2, task_type="1. Product Photography"):
        """Create a test context with sample strategies and style guidance."""
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
                }
            ]
        
        if style_guidance is None:
            style_guidance = [
                {
                    "style_keywords": ["modern", "minimalist", "clean"],
                    "style_description": "A clean, modern aesthetic with minimalist composition and natural lighting that emphasizes product clarity.",
                    "marketing_impact": "The minimalist style creates a premium feel that appeals to young professionals and enhances shareability on Instagram.",
                    "source_strategy_index": 0
                },
                {
                    "style_keywords": ["elegant", "sophisticated", "dramatic"],
                    "style_description": "An elegant, sophisticated visual style with dramatic lighting and rich textures that conveys luxury and refinement.",
                    "marketing_impact": "The sophisticated style builds brand prestige and appeals to foodie bloggers seeking high-quality content.",
                    "source_strategy_index": 1
                }
            ]
        
        ctx = PipelineContext()
        ctx.mode = "easy_mode"
        ctx.task_type = task_type
        ctx.creativity_level = creativity_level
        ctx.prompt = "A delicious gourmet burger"
        ctx.target_platform = {
            "name": "Instagram Post (1:1 Square)",
            "resolution_details": {
                "width": 1080,
                "height": 1080,
                "aspect_ratio": "1:1"
            }
        }
        ctx.render_text = False
        ctx.apply_branding = False
        ctx.suggested_marketing_strategies = strategies
        ctx.style_guidance_sets = style_guidance
        
        return ctx

    def create_mock_client(self, response_type="success"):
        """Create a mock LLM client with different response types."""
        mock_client = Mock()
        mock_completion = Mock()
        
        if response_type == "success":
            # Mock successful response
            sample_visual_concept = {
                "main_subject": "A gourmet burger with artisanal bun, fresh lettuce, tomato, and premium beef patty",
                "composition_and_framing": "Close-up shot with shallow depth of field, centered composition",
                "background_environment": "Clean white marble surface with soft natural lighting",
                "foreground_elements": None,
                "lighting_and_mood": "Soft, natural daylight from the side creating gentle shadows",
                "color_palette": "Warm browns and greens with clean white background",
                "visual_style": "Modern minimalist food photography with clean lines and natural textures",
                "promotional_text_visuals": None,
                "branding_visuals": None,
                "texture_and_details": "Visible sesame seeds on bun, glistening lettuce, juicy beef texture",
                "negative_elements": "Avoid cluttered backgrounds, harsh lighting, or oversaturated colors",
                "creative_reasoning": "The minimalist style aligns with the young professional audience's preference for clean aesthetics while the natural lighting enhances the burger's appeal."
            }
            
            mock_response = {
                "visual_concept": sample_visual_concept,
                "source_strategy_index": 0
            }
            
            mock_completion.model_dump.return_value = mock_response
            mock_completion.choices = [Mock()]
            mock_completion.choices[0].message.content = json.dumps(mock_response)
            
        elif response_type == "json_in_markdown":
            # Mock response with JSON in markdown blocks
            sample_response = {
                "visual_concept": {
                    "main_subject": "Elegant fine dining dish with artistic plating",
                    "composition_and_framing": "Overhead shot with dramatic angles",
                    "background_environment": "Dark wooden table with ambient lighting",
                    "foreground_elements": "Elegant silverware and wine glass",
                    "lighting_and_mood": "Warm, dramatic lighting with soft shadows",
                    "color_palette": "Rich browns, golds, and deep reds",
                    "visual_style": "Sophisticated food photography with dramatic lighting and elegant styling",
                    "promotional_text_visuals": None,
                    "branding_visuals": None,
                    "texture_and_details": "Smooth sauces, crispy garnishes, polished surfaces",
                    "negative_elements": "Avoid casual presentation or bright lighting",
                    "creative_reasoning": "The sophisticated style conveys luxury dining experience that appeals to foodie bloggers."
                }
            }
            mock_completion.choices = [Mock()]
            mock_completion.choices[0].message.content = f"```json\n{json.dumps(sample_response)}\n```"
            
        elif response_type == "invalid_json":
            # Mock response with invalid JSON
            mock_completion.choices = [Mock()]
            mock_completion.choices[0].message.content = "This is not valid JSON response from the model"
            
        elif response_type == "api_error":
            # Mock API error
            from openai import APIConnectionError
            mock_client.chat.completions.create.side_effect = APIConnectionError("Connection failed")
            return mock_client
        
        # Add usage information
        mock_usage = Mock()
        mock_usage.model_dump.return_value = {
            "prompt_tokens": 1500,
            "completion_tokens": 800,
            "total_tokens": 2300
        }
        mock_completion._raw_response = Mock()
        mock_completion._raw_response.usage = mock_usage
        
        mock_client.chat.completions.create.return_value = mock_completion
        return mock_client

    def test_creative_expert_basic_functionality(self):
        """Test basic creative expert functionality with successful client response."""
        ctx = self.create_test_context()
        ctx.creative_expert_client = self.create_mock_client("success")
        
        # Run the stage
        run(ctx)
        
        # Verify the stage completed successfully
        assert ctx.generated_image_prompts is not None
        assert len(ctx.generated_image_prompts) == 2
        
        # Verify structure of first visual concept
        first_concept = ctx.generated_image_prompts[0]
        assert "visual_concept" in first_concept
        assert "source_strategy_index" in first_concept
        
        visual_concept = first_concept["visual_concept"]
        assert "main_subject" in visual_concept
        assert "composition_and_framing" in visual_concept
        assert "background_environment" in visual_concept
        assert "lighting_and_mood" in visual_concept
        assert "color_palette" in visual_concept
        assert "visual_style" in visual_concept
        assert "creative_reasoning" in visual_concept
        
        # Verify content
        assert "gourmet burger" in visual_concept["main_subject"]
        assert "minimalist" in visual_concept["visual_style"]
        assert first_concept["source_strategy_index"] == 0

    def test_json_parsing_from_markdown(self):
        """Test parsing JSON from markdown code blocks."""
        ctx = self.create_test_context()
        ctx.creative_expert_client = self.create_mock_client("json_in_markdown")
        
        # Run the stage
        run(ctx)
        
        # Verify successful parsing
        assert ctx.generated_image_prompts is not None
        assert len(ctx.generated_image_prompts) == 2
        
        # Check content from markdown-wrapped response
        first_concept = ctx.generated_image_prompts[0]
        visual_concept = first_concept["visual_concept"]
        assert "fine dining dish" in visual_concept["main_subject"]
        assert "Sophisticated" in visual_concept["visual_style"]  # Capital S to match the mock response

    def test_creativity_levels(self):
        """Test different creativity levels affect generation."""
        # Test creativity level 1 (photorealistic)
        ctx_level1 = self.create_test_context(creativity_level=1)
        ctx_level1.creative_expert_client = self.create_mock_client("success")
        
        run(ctx_level1)
        
        assert ctx_level1.generated_image_prompts is not None
        assert len(ctx_level1.generated_image_prompts) == 2
        
        # Test creativity level 3 (abstract)
        ctx_level3 = self.create_test_context(creativity_level=3)
        ctx_level3.creative_expert_client = self.create_mock_client("success")
        
        run(ctx_level3)
        
        assert ctx_level3.generated_image_prompts is not None
        assert len(ctx_level3.generated_image_prompts) == 2

    def test_text_and_branding_flags(self):
        """Test that text and branding flags are handled correctly."""
        ctx = self.create_test_context()
        ctx.render_text = True
        ctx.apply_branding = True
        ctx.task_description = "Special promotion: 50% off burgers"
        ctx.branding_elements = "Logo in top-right corner, use brand colors #FF6B35"
        ctx.creative_expert_client = self.create_mock_client("success")
        
        # Run the stage
        run(ctx)
        
        # Verify the stage completed successfully
        assert ctx.generated_image_prompts is not None
        assert len(ctx.generated_image_prompts) == 2

    def test_image_reference_handling(self):
        """Test handling of image references."""
        ctx = self.create_test_context()
        ctx.image_reference = {
            "filename": "burger_ref.jpg",
            "instruction": "Make the lighting more dramatic"
        }
        ctx.image_analysis_result = {
            "main_subject": "Gourmet Burger"
        }
        ctx.creative_expert_client = self.create_mock_client("success")
        
        run(ctx)
        
        assert ctx.generated_image_prompts is not None
        assert len(ctx.generated_image_prompts) == 2

    def test_default_edit_scenario(self):
        """Test default edit scenario (image reference without instruction)."""
        ctx = self.create_test_context()
        ctx.image_reference = {
            "filename": "burger_ref.jpg"
            # No instruction provided
        }
        ctx.image_analysis_result = {
            "main_subject": "Gourmet Burger"
        }
        ctx.creative_expert_client = self.create_mock_client("success")
        
        run(ctx)
        
        assert ctx.generated_image_prompts is not None
        assert len(ctx.generated_image_prompts) == 2

    def test_different_task_types(self):
        """Test different task types generate appropriate concepts."""
        task_types = [
            "1. Product Photography",
            "2. Promotional Graphics & Announcements", 
            "3. Store Atmosphere & Decor",
            "4. Menu Spotlights"
        ]
        
        for task_type in task_types:
            ctx = self.create_test_context(task_type=task_type)
            ctx.creative_expert_client = self.create_mock_client("success")
            
            run(ctx)
            
            assert ctx.generated_image_prompts is not None
            assert len(ctx.generated_image_prompts) == 2

    def test_missing_client(self):
        """Test behavior when client is not available."""
        ctx = self.create_test_context()
        # Don't set creative_expert_client
        
        run(ctx)
        
        # Should handle gracefully
        assert ctx.generated_image_prompts is None

    def test_missing_models(self):
        """Test behavior when Pydantic models are not available."""
        ctx = self.create_test_context()
        ctx.creative_expert_client = self.create_mock_client("success")
        
        # This would happen if imports failed
        # We can't easily mock this without modifying the module
        run(ctx)
        
        # Should still work with current imports
        assert ctx.generated_image_prompts is not None

    def test_missing_strategies(self):
        """Test behavior when no strategies are provided."""
        ctx = self.create_test_context(strategies=[])
        ctx.creative_expert_client = self.create_mock_client("success")
        
        run(ctx)
        
        assert ctx.generated_image_prompts == []

    def test_missing_style_guidance(self):
        """Test behavior when no style guidance is provided."""
        ctx = self.create_test_context(style_guidance=[])
        ctx.creative_expert_client = self.create_mock_client("success")
        
        run(ctx)
        
        assert ctx.generated_image_prompts is None

    def test_strategy_style_mismatch(self):
        """Test behavior when strategies and style guidance counts don't match."""
        strategies = [
            {
                "target_audience": "Young Professionals",
                "target_niche": "Cafe",
                "target_objective": "Drive Traffic",
                "target_voice": "Casual"
            }
        ]
        style_guidance = [
            {
                "style_keywords": ["modern"],
                "style_description": "Modern style",
                "marketing_impact": "Appeals to young audience",
                "source_strategy_index": 0
            },
            {
                "style_keywords": ["elegant"],
                "style_description": "Elegant style", 
                "marketing_impact": "Creates premium feel",
                "source_strategy_index": 1
            }
        ]
        
        ctx = self.create_test_context(strategies=strategies, style_guidance=style_guidance)
        ctx.creative_expert_client = self.create_mock_client("success")
        
        run(ctx)
        
        # Should detect mismatch and fail gracefully
        assert ctx.generated_image_prompts is None

    def test_invalid_json_response(self):
        """Test handling of invalid JSON responses."""
        ctx = self.create_test_context()
        ctx.creative_expert_client = self.create_mock_client("invalid_json")
        
        run(ctx)
        
        # Should handle JSON parsing errors gracefully
        # When all concepts fail, result should be None (not an empty list)
        assert ctx.generated_image_prompts is None

    def test_api_error_handling(self):
        """Test handling of API errors.""" 
        ctx = self.create_test_context()
        
        # Create a mock client that raises API error
        mock_client = Mock()
        mock_client.chat.completions.create.side_effect = Exception("API connection failed")
        ctx.creative_expert_client = mock_client
        
        run(ctx)
        
        # Should handle API errors gracefully
        # When all concepts fail due to API errors, result should be None
        assert ctx.generated_image_prompts is None

    def test_style_guidance_integration(self):
        """Test that style guidance is properly integrated into prompts."""
        style_guidance = [
            {
                "style_keywords": ["vintage", "rustic", "warm"],
                "style_description": "A vintage, rustic aesthetic with warm tones and textured surfaces that evokes nostalgia and comfort.",
                "marketing_impact": "The vintage style creates emotional connection and appeals to customers seeking authentic experiences.",
                "source_strategy_index": 0
            }
        ]
        
        # Create a temporary context to get a strategy, then create the real context
        temp_ctx = self.create_test_context()
        single_strategy = temp_ctx.suggested_marketing_strategies[0]
        
        ctx = self.create_test_context(
            strategies=[single_strategy],
            style_guidance=style_guidance
        )
        ctx.creative_expert_client = self.create_mock_client("success")
        
        run(ctx)
        
        assert ctx.generated_image_prompts is not None
        assert len(ctx.generated_image_prompts) == 1

    def test_usage_tracking(self):
        """Test that usage information is tracked correctly."""
        ctx = self.create_test_context()
        ctx.creative_expert_client = self.create_mock_client("success")
        
        run(ctx)
        
        # Check that usage information was stored
        assert hasattr(ctx, 'llm_usage')
        assert "creative_expert_strategy_0" in ctx.llm_usage
        assert "creative_expert_strategy_1" in ctx.llm_usage
        
        usage_0 = ctx.llm_usage["creative_expert_strategy_0"]
        assert "prompt_tokens" in usage_0
        assert "completion_tokens" in usage_0
        assert "total_tokens" in usage_0

    def test_platform_optimization(self):
        """Test platform-specific optimization."""
        platforms = [
            {
                "name": "Instagram Post (1:1 Square)",
                "resolution_details": {"aspect_ratio": "1:1"}
            },
            {
                "name": "Pinterest Pin (2:3 Vertical)", 
                "resolution_details": {"aspect_ratio": "2:3"}
            },
            {
                "name": "Instagram Story/Reel (9:16 Vertical)",
                "resolution_details": {"aspect_ratio": "9:16"}
            }
        ]
        
        for platform in platforms:
            ctx = self.create_test_context()
            ctx.target_platform = platform
            ctx.creative_expert_client = self.create_mock_client("success")
            
            run(ctx)
            
            assert ctx.generated_image_prompts is not None
            assert len(ctx.generated_image_prompts) == 2 

    def test_visual_concept_structure_validation(self):
        """Test that visual concept structure exactly matches original VisualConceptDetails model."""
        ctx = self.create_test_context()
        ctx.creative_expert_client = self.create_mock_client("success")
        
        # Run the stage
        run(ctx)
        
        # Verify complete structure matches original VisualConceptDetails
        assert ctx.generated_image_prompts is not None
        assert len(ctx.generated_image_prompts) == 2
        
        for i, prompt_data in enumerate(ctx.generated_image_prompts):
            # Test ImageGenerationPrompt structure
            assert "visual_concept" in prompt_data
            assert "source_strategy_index" in prompt_data
            assert prompt_data["source_strategy_index"] == i
            
            vc = prompt_data["visual_concept"]
            
            # Test required fields (from original VisualConceptDetails)
            required_fields = [
                "composition_and_framing",
                "background_environment", 
                "lighting_and_mood",
                "color_palette",
                "visual_style"
            ]
            for field in required_fields:
                assert field in vc, f"Required field '{field}' missing from visual_concept"
                assert vc[field] is not None, f"Required field '{field}' should not be None"
                assert isinstance(vc[field], str), f"Field '{field}' should be string"
                assert len(vc[field]) > 0, f"Field '{field}' should not be empty"
            
            # Test optional fields (may be None based on flags/conditions)
            optional_fields = [
                "main_subject",  # Can be None in default edit scenarios
                "foreground_elements",
                "promotional_text_visuals",  # Should be None when render_text=False
                "branding_visuals",  # Should be None when apply_branding=False
                "texture_and_details",
                "negative_elements",
                "creative_reasoning"
            ]
            for field in optional_fields:
                if field in vc:  # Field may be present or omitted
                    # If present, should be string or None
                    assert vc[field] is None or isinstance(vc[field], str), f"Optional field '{field}' should be string or None"
            
            # Test specific flag-based field logic (matches original)
            # Since render_text=False and apply_branding=False in default test
            if "promotional_text_visuals" in vc:
                assert vc["promotional_text_visuals"] is None, "promotional_text_visuals should be None when render_text=False"
            if "branding_visuals" in vc:
                assert vc["branding_visuals"] is None, "branding_visuals should be None when apply_branding=False" 