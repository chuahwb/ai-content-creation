"""
Test language control functionality across the pipeline.
"""

import pytest
from churns.pipeline.context import PipelineContext
from churns.stages.creative_expert import _get_creative_expert_system_prompt, _get_creative_expert_user_prompt
from churns.stages.caption import _get_analyst_system_prompt, _get_writer_system_prompt


class TestLanguageControl:
    """Test language control implementation."""

    def test_pipeline_context_default_language(self):
        """Test that PipelineContext defaults to English."""
        ctx = PipelineContext()
        assert ctx.language == 'en'

    def test_pipeline_context_custom_language(self):
        """Test that PipelineContext accepts custom language."""
        ctx = PipelineContext(language='zh')
        assert ctx.language == 'zh'

    def test_pipeline_context_from_dict(self):
        """Test that PipelineContext.from_dict includes language."""
        data = {
            "request_details": {
                "mode": "easy_mode",
                "language": "zh"
            },
            "user_inputs": {},
            "processing_context": {}
        }
        ctx = PipelineContext.from_dict(data)
        assert ctx.language == 'zh'

    def test_pipeline_context_from_dict_default(self):
        """Test that PipelineContext.from_dict defaults to English."""
        data = {
            "request_details": {
                "mode": "easy_mode"
            },
            "user_inputs": {},
            "processing_context": {}
        }
        ctx = PipelineContext.from_dict(data)
        assert ctx.language == 'en'

    def test_creative_expert_system_prompt_english(self):
        """Test that Creative Expert system prompt includes English language control."""
        prompt = _get_creative_expert_system_prompt(
            creativity_level=2,
            task_type="1. Product Photography",
            use_instructor_parsing=True,
            has_reference=False,
            has_instruction=False,
            render_text_flag=True,
            apply_branding_flag=True,
            platform_name="Instagram Post",
            language='en'
        )
        
        assert "Language Control (IMPORTANT)" in prompt
        assert "Write the following JSON fields **only** in EN:" in prompt
        assert "promotional_text_visuals" in prompt
        assert "logo_visuals" in prompt
        assert "suggested_alt_text" in prompt

    def test_creative_expert_system_prompt_chinese(self):
        """Test that Creative Expert system prompt includes Chinese language control."""
        prompt = _get_creative_expert_system_prompt(
            creativity_level=2,
            task_type="1. Product Photography",
            use_instructor_parsing=True,
            has_reference=False,
            has_instruction=False,
            render_text_flag=True,
            apply_branding_flag=True,
            platform_name="Instagram Post",
            language='zh'
        )
        
        assert "Language Control (IMPORTANT)" in prompt
        assert "Write the following JSON fields **only** in SIMPLIFIED CHINESE:" in prompt

    def test_caption_analyst_system_prompt_english(self):
        """Test that Caption Analyst system prompt includes English language control."""
        prompt = _get_analyst_system_prompt('en')
        
        assert "Generate the *language-controlled* fields listed below in ENGLISH" in prompt

    def test_caption_analyst_system_prompt_chinese(self):
        """Test that Caption Analyst system prompt includes Chinese language control."""
        prompt = _get_analyst_system_prompt('zh')
        
        assert "Generate the *language-controlled* fields listed below in SIMPLIFIED CHINESE" in prompt

    def test_caption_writer_system_prompt_english(self):
        """Test that Caption Writer system prompt includes English language control."""
        prompt = _get_writer_system_prompt('en')
        
        assert "Write the final caption in ENGLISH" in prompt

    def test_caption_writer_system_prompt_chinese(self):
        """Test that Caption Writer system prompt includes Chinese language control."""
        prompt = _get_writer_system_prompt('zh')
        
        assert "Write the final caption in SIMPLIFIED CHINESE" in prompt

    def test_creative_expert_user_prompt_language_reminder(self):
        """Test that Creative Expert user prompt includes language reminder."""
        from churns.models import StyleGuidance
        
        style_guidance = StyleGuidance(
            style_keywords=["modern", "clean"],
            style_description="A modern and clean aesthetic",
            marketing_impact="Supports brand recognition and engagement",
            source_strategy_index=0
        )
        
        prompt = _get_creative_expert_user_prompt(
            platform_name="Instagram Post",
            aspect_ratio_for_prompt="1:1",
            strategy={"target_audience": "Young professionals", "target_objective": "Increase engagement"},
            task_type="1. Product Photography",
            user_prompt_original="Coffee cup",
            task_description=None,
            branding_elements=None,
            render_text_flag=True,
            apply_branding_flag=True,
            has_image_reference=False,
            saved_image_filename=None,
            image_subject_from_analysis=None,
            image_instruction=None,
            use_instructor_parsing=True,
            is_default_edit=False,
            style_guidance_item=style_guidance,
            language='zh'
        )
        
        assert "Language Reminder" in prompt
        assert "use Simplified Chinese" in prompt
        assert "All other descriptions stay in English" in prompt

    @pytest.mark.parametrize("language,expected_name", [
        ('en', 'English'),
        ('zh', 'Simplified Chinese'),
        ('es', 'Spanish'),
        ('fr', 'French'),
        ('ja', 'Japanese'),
        ('unknown', 'UNKNOWN')
    ])
    def test_language_mapping(self, language, expected_name):
        """Test that language codes are correctly mapped to readable names."""
        prompt = _get_analyst_system_prompt(language)
        assert expected_name.upper() in prompt 