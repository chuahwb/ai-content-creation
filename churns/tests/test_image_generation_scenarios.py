"""
Test suite for enhanced image generation scenarios with multi-modal support.

This test file validates the new image generation functionality that supports:
1. Text-to-image generation (no input images)
2. Single image editing (reference image only)
3. Logo-only editing (logo as reference)
4. Multi-modal editing (reference image + logo)
5. Error handling and fallback mechanisms

Created as part of the IMAGE_GENERATION_ENHANCEMENT_PLAN implementation.
"""

import pytest
import asyncio
import os
import tempfile
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from pathlib import Path

# Import the functions we're testing
from churns.stages.image_generation import (
    generate_image,
    _generate_with_no_input_image,
    _generate_with_single_input_edit,
    _generate_with_multiple_inputs,
    run
)
from churns.pipeline.context import PipelineContext


class TestImageGenerationScenarios:
    """Test class for enhanced image generation scenarios."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock OpenAI client."""
        client = Mock()
        client.images = Mock()
        client.images.generate = AsyncMock()
        client.images.edit = AsyncMock()
        client.chat = Mock()
        client.chat.completions = Mock()
        client.chat.completions.create = AsyncMock()
        return client

    @pytest.fixture
    def temp_run_directory(self):
        """Create a temporary directory for test runs."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    @pytest.fixture
    def sample_image_path(self, temp_run_directory):
        """Create a sample image file for testing."""
        image_path = os.path.join(temp_run_directory, "test_image.jpg")
        # Create a minimal fake image file
        with open(image_path, "wb") as f:
            f.write(b"fake_image_data")
        return image_path

    @pytest.fixture
    def sample_logo_path(self, temp_run_directory):
        """Create a sample logo file for testing."""
        logo_path = os.path.join(temp_run_directory, "test_logo.png")
        # Create a minimal fake logo file
        with open(logo_path, "wb") as f:
            f.write(b"fake_logo_data")
        return logo_path

    @pytest.fixture
    def mock_image_response(self):
        """Create a mock image API response."""
        mock_response = Mock()
        mock_response.data = [Mock()]
        mock_response.data[0].b64_json = "fake_base64_data"
        mock_response.data[0].url = None
        return mock_response

    @pytest.fixture
    def pipeline_context(self, temp_run_directory):
        """Create a test pipeline context."""
        ctx = PipelineContext(run_id="test_run_123")
        ctx.output_directory = temp_run_directory
        return ctx

    async def test_text_to_image_generation_no_inputs(self, mock_client, temp_run_directory, mock_image_response):
        """Test Case 1: Standard text-to-image generation with no input images."""
        mock_client.images.generate.return_value = mock_image_response
        
        with patch('churns.stages.image_generation.image_gen_client', mock_client):
            with patch('churns.stages.image_generation.IMAGE_GENERATION_MODEL_ID', 'gpt-image-1'):
                status, result, tokens = await generate_image(
                    final_prompt="A beautiful sunset",
                    platform_aspect_ratio="1:1",
                    client=mock_client,
                    run_directory=temp_run_directory,
                    strategy_index=1,
                    reference_image_path=None,
                    logo_image_path=None
                )
        
        # Verify the standard generate API was called
        mock_client.images.generate.assert_called_once()
        assert status == "success"
        assert tokens > 0

    async def test_single_image_edit_reference_only(self, mock_client, temp_run_directory, sample_image_path, mock_image_response):
        """Test Case 2: Single image editing with reference image only."""
        mock_client.images.edit.return_value = mock_image_response
        
        with patch('churns.stages.image_generation.image_gen_client', mock_client):
            with patch('churns.stages.image_generation.IMAGE_GENERATION_MODEL_ID', 'gpt-image-1'):
                status, result, tokens = await generate_image(
                    final_prompt="Edit this image to be more colorful",
                    platform_aspect_ratio="1:1",
                    client=mock_client,
                    run_directory=temp_run_directory,
                    strategy_index=1,
                    reference_image_path=sample_image_path,
                    logo_image_path=None
                )
        
        # Verify the edit API was called
        mock_client.images.edit.assert_called_once()
        assert status == "success"
        assert tokens > 0

    async def test_logo_only_edit(self, mock_client, temp_run_directory, sample_logo_path, mock_image_response):
        """Test Case 4: Logo-only editing (logo as reference image)."""
        mock_client.images.edit.return_value = mock_image_response
        
        with patch('churns.stages.image_generation.image_gen_client', mock_client):
            with patch('churns.stages.image_generation.IMAGE_GENERATION_MODEL_ID', 'gpt-image-1'):
                status, result, tokens = await generate_image(
                    final_prompt="Adapt this logo for a festive campaign",
                    platform_aspect_ratio="1:1",
                    client=mock_client,
                    run_directory=temp_run_directory,
                    strategy_index=1,
                    reference_image_path=None,
                    logo_image_path=sample_logo_path
                )
        
        # Verify the edit API was called with logo as input
        mock_client.images.edit.assert_called_once()
        assert status == "success"
        assert tokens > 0

    async def test_multi_modal_reference_and_logo(self, mock_client, temp_run_directory, sample_image_path, sample_logo_path, mock_image_response):
        """Test Case 3: Multi-modal editing with both reference image and logo."""
        # The multi-modal function will fall back to single image edit
        mock_client.images.edit.return_value = mock_image_response
        
        with patch('churns.stages.image_generation.image_gen_client', mock_client):
            with patch('churns.stages.image_generation.IMAGE_GENERATION_MODEL_ID', 'gpt-image-1'):
                status, result, tokens = await generate_image(
                    final_prompt="Integrate the logo into the scene",
                    platform_aspect_ratio="1:1",
                    client=mock_client,
                    run_directory=temp_run_directory,
                    strategy_index=1,
                    reference_image_path=sample_image_path,
                    logo_image_path=sample_logo_path
                )
        
        # Should fall back to single image edit with reference image
        mock_client.images.edit.assert_called_once()
        assert status == "success"
        assert tokens > 0

    async def test_multi_modal_api_call_structure(self, mock_client, temp_run_directory, sample_image_path, sample_logo_path):
        """Test Case 3b: Verify multi-modal API call structure with proper images.edit endpoint."""
        # Mock successful multi-modal response
        mock_image_response = Mock()
        mock_image_response.data = [Mock()]
        mock_image_response.data[0].b64_json = "fake_base64_data"
        mock_client.images.edit.return_value = mock_image_response
        
        with patch('churns.stages.image_generation.image_gen_client', mock_client):
            with patch('churns.stages.image_generation.IMAGE_GENERATION_MODEL_ID', 'gpt-image-1'):
                status, result, tokens = await _generate_with_multiple_inputs(
                    final_prompt="Integrate the logo into the scene",
                    platform_aspect_ratio="1:1",
                    client=mock_client,
                    run_directory=temp_run_directory,
                    strategy_index=1,
                    reference_image_path=sample_image_path,
                    logo_image_path=sample_logo_path,
                    image_quality_setting="medium"
                )
        
        # Verify the multi-modal images.edit API was called correctly
        mock_client.images.edit.assert_called_once()
        call_args = mock_client.images.edit.call_args
        
        # Verify the API call structure
        assert call_args.kwargs['model'] == 'gpt-image-1'
        assert call_args.kwargs['prompt'] == "Integrate the logo into the scene"
        assert call_args.kwargs['n'] == 1
        assert call_args.kwargs['size'] == "1024x1024"
        assert call_args.kwargs['quality'] == "medium"
        assert call_args.kwargs['input_fidelity'] == "high"
        # Note: The 'image' parameter would contain file objects, harder to test directly
        
        assert status == "success"
        assert tokens > 0

    async def test_multi_modal_fallback_mechanism(self, mock_client, temp_run_directory, sample_image_path, sample_logo_path):
        """Test Case 5: Multi-modal API failure triggers fallback to single image edit."""
        # Make the multi-modal API call fail with APIStatusError (indicating feature not available)
        from openai import APIStatusError
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": {"message": "Multi-image editing not supported"}}
        api_error = APIStatusError("Multi-image editing not supported", response=mock_response, body=None)
        
        # Mock multi-modal call to fail
        mock_client.images.edit.side_effect = [api_error, None]  # First call fails, second (fallback) succeeds
        
        # Mock successful fallback response
        mock_image_response = Mock()
        mock_image_response.data = [Mock()]
        mock_image_response.data[0].b64_json = "fake_base64_data"
        mock_client.images.edit.side_effect = [api_error, mock_image_response]  # Fail, then succeed
        
        with patch('churns.stages.image_generation.image_gen_client', mock_client):
            with patch('churns.stages.image_generation.IMAGE_GENERATION_MODEL_ID', 'gpt-image-1'):
                status, result, tokens = await _generate_with_multiple_inputs(
                    final_prompt="Integrate the logo into the scene",
                    platform_aspect_ratio="1:1",
                    client=mock_client,
                    run_directory=temp_run_directory,
                    strategy_index=1,
                    reference_image_path=sample_image_path,
                    logo_image_path=sample_logo_path,
                    image_quality_setting="medium"
                )
        
        # Verify fallback was used (images.edit called twice - once for multi-modal, once for fallback)
        assert mock_client.images.edit.call_count == 2
        assert status == "success"
        assert tokens > 0

    async def test_error_handling_missing_files(self, mock_client, temp_run_directory):
        """Test error handling when image files are missing."""
        with patch('churns.stages.image_generation.image_gen_client', mock_client):
            with patch('churns.stages.image_generation.IMAGE_GENERATION_MODEL_ID', 'gpt-image-1'):
                status, result, tokens = await generate_image(
                    final_prompt="Edit this missing image",
                    platform_aspect_ratio="1:1",
                    client=mock_client,
                    run_directory=temp_run_directory,
                    strategy_index=1,
                    reference_image_path="/nonexistent/path.jpg",
                    logo_image_path=None
                )
        
        assert status == "error"
        assert "not found" in result.lower()
        assert tokens > 0

    async def test_run_function_routing_logic(self, mock_client, temp_run_directory, sample_image_path, sample_logo_path):
        """Test the run function properly routes to different scenarios."""
        # Create a context with both reference and logo
        ctx = PipelineContext(run_id="test_routing")
        ctx.final_assembled_prompts = [
            {
                "index": 1,
                "prompt": "Test prompt",
                "assembly_type": "complex_edit",
                "has_reference": True,
                "has_logo": True
            }
        ]
        ctx.target_platform = {"resolution_details": {"aspect_ratio": "1:1"}}
        ctx.image_reference = {"saved_image_path_in_run_dir": sample_image_path}
        ctx.brand_kit = {"saved_logo_path_in_run_dir": sample_logo_path}
        
        # Mock successful response
        mock_image_response = Mock()
        mock_image_response.data = [Mock()]
        mock_image_response.data[0].b64_json = "fake_base64_data"
        mock_client.images.edit.return_value = mock_image_response
        
        with patch('churns.stages.image_generation.image_gen_client', mock_client):
            with patch('churns.stages.image_generation.IMAGE_GENERATION_MODEL_ID', 'gpt-image-1'):
                await run(ctx)
        
        # Verify results were stored
        assert hasattr(ctx, 'generated_image_results')
        assert len(ctx.generated_image_results) == 1
        assert ctx.generated_image_results[0]["status"] == "success"


@pytest.mark.asyncio
class TestImageGenerationIntegration:
    """Integration tests for the enhanced image generation pipeline."""

    async def test_full_pipeline_with_brand_kit(self):
        """Test the full pipeline integration with brand kit and reference image."""
        # This would be a more comprehensive integration test
        # Testing the full flow from context setup to final results
        pass

    async def test_cost_calculation_multi_modal(self):
        """Test cost calculation for multi-modal scenarios."""
        # This would test the updated cost calculation logic
        # in background_tasks.py for multiple input images
        pass


if __name__ == "__main__":
    pytest.main([__file__]) 