import pytest
from churns.stages.style_adaptation import _build_system_prompt

def test_system_prompt_instructs_subject_agnosticism():
    """
    Tests that the system prompt correctly instructs the model to ignore
    subject-specific details in the framework.
    """
    prompt = _build_system_prompt(render_text_enabled=True, apply_branding_enabled=True, language="en", use_instructor_parsing=False)
    
    # Check for the key instruction
    assert "It may contain descriptions of a *previous* subject; you MUST ignore those and extract only the abstract, subject-agnostic properties" in prompt
    assert "e.g., 'low-angle shot', 'dramatic lighting'" in prompt

def test_system_prompt_without_text_or_branding():
    """
    Tests that the system prompt correctly omits text and branding instructions
    when they are disabled.
    """
    prompt = _build_system_prompt(render_text_enabled=False, apply_branding_enabled=False, language="en", use_instructor_parsing=False)
    
    assert "Omit Text" in prompt
    assert "Omit Branding" in prompt
    assert "Adapt Text" not in prompt
    assert "Adapt Branding" not in prompt

def test_system_prompt_language_instructions():
    """
    Tests that the system prompt correctly includes language instructions.
    """
    prompt_en = _build_system_prompt(True, True, "en", False)
    assert "The target language is English" in prompt_en
    
    prompt_zh = _build_system_prompt(True, True, "zh", False)
    assert "The target language is SIMPLIFIED CHINESE" in prompt_zh
    assert "All other fields MUST be in ENGLISH" in prompt_zh
