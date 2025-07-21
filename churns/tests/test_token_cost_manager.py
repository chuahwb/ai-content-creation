"""
Test suite for the token cost manager, including multi-modal image generation scenarios.

This test file validates the token cost calculation functionality for:
1. Standard LLM usage
2. Single image input scenarios  
3. Multi-modal image generation with multiple input images
4. Cost breakdown calculations

Created as part of the IMAGE_GENERATION_ENHANCEMENT_PLAN implementation.
"""

import pytest
from unittest.mock import Mock, patch
from churns.core.token_cost_manager import TokenUsage, TokenCostManager, CostBreakdown


class TestTokenCostManager:
    """Test class for token cost management functionality."""

    @pytest.fixture
    def token_manager(self):
        """Create a token cost manager instance."""
        return TokenCostManager()

    def test_basic_token_usage_creation(self):
        """Test basic TokenUsage object creation."""
        usage = TokenUsage(
            prompt_tokens=100,
            completion_tokens=50,
            total_tokens=150,
            model="gpt-4",
            provider="openai"
        )
        
        assert usage.prompt_tokens == 100
        assert usage.completion_tokens == 50
        assert usage.total_tokens == 150
        assert usage.model == "gpt-4"
        assert usage.provider == "openai"

    def test_single_image_token_calculation(self, token_manager):
        """Test token calculation for single image input."""
        # Test with a standard image size
        tokens = token_manager.calculate_image_tokens(
            width=1024,
            height=1024,
            model_id="gpt-4-vision-preview"
        )
        
        assert tokens > 0
        assert isinstance(tokens, int)

    def test_multi_modal_image_generation_cost_calculation(self, token_manager):
        """Test cost calculation for multi-modal image generation with multiple input images."""
        # Create a token usage object for multi-modal scenario
        usage = TokenUsage(
            prompt_tokens=1500,  # 500 text tokens + 500 ref image tokens + 500 logo tokens
            completion_tokens=0,  # Image generation doesn't have completion tokens
            total_tokens=1500,
            image_tokens=1000,  # 500 + 500 for two input images
            text_tokens=500,  # Original text prompt
            image_count=2,  # Reference image + logo
            model="gpt-image-1",
            provider="openai"
        )
        
        image_details = {
            "count": 1,  # One output image
            "resolution": "1024x1024",
            "quality": "medium",
            "input_images": 2  # Two input images
        }
        
        cost_breakdown = token_manager.calculate_cost(usage, image_details)
        
        # Verify cost calculation includes input image tokens
        assert cost_breakdown.total_cost > 0
        assert usage.image_tokens == 1000
        assert usage.text_tokens == 500
        assert usage.total_tokens == 1500
        assert usage.image_count == 2
        
        # Verify the cost breakdown includes proper categorization
        assert cost_breakdown.model == "gpt-image-1"
        assert cost_breakdown.provider == "openai"

    def test_multiple_input_images_token_calculation(self, token_manager):
        """Test token calculation when multiple images are provided as input."""
        # Calculate tokens for reference image (1024x1024)
        ref_tokens = token_manager.calculate_image_tokens(
            width=1024,
            height=1024,
            model_id="gpt-image-1"
        )
        
        # Calculate tokens for logo image (512x512)
        logo_tokens = token_manager.calculate_image_tokens(
            width=512,
            height=512,
            model_id="gpt-image-1"
        )
        
        # Total input image tokens
        total_image_tokens = ref_tokens + logo_tokens
        
        # Create usage with combined tokens
        text_tokens = 200  # Text prompt tokens
        total_tokens = text_tokens + total_image_tokens
        
        usage = TokenUsage(
            prompt_tokens=total_tokens,
            completion_tokens=0,
            total_tokens=total_tokens,
            image_tokens=total_image_tokens,
            text_tokens=text_tokens,
            image_count=2,
            model="gpt-image-1",
            provider="openai"
        )
        
        # Verify token distribution
        assert usage.image_tokens == total_image_tokens
        assert usage.text_tokens == text_tokens
        assert usage.total_tokens == text_tokens + total_image_tokens
        assert usage.image_count == 2

    def test_cost_breakdown_structure(self, token_manager):
        """Test the structure of cost breakdown for multi-modal scenarios."""
        usage = TokenUsage(
            prompt_tokens=1000,
            completion_tokens=0,
            total_tokens=1000,
            image_tokens=600,
            text_tokens=400,
            image_count=2,
            model="gpt-image-1",
            provider="openai"
        )
        
        image_details = {
            "count": 1,
            "resolution": "1024x1024",
            "quality": "medium",
            "input_images": 2
        }
        
        cost_breakdown = token_manager.calculate_cost(usage, image_details)
        
        # Verify cost breakdown structure
        assert hasattr(cost_breakdown, 'input_cost')
        assert hasattr(cost_breakdown, 'output_cost')
        assert hasattr(cost_breakdown, 'image_input_cost')
        assert hasattr(cost_breakdown, 'image_output_cost')
        assert hasattr(cost_breakdown, 'total_cost')
        assert hasattr(cost_breakdown, 'model')
        assert hasattr(cost_breakdown, 'provider')
        assert hasattr(cost_breakdown, 'notes')
        
        # Verify model and provider are set correctly
        assert cost_breakdown.model == "gpt-image-1"
        assert cost_breakdown.provider == "openai"

    def test_token_usage_to_dict(self):
        """Test TokenUsage serialization to dictionary."""
        usage = TokenUsage(
            prompt_tokens=1500,
            completion_tokens=0,
            total_tokens=1500,
            image_tokens=1000,
            text_tokens=500,
            image_count=2,
            model="gpt-image-1",
            provider="openai"
        )
        
        usage_dict = usage.to_dict()
        
        assert usage_dict["prompt_tokens"] == 1500
        assert usage_dict["completion_tokens"] == 0
        assert usage_dict["total_tokens"] == 1500
        assert usage_dict["image_tokens"] == 1000
        assert usage_dict["text_tokens"] == 500
        assert usage_dict["image_count"] == 2
        assert usage_dict["model"] == "gpt-image-1"
        assert usage_dict["provider"] == "openai"

    def test_cost_breakdown_to_dict(self, token_manager):
        """Test CostBreakdown serialization to dictionary."""
        usage = TokenUsage(
            prompt_tokens=500,
            completion_tokens=0,
            total_tokens=500,
            model="gpt-image-1",
            provider="openai"
        )
        
        image_details = {"count": 1, "resolution": "1024x1024", "quality": "medium"}
        cost_breakdown = token_manager.calculate_cost(usage, image_details)
        
        breakdown_dict = cost_breakdown.to_dict()
        
        # Verify dictionary structure
        required_keys = [
            "input_cost", "output_cost", "image_input_cost", "image_output_cost",
            "total_cost", "currency", "model", "provider", "notes"
        ]
        
        for key in required_keys:
            assert key in breakdown_dict

    def test_image_token_calculation_edge_cases(self, token_manager):
        """Test image token calculation with edge cases."""
        # Test very small image
        small_tokens = token_manager.calculate_image_tokens(
            width=64,
            height=64,
            model_id="gpt-4-vision-preview"
        )
        
        # Test large image
        large_tokens = token_manager.calculate_image_tokens(
            width=2048,
            height=2048,
            model_id="gpt-4-vision-preview"
        )
        
        # Larger image should have more tokens
        assert large_tokens > small_tokens
        assert small_tokens > 0
        assert large_tokens > 0


if __name__ == "__main__":
    pytest.main([__file__]) 