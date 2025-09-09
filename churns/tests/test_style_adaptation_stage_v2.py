import pytest
from unittest.mock import MagicMock, AsyncMock

# Assuming the following imports are necessary based on the context of the file being tested
from churns.pipeline.context import PipelineContext
from churns.stages.style_adaptation import run, _build_system_prompt, _build_user_prompt
from churns.api.database import PresetType

@pytest.fixture
def mock_context():
    """Provides a mock PipelineContext for testing."""
    ctx = PipelineContext(run_id="test_run")
    ctx.preset_type = PresetType.STYLE_RECIPE
    ctx.render_text = True
    ctx.apply_branding = True
    ctx.language = "en"
    ctx.adaptation_prompt = "A new photo of a sports car"
    ctx.image_analysis_result = {"main_subject": "sports car"}
    ctx.preset_data = {
        "style_guidance": {
            "style_keywords": ["dramatic", "bold"],
            "style_description": "A very dramatic and bold style."
        },
        "visual_concept": {
            "composition_and_framing": "low-angle shot",
            "lighting_and_mood": "dark and moody",
            "visual_style": "photorealistic",
            "promotional_text_visuals": "bold text at the bottom",
            "logo_visuals": "logo in top-right corner"
        }
    }
    return ctx

def test_build_system_prompt_all_enabled():
    """Tests that the system prompt is built correctly when all features are enabled."""
    prompt = _build_system_prompt(True, True, "en", False)
    assert "Adapt Text" in prompt
    assert "Adapt Branding" in prompt
    assert "The target language is English" in prompt

def test_build_user_prompt_structure():
    """Tests the structure of the user prompt for clarity and correctness."""
    style_guidance = {
        "style_keywords": ["dramatic", "bold"],
        "style_description": "A very dramatic and bold style."
    }
    original_visual_concept = {
        "composition_and_framing": "low-angle shot",
        "lighting_and_mood": "dark and moody",
        "visual_style": "photorealistic",
        "promotional_text_visuals": "bold text at the bottom",
        "branding_visuals": "logo in top-right corner"
    }
    new_image_analysis = {"main_subject": "sports car"}
    
    prompt = _build_user_prompt(style_guidance, original_visual_concept, "A new photo of a sports car", new_image_analysis)
    
    assert "### STRUCTURAL FRAMEWORK (Strictly Adhere)" in prompt
    assert "### AESTHETIC GUIDANCE (Apply this Vibe)" in prompt
    assert "### NEW SUBJECT (Adapt the Framework to this Content)" in prompt
    assert "### CONSISTENCY CHECKLIST (Must-Pass)" in prompt
    
    # Check that visual_style is under "AESTHETIC GUIDANCE"
    assert 'Visual Style' in prompt.split("### AESTHETIC GUIDANCE (Apply this Vibe)")[1]
    assert 'Visual Style' not in prompt.split("### STRUCTURAL FRAMEWORK (Strictly Adhere)")[1]
    
@pytest.mark.asyncio
async def test_run_style_adaptation_stage(mock_context):
    """A full integration test for the style_adaptation stage run function."""
    # This is a placeholder for a more detailed test.
    # A complete test would mock the LLM client and verify the output.
    
    # Mocking the LLM client
    mock_client = MagicMock()
    mock_completion = MagicMock()
    mock_completion.choices = [MagicMock()]
    mock_completion.choices[0].message.content = '{"main_subject": "A sports car in a dramatic and bold style."}'
    mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

    # We need to mock the global variables that `run` depends on
    from churns.stages import style_adaptation
    style_adaptation.base_llm_client_style_adaptation = mock_client
    style_adaptation.VisualConceptDetails = MagicMock()

    await run(mock_context)
    
    assert mock_context.stage_error is None
    assert "generated_image_prompts" in mock_context
    assert len(mock_context.generated_image_prompts) > 0
    # Add more assertions here to check the content of the generated prompts
