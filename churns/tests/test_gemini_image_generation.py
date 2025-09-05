"""
Unit tests for Gemini image generation integration.

Tests the provider-aware routing, Gemini adapters, and response normalization
without requiring actual API calls.
"""

import pytest
import asyncio
import base64
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

# Import the functions we want to test
from churns.stages.image_generation import (
    _add_aspect_ratio_to_prompt,
    _normalize_gemini_response,
    _handle_gemini_api_error,
    _OpenAIStyleResponse,
    _OpenAIStyleImageData,
    _gemini_generate_with_no_input_image,
    _gemini_generate_with_single_input_edit,
    _gemini_generate_with_multiple_inputs,
    generate_image
)
from churns.pipeline.context import PipelineContext


class TestAspectRatioHandling:
    """Test aspect ratio prompt modification for Gemini."""
    
    def test_aspect_ratio_square(self):
        """Test 1:1 aspect ratio directive."""
        prompt = "Generate a beautiful landscape"
        result = _add_aspect_ratio_to_prompt(prompt, "1:1")
        assert "1:1 aspect ratio (square)" in result
        assert prompt in result
    
    def test_aspect_ratio_vertical(self):
        """Test vertical aspect ratio directive."""
        prompt = "Generate a portrait"
        result = _add_aspect_ratio_to_prompt(prompt, "9:16")
        assert "9:16 aspect ratio (vertical)" in result
        assert prompt in result
    
    def test_aspect_ratio_horizontal(self):
        """Test horizontal aspect ratio directive."""
        prompt = "Generate a landscape"
        result = _add_aspect_ratio_to_prompt(prompt, "16:9")
        assert "16:9 aspect ratio (horizontal)" in result
        assert prompt in result
    
    def test_aspect_ratio_unknown(self):
        """Test unknown aspect ratio falls back to square."""
        prompt = "Generate an image"
        result = _add_aspect_ratio_to_prompt(prompt, "unknown")
        assert "1:1 aspect ratio (square)" in result
        assert prompt in result


class TestGeminiResponseNormalization:
    """Test Gemini response normalization to OpenAI format."""
    
    def test_normalize_valid_response(self):
        """Test normalization of valid Gemini response."""
        # Mock Gemini response structure
        mock_inline_data = Mock()
        mock_inline_data.data = "base64imagedata"
        
        mock_part = Mock()
        mock_part.inline_data = mock_inline_data
        
        mock_content = Mock()
        mock_content.parts = [mock_part]
        
        mock_candidate = Mock()
        mock_candidate.content = mock_content
        
        mock_response = Mock()
        mock_response.candidates = [mock_candidate]
        
        # Test normalization
        normalized = _normalize_gemini_response(mock_response)
        
        assert isinstance(normalized, _OpenAIStyleResponse)
        assert len(normalized.data) == 1
        assert normalized.data[0].b64_json == "base64imagedata"
        assert normalized.data[0].url is None
    
    def test_normalize_no_image_data(self):
        """Test normalization when no image data is found."""
        mock_response = Mock()
        mock_response.candidates = []
        
        with pytest.raises(ValueError, match="No image data found"):
            _normalize_gemini_response(mock_response)
    
    def test_normalize_malformed_response(self):
        """Test normalization with malformed response."""
        mock_response = Mock()
        mock_response.candidates = None
        
        with pytest.raises(ValueError, match="Failed to normalize"):
            _normalize_gemini_response(mock_response)


class TestGeminiErrorHandling:
    """Test Gemini API error handling."""
    
    def test_quota_error(self):
        """Test quota exceeded error mapping."""
        error = Exception("quota exceeded")
        status, message, tokens = _handle_gemini_api_error(error, "generation", 100)
        
        assert status == "error"
        assert "quota exceeded" in message
        assert tokens == 100
    
    def test_safety_error(self):
        """Test safety filter error mapping."""
        error = Exception("content blocked by safety filters")
        status, message, tokens = _handle_gemini_api_error(error, "generation", 100)
        
        assert status == "error"
        assert "safety filters" in message
        assert tokens == 100
    
    def test_generic_error(self):
        """Test generic error mapping."""
        error = Exception("some random error")
        status, message, tokens = _handle_gemini_api_error(error, "generation", 100)
        
        assert status == "error"
        assert "some random error" in message
        assert tokens == 100


class TestGeminiGenerationFunctions:
    """Test Gemini image generation functions with mocked clients."""
    
    @pytest.fixture
    def mock_context(self):
        """Create a mock pipeline context."""
        ctx = Mock(spec=PipelineContext)
        ctx.log = Mock()
        return ctx
    
    @pytest.fixture
    def temp_run_dir(self, tmp_path):
        """Create a temporary run directory."""
        run_dir = tmp_path / "test_run"
        run_dir.mkdir()
        return str(run_dir)
    
    @pytest.fixture
    def mock_image_file(self, tmp_path):
        """Create a mock image file."""
        image_path = tmp_path / "test_image.png"
        # Create a minimal PNG file
        png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x01\x00\x00\x00\x01\x00\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01\xdd\xcc\xdb\x00\x00\x00\x00IEND\xaeB`\x82'
        image_path.write_bytes(png_data)
        return str(image_path)
    
    @patch('churns.stages.image_generation.image_gen_client_gemini')
    @patch('churns.stages.image_generation._calculate_comprehensive_tokens')
    @patch('churns.stages.image_generation._process_image_response')
    async def test_gemini_no_input_generation(
        self, mock_process, mock_calc_tokens, mock_client, 
        mock_context, temp_run_dir
    ):
        """Test Gemini text-to-image generation."""
        # Setup mocks
        mock_calc_tokens.return_value = {"total_tokens": 100}
        mock_process.return_value = ("success", "test_image.png", 100)
        
        mock_response = Mock()
        mock_client.models.generate_content = Mock(return_value=mock_response)
        
        with patch('churns.stages.image_generation._normalize_gemini_response') as mock_normalize:
            mock_normalize.return_value = _OpenAIStyleResponse("base64data")
            
            result = await _gemini_generate_with_no_input_image(
                "test prompt", "1:1", temp_run_dir, 0, "medium", mock_context
            )
        
        assert result[0] == "success"
        assert result[1] == "test_image.png"
        assert result[2] == 100
        
        # Verify the client was called with aspect ratio modified prompt
        mock_client.models.generate_content.assert_called_once()
        call_args = mock_client.models.generate_content.call_args
        assert "1:1 aspect ratio" in call_args.kwargs['contents'][0]
    
    @patch('churns.stages.image_generation.image_gen_client_gemini')
    @patch('churns.stages.image_generation._calculate_comprehensive_tokens')
    @patch('churns.stages.image_generation._process_image_response')
    async def test_gemini_single_input_edit(
        self, mock_process, mock_calc_tokens, mock_client,
        mock_context, temp_run_dir, mock_image_file
    ):
        """Test Gemini single image editing."""
        # Setup mocks
        mock_calc_tokens.return_value = {"total_tokens": 150}
        mock_process.return_value = ("success", "edited_image.png", 150)
        
        mock_response = Mock()
        mock_client.models.generate_content = Mock(return_value=mock_response)
        
        with patch('churns.stages.image_generation._normalize_gemini_response') as mock_normalize:
            mock_normalize.return_value = _OpenAIStyleResponse("base64data")
            
            result = await _gemini_generate_with_single_input_edit(
                "edit this image", "1:1", temp_run_dir, 0, 
                mock_image_file, "medium", mock_context
            )
        
        assert result[0] == "success"
        assert result[1] == "edited_image.png"
        assert result[2] == 150
        
        # Verify the client was called with image data
        mock_client.models.generate_content.assert_called_once()
        call_args = mock_client.models.generate_content.call_args
        contents = call_args.kwargs['contents']
        assert len(contents) == 2  # prompt + image
        assert "inline_data" in contents[1]
    
    @patch('churns.stages.image_generation.image_gen_client_gemini')
    @patch('churns.stages.image_generation._calculate_comprehensive_tokens')
    @patch('churns.stages.image_generation._process_image_response')
    async def test_gemini_multiple_input_edit(
        self, mock_process, mock_calc_tokens, mock_client,
        mock_context, temp_run_dir, mock_image_file
    ):
        """Test Gemini multi-image editing."""
        # Setup mocks
        mock_calc_tokens.return_value = {"total_tokens": 200}
        mock_process.return_value = ("success", "multi_edited_image.png", 200)
        
        mock_response = Mock()
        mock_client.models.generate_content = Mock(return_value=mock_response)
        
        # Create second mock image
        logo_path = Path(mock_image_file).parent / "logo.png"
        logo_path.write_bytes(Path(mock_image_file).read_bytes())
        
        with patch('churns.stages.image_generation._normalize_gemini_response') as mock_normalize:
            mock_normalize.return_value = _OpenAIStyleResponse("base64data")
            
            result = await _gemini_generate_with_multiple_inputs(
                "combine these images", "1:1", temp_run_dir, 0,
                mock_image_file, str(logo_path), "medium", mock_context
            )
        
        assert result[0] == "success"
        assert result[1] == "multi_edited_image.png"
        assert result[2] == 200
        
        # Verify the client was called with multiple images
        mock_client.models.generate_content.assert_called_once()
        call_args = mock_client.models.generate_content.call_args
        contents = call_args.kwargs['contents']
        assert len(contents) == 3  # prompt + 2 images
        assert "inline_data" in contents[1]
        assert "inline_data" in contents[2]
    
    @patch('churns.stages.image_generation.image_gen_client_gemini', None)
    async def test_gemini_no_client_error(self, mock_context, temp_run_dir):
        """Test error when Gemini client is not available."""
        result = await _gemini_generate_with_no_input_image(
            "test prompt", "1:1", temp_run_dir, 0, "medium", mock_context
        )
        
        assert result[0] == "error"
        assert "not available" in result[1]


class TestProviderRouting:
    """Test provider-aware routing in the main generate_image function."""
    
    @pytest.fixture
    def mock_context(self):
        """Create a mock pipeline context."""
        ctx = Mock(spec=PipelineContext)
        ctx.log = Mock()
        return ctx
    
    @pytest.fixture
    def temp_run_dir(self, tmp_path):
        """Create a temporary run directory."""
        run_dir = tmp_path / "test_run"
        run_dir.mkdir()
        return str(run_dir)
    
    @patch('churns.stages.image_generation.IMAGE_GENERATION_MODEL_PROVIDER', 'Gemini')
    @patch('churns.stages.image_generation._gemini_generate_with_no_input_image')
    async def test_route_to_gemini_generation(
        self, mock_gemini_func, mock_context, temp_run_dir
    ):
        """Test routing to Gemini for text-to-image generation."""
        mock_gemini_func.return_value = ("success", "test.png", 100)
        
        result = await generate_image(
            "test prompt", "1:1", None, temp_run_dir, 0,
            ctx=mock_context
        )
        
        assert result[0] == "success"
        mock_gemini_func.assert_called_once()
    
    @patch('churns.stages.image_generation.IMAGE_GENERATION_MODEL_PROVIDER', 'OpenAI')
    @patch('churns.stages.image_generation._generate_with_no_input_image')
    async def test_route_to_openai_generation(
        self, mock_openai_func, mock_context, temp_run_dir
    ):
        """Test routing to OpenAI for text-to-image generation."""
        mock_openai_func.return_value = ("success", "test.png", 100)
        
        mock_client = Mock()
        result = await generate_image(
            "test prompt", "1:1", mock_client, temp_run_dir, 0,
            ctx=mock_context
        )
        
        assert result[0] == "success"
        mock_openai_func.assert_called_once()
    
    @patch('churns.stages.image_generation.IMAGE_GENERATION_MODEL_PROVIDER', None)
    @patch('churns.stages.image_generation._generate_with_no_input_image')
    async def test_default_to_openai(
        self, mock_openai_func, mock_context, temp_run_dir
    ):
        """Test default routing to OpenAI when provider is None."""
        mock_openai_func.return_value = ("success", "test.png", 100)
        
        mock_client = Mock()
        result = await generate_image(
            "test prompt", "1:1", mock_client, temp_run_dir, 0,
            ctx=mock_context
        )
        
        assert result[0] == "success"
        mock_openai_func.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__])
