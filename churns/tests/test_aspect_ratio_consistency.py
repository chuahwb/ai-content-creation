"""
Test aspect ratio consistency in creative expert stage.
"""

import pytest
from churns.stages.creative_expert import (
    _map_to_supported_aspect_ratio_for_prompt,
    _clean_platform_name,
    _get_creative_expert_user_prompt
)


class TestAspectRatioConsistency:
    """Test that aspect ratios are handled consistently in creative expert."""
    
    def test_aspect_ratio_mapping(self):
        """Test the basic aspect ratio mapping function."""
        assert _map_to_supported_aspect_ratio_for_prompt("1:1") == "1:1"
        assert _map_to_supported_aspect_ratio_for_prompt("9:16") == "2:3"
        assert _map_to_supported_aspect_ratio_for_prompt("3:4") == "2:3"
        assert _map_to_supported_aspect_ratio_for_prompt("16:9") == "3:2"
        assert _map_to_supported_aspect_ratio_for_prompt("1.91:1") == "3:2"
        assert _map_to_supported_aspect_ratio_for_prompt("unknown") == "1:1"
    
    def test_platform_name_cleaning(self):
        """Test that platform names are cleaned properly."""
        assert _clean_platform_name("Instagram Story/Reel (9:16 Vertical)") == "Instagram Story/Reel"
        assert _clean_platform_name("Instagram Post (1:1 Square)") == "Instagram Post"
        assert _clean_platform_name("Pinterest Pin (2:3 Vertical)") == "Pinterest Pin"
        assert _clean_platform_name("Facebook Post (Mixed)") == "Facebook Post"
        assert _clean_platform_name("Xiaohongshu (Red Note) (3:4 Vertical)") == "Xiaohongshu (Red Note)"
        
        # Test edge cases
        assert _clean_platform_name("Custom Platform") == "Custom Platform"  # No parentheses
        assert _clean_platform_name("Platform (No Aspect)") == "Platform (No Aspect)"  # No aspect ratio pattern
    
    def test_user_prompt_consistency(self):
        """Test that user prompt uses consistent aspect ratios and cleaned platform names."""
        platform_name = "Instagram Story/Reel (9:16 Vertical)"
        aspect_ratio_for_prompt = "2:3"  # Mapped from 9:16
        
        strategy = {
            "target_audience": "Test audience",
            "target_niche": "Test niche", 
            "target_objective": "Test objective",
            "target_voice": "Test voice"
        }
        
        prompt = _get_creative_expert_user_prompt(
            platform_name=platform_name,
            aspect_ratio_for_prompt=aspect_ratio_for_prompt,
            strategy=strategy,
            task_type="1. Product Photography",
            user_prompt_original="Test prompt",
            task_description="Test description",
            branding_elements="Test branding",
            render_text_flag=True,
            apply_branding_flag=True,
            has_image_reference=False,
            saved_image_filename=None,
            image_subject_from_analysis=None,
            image_instruction=None,
            use_instructor_parsing=True,
            is_default_edit=False,
            style_guidance_item=None
        )
        
        # Should contain consistent 2:3 aspect ratio references
        assert "2:3" in prompt
        # Should not contain the original 9:16 aspect ratio
        assert "9:16" not in prompt
        # Should contain the intended aspect ratio instruction
        assert "intended visual aspect ratio for prompt: 2:3" in prompt
        # Platform guidance should use consistent aspect ratio
        assert "2:3 vertical format" in prompt
        # Should use cleaned platform name (without aspect ratio)
        assert "Instagram Story/Reel" in prompt
        # Should not contain the aspect ratio part of platform name
        assert "(9:16 Vertical)" not in prompt 