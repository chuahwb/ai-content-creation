"""
Tests for Stage 5: Prompt Assembly

Tests the extraction of prompt assembly functionality from the original monolith.
Validates that final text prompts are correctly assembled from structured visual concepts.
"""

import pytest
from unittest.mock import Mock, patch
from churns.pipeline.context import PipelineContext
from churns.stages.prompt_assembly import run, assemble_final_prompt, map_to_supported_aspect_ratio_for_prompt


class TestPromptAssemblyStage:
    """Test the prompt assembly stage functionality."""
    
    def create_test_context(self, 
                          has_image_reference=False, 
                          has_instruction=False,
                          render_text=True,
                          apply_branding=True):
        """Create a test context with sample data."""
        ctx = PipelineContext()
        ctx.creativity_level = 2
        ctx.task_type = "2. Promotional Graphics & Announcements"
        ctx.target_platform = {
            "name": "Instagram Post (1:1 Square)",
            "resolution_details": {"width": 1080, "height": 1080, "aspect_ratio": "1:1"}
        }
        ctx.render_text = render_text
        ctx.apply_branding = apply_branding
        
        # Set up user inputs
        ctx.prompt = "Holiday special promotion"
        ctx.task_description = "Special holiday offer - 50% off all items"
        ctx.branding_elements = "Logo in top-right, use red and green colors"
        
        # Set up image reference if needed
        if has_image_reference:
            ctx.image_reference = {
                "filename": "test_burger.jpg",
                "content_type": "image/jpeg",
                "size_bytes": 150000,
                "instruction": "Make the burger look more festive" if has_instruction else None,
                "saved_image_path_in_run_dir": "/test/path/input_image.jpg"
            }
        
        # Set up generated image prompts (output from creative expert stage)
        ctx.generated_image_prompts = [
            {
                "visual_concept": {
                    "main_subject": "Gourmet burger with festive garnish" if not (has_image_reference and not has_instruction) else None,
                    "composition_and_framing": "Close-up shot with 45-degree angle",
                    "background_environment": "Warm holiday setting with soft bokeh lights",
                    "foreground_elements": "Holly leaves and cranberries",
                    "lighting_and_mood": "Warm, cozy holiday lighting with golden tones",
                    "color_palette": "Rich reds, warm golds, and deep greens",
                    "visual_style": "Festive food photography with holiday styling",
                    "promotional_text_visuals": "Bold '50% OFF' text in festive red font" if render_text else None,
                    "branding_visuals": "Logo in top-right corner with subtle holiday wreath" if apply_branding else None,
                    "texture_and_details": "Crispy lettuce, melted cheese, rustic bun texture",
                    "negative_elements": "Avoid clutter, no artificial decorations",
                    "creative_reasoning": "Holiday styling supports promotional objective"
                },
                "source_strategy_index": 0
            },
            {
                "visual_concept": {
                    "main_subject": "Artisan burger with seasonal ingredients",
                    "composition_and_framing": "Medium shot with symmetrical framing",
                    "background_environment": "Clean white background with subtle shadows",
                    "foreground_elements": None,
                    "lighting_and_mood": "Bright, clean studio lighting",
                    "color_palette": "Fresh greens, warm browns, bright reds",
                    "visual_style": "Clean product photography with premium feel",
                    "promotional_text_visuals": "Elegant 'Holiday Special' text in serif font" if render_text else None,
                    "branding_visuals": "Minimalist logo placement bottom-left" if apply_branding else None,
                    "texture_and_details": "Fresh ingredients, artisan bun texture",
                    "negative_elements": "No busy backgrounds",
                    "creative_reasoning": "Clean style appeals to quality-conscious audience"
                },
                "source_strategy_index": 1
            }
        ]
        
        return ctx
    
    def test_successful_prompt_assembly_full_generation(self):
        """Test successful assembly of prompts for full generation (no image reference)."""
        ctx = self.create_test_context()
        
        # Run the stage
        run(ctx)
        
        # Validate results
        assert ctx.final_assembled_prompts is not None
        assert len(ctx.final_assembled_prompts) == 2
        
        # Check first assembled prompt
        prompt1 = ctx.final_assembled_prompts[0]
        assert prompt1["index"] == 0
        assert prompt1["assembly_type"] == "full_generation"
        assert prompt1["platform_aspect_ratio"] == "1:1"
        assert prompt1["supported_aspect_ratio"] == "1:1"
        
        # Validate prompt content
        prompt_text = prompt1["prompt"]
        assert "Gourmet burger with festive garnish" in prompt_text
        assert "Close-up shot with 45-degree angle" in prompt_text
        assert "Warm holiday setting" in prompt_text
        assert "50% OFF" in prompt_text  # Text rendering enabled
        assert "Logo in top-right corner" in prompt_text  # Branding enabled
        assert "aspect ratio" in prompt_text.lower()
        
        # Check second assembled prompt
        prompt2 = ctx.final_assembled_prompts[1]
        assert prompt2["index"] == 1
        assert "Artisan burger with seasonal ingredients" in prompt2["prompt"]
        assert "Holiday Special" in prompt2["prompt"]
    
    def test_prompt_assembly_default_edit_scenario(self):
        """Test prompt assembly for default edit scenario (image ref, no instruction)."""
        ctx = self.create_test_context(has_image_reference=True, has_instruction=False)
        
        # Run the stage
        run(ctx)
        
        # Validate results
        assert len(ctx.final_assembled_prompts) == 2
        
        # Check assembly type
        prompt1 = ctx.final_assembled_prompts[0]
        assert prompt1["assembly_type"] == "default_edit"
        
        # Validate prompt structure for default edit
        prompt_text = prompt1["prompt"]
        assert "Edit the provided image" in prompt_text
        assert "Preserve the main subject exactly as it is" in prompt_text
        assert "surrounding context" in prompt_text
        assert "Close-up shot with 45-degree angle" in prompt_text
        assert "Gourmet burger with festive garnish" not in prompt_text  # Main subject omitted
    
    def test_prompt_assembly_instructed_edit_scenario(self):
        """Test prompt assembly for instructed edit scenario (image ref + instruction)."""
        ctx = self.create_test_context(has_image_reference=True, has_instruction=True)
        
        # Run the stage
        run(ctx)
        
        # Validate results
        assert len(ctx.final_assembled_prompts) == 2
        
        # Check assembly type
        prompt1 = ctx.final_assembled_prompts[0]
        assert prompt1["assembly_type"] == "full_generation"
        
        # Validate prompt structure for instructed edit
        prompt_text = prompt1["prompt"]
        assert "Based on the provided reference image" in prompt_text
        assert "Make the burger look more festive" in prompt_text
        assert "Gourmet burger with festive garnish" in prompt_text  # Main subject included
    
    def test_prompt_assembly_text_rendering_disabled(self):
        """Test prompt assembly when text rendering is disabled."""
        ctx = self.create_test_context(render_text=False)
        
        # Run the stage
        run(ctx)
        
        # Validate that promotional text is excluded
        prompt1 = ctx.final_assembled_prompts[0]
        prompt_text = prompt1["prompt"]
        assert "50% OFF" not in prompt_text
        assert "Holiday Special" not in prompt1["prompt"] if len(ctx.final_assembled_prompts) > 1 else True
    
    def test_prompt_assembly_branding_disabled(self):
        """Test prompt assembly when branding is disabled."""
        ctx = self.create_test_context(apply_branding=False)
        
        # Run the stage
        run(ctx)
        
        # Validate that branding elements are excluded
        prompt1 = ctx.final_assembled_prompts[0]
        prompt_text = prompt1["prompt"]
        assert "Logo in top-right corner" not in prompt_text
        assert "Minimalist logo placement" not in prompt_text
    
    def test_prompt_assembly_no_prompts_available(self):
        """Test prompt assembly when no structured prompts are available."""
        ctx = PipelineContext()
        ctx.generated_image_prompts = []
        ctx.target_platform = {"resolution_details": {"aspect_ratio": "1:1"}}
        
        # Run the stage
        run(ctx)
        
        # Validate empty results
        assert ctx.final_assembled_prompts == []
        assert any("No structured prompts available" in log for log in ctx.logs)
    
    def test_prompt_assembly_aspect_ratio_handling(self):
        """Test prompt assembly with different aspect ratios."""
        ctx = self.create_test_context()
        
        # Test vertical aspect ratio
        ctx.target_platform = {
            "resolution_details": {"aspect_ratio": "9:16"}
        }
        
        # Run the stage
        run(ctx)
        
        # Validate aspect ratio mapping
        prompt1 = ctx.final_assembled_prompts[0]
        assert prompt1["platform_aspect_ratio"] == "9:16"
        assert prompt1["supported_aspect_ratio"] == "2:3"
        assert "2:3 aspect ratio" in prompt1["prompt"]
    
    def test_prompt_assembly_error_handling(self):
        """Test prompt assembly error handling for malformed data."""
        ctx = PipelineContext()
        ctx.target_platform = {"resolution_details": {"aspect_ratio": "1:1"}}
        
        # Set up malformed prompt data
        ctx.generated_image_prompts = [
            {"invalid": "structure"},  # Missing visual_concept
            {
                "visual_concept": {},  # Empty visual concept
                "source_strategy_index": 1
            }
        ]
        
        # Run the stage
        run(ctx)
        
        # Validate error handling
        assert len(ctx.final_assembled_prompts) == 2
        
        # Check that errors are properly handled
        for prompt_data in ctx.final_assembled_prompts:
            if prompt_data["prompt"].startswith("Error:"):
                assert "Invalid structured prompt data" in prompt_data["prompt"]


class TestPromptAssemblyHelperFunctions:
    """Test the helper functions used in prompt assembly."""
    
    def test_map_aspect_ratio_for_prompt(self):
        """Test aspect ratio mapping for prompt text."""
        # Test square aspect ratio
        assert map_to_supported_aspect_ratio_for_prompt("1:1") == "1:1"
        
        # Test vertical aspect ratios
        assert map_to_supported_aspect_ratio_for_prompt("9:16") == "2:3"
        assert map_to_supported_aspect_ratio_for_prompt("3:4") == "2:3"
        assert map_to_supported_aspect_ratio_for_prompt("2:3") == "2:3"
        
        # Test horizontal aspect ratios
        assert map_to_supported_aspect_ratio_for_prompt("16:9") == "3:2"
        assert map_to_supported_aspect_ratio_for_prompt("1.91:1") == "3:2"
        
        # Test unsupported aspect ratio
        assert map_to_supported_aspect_ratio_for_prompt("4:5") == "1:1"
    
    def test_assemble_final_prompt_function(self):
        """Test the core assemble_final_prompt function directly."""
        # Test data
        structured_data = {
            "visual_concept": {
                "main_subject": "Delicious burger",
                "composition_and_framing": "Close-up shot",
                "background_environment": "Clean white background",
                "lighting_and_mood": "Bright studio lighting",
                "color_palette": "Warm browns and greens",
                "visual_style": "Product photography"
            }
        }
        
        user_inputs = {
            "render_text": False,
            "apply_branding": False
        }
        
        # Test assembly
        result = assemble_final_prompt(structured_data, user_inputs, "1:1")
        
        # Validate result
        assert "Delicious burger" in result
        assert "Close-up shot" in result
        assert "Clean white background" in result
        assert "1:1 aspect ratio" in result
    
    def test_assemble_final_prompt_invalid_data(self):
        """Test assemble_final_prompt with invalid input data."""
        # Test with missing visual_concept
        result = assemble_final_prompt({}, {}, "1:1")
        assert result.startswith("Error:")
        
        # Test with None input
        result = assemble_final_prompt(None, {}, "1:1")
        assert result.startswith("Error:")


class TestPromptAssemblyIntegration:
    """Integration tests for prompt assembly stage."""
    
    def test_prompt_assembly_integration_with_context(self):
        """Test prompt assembly integration with full pipeline context."""
        ctx = PipelineContext()
        
        # Set up realistic pipeline state
        ctx.target_platform = {
            "name": "Instagram Story/Reel (9:16 Vertical)",
            "resolution_details": {"width": 1080, "height": 1920, "aspect_ratio": "9:16"}
        }
        ctx.render_text = True
        ctx.apply_branding = True
        
        # Mock previous stage outputs
        ctx.generated_image_prompts = [
            {
                "visual_concept": {
                    "main_subject": "Fresh salad bowl",
                    "composition_and_framing": "Top-down view",
                    "background_environment": "Marble countertop",
                    "lighting_and_mood": "Natural daylight",
                    "color_palette": "Fresh greens and colorful vegetables",
                    "visual_style": "Healthy lifestyle photography",
                    "promotional_text_visuals": "Fresh & Healthy text overlay",
                    "branding_visuals": "Subtle logo watermark"
                },
                "source_strategy_index": 0
            }
        ]
        
        # Run the stage
        run(ctx)
        
        # Validate integration
        assert len(ctx.final_assembled_prompts) == 1
        prompt_data = ctx.final_assembled_prompts[0]
        
        # Check metadata
        assert prompt_data["platform_aspect_ratio"] == "9:16"
        assert prompt_data["supported_aspect_ratio"] == "2:3"
        assert prompt_data["assembly_type"] == "full_generation"
        
        # Check prompt content includes all elements
        prompt_text = prompt_data["prompt"]
        assert "Fresh salad bowl" in prompt_text
        assert "Top-down view" in prompt_text
        assert "Fresh & Healthy text overlay" in prompt_text
        assert "Subtle logo watermark" in prompt_text
        assert "2:3 aspect ratio" in prompt_text
    
    def test_prompt_assembly_stage_logging(self):
        """Test that prompt assembly stage provides proper logging."""
        ctx = self.create_basic_context()
        
        # Run the stage
        run(ctx)
        
        # Check logging
        log_messages = [log for log in ctx.logs]
        assert any("Starting Prompt Assembly stage" in log for log in log_messages)
        assert any("Successfully assembled" in log for log in log_messages)
        assert any("Assembling prompt for Strategy" in log for log in log_messages)
    
    def create_basic_context(self):
        """Create a basic context for testing."""
        ctx = PipelineContext()
        ctx.target_platform = {"resolution_details": {"aspect_ratio": "1:1"}}
        ctx.generated_image_prompts = [
            {
                "visual_concept": {
                    "main_subject": "Test subject",
                    "composition_and_framing": "Test composition",
                    "background_environment": "Test background",
                    "lighting_and_mood": "Test lighting",
                    "color_palette": "Test colors",
                    "visual_style": "Test style"
                },
                "source_strategy_index": 0
            }
        ]
        return ctx


class TestPromptAssemblyMigrationFidelity:
    """Tests to ensure migrated prompt assembly maintains fidelity with original monolith."""
    
    def test_prompt_structure_matches_original(self):
        """Test that assembled prompts match the original monolith structure."""
        # This test validates that our extracted logic produces the same prompt
        # structure as the original assemble_final_prompt function
        
        ctx = PipelineContext()
        ctx.target_platform = {"resolution_details": {"aspect_ratio": "1:1"}}
        ctx.render_text = True
        ctx.apply_branding = True
        
        # Use the exact same test data that would be used in the original
        ctx.generated_image_prompts = [
            {
                "visual_concept": {
                    "main_subject": "Gourmet burger with artisan toppings",
                    "composition_and_framing": "45-degree angle, close-up shot",
                    "background_environment": "Rustic wooden table with soft lighting",
                    "foreground_elements": "Fresh herbs and tomato slices",
                    "lighting_and_mood": "Warm, appetizing natural light",
                    "color_palette": "Rich browns, fresh greens, vibrant reds",
                    "visual_style": "Food photography with shallow depth of field",
                    "promotional_text_visuals": "Special Price: $12.99",
                    "branding_visuals": "Restaurant logo in bottom-right corner",
                    "texture_and_details": "Crispy lettuce, melted cheese details",
                    "negative_elements": "No artificial lighting, no plastic appearance"
                },
                "source_strategy_index": 0
            }
        ]
        
        # Run the stage
        run(ctx)
        
        # Validate prompt structure matches expected format from original
        prompt_data = ctx.final_assembled_prompts[0]
        prompt_text = prompt_data["prompt"]
        
        # Verify all visual concept elements are included in correct order
        elements_in_order = [
            "Gourmet burger with artisan toppings",  # main_subject
            "45-degree angle, close-up shot",        # composition_and_framing
            "Background: Rustic wooden table",       # background_environment
            "Foreground elements: Fresh herbs",      # foreground_elements
            "Lighting & Mood: Warm, appetizing",     # lighting_and_mood
            "Color Palette: Rich browns",            # color_palette
            "Visual Style: Food photography",        # visual_style
            "Textures & Details: Crispy lettuce",    # texture_and_details (comes before text/branding)
            "Promotional Text Visuals: Special Price", # promotional_text_visuals
            "Branding Visuals: Restaurant logo",     # branding_visuals
            "Avoid the following elements: No artificial", # negative_elements
            "1:1 aspect ratio"                       # aspect ratio constraint
        ]
        
        # Check that elements appear in the expected order
        last_position = -1
        for element in elements_in_order:
            position = prompt_text.find(element)
            assert position > last_position, f"Element '{element}' not found or out of order in prompt"
            last_position = position 