"""
Tests for task type caption optimization feature.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from churns.stages.caption import (
    _get_task_type_guidance,
    _extract_style_context,
    _get_analyst_user_prompt,
    TASK_TYPE_CAPTION_GUIDANCE
)
from churns.pipeline.context import PipelineContext
from churns.models import CaptionSettings


class TestTaskTypeCaptionOptimization:
    """Test task type caption optimization functionality."""
    
    def test_get_task_type_guidance_valid(self):
        """Test retrieving guidance for valid task type."""
        guidance = _get_task_type_guidance("1. Product Photography")
        
        assert guidance is not None
        assert "captionObjective" in guidance
        assert "toneHints" in guidance
        assert "hookTemplate" in guidance
        assert "structuralHints" in guidance
        assert guidance["captionObjective"] == "Showcase product features & craftsmanship to spark desire and perceived quality."
    
    def test_get_task_type_guidance_invalid(self):
        """Test retrieving guidance for invalid task type."""
        guidance = _get_task_type_guidance("Invalid Task Type")
        assert guidance is None
    
    def test_extract_style_context_with_data(self):
        """Test extracting style context when data is available."""
        ctx = PipelineContext()
        ctx.style_guidance_sets = [
            {"style_keywords": ["modern", "minimalist", "clean"]}
        ]
        ctx.generated_image_prompts = [
            {
                "visual_concept": {
                    "creative_reasoning": "This design emphasizes clean lines and modern aesthetics."
                }
            }
        ]
        ctx.suggested_marketing_strategies = [
            {"target_niche": "Premium Coffee"}
        ]
        
        style_context = _extract_style_context(ctx, 0)
        
        assert style_context["style_keywords"] == ["modern", "minimalist", "clean"]
        assert style_context["creative_reasoning"] == "This design emphasizes clean lines and modern aesthetics."
        assert style_context["target_niche"] == "Premium Coffee"
    
    def test_extract_style_context_empty(self):
        """Test extracting style context when no data is available."""
        ctx = PipelineContext()
        
        style_context = _extract_style_context(ctx, 0)
        
        assert style_context["style_keywords"] == []
        assert style_context["creative_reasoning"] is None
        assert style_context["target_niche"] is None
    
    def test_analyst_prompt_includes_task_type_context(self):
        """Test that analyst prompt includes task type context when available."""
        ctx = PipelineContext()
        ctx.task_type = "6. Recipes & Food Tips"
        ctx.enable_task_type_caption_optimization = True
        ctx.image_analysis_result = {"main_subject": "Soy milk bottle"}
        
        settings = CaptionSettings()
        strategy = {
            "target_audience": "Health-conscious millennials",
            "target_objective": "Educate about plant-based nutrition",
            "target_voice": "Friendly and informative"
        }
        visual_concept = {
            "main_subject": "Soy milk bottle",
            "lighting_and_mood": "Natural morning light",
            "suggested_alt_text": "Bottle of organic soy milk"
        }
        
        prompt = _get_analyst_user_prompt(
            ctx, settings, "Instagram", strategy, visual_concept, "Bottle of organic soy milk", 0
        )
        
        assert "**Task Type Context:**" in prompt
        assert "Recipes & Food Tips" in prompt
        assert "Educate followers with practical recipes" in prompt
        assert "educational, encouraging, practical" in prompt
        assert "Save this recipe:" in prompt
    
    def test_analyst_prompt_excludes_task_type_when_disabled(self):
        """Test that analyst prompt excludes task type context when disabled."""
        ctx = PipelineContext()
        ctx.task_type = "6. Recipes & Food Tips"
        ctx.enable_task_type_caption_optimization = False
        ctx.image_analysis_result = {"main_subject": "Soy milk bottle"}
        
        settings = CaptionSettings()
        strategy = {
            "target_audience": "Health-conscious millennials",
            "target_objective": "Educate about plant-based nutrition"
        }
        visual_concept = {
            "main_subject": "Soy milk bottle",
            "suggested_alt_text": "Bottle of organic soy milk"
        }
        
        prompt = _get_analyst_user_prompt(
            ctx, settings, "Instagram", strategy, visual_concept, "Bottle of organic soy milk", 0
        )
        
        assert "**Task Type Context:**" not in prompt
        assert "Recipes & Food Tips" not in prompt
    
    def test_analyst_prompt_includes_style_context(self):
        """Test that analyst prompt includes style context when available."""
        ctx = PipelineContext()
        ctx.style_guidance_sets = [
            {"style_keywords": ["wabi-sabi", "minimalist", "organic"]}
        ]
        ctx.generated_image_prompts = [
            {
                "visual_concept": {
                    "creative_reasoning": "Emphasizes natural textures and imperfect beauty"
                }
            }
        ]
        ctx.image_analysis_result = {"main_subject": "Soy milk bottle"}
        
        settings = CaptionSettings()
        strategy = {
            "target_audience": "Health-conscious millennials",
            "target_objective": "Educate about plant-based nutrition"
        }
        visual_concept = {
            "main_subject": "Soy milk bottle",
            "suggested_alt_text": "Bottle of organic soy milk"
        }
        
        prompt = _get_analyst_user_prompt(
            ctx, settings, "Instagram", strategy, visual_concept, "Bottle of organic soy milk", 0
        )
        
        assert "**Style Context:**" in prompt
        assert "wabi-sabi, minimalist, organic" in prompt
        assert "natural textures and imperfect beauty" in prompt
    
    def test_all_task_types_have_required_fields(self):
        """Test that all task types in guidance have required fields."""
        required_fields = ["captionObjective", "toneHints", "hookTemplate", "structuralHints"]
        
        for task_type, guidance in TASK_TYPE_CAPTION_GUIDANCE.items():
            for field in required_fields:
                assert field in guidance, f"Task type '{task_type}' missing field '{field}'"
                assert guidance[field], f"Task type '{task_type}' has empty field '{field}'"
            
            # Verify toneHints is a list
            assert isinstance(guidance["toneHints"], list), f"Task type '{task_type}' toneHints should be a list"
            assert len(guidance["toneHints"]) > 0, f"Task type '{task_type}' should have at least one tone hint"


if __name__ == "__main__":
    pytest.main([__file__]) 