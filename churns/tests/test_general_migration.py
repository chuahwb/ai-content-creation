"""
Test to demonstrate the stage migration is working correctly.

This test shows how the first stage (image_eval) has been successfully
extracted from the monolith and integrated into the new pipeline executor.
"""

import pytest
from ..pipeline.context import PipelineContext
from ..pipeline.executor import PipelineExecutor


def test_pipeline_context_creation():
    """Test that PipelineContext can be created and used."""
    ctx = PipelineContext(
        mode="easy_mode",
        creativity_level=2,
        prompt="Test burger image",
        render_text=True,
        apply_branding=False
    )
    
    assert ctx.mode == "easy_mode"
    assert ctx.creativity_level == 2
    assert ctx.prompt == "Test burger image"
    assert ctx.render_text is True
    assert ctx.apply_branding is False
    assert ctx.image_analysis_result is None
    

def test_pipeline_context_logging():
    """Test that logging works in PipelineContext."""
    ctx = PipelineContext()
    
    ctx.log("Test message 1")
    ctx.log("Test message 2")
    
    assert len(ctx.logs) == 2
    assert "Test message 1" in ctx.logs[0]
    assert "Test message 2" in ctx.logs[1]
    # Check timestamp format
    assert "[" in ctx.logs[0] and "]" in ctx.logs[0]


def test_pipeline_context_dict_conversion():
    """Test converting PipelineContext to/from dict format."""
    ctx = PipelineContext(
        mode="custom_mode",
        task_type="1. Product Photography",
        prompt="Gourmet burger on marble background"
    )
    
    # Convert to dict
    ctx_dict = ctx.to_dict()
    
    assert ctx_dict["request_details"]["mode"] == "custom_mode"
    assert ctx_dict["request_details"]["task_type"] == "1. Product Photography"
    assert ctx_dict["user_inputs"]["prompt"] == "Gourmet burger on marble background"
    
    # Convert back from dict
    ctx2 = PipelineContext.from_dict(ctx_dict)
    
    assert ctx2.mode == "custom_mode"
    assert ctx2.task_type == "1. Product Photography"
    assert ctx2.prompt == "Gourmet burger on marble background"


def test_executor_creation():
    """Test that PipelineExecutor can be created."""
    executor = PipelineExecutor()
    
    # Should have default stages
    assert len(executor.stages) > 0
    assert "image_eval" in executor.stages
    

def test_image_eval_stage_importable():
    """Test that the image_eval stage can be imported."""
    from ..stages import image_eval
    
    # Should have the main run function
    assert hasattr(image_eval, 'run')
    assert callable(image_eval.run)
    
    # Should have helper functions
    assert hasattr(image_eval, 'extract_json_from_llm_response')
    assert hasattr(image_eval, 'simulate_image_evaluation_fallback')


def test_image_eval_stage_simulation():
    """Test that image_eval stage works with simulation (no API calls)."""
    ctx = PipelineContext(
        mode="easy_mode",
        prompt="Test burger image"
    )
    
    # Import and run the stage
    from ..stages import image_eval
    
    # Run the stage (should use simulation since no image provided)
    image_eval.run(ctx)
    
    # Should have logged activity
    assert len(ctx.logs) > 0
    assert any("image evaluation" in log.lower() for log in ctx.logs)
    
    # Should have set image_analysis_result to None (no image provided)
    assert ctx.image_analysis_result is None


def test_image_eval_stage_with_mock_image():
    """Test image_eval stage with a mock image reference."""
    ctx = PipelineContext(
        mode="easy_mode",
        prompt="Test burger image",
        image_reference={
            "filename": "test_burger.jpg",
            "content_type": "image/jpeg",
            "size_bytes": 123456,
            "image_content_base64": "fake_base64_data"
        },
        task_type="1. Product Photography"
    )
    
    from ..stages import image_eval
    
    # Run the stage (should use simulation since no real API clients)
    image_eval.run(ctx)
    
    # Should have logged activity
    assert len(ctx.logs) > 0
    assert any("image" in log.lower() for log in ctx.logs)
    
    # Should have analysis result (fallback simulation)
    assert ctx.image_analysis_result is not None
    assert "main_subject" in ctx.image_analysis_result


def test_input_validation_patterns():
    """Test input validation patterns that mirror the original monolith logic."""
    
    # Test 1: Valid easy mode context (like original validation)
    ctx_easy = PipelineContext(
        mode="easy_mode",
        target_platform={
            "name": "Instagram Post (1:1 Square)",
            "resolution_details": {"width": 1080, "height": 1080, "aspect_ratio": "1:1"}
        },
        prompt="Test burger image"
    )
    assert ctx_easy.mode == "easy_mode"
    assert ctx_easy.target_platform["name"] == "Instagram Post (1:1 Square)"
    assert ctx_easy.prompt == "Test burger image"
    
    # Test 2: Custom mode with complete marketing goals (like original structure)
    ctx_custom = PipelineContext(
        mode="custom_mode",
        target_platform={
            "name": "Pinterest Pin (2:3 Vertical)",
            "resolution_details": {"width": 1024, "height": 1536, "aspect_ratio": "2:3"}
        },
        prompt="Gourmet coffee setup",
        branding_elements="Logo in top-right, brand colors #8B4513",
        task_description="Showcase artisan coffee brewing",
        marketing_goals={
            "target_audience": "Coffee Enthusiasts",
            "objective": "Showcase Quality/Freshness", 
            "voice": "Sophisticated & Elegant",
            "niche": "Cafe/Coffee Shop"
        }
    )
    
    # Verify custom mode structure matches original patterns
    assert ctx_custom.mode == "custom_mode"
    assert ctx_custom.branding_elements is not None
    assert ctx_custom.task_description is not None
    assert ctx_custom.marketing_goals is not None
    assert ctx_custom.marketing_goals["niche"] == "Cafe/Coffee Shop"
    
    # Test 3: Task-specific mode (like original task-specific validation)
    ctx_task = PipelineContext(
        mode="task_specific_mode",
        task_type="1. Product Photography",
        target_platform={
            "name": "Xiaohongshu (Red Note) (3:4 Vertical)",
            "resolution_details": {"width": 1080, "height": 1440, "aspect_ratio": "3:4"}
        },
        prompt="Featured dish photography",
        creativity_level=3
    )
    
    assert ctx_task.mode == "task_specific_mode"
    assert ctx_task.task_type == "1. Product Photography"
    assert ctx_task.creativity_level == 3
    
    # Test 4: Image reference handling (like original image processing)
    ctx_with_image = PipelineContext(
        mode="easy_mode",
        target_platform={"name": "Instagram Post (1:1 Square)"},
        image_reference={
            "filename": "test_burger.jpg",
            "content_type": "image/jpeg",
            "size_bytes": 245760,
            "instruction": "Enhance the lighting and make colors more vibrant",
            "image_content_base64": "fake_base64_content_for_testing"
        }
    )
    
    # Verify image reference structure matches original
    assert ctx_with_image.image_reference is not None
    assert ctx_with_image.image_reference["filename"] == "test_burger.jpg"
    assert ctx_with_image.image_reference["content_type"] == "image/jpeg"
    assert ctx_with_image.image_reference["instruction"] is not None
    
    # Test 5: Validate flags match original boolean handling
    ctx_flags = PipelineContext(
        render_text=True,
        apply_branding=False
    )
    assert isinstance(ctx_flags.render_text, bool)
    assert isinstance(ctx_flags.apply_branding, bool)
    assert ctx_flags.render_text is True
    assert ctx_flags.apply_branding is False


if __name__ == "__main__":
    # Run the tests manually for demonstration
    test_pipeline_context_creation()
    test_pipeline_context_logging()
    test_pipeline_context_dict_conversion()
    test_executor_creation()
    test_image_eval_stage_importable()
    test_image_eval_stage_simulation()
    test_image_eval_stage_with_mock_image()
    test_input_validation_patterns()
    
    print("✅ All tests passed! Stage migration is working correctly.") 