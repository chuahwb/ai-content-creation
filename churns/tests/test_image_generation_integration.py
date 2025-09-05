"""
Integration tests for image generation stage with provider switching.

Tests the full pipeline integration with both OpenAI and Gemini providers,
including client injection and configuration switching.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path

from churns.pipeline.executor import PipelineExecutor
from churns.pipeline.context import PipelineContext
from churns.core.client_config import ClientConfig
import churns.stages.image_generation as img_gen_stage


class TestImageGenerationStageIntegration:
    """Test image generation stage with different providers."""
    
    @pytest.fixture
    def mock_run_context(self, tmp_path):
        """Create a mock pipeline context with run directory."""
        ctx = PipelineContext(
            run_id="test_run_123",
            output_directory=str(tmp_path / "test_run")
        )
        
        # Create output directory
        Path(ctx.output_directory).mkdir(parents=True, exist_ok=True)
        
        # Add mock assembled prompts
        ctx.final_assembled_prompts = [
            {
                "index": 0,
                "prompt": "A beautiful sunset over mountains",
                "platform_aspect_ratio": "1:1",
                "reference_image_path": None,
                "logo_image_path": None
            }
        ]
        
        return ctx
    
    @pytest.fixture
    def mock_openai_client(self):
        """Create a mock OpenAI client."""
        client = Mock()
        
        # Mock successful image generation response
        mock_response = Mock()
        mock_response.data = [Mock()]
        mock_response.data[0].b64_json = "base64_image_data"
        mock_response.data[0].url = None
        
        client.images.generate.return_value = mock_response
        return client
    
    @pytest.fixture
    def mock_gemini_client(self):
        """Create a mock Gemini client."""
        client = Mock()
        
        # Mock successful Gemini response
        mock_inline_data = Mock()
        mock_inline_data.data = "base64_image_data"
        
        mock_part = Mock()
        mock_part.inline_data = mock_inline_data
        
        mock_content = Mock()
        mock_content.parts = [mock_part]
        
        mock_candidate = Mock()
        mock_candidate.content = mock_content
        
        mock_response = Mock()
        mock_response.candidates = [mock_candidate]
        
        client.models.generate_content.return_value = mock_response
        return client
    
    @patch('churns.stages.image_generation._process_image_response')
    async def test_openai_provider_integration(
        self, mock_process_response, mock_run_context, mock_openai_client
    ):
        """Test full integration with OpenAI provider."""
        # Mock successful image processing
        mock_process_response.return_value = ("success", "generated_image.png", 100)
        
        # Inject OpenAI configuration into stage
        img_gen_stage.image_gen_client = mock_openai_client
        img_gen_stage.image_gen_client_openai = mock_openai_client
        img_gen_stage.image_gen_client_gemini = None
        img_gen_stage.IMAGE_GENERATION_MODEL_ID = "gpt-image-1"
        img_gen_stage.IMAGE_GENERATION_MODEL_PROVIDER = "OpenAI"
        
        # Run the stage
        await img_gen_stage.run(mock_run_context)
        
        # Verify results
        assert hasattr(mock_run_context, 'generated_image_results')
        assert len(mock_run_context.generated_image_results) == 1
        
        result = mock_run_context.generated_image_results[0]
        assert result['status'] == 'success'
        assert result['result_path'] == 'generated_image.png'
        
        # Verify OpenAI client was called
        mock_openai_client.images.generate.assert_called_once()
    
    @patch('churns.stages.image_generation._process_image_response')
    async def test_gemini_provider_integration(
        self, mock_process_response, mock_run_context, mock_gemini_client
    ):
        """Test full integration with Gemini provider."""
        # Mock successful image processing
        mock_process_response.return_value = ("success", "generated_image.png", 100)
        
        # Inject Gemini configuration into stage
        img_gen_stage.image_gen_client = None  # OpenAI client not available
        img_gen_stage.image_gen_client_openai = None
        img_gen_stage.image_gen_client_gemini = mock_gemini_client
        img_gen_stage.IMAGE_GENERATION_MODEL_ID = "gemini-2.5-flash-image-preview"
        img_gen_stage.IMAGE_GENERATION_MODEL_PROVIDER = "Gemini"
        
        # Run the stage
        await img_gen_stage.run(mock_run_context)
        
        # Verify results
        assert hasattr(mock_run_context, 'generated_image_results')
        assert len(mock_run_context.generated_image_results) == 1
        
        result = mock_run_context.generated_image_results[0]
        assert result['status'] == 'success'
        assert result['result_path'] == 'generated_image.png'
        
        # Verify Gemini client was called
        mock_gemini_client.models.generate_content.assert_called_once()
        
        # Verify aspect ratio was added to prompt
        call_args = mock_gemini_client.models.generate_content.call_args
        contents = call_args.kwargs['contents']
        assert "1:1 aspect ratio" in contents[0]
    
    async def test_no_client_available_error(self, mock_run_context):
        """Test error handling when no client is available."""
        # No clients injected
        img_gen_stage.image_gen_client = None
        img_gen_stage.image_gen_client_openai = None
        img_gen_stage.image_gen_client_gemini = None
        img_gen_stage.IMAGE_GENERATION_MODEL_PROVIDER = "OpenAI"
        
        # Run the stage
        await img_gen_stage.run(mock_run_context)
        
        # Verify error results
        assert hasattr(mock_run_context, 'generated_image_results')
        assert len(mock_run_context.generated_image_results) == 1
        
        result = mock_run_context.generated_image_results[0]
        assert result['status'] == 'error'
        assert 'not available' in result['error_message']


class TestPipelineExecutorIntegration:
    """Test pipeline executor with image generation provider switching."""
    
    @pytest.fixture
    def mock_clients_openai(self, mock_openai_client):
        """Mock client configuration for OpenAI."""
        return {
            'image_gen_client': mock_openai_client,
            'image_gen_client_openai': mock_openai_client,
            'image_gen_client_gemini': None,
            'model_config': {
                'IMAGE_GENERATION_MODEL_ID': 'gpt-image-1',
                'IMAGE_GENERATION_MODEL_PROVIDER': 'OpenAI'
            }
        }
    
    @pytest.fixture
    def mock_clients_gemini(self, mock_gemini_client):
        """Mock client configuration for Gemini."""
        return {
            'image_gen_client': None,
            'image_gen_client_openai': None,
            'image_gen_client_gemini': mock_gemini_client,
            'model_config': {
                'IMAGE_GENERATION_MODEL_ID': 'gemini-2.5-flash-image-preview',
                'IMAGE_GENERATION_MODEL_PROVIDER': 'Gemini'
            }
        }
    
    @pytest.fixture
    def mock_openai_client(self):
        """Create a mock OpenAI client."""
        client = Mock()
        mock_response = Mock()
        mock_response.data = [Mock()]
        mock_response.data[0].b64_json = "base64_image_data"
        client.images.generate.return_value = mock_response
        return client
    
    @pytest.fixture
    def mock_gemini_client(self):
        """Create a mock Gemini client."""
        client = Mock()
        
        # Mock Gemini response structure
        mock_inline_data = Mock()
        mock_inline_data.data = "base64_image_data"
        
        mock_part = Mock()
        mock_part.inline_data = mock_inline_data
        
        mock_content = Mock()
        mock_content.parts = [mock_part]
        
        mock_candidate = Mock()
        mock_candidate.content = mock_content
        
        mock_response = Mock()
        mock_response.candidates = [mock_candidate]
        
        client.models.generate_content.return_value = mock_response
        return client
    
    @patch('churns.stages.image_generation._process_image_response')
    @patch('churns.stages.image_generation.IMAGE_GENERATION_MODEL_PROVIDER', 'OpenAI')
    async def test_executor_openai_injection(
        self, mock_process_response, mock_clients_openai, tmp_path
    ):
        """Test pipeline executor correctly injects OpenAI clients."""
        mock_process_response.return_value = ("success", "test.png", 100)
        
        # Mock the client injection directly in the stage
        with patch('churns.stages.image_generation.image_gen_client', mock_clients_openai['image_gen_client']):
            # Create executor for image generation only
            with patch('churns.pipeline.executor.PipelineExecutor._load_stage_config') as mock_load:
                mock_load.return_value = ['image_generation']
                
                executor = PipelineExecutor(mode="generation")
                
                # Create context
                ctx = PipelineContext(
                    run_id="test_run",
                    output_directory=str(tmp_path / "test_run")
                )
                Path(ctx.output_directory).mkdir(parents=True, exist_ok=True)
                
                ctx.final_assembled_prompts = [{
                    "index": 0,
                    "prompt": "Test prompt",
                    "platform_aspect_ratio": "1:1",
                    "reference_image_path": None,
                    "logo_image_path": None
                }]
                
                # Run executor
                await executor.run_async(ctx)
                
                # Verify OpenAI client was called (the mock client we provided)
                mock_clients_openai['image_gen_client'].images.generate.assert_called_once()
    
    @patch('churns.stages.image_generation._process_image_response')
    @patch('churns.stages.image_generation.IMAGE_GENERATION_MODEL_PROVIDER', 'Gemini')
    async def test_executor_gemini_injection(
        self, mock_process_response, mock_clients_gemini, tmp_path
    ):
        """Test pipeline executor correctly injects Gemini clients."""
        mock_process_response.return_value = ("success", "test.png", 100)
        
        # Mock the client injection directly in the stage
        with patch('churns.stages.image_generation.image_gen_client_gemini', mock_clients_gemini['image_gen_client_gemini']):
            # Create executor for image generation only
            with patch('churns.pipeline.executor.PipelineExecutor._load_stage_config') as mock_load:
                mock_load.return_value = ['image_generation']
                
                executor = PipelineExecutor(mode="generation")
                
                # Create context
                ctx = PipelineContext(
                    run_id="test_run",
                    output_directory=str(tmp_path / "test_run")
                )
                Path(ctx.output_directory).mkdir(parents=True, exist_ok=True)
                
                ctx.final_assembled_prompts = [{
                    "index": 0,
                    "prompt": "Test prompt",
                    "platform_aspect_ratio": "1:1",
                    "reference_image_path": None,
                    "logo_image_path": None
                }]
                
                # Run executor
                await executor.run_async(ctx)
                
                # Verify Gemini client was called (the mock client we provided)
                mock_clients_gemini['image_gen_client_gemini'].models.generate_content.assert_called_once()


class TestTokenCostManagerIntegration:
    """Test token cost manager integration with Gemini models."""
    
    def test_gemini_provider_detection(self):
        """Test provider detection for Gemini image models."""
        from churns.core.token_cost_manager import _get_provider_for_model
        
        # Test Gemini image model
        provider = _get_provider_for_model("gemini-2.5-flash-image-preview")
        assert provider == "google"
        
        # Test OpenAI image model  
        provider = _get_provider_for_model("gpt-image-1")
        assert provider == "openai"
        
        # Test fallback for unknown Gemini model
        provider = _get_provider_for_model("gemini-unknown-model")
        assert provider == "google"
    
    def test_gemini_pricing_lookup(self):
        """Test pricing lookup for Gemini image model."""
        from churns.core.token_cost_manager import get_token_cost_manager, TokenUsage
        from churns.core.constants import GEMINI_IMAGE_GENERATION_MODEL_ID
        
        manager = get_token_cost_manager()
        
        # Create mock usage for Gemini model
        usage = TokenUsage(
            prompt_tokens=100,
            completion_tokens=0,
            total_tokens=100,
            model=GEMINI_IMAGE_GENERATION_MODEL_ID,
            provider="google"
        )
        
        # Test cost calculation with mock image details
        image_details = {"count": 1, "resolution": "1024x1024", "quality": "default"}
        cost = manager.calculate_cost(usage, image_details)
        
        assert cost.model == GEMINI_IMAGE_GENERATION_MODEL_ID
        assert cost.provider == "google"
        assert cost.currency == "USD"
        # Should have some cost calculated based on our pricing config
        assert cost.total_cost > 0


if __name__ == "__main__":
    pytest.main([__file__])
