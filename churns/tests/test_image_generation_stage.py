"""
Tests for Stage 6: Image Generation

Tests the extraction of image generation functionality from the original monolith.
Validates that images are correctly generated using gpt-image-1 via OpenAI Images API.
"""

import pytest
import os
import tempfile
from unittest.mock import Mock, patch, mock_open
from churns.pipeline.context import PipelineContext
from churns.stages.image_generation import run, generate_image, map_aspect_ratio_to_size_for_api


class TestImageGenerationStage:
    """Test the image generation stage functionality."""
    
    def create_test_context(self, 
                          has_assembled_prompts=True,
                          has_image_client=True,
                          platform_aspect_ratio="1:1",
                          has_reference_image=False):
        """Create a test context for image generation."""
        ctx = PipelineContext()
        ctx.creativity_level = 2
        ctx.task_type = "2. Promotional Graphics & Announcements"
        ctx.target_platform = {
            "name": "Instagram Post (1:1 Square)",
            "resolution_details": {"width": 1080, "height": 1080, "aspect_ratio": platform_aspect_ratio}
        }
        
        if has_assembled_prompts:
            ctx.final_assembled_prompts = [
                {
                    "index": 0,
                    "prompt": "Gourmet burger with artisan toppings, 45-degree angle close-up shot, rustic wooden table background, warm appetizing natural light, rich browns and fresh greens color palette. Ensure the image strictly adheres to a 1:1 aspect ratio."
                },
                {
                    "index": 1,
                    "prompt": "Artisanal coffee latte with foam art, overhead view composition, marble counter background, soft morning lighting, cream and brown color tones. Ensure the image strictly adheres to a 1:1 aspect ratio."
                }
            ]
        else:
            ctx.final_assembled_prompts = []
            
        if has_image_client:
            ctx.image_generation_client = Mock()
        else:
            ctx.image_generation_client = None
            
        if has_reference_image:
            ctx.image_reference = {
                "filename": "reference_burger.jpg",
                "saved_image_path_in_run_dir": "/test/path/reference_burger.jpg"
            }
        else:
            ctx.image_reference = None
            
        # Set up a temporary output directory
        ctx.output_directory = tempfile.mkdtemp()
        
        return ctx
    
    def create_mock_openai_response(self, success=True, use_base64=True, use_url=False):
        """Create a mock OpenAI API response."""
        if not success:
            raise Exception("API Error")
            
        mock_response = Mock()
        mock_response.data = []
        
        if success:
            mock_image_data = Mock()
            
            if use_base64:
                # Create a simple fake base64 image data
                mock_image_data.b64_json = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
                mock_image_data.url = None
            elif use_url:
                mock_image_data.b64_json = None
                mock_image_data.url = "https://example.com/generated_image.png"
            else:
                mock_image_data.b64_json = None
                mock_image_data.url = None
                
            mock_response.data = [mock_image_data]
            
        return mock_response

    def test_successful_image_generation(self):
        """Test successful image generation for multiple strategies."""
        ctx = self.create_test_context()
        
        # Mock successful API responses
        ctx.image_generation_client.images.generate.side_effect = [
            self.create_mock_openai_response(success=True, use_base64=True),
            self.create_mock_openai_response(success=True, use_base64=True)
        ]
        
        # Run the stage
        run(ctx)
        
        # Verify results
        assert ctx.generated_image_results is not None
        assert len(ctx.generated_image_results) == 2
        
        # Check first result
        result1 = ctx.generated_image_results[0]
        assert result1["index"] == 0
        assert result1["status"] == "success"
        assert result1["result_path"] is not None
        assert result1["error_message"] is None
        assert "strategy_0_" in result1["result_path"]
        assert result1["result_path"].endswith(".png")
        
        # Check second result
        result2 = ctx.generated_image_results[1]
        assert result2["index"] == 1
        assert result2["status"] == "success"
        assert result2["result_path"] is not None
        assert result2["error_message"] is None
        
        # Verify API calls
        assert ctx.image_generation_client.images.generate.call_count == 2
        
        # Check API call parameters
        call_args = ctx.image_generation_client.images.generate.call_args_list[0][1]
        assert call_args["model"] == "gpt-image-1"
        assert call_args["size"] == "1024x1024"  # 1:1 aspect ratio
        assert call_args["quality"] == "medium"
        assert call_args["n"] == 1

    def test_image_generation_with_reference_image(self):
        """Test image generation with reference image (editing mode)."""
        ctx = self.create_test_context(has_reference_image=True)
        
        # Mock successful edit API response
        ctx.image_generation_client.images.edit.return_value = self.create_mock_openai_response(success=True, use_base64=True)
        
        # Mock file existence
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=b'fake_image_data')):
            
            # Run the stage
            run(ctx)
        
        # Verify results
        assert len(ctx.generated_image_results) == 2
        result = ctx.generated_image_results[0]
        assert result["status"] == "success"
        assert "edited_image_strategy_0" in result["result_path"]
        
        # Verify edit API was called instead of generate
        ctx.image_generation_client.images.edit.assert_called()
        ctx.image_generation_client.images.generate.assert_not_called()

    def test_image_generation_with_url_response(self):
        """Test image generation with URL response (fallback scenario)."""
        ctx = self.create_test_context()
        
        # Mock API response with URL
        ctx.image_generation_client.images.generate.return_value = self.create_mock_openai_response(success=True, use_url=True)
        
        # Mock successful HTTP download
        mock_response = Mock()
        mock_response.iter_content.return_value = [b'fake_image_data']
        mock_response.raise_for_status.return_value = None
        
        with patch('requests.get', return_value=mock_response):
            # Run the stage
            run(ctx)
        
        # Verify results
        assert len(ctx.generated_image_results) == 2
        result = ctx.generated_image_results[0]
        assert result["status"] == "success"
        assert result["result_path"] is not None

    def test_no_image_client_configured(self):
        """Test behavior when no image generation client is configured."""
        ctx = self.create_test_context(has_image_client=False)
        
        # Run the stage
        run(ctx)
        
        # Verify results
        assert ctx.generated_image_results == []
        assert any("Image Generation Client not configured" in log for log in ctx.logs)

    def test_no_assembled_prompts(self):
        """Test behavior when no assembled prompts are available."""
        ctx = self.create_test_context(has_assembled_prompts=False)
        
        # Run the stage
        run(ctx)
        
        # Verify results
        assert ctx.generated_image_results == []
        assert any("No assembled prompts available" in log for log in ctx.logs)

    def test_prompt_assembly_error_handling(self):
        """Test handling of prompts that start with 'Error:'."""
        ctx = self.create_test_context()
        ctx.final_assembled_prompts = [
            {
                "index": 0,
                "prompt": "Error: Invalid visual concept data for assembly."
            }
        ]
        
        # Run the stage
        run(ctx)
        
        # Verify results
        assert len(ctx.generated_image_results) == 1
        result = ctx.generated_image_results[0]
        assert result["status"] == "error"
        assert result["result_path"] is None
        assert "Invalid visual concept data" in result["error_message"]

    def test_api_connection_error(self):
        """Test handling of API connection errors."""
        ctx = self.create_test_context()
        
        # Mock API connection error
        ctx.image_generation_client.images.generate.side_effect = Exception("Connection error")
        
        # Run the stage
        run(ctx)
        
        # Verify error handling
        assert len(ctx.generated_image_results) == 2
        for result in ctx.generated_image_results:
            assert result["status"] == "error"
            assert "error" in result["error_message"].lower()

    def test_different_aspect_ratios(self):
        """Test image generation with different platform aspect ratios."""
        # Test vertical aspect ratio (9:16)
        ctx = self.create_test_context(platform_aspect_ratio="9:16")
        ctx.image_generation_client.images.generate.return_value = self.create_mock_openai_response(success=True, use_base64=True)
        
        run(ctx)
        
        # Verify API was called with correct size
        call_args = ctx.image_generation_client.images.generate.call_args_list[0][1]
        assert call_args["size"] == "1024x1536"  # Mapped from 9:16
        
        # Test horizontal aspect ratio (16:9)
        ctx2 = self.create_test_context(platform_aspect_ratio="16:9")
        ctx2.image_generation_client.images.generate.return_value = self.create_mock_openai_response(success=True, use_base64=True)
        
        run(ctx2)
        
        # Verify API was called with correct size
        call_args2 = ctx2.image_generation_client.images.generate.call_args_list[0][1]
        assert call_args2["size"] == "1536x1024"  # Mapped from 16:9

    def test_image_generation_logging(self):
        """Test that appropriate log messages are generated."""
        ctx = self.create_test_context()
        ctx.image_generation_client.images.generate.return_value = self.create_mock_openai_response(success=True, use_base64=True)
        
        # Run the stage
        run(ctx)
        
        # Verify logging
        log_messages = [log for log in ctx.logs]
        assert any("Starting Image Generation stage" in log for log in log_messages)
        assert any("Generating images for 2 assembled prompts" in log for log in log_messages)
        assert any("✅ Image generated successfully" in log for log in log_messages)
        assert any("Image Generation stage completed" in log for log in log_messages)
        assert any("Generated 2/2 images successfully" in log for log in log_messages)


class TestImageGenerationHelpers:
    """Test helper functions for image generation."""
    
    def test_map_aspect_ratio_to_size_for_api(self):
        """Test aspect ratio to API size mapping."""
        ctx = Mock()
        
        # Test square ratio
        assert map_aspect_ratio_to_size_for_api("1:1", ctx) == "1024x1024"
        
        # Test vertical ratios
        assert map_aspect_ratio_to_size_for_api("9:16", ctx) == "1024x1536"
        assert map_aspect_ratio_to_size_for_api("3:4", ctx) == "1024x1536"
        assert map_aspect_ratio_to_size_for_api("2:3", ctx) == "1024x1536"
        
        # Test horizontal ratios
        assert map_aspect_ratio_to_size_for_api("16:9", ctx) == "1536x1024"
        assert map_aspect_ratio_to_size_for_api("1.91:1", ctx) == "1536x1024"
        
        # Test unsupported ratio (should default to square)
        assert map_aspect_ratio_to_size_for_api("4:3", ctx) == "1024x1024"
        
    def test_generate_image_function_validation(self):
        """Test input validation in generate_image function."""
        # Test with no client
        status, result, tokens = generate_image("test prompt", "1:1", None, "/tmp", 0)
        assert status == "error"
        assert "client not available" in result
        
        # Test with invalid prompt
        mock_client = Mock()
        status, result, tokens = generate_image("Error: invalid", "1:1", mock_client, "/tmp", 0)
        assert status == "error"
        assert "Invalid final prompt" in result
        
        # Test with invalid directory
        status, result, tokens = generate_image("test prompt", "1:1", mock_client, "/nonexistent", 0)
        assert status == "error"
        assert "Invalid run_directory" in result

    def test_generate_image_with_context_logging(self):
        """Test that generate_image properly logs via context when provided."""
        ctx = PipelineContext()
        mock_client = Mock()
        
        # Test with unsupported aspect ratio to trigger logging
        with patch('os.path.isdir', return_value=True):
            status, result, tokens = generate_image("test prompt", "4:3", mock_client, "/tmp", 0, ctx=ctx)
        
        # Verify context logging was used
        assert len(ctx.logs) > 0
        assert any("Warning: Unsupported aspect ratio" in log for log in ctx.logs)


class TestImageGenerationIntegration:
    """Integration tests for the image generation stage."""
    
    def test_end_to_end_image_generation_flow(self):
        """Test the complete flow from assembled prompts to generated images."""
        ctx = PipelineContext()
        
        # Set up complete context with all required data
        ctx.final_assembled_prompts = [
            {
                "index": 0,
                "prompt": "Professional food photography of a gourmet burger",
                "assembly_type": "full_generation",
                "platform_aspect_ratio": "1:1",
                "supported_aspect_ratio": "1:1"
            }
        ]
        
        ctx.target_platform = {
            "name": "Instagram Post (1:1 Square)",
            "resolution_details": {"aspect_ratio": "1:1"}
        }
        
        ctx.image_generation_client = Mock()
        ctx.image_generation_client.images.generate.return_value = Mock(
            data=[Mock(
                b64_json="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
                url=None
            )]
        )
        
        ctx.output_directory = tempfile.mkdtemp()
        
        # Run the stage
        run(ctx)
        
        # Verify complete results
        assert len(ctx.generated_image_results) == 1
        result = ctx.generated_image_results[0]
        assert result["status"] == "success"
        assert result["index"] == 0
        assert result["result_path"].endswith(".png")
        assert os.path.exists(result["result_path"])
        
        # Verify API call
        ctx.image_generation_client.images.generate.assert_called_once()
        call_kwargs = ctx.image_generation_client.images.generate.call_args.kwargs
        assert call_kwargs["model"] == "gpt-image-1"
        assert call_kwargs["prompt"] == "Professional food photography of a gourmet burger"
        assert call_kwargs["size"] == "1024x1024" 