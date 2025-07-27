import pytest
from churns.stages.prompt_assembly import _get_prompt_prefix

# Test cases for the _get_prompt_prefix function
# Each tuple contains: (test_id, args_dict, expected_prefix)
prefix_test_cases = [
    # Style Adaptation Scenarios
    ("style_adaptation_no_logo", {
        "is_style_adaptation": True, "has_reference": True, "has_logo": False, "has_instruction": False, "instruction_text": ""
    }, "Adapt the provided reference image to match the following detailed visual concept. Focus on applying the stylistic elements (lighting, color, mood, texture) from the description to the composition of the reference image: "),
    
    ("style_adaptation_with_logo", {
        "is_style_adaptation": True, "has_reference": True, "has_logo": True, "has_instruction": False, "instruction_text": ""
    }, "Adapt the provided reference image, integrating the provided logo, to match the following detailed visual concept. Focus on applying the stylistic elements (lighting, color, mood, texture) from the description to the composition of the reference image: "),

    # Complex Edit Scenarios (Reference + Logo)
    ("complex_edit_with_instruction", {
        "is_style_adaptation": False, "has_reference": True, "has_logo": True, "has_instruction": True, "instruction_text": "make it pop"
    }, "Based on the provided primary reference image and the secondary image as a logo, modify it according to the user instruction 'make it pop' to achieve the following detailed visual concept: "),
    
    ("complex_edit_no_instruction", {
        "is_style_adaptation": False, "has_reference": True, "has_logo": True, "has_instruction": False, "instruction_text": ""
    }, "Using the provided primary reference image and the secondary logo image, create a composition that integrates both elements according to the following detailed visual concept: "),

    # Reference Image Only Scenarios
    ("instructed_edit", {
        "is_style_adaptation": False, "has_reference": True, "has_logo": False, "has_instruction": True, "instruction_text": "change background"
    }, "Based on the provided reference image, modify it according to the user instruction 'change background' to achieve the following detailed visual concept: "),
    
    ("default_edit", {
        "is_style_adaptation": False, "has_reference": True, "has_logo": False, "has_instruction": False, "instruction_text": ""
    }, "Edit the provided image. Preserve the main subject exactly as it is in the original image. Modify only the surrounding context (background, lighting, style, composition, etc.) to match this description: "),

    # Logo Only Scenarios
    ("logo_only_with_instruction", {
        "is_style_adaptation": False, "has_reference": False, "has_logo": True, "has_instruction": True, "instruction_text": "add a cool effect"
    }, "Using the provided logo, adapt it according to the user instruction 'add a cool effect' to achieve the following detailed visual concept: "),
    
    ("logo_only_no_instruction", {
        "is_style_adaptation": False, "has_reference": False, "has_logo": True, "has_instruction": False, "instruction_text": ""
    }, "Using the provided logo as the base, create a composition according to the following detailed visual concept: "),

    # Full Generation Scenario
    ("full_generation", {
        "is_style_adaptation": False, "has_reference": False, "has_logo": False, "has_instruction": False, "instruction_text": ""
    }, "Create an image based on the following detailed visual concept: "),
]

@pytest.mark.parametrize("test_id, args_dict, expected_prefix", prefix_test_cases)
def test_get_prompt_prefix(test_id, args_dict, expected_prefix):
    """Tests the _get_prompt_prefix function with various scenarios."""
    prefix = _get_prompt_prefix(**args_dict)
    assert prefix == expected_prefix 