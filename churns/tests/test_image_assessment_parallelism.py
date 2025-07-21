"""
Test suite to validate parallel execution in the image assessment stage.

This test verifies that the refactored image assessment stage properly executes
image assessments in parallel rather than sequentially, which should result in
significant performance improvements when processing multiple images.
"""

import pytest
import asyncio
import time
import tempfile
import os
from unittest.mock import Mock, AsyncMock, patch
from typing import Dict, Any, List

# Import the modules we need to test
from churns.stages.image_assessment import run as image_assessment_run
from churns.pipeline.context import PipelineContext


class MockResponse:
    """Mock response object for OpenAI API calls."""
    
    def __init__(self, content: str):
        self.choices = [Mock()]
        self.choices[0].message = Mock()
        self.choices[0].message.content = content
        self.usage = Mock()
        self.usage.prompt_tokens = 1000
        self.usage.completion_tokens = 150
        self.usage.total_tokens = 1150


def create_mock_assessment_response() -> str:
    """Create a valid JSON assessment response for mocking."""
    return """{
        "assessment_scores": {
            "concept_adherence": 4,
            "technical_quality": 4,
            "subject_preservation": 3,
            "text_rendering_quality": 4
        },
        "assessment_justification": {
            "concept_adherence": "Good alignment with visual concept",
            "technical_quality": "High quality with minor issues",
            "subject_preservation": "Subject is recognizable but some details lost",
            "text_rendering_quality": "Text is legible and well integrated"
        }
    }"""


def create_dummy_image_file() -> str:
    """Create a temporary dummy image file for testing."""
    # Create a simple PNG-like file (not a real image, but enough for testing)
    temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
    # Write minimal PNG header bytes to make it look like an image file
    png_header = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde'
    temp_file.write(png_header)
    temp_file.close()
    return temp_file.name


def create_mock_pipeline_context(num_images: int = 3) -> PipelineContext:
    """Create a mock PipelineContext with the specified number of generated images."""
    ctx = PipelineContext()
    
    # Create temporary image files
    temp_images = [create_dummy_image_file() for _ in range(num_images)]
    
    # Set up the context with generated image results
    ctx.generated_image_results = []
    for i in range(num_images):
        ctx.generated_image_results.append({
            "index": i,
            "status": "success",
            "result_path": os.path.basename(temp_images[i]),
            "error_message": None
        })
    
    # Set up visual concepts (required for assessment)
    ctx.generated_image_prompts = []
    for i in range(num_images):
        ctx.generated_image_prompts.append({
            "source_strategy_index": i,
            "visual_concept": {
                "themes": ["modern", "clean"],
                "mood": "professional",
                "color_palette": ["blue", "white"],
                "composition": "centered"
            }
        })
    
    # Set up other required context attributes
    ctx.creativity_level = 2
    ctx.render_text = False
    ctx.task_type = "Marketing Asset"
    ctx.target_platform = {"name": "Instagram"}
    ctx.image_reference = None
    ctx.llm_usage = {}
    
    # Set up output directory with the temp images
    ctx.output_directory = os.path.dirname(temp_images[0])
    
    # Store temp files for cleanup
    ctx._temp_files = temp_images
    
    return ctx


@pytest.mark.asyncio
async def test_parallel_assessment_is_faster():
    """
    Test that parallel image assessment is significantly faster than sequential execution.
    
    This test creates multiple dummy images, mocks the OpenAI API to simulate network
    latency, and verifies that the total execution time is closer to the latency of
    a single call rather than the sum of all calls (proving parallel execution).
    """
    num_images = 4
    simulated_latency = 0.5  # 500ms per API call
    
    # Create mock context
    ctx = create_mock_pipeline_context(num_images)
    
    try:
        # Mock the OpenAI client to simulate network latency
        async def mock_api_call(*args, **kwargs):
            # Simulate network latency
            await asyncio.sleep(simulated_latency)
            return MockResponse(create_mock_assessment_response())
        
        # Mock the global client and model variables
        with patch('churns.stages.image_assessment.base_llm_client_image_assessment') as mock_client, \
             patch('churns.stages.image_assessment.IMAGE_ASSESSMENT_MODEL_ID', 'gpt-4o'), \
             patch('churns.stages.image_assessment.IMAGE_ASSESSMENT_MODEL_PROVIDER', 'openai'), \
             patch('churns.stages.image_assessment.INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS', []):
            
            # Set up the mock client
            mock_client.chat.completions.create = AsyncMock(side_effect=mock_api_call)
            
            # Record start time
            start_time = time.time()
            
            # Run the image assessment stage
            await image_assessment_run(ctx)
            
            # Record end time
            end_time = time.time()
            total_duration = end_time - start_time
            
            # Verify results
            assert hasattr(ctx, 'image_assessments'), "Image assessments should be stored in context"
            assert len(ctx.image_assessments) == num_images, f"Should have {num_images} assessments"
            
            # Verify that all assessments completed successfully
            for assessment in ctx.image_assessments:
                assert "assessment_scores" in assessment, "Assessment should contain scores"
                assert "general_score" in assessment, "Assessment should contain general score"
                assert assessment.get("general_score", 0) > 0, "General score should be calculated"
            
            # Verify parallelism: total time should be closer to single call latency
            # rather than sum of all calls
            single_call_time = simulated_latency
            sequential_time = simulated_latency * num_images
            
            # Allow for some overhead, but should be much closer to parallel than sequential
            max_acceptable_time = single_call_time + 1.0  # 1 second overhead allowance
            min_time_saved = sequential_time * 0.5  # Should save at least 50% of sequential time
            
            print(f"\n--- Parallelism Test Results ---")
            print(f"Number of images: {num_images}")
            print(f"Simulated latency per call: {simulated_latency}s")
            print(f"Expected sequential time: {sequential_time}s")
            print(f"Expected parallel time: ~{single_call_time}s")
            print(f"Actual execution time: {total_duration:.2f}s")
            print(f"Time saved vs sequential: {sequential_time - total_duration:.2f}s")
            
            # Assertions to verify parallel execution
            assert total_duration < max_acceptable_time, \
                f"Execution took {total_duration:.2f}s, expected < {max_acceptable_time}s (indicating parallel execution)"
            
            assert total_duration < sequential_time - min_time_saved, \
                f"Should save significant time vs sequential execution. Actual: {total_duration:.2f}s, Sequential: {sequential_time}s"
            
            # Verify API was called the correct number of times
            assert mock_client.chat.completions.create.call_count == num_images, \
                f"Should make {num_images} API calls, made {mock_client.chat.completions.create.call_count}"
            
            print("✅ Parallel execution verified!")
            
    finally:
        # Cleanup temporary files
        if hasattr(ctx, '_temp_files'):
            for temp_file in ctx._temp_files:
                try:
                    os.unlink(temp_file)
                except OSError:
                    pass


@pytest.mark.asyncio
async def test_parallel_assessment_with_reference_image():
    """
    Test parallel assessment when reference images are provided.
    
    This ensures that the parallelism works correctly even when additional
    complexity (reference images) is involved.
    """
    num_images = 3
    simulated_latency = 0.3
    
    # Create mock context with reference image
    ctx = create_mock_pipeline_context(num_images)
    ctx.image_reference = {
        "image_content_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg==",
        "filename": "reference.png"
    }
    
    try:
        async def mock_api_call(*args, **kwargs):
            await asyncio.sleep(simulated_latency)
            return MockResponse(create_mock_assessment_response())
        
        with patch('churns.stages.image_assessment.base_llm_client_image_assessment') as mock_client, \
             patch('churns.stages.image_assessment.IMAGE_ASSESSMENT_MODEL_ID', 'gpt-4o'), \
             patch('churns.stages.image_assessment.IMAGE_ASSESSMENT_MODEL_PROVIDER', 'openai'), \
             patch('churns.stages.image_assessment.INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS', []):
            
            mock_client.chat.completions.create = AsyncMock(side_effect=mock_api_call)
            
            start_time = time.time()
            await image_assessment_run(ctx)
            end_time = time.time()
            
            total_duration = end_time - start_time
            sequential_time = simulated_latency * num_images
            
            # Verify results
            assert len(ctx.image_assessments) == num_images
            
            # Check that subject preservation was assessed (indicates reference image was used)
            for assessment in ctx.image_assessments:
                scores = assessment.get("assessment_scores", {})
                assert "subject_preservation" in scores, "Should assess subject preservation with reference image"
            
            # Verify parallel execution
            max_acceptable_time = simulated_latency + 0.8  # Allow overhead for reference image processing
            assert total_duration < max_acceptable_time, \
                f"With reference image, execution took {total_duration:.2f}s, expected < {max_acceptable_time}s"
            
            print(f"✅ Parallel execution with reference image verified! Duration: {total_duration:.2f}s")
            
    finally:
        if hasattr(ctx, '_temp_files'):
            for temp_file in ctx._temp_files:
                try:
                    os.unlink(temp_file)
                except OSError:
                    pass


@pytest.mark.asyncio 
async def test_error_handling_in_parallel_execution():
    """
    Test that errors in individual assessments don't break the parallel execution
    and that fallbacks work correctly.
    """
    num_images = 3
    
    ctx = create_mock_pipeline_context(num_images)
    
    try:
        # Mock API to fail on the second call but succeed on others
        call_count = 0
        async def mock_api_call_with_failure(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.1)  # Small delay
            
            if call_count == 2:  # Fail on second call
                raise Exception("Simulated API failure")
            else:
                return MockResponse(create_mock_assessment_response())
        
        with patch('churns.stages.image_assessment.base_llm_client_image_assessment') as mock_client, \
             patch('churns.stages.image_assessment.IMAGE_ASSESSMENT_MODEL_ID', 'gpt-4o'), \
             patch('churns.stages.image_assessment.IMAGE_ASSESSMENT_MODEL_PROVIDER', 'openai'), \
             patch('churns.stages.image_assessment.INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS', []):
            
            mock_client.chat.completions.create = AsyncMock(side_effect=mock_api_call_with_failure)
            
            await image_assessment_run(ctx)
            
            # Should still have all assessments (including fallbacks)
            assert len(ctx.image_assessments) == num_images
            
            # Check that we have both successful and fallback assessments
            successful_assessments = 0
            fallback_assessments = 0
            
            for assessment in ctx.image_assessments:
                if "assessment_scores" in assessment:
                    # Check if this looks like a fallback (simulated) assessment
                    justification = assessment.get("assessment_justification", {})
                    if any("Simulated assessment" in str(v) for v in justification.values()):
                        fallback_assessments += 1
                    else:
                        successful_assessments += 1
            
            print(f"✅ Error handling verified! Successful: {successful_assessments}, Fallbacks: {fallback_assessments}")
            assert successful_assessments >= 1, "Should have at least one successful assessment"
            assert fallback_assessments >= 1, "Should have at least one fallback assessment"
            
    finally:
        if hasattr(ctx, '_temp_files'):
            for temp_file in ctx._temp_files:
                try:
                    os.unlink(temp_file)
                except OSError:
                    pass


if __name__ == "__main__":
    # Run the tests directly
    asyncio.run(test_parallel_assessment_is_faster())
    asyncio.run(test_parallel_assessment_with_reference_image())
    asyncio.run(test_error_handling_in_parallel_execution())
    print("All parallelism tests completed successfully!") 