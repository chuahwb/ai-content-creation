"""
Token and Cost Management System for AI Marketing Pipeline
==========================================================

🎯 CENTRALIZED TOKEN & COST MANAGEMENT - Single Source of Truth
---------------------------------------------------------------
This module handles all token usage tracking and cost calculations for:
- Text input/output tokens across all LLM providers
- Image input tokens (vision models) with complex calculation methods  
- Image output tokens (generation models)
- Cost calculation using centralized pricing from constants
- Usage aggregation and reporting across pipeline stages

Supports:
- OpenAI Direct API (text, vision, image generation)
- OpenRouter API (various text models)
- Google/Gemini API (text and vision)
- Complex image token calculation (patch-based and tile-based methods)

Design Pattern:
- TokenCostManager: Main class for all operations
- Provider-specific handlers for different API response formats
- Backward compatible with existing stage implementations
- Centralized pricing and model configuration
"""

import math
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
import io
import base64
from dataclasses import dataclass
from enum import Enum

# Optional PIL import with fallback
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False
    Image = None

from .constants import (
    MODEL_PRICING,
    IMAGE_TOKEN_CALCULATION_METHODS, 
    IMAGE_TOKEN_MODEL_FAMILIES,
    IMG_EVAL_MODEL_PROVIDER, IMG_EVAL_MODEL_ID,
    STRATEGY_MODEL_PROVIDER, STRATEGY_MODEL_ID, 
    STYLE_GUIDER_MODEL_PROVIDER, STYLE_GUIDER_MODEL_ID,
    CREATIVE_EXPERT_MODEL_PROVIDER, CREATIVE_EXPERT_MODEL_ID,
    IMAGE_ASSESSMENT_MODEL_PROVIDER, IMAGE_ASSESSMENT_MODEL_ID,
    IMAGE_GENERATION_MODEL_ID
)

logger = logging.getLogger(__name__)


class ProviderType(Enum):
    """Supported API providers."""
    OPENAI = "openai"
    OPENROUTER = "openrouter" 
    GOOGLE = "google"
    UNKNOWN = "unknown"


class TokenType(Enum):
    """Types of tokens for billing."""
    TEXT_INPUT = "text_input"
    TEXT_OUTPUT = "text_output"
    IMAGE_INPUT = "image_input"
    IMAGE_OUTPUT = "image_output"


@dataclass
class TokenUsage:
    """Standardized token usage information."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    # Image-specific breakdowns
    image_tokens: int = 0
    text_tokens: int = 0
    
    # Model and provider info
    model: str = ""
    provider: str = ""
    
    # Additional metadata
    detail_level: Optional[str] = None
    image_count: int = 0
    fallback_used: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "image_tokens": self.image_tokens,
            "text_tokens": self.text_tokens,
            "model": self.model,
            "provider": self.provider,
            "detail_level": self.detail_level,
            "image_count": self.image_count,
            "fallback_used": self.fallback_used
        }


@dataclass 
class CostBreakdown:
    """Detailed cost breakdown for a model call."""
    input_cost: float = 0.0
    output_cost: float = 0.0
    image_input_cost: float = 0.0
    image_output_cost: float = 0.0
    total_cost: float = 0.0
    
    currency: str = "USD"
    model: str = ""
    provider: str = ""
    
    # Pricing rates used
    input_rate: Optional[float] = None
    output_rate: Optional[float] = None
    image_input_rate: Optional[float] = None
    image_output_rate: Optional[float] = None
    
    notes: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "input_cost": self.input_cost,
            "output_cost": self.output_cost,
            "image_input_cost": self.image_input_cost,
            "image_output_cost": self.image_output_cost,
            "total_cost": self.total_cost,
            "currency": self.currency,
            "model": self.model,
            "provider": self.provider,
            "input_rate": self.input_rate,
            "output_rate": self.output_rate,
            "image_input_rate": self.image_input_rate,
            "image_output_rate": self.image_output_rate,
            "notes": self.notes
        }


class TokenCostManager:
    """
    Centralized manager for all token usage tracking and cost calculations.
    
    Handles:
    - Token extraction from various API response formats
    - Complex image token calculations (OpenAI's patch/tile methods)
    - Cost calculation using centralized pricing
    - Usage aggregation across pipeline stages
    """
    
    def __init__(self):
        """Initialize the manager with configuration."""
        self.patch_config = IMAGE_TOKEN_CALCULATION_METHODS["patch_based"]
        self.tile_config = IMAGE_TOKEN_CALCULATION_METHODS["tile_based"]
        self.model_families = IMAGE_TOKEN_MODEL_FAMILIES
        
        if not PIL_AVAILABLE:
            logger.warning("PIL (Pillow) not available. Image dimension extraction will use fallback methods.")
    
    # ================================
    # TOKEN EXTRACTION FROM API RESPONSES
    # ================================
    
    def extract_usage_from_response(
        self, 
        response: Any, 
        model_id: str,
        provider: Optional[str] = None
    ) -> TokenUsage:
        """
        Extract token usage from any API response format.
        
        Args:
            response: API response object (OpenAI, OpenRouter, etc.)
            model_id: Model identifier
            provider: Provider type (auto-detected if not provided)
            
        Returns:
            Standardized TokenUsage object
        """
        if provider is None:
            provider = self._detect_provider(response, model_id)
        
        provider_enum = ProviderType(provider) if provider in [p.value for p in ProviderType] else ProviderType.UNKNOWN
        
        if provider_enum == ProviderType.OPENAI:
            return self._extract_openai_usage(response, model_id, provider)
        elif provider_enum == ProviderType.OPENROUTER:
            return self._extract_openrouter_usage(response, model_id, provider)
        elif provider_enum == ProviderType.GOOGLE:
            return self._extract_google_usage(response, model_id, provider)
        else:
            return self._extract_generic_usage(response, model_id, provider)
    
    def _detect_provider(self, response: Any, model_id: str) -> str:
        """Auto-detect provider from response or model ID."""
        # Check model ID patterns
        if model_id.startswith(("gpt-", "o1-", "o3-", "gpt-image-")):
            return ProviderType.OPENAI.value
        elif "/" in model_id and any(prefix in model_id for prefix in ["openai/", "anthropic/", "google/", "meta/"]):
            return ProviderType.OPENROUTER.value
        elif model_id.startswith(("gemini-", "models/")):
            return ProviderType.GOOGLE.value
        
        # Check response object attributes
        if hasattr(response, 'usage') and hasattr(response.usage, 'prompt_tokens'):
            # OpenAI-style response
            return ProviderType.OPENAI.value
        
        return ProviderType.UNKNOWN.value
    
    def _extract_openai_usage(self, response: Any, model_id: str, provider: str) -> TokenUsage:
        """Extract usage from OpenAI API response."""
        usage = TokenUsage(model=model_id, provider=provider)
        
        try:
            if hasattr(response, 'usage') and response.usage:
                usage.prompt_tokens = getattr(response.usage, 'prompt_tokens', 0)
                usage.completion_tokens = getattr(response.usage, 'completion_tokens', 0)
                usage.total_tokens = getattr(response.usage, 'total_tokens', 0)
                
                # Handle image token details if available (some OpenAI responses include this)
                if hasattr(response.usage, 'prompt_tokens_details'):
                    details = response.usage.prompt_tokens_details
                    if hasattr(details, 'cached_tokens'):
                        # Handle cached tokens if needed
                        pass
                
            else:
                logger.warning(f"No usage information in OpenAI response for {model_id}")
                usage.fallback_used = True
                
        except Exception as e:
            logger.error(f"Error extracting OpenAI usage for {model_id}: {e}")
            usage.fallback_used = True
        
        return usage
    
    def _extract_openrouter_usage(self, response: Any, model_id: str, provider: str) -> TokenUsage:
        """Extract usage from OpenRouter API response."""
        usage = TokenUsage(model=model_id, provider=provider)
        
        try:
            # OpenRouter typically follows OpenAI format
            if hasattr(response, 'usage') and response.usage:
                usage.prompt_tokens = getattr(response.usage, 'prompt_tokens', 0)
                usage.completion_tokens = getattr(response.usage, 'completion_tokens', 0)
                usage.total_tokens = getattr(response.usage, 'total_tokens', 0)
            else:
                logger.warning(f"No usage information in OpenRouter response for {model_id}")
                usage.fallback_used = True
                
        except Exception as e:
            logger.error(f"Error extracting OpenRouter usage for {model_id}: {e}")
            usage.fallback_used = True
        
        return usage
    
    def _extract_google_usage(self, response: Any, model_id: str, provider: str) -> TokenUsage:
        """Extract usage from Google/Gemini API response."""
        usage = TokenUsage(model=model_id, provider=provider)
        
        try:
            # Google API has different structure
            if hasattr(response, 'usage_metadata'):
                metadata = response.usage_metadata
                usage.prompt_tokens = getattr(metadata, 'prompt_token_count', 0)
                usage.completion_tokens = getattr(metadata, 'candidates_token_count', 0)
                usage.total_tokens = getattr(metadata, 'total_token_count', 0)
            elif hasattr(response, 'usage'):
                # Some Google responses might follow OpenAI format
                usage.prompt_tokens = getattr(response.usage, 'prompt_tokens', 0)
                usage.completion_tokens = getattr(response.usage, 'completion_tokens', 0)
                usage.total_tokens = getattr(response.usage, 'total_tokens', 0)
            else:
                logger.warning(f"No usage information in Google response for {model_id}")
                usage.fallback_used = True
                
        except Exception as e:
            logger.error(f"Error extracting Google usage for {model_id}: {e}")
            usage.fallback_used = True
        
        return usage
    
    def _extract_generic_usage(self, response: Any, model_id: str, provider: str) -> TokenUsage:
        """Extract usage from unknown provider format."""
        usage = TokenUsage(model=model_id, provider=provider)
        
        try:
            # Try common patterns
            if hasattr(response, 'usage'):
                usage_obj = response.usage
                usage.prompt_tokens = getattr(usage_obj, 'prompt_tokens', 0) or getattr(usage_obj, 'input_tokens', 0)
                usage.completion_tokens = getattr(usage_obj, 'completion_tokens', 0) or getattr(usage_obj, 'output_tokens', 0)
                usage.total_tokens = getattr(usage_obj, 'total_tokens', 0) or (usage.prompt_tokens + usage.completion_tokens)
            else:
                logger.warning(f"Unknown response format for {model_id} from {provider}")
                usage.fallback_used = True
                
        except Exception as e:
            logger.error(f"Error extracting generic usage for {model_id}: {e}")
            usage.fallback_used = True
        
        return usage
    
    # ================================
    # IMAGE TOKEN CALCULATIONS
    # ================================
    
    def calculate_image_tokens(
        self, 
        width: int, 
        height: int, 
        model_id: str, 
        detail: str = "high"
    ) -> int:
        """
        Calculate image tokens using OpenAI's complex calculation methods.
        
        Args:
            width: Image width in pixels
            height: Image height in pixels
            model_id: Model identifier to determine calculation method
            detail: Detail level ("high" or "low")
            
        Returns:
            Number of tokens for the image
        """
        try:
            # Determine which calculation method to use
            if self._is_patch_based_model(model_id):
                return self._calculate_patch_based_tokens(width, height, model_id)
            elif self._is_tile_based_model(model_id):
                return self._calculate_tile_based_tokens(width, height, model_id, detail)
            else:
                # Fallback for unknown models
                return self._fallback_image_calculation(width, height)
                
        except Exception as e:
            logger.error(f"Error calculating image tokens for {model_id}: {e}")
            return self._fallback_image_calculation(width, height)
    
    def calculate_tokens_from_base64(
        self, 
        image_base64: str, 
        model_id: str, 
        detail: str = "high"
    ) -> int:
        """
        Calculate image tokens from base64 encoded image.
        
        Args:
            image_base64: Base64 encoded image data
            model_id: Model identifier
            detail: Detail level ("high" or "low")
            
        Returns:
            Number of tokens for the image
        """
        try:
            width, height = self._get_image_dimensions_from_base64(image_base64)
            return self.calculate_image_tokens(width, height, model_id, detail)
        except Exception as e:
            logger.error(f"Error calculating tokens from base64 for {model_id}: {e}")
            return self._fallback_image_calculation(1024, 1024)  # Default size fallback
    
    def _is_patch_based_model(self, model_id: str) -> bool:
        """Check if model uses patch-based calculation."""
        # Remove provider prefix for matching
        clean_model_id = model_id.split("/")[-1] if "/" in model_id else model_id
        return clean_model_id in self.model_families.get("patch_based", [])
    
    def _is_tile_based_model(self, model_id: str) -> bool:
        """Check if model uses tile-based calculation."""
        # Remove provider prefix for matching
        clean_model_id = model_id.split("/")[-1] if "/" in model_id else model_id
        return clean_model_id in self.model_families.get("tile_based", [])
    
    def _calculate_patch_based_tokens(self, width: int, height: int, model_id: str) -> int:
        """Calculate tokens using patch method (GPT-4.1-mini, o4-mini, etc.)."""
        # Remove provider prefix for multiplier lookup
        clean_model_id = model_id.split("/")[-1] if "/" in model_id else model_id
        
        patch_size = self.patch_config["patch_size"]
        max_patches = self.patch_config["max_patches"]
        multipliers = self.patch_config["model_multipliers"]
        
        # Calculate number of patches
        width_patches = math.ceil(width / patch_size)
        height_patches = math.ceil(height / patch_size)
        total_patches = width_patches * height_patches
        
        # Apply cap
        capped_patches = min(total_patches, max_patches)
        
        # Base token calculation (1 token per patch)
        image_tokens = capped_patches
        
        # Apply model-specific multiplier
        multiplier = multipliers.get(clean_model_id, 1.0)
        final_tokens = int(image_tokens * multiplier)
        
        logger.debug(f"Patch-based calculation for {model_id}: "
                    f"{width}x{height} -> {total_patches} patches -> "
                    f"{capped_patches} capped -> {final_tokens} final tokens (×{multiplier})")
        
        return final_tokens
    
    def _calculate_tile_based_tokens(self, width: int, height: int, model_id: str, detail: str) -> int:
        """Calculate tokens using tile method (GPT-4o, GPT-4.1, etc.)."""
        # Remove provider prefix for cost lookup
        clean_model_id = model_id.split("/")[-1] if "/" in model_id else model_id
        
        model_costs = self.tile_config["model_costs"].get(clean_model_id)
        if not model_costs:
            logger.warning(f"No tile costs found for model {clean_model_id}, using fallback")
            return self._fallback_image_calculation(width, height)
        
        base_tokens = model_costs["base_tokens"]
        tile_tokens = model_costs["tile_tokens"]
        
        # Low detail is always fixed cost
        if detail == "low":
            logger.debug(f"Tile-based calculation for {model_id}: low detail = {base_tokens} tokens")
            return base_tokens
        
        # High detail calculation
        max_square = self.tile_config["max_square"]
        shortest_side_target = self.tile_config["shortest_side_target"]
        tile_size = self.tile_config["tile_size"]
        
        # Step 1: Scale to fit in max_square (maintaining aspect ratio)
        if max(width, height) > max_square:
            scale_factor = max_square / max(width, height)
            width = int(width * scale_factor)
            height = int(height * scale_factor)
        
        # Step 2: Scale so shortest side is shortest_side_target
        shortest_side = min(width, height)
        if shortest_side != shortest_side_target:
            scale_factor = shortest_side_target / shortest_side
            width = int(width * scale_factor)
            height = int(height * scale_factor)
        
        # Step 3: Count 512px tiles needed
        width_tiles = (width + tile_size - 1) // tile_size
        height_tiles = (height + tile_size - 1) // tile_size
        num_tiles = width_tiles * height_tiles
        
        # Step 4: Calculate final cost
        total_tokens = base_tokens + (tile_tokens * num_tiles)
        
        logger.debug(f"Tile-based calculation for {model_id}: "
                    f"original={width}x{height} -> scaled={width}x{height} -> "
                    f"{num_tiles} tiles -> {total_tokens} tokens "
                    f"({base_tokens} base + {tile_tokens}×{num_tiles} tiles)")
        
        return total_tokens
    
    def _fallback_image_calculation(self, width: int, height: int) -> int:
        """Fallback calculation for unknown models."""
        # Simple area-based fallback (roughly equivalent to 1024x1024 = 1000 tokens)
        area = width * height
        base_area = 1024 * 1024
        base_tokens = 1000
        
        tokens = int((area / base_area) * base_tokens)
        logger.debug(f"Fallback calculation: {width}x{height} -> {tokens} tokens")
        return max(tokens, 100)  # Minimum 100 tokens
    
    def _get_image_dimensions_from_base64(self, image_base64: str) -> Tuple[int, int]:
        """Extract image dimensions from base64 data."""
        if PIL_AVAILABLE:
            try:
                # Decode base64 and get image dimensions
                image_data = base64.b64decode(image_base64)
                image = Image.open(io.BytesIO(image_data))
                return image.width, image.height
            except Exception as e:
                logger.warning(f"PIL image dimension extraction failed: {e}")
        
        # Fallback: Try to parse image headers without PIL
        try:
            return self._parse_image_header_dimensions(image_base64)
        except Exception as e:
            logger.warning(f"Header parsing failed: {e}")
            # Ultimate fallback
            return 1024, 1024
    
    def _parse_image_header_dimensions(self, image_base64: str) -> Tuple[int, int]:
        """Parse image dimensions from headers without PIL."""
        try:
            image_data = base64.b64decode(image_base64)
            
            # PNG signature and IHDR chunk
            if image_data.startswith(b'\x89PNG\r\n\x1a\n'):
                # PNG: width and height are at bytes 16-23 in IHDR chunk
                if len(image_data) >= 24:
                    width = int.from_bytes(image_data[16:20], 'big')
                    height = int.from_bytes(image_data[20:24], 'big')
                    return width, height
            
            # JPEG SOI marker
            elif image_data.startswith(b'\xff\xd8'):
                # JPEG: Need to parse segments to find SOF
                return self._parse_jpeg_dimensions(image_data)
            
            # WebP signature
            elif image_data.startswith(b'RIFF') and b'WEBP' in image_data[:12]:
                return self._parse_webp_dimensions(image_data)
                
        except Exception as e:
            logger.warning(f"Image header parsing error: {e}")
        
        # Fallback if parsing fails
        return 1024, 1024
    
    def _parse_jpeg_dimensions(self, data: bytes) -> Tuple[int, int]:
        """Parse JPEG dimensions from SOF segment."""
        i = 2  # Skip SOI marker
        while i < len(data) - 9:
            if data[i] == 0xFF:
                marker = data[i + 1]
                # SOF markers (Start of Frame)
                if marker in [0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF]:
                    # SOF: length(2) + precision(1) + height(2) + width(2) + components(1)
                    height = int.from_bytes(data[i + 5:i + 7], 'big')
                    width = int.from_bytes(data[i + 7:i + 9], 'big')
                    return width, height
                
                # Skip this segment
                if i + 3 < len(data):
                    segment_length = int.from_bytes(data[i + 2:i + 4], 'big')
                    i += 2 + segment_length
                else:
                    break
            else:
                i += 1
        
        return 1024, 1024  # Fallback
    
    def _parse_webp_dimensions(self, data: bytes) -> Tuple[int, int]:
        """Parse WebP dimensions."""
        try:
            # Skip RIFF header (12 bytes)
            if len(data) >= 30:
                # VP8 chunk
                if data[12:16] == b'VP8 ':
                    # VP8: dimensions are in a specific format
                    width = int.from_bytes(data[26:28], 'little') & 0x3FFF
                    height = int.from_bytes(data[28:30], 'little') & 0x3FFF
                    return width, height
        except Exception:
            pass
        
        return 1024, 1024  # Fallback
    
    # ================================
    # COST CALCULATIONS
    # ================================
    
    def calculate_cost(
        self, 
        usage: TokenUsage, 
        image_details: Optional[Dict[str, Any]] = None
    ) -> CostBreakdown:
        """
        Calculate cost for a model call using centralized pricing.
        
        Args:
            usage: Token usage information
            image_details: Additional image generation details if applicable
                          {"count": 2, "resolution": "1024x1024", "quality": "high"}
            
        Returns:
            Detailed cost breakdown
        """
        cost = CostBreakdown(
            model=usage.model,
            provider=usage.provider,
            currency="USD"
        )
        
        try:
            # Get pricing information
            pricing = MODEL_PRICING.get(usage.model)
            if not pricing:
                cost.notes = f"No pricing found for model {usage.model}"
                logger.warning(cost.notes)
                return cost
            
            # Text model cost calculation
            if "input_cost_per_mtok" in pricing and "output_cost_per_mtok" in pricing:
                cost.input_rate = pricing["input_cost_per_mtok"]
                cost.output_rate = pricing["output_cost_per_mtok"]
                
                cost.input_cost = (usage.prompt_tokens / 1_000_000) * cost.input_rate
                cost.output_cost = (usage.completion_tokens / 1_000_000) * cost.output_rate
                cost.total_cost = cost.input_cost + cost.output_cost
                
                cost.notes = f"Text model: {usage.prompt_tokens:,} input + {usage.completion_tokens:,} output tokens"
            
            # Image generation model cost calculation (gpt-image-1 style)
            elif usage.model == "gpt-image-1" and image_details:
                cost = self._calculate_image_generation_cost(usage, image_details, pricing)
            
            # Vision model with image input tokens
            elif usage.image_tokens > 0:
                cost = self._calculate_vision_model_cost(usage, pricing)
            
            else:
                cost.notes = f"Unsupported pricing structure for model {usage.model}"
                logger.warning(cost.notes)
            
            cost.notes = f"{pricing.get('notes', '')}. {cost.notes}".strip(". ")
            
        except Exception as e:
            cost.notes = f"Error calculating cost: {e}"
            logger.error(f"Cost calculation failed for {usage.model}: {e}")
        
        return cost
    
    def _calculate_image_generation_cost(
        self, 
        usage: TokenUsage, 
        image_details: Dict[str, Any], 
        pricing: Dict[str, Any]
    ) -> CostBreakdown:
        """Calculate cost for image generation models."""
        cost = CostBreakdown(model=usage.model, provider=usage.provider)
        
        # Text input cost
        if "input_text_cost_per_mtok" in pricing and usage.prompt_tokens > 0:
            cost.input_rate = pricing["input_text_cost_per_mtok"]
            cost.input_cost = (usage.prompt_tokens / 1_000_000) * cost.input_rate
        
        # Image output cost - check if using token-based or per-image pricing
        if "output_image_cost_per_mtok" in pricing:
            # Token-based pricing (newer gpt-image-1 format)
            cost.image_output_rate = pricing["output_image_cost_per_mtok"]
            
            # Use token count from quality/size if available
            image_count = image_details.get("count", 1)
            resolution = image_details.get("resolution", "1024x1024")
            quality = image_details.get("quality", "medium")
            
            # Get token count from pricing table
            token_counts = pricing.get("token_counts_by_quality", {})
            tokens_per_image = token_counts.get(quality, {}).get(resolution, 1056)  # Default to medium 1024x1024
            
            total_image_tokens = tokens_per_image * image_count
            cost.image_output_cost = (total_image_tokens / 1_000_000) * cost.image_output_rate
            
            cost.notes = f"Image generation: {image_count} {quality} {resolution} images ({total_image_tokens:,} tokens)"
            
        elif "cost_per_image" in pricing:
            # Per-image pricing (older format)
            image_count = image_details.get("count", 1)
            resolution = image_details.get("resolution", "1024x1024")
            quality = image_details.get("quality", "medium")
            
            cost_per_image = pricing["cost_per_image"].get(quality, {}).get(resolution, 0.042)
            cost.image_output_cost = image_count * cost_per_image
            
            cost.notes = f"Image generation: {image_count} {quality} {resolution} images (${cost_per_image:.3f} each)"
        
        cost.total_cost = cost.input_cost + cost.image_output_cost
        return cost
    
    def _calculate_vision_model_cost(self, usage: TokenUsage, pricing: Dict[str, Any]) -> CostBreakdown:
        """Calculate cost for vision models with image inputs."""
        cost = CostBreakdown(model=usage.model, provider=usage.provider)
        
        # For vision models, all tokens are typically billed at text rates
        # (image tokens are converted to equivalent text tokens)
        if "input_cost_per_mtok" in pricing and "output_cost_per_mtok" in pricing:
            cost.input_rate = pricing["input_cost_per_mtok"]
            cost.output_rate = pricing["output_cost_per_mtok"]
            
            cost.input_cost = (usage.prompt_tokens / 1_000_000) * cost.input_rate
            cost.output_cost = (usage.completion_tokens / 1_000_000) * cost.output_rate
            cost.total_cost = cost.input_cost + cost.output_cost
            
            cost.notes = f"Vision model: {usage.prompt_tokens:,} input ({usage.image_tokens:,} image + {usage.text_tokens:,} text) + {usage.completion_tokens:,} output tokens"
        
        return cost
    
    def calculate_stage_cost(
        self, 
        stage_name: str, 
        usage_data: Union[Dict[str, Any], List[Dict[str, Any]]], 
        model_id: str,
        image_details: Optional[Dict[str, Any]] = None
    ) -> CostBreakdown:
        """
        Calculate total cost for a pipeline stage.
        
        Args:
            stage_name: Name of the pipeline stage
            usage_data: Token usage data (single dict or list for multiple calls)
            model_id: Model identifier
            image_details: Image generation details if applicable
            
        Returns:
            Aggregated cost breakdown for the stage
        """
        stage_cost = CostBreakdown(model=model_id)
        stage_cost.notes = f"Stage: {stage_name}"
        
        try:
            # Handle single usage dict
            if isinstance(usage_data, dict):
                usage_list = [usage_data]
            else:
                usage_list = usage_data
            
            # Aggregate costs from all calls in the stage
            for usage_dict in usage_list:
                # Convert dict to TokenUsage object
                usage = TokenUsage(
                    prompt_tokens=usage_dict.get("prompt_tokens", 0),
                    completion_tokens=usage_dict.get("completion_tokens", 0),
                    total_tokens=usage_dict.get("total_tokens", 0),
                    image_tokens=usage_dict.get("image_tokens", 0),
                    text_tokens=usage_dict.get("text_tokens", 0),
                    model=model_id,
                    provider=usage_dict.get("provider", "")
                )
                
                # Calculate cost for this call
                call_cost = self.calculate_cost(usage, image_details)
                
                # Aggregate to stage total
                stage_cost.input_cost += call_cost.input_cost
                stage_cost.output_cost += call_cost.output_cost
                stage_cost.image_input_cost += call_cost.image_input_cost
                stage_cost.image_output_cost += call_cost.image_output_cost
                stage_cost.total_cost += call_cost.total_cost
                
                # Use the first non-empty rates found
                if not stage_cost.input_rate and call_cost.input_rate:
                    stage_cost.input_rate = call_cost.input_rate
                if not stage_cost.output_rate and call_cost.output_rate:
                    stage_cost.output_rate = call_cost.output_rate
            
        except Exception as e:
            stage_cost.notes += f" | Error: {e}"
            logger.error(f"Stage cost calculation failed for {stage_name}: {e}")
        
        return stage_cost
    
    # ================================
    # USAGE AGGREGATION AND REPORTING
    # ================================
    
    def aggregate_stage_usage(
        self, 
        individual_usages: List[Dict[str, Any]], 
        stage_name: str,
        model_id: str
    ) -> Dict[str, Any]:
        """
        Aggregate multiple API calls into a single stage usage summary.
        
        Args:
            individual_usages: List of individual API call usage dicts
            stage_name: Name of the pipeline stage
            model_id: Model identifier
            
        Returns:
            Aggregated usage dictionary
        """
        aggregated = {
            "stage_name": stage_name,
            "model": model_id,
            "call_count": len(individual_usages),
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "image_tokens": 0,
            "text_tokens": 0,
            "individual_calls": individual_usages
        }
        
        for usage in individual_usages:
            aggregated["prompt_tokens"] += usage.get("prompt_tokens", 0)
            aggregated["completion_tokens"] += usage.get("completion_tokens", 0)
            aggregated["total_tokens"] += usage.get("total_tokens", 0)
            aggregated["image_tokens"] += usage.get("image_tokens", 0)
            aggregated["text_tokens"] += usage.get("text_tokens", 0)
        
        return aggregated
    
    def create_detailed_image_breakdown(
        self, 
        images: List[Tuple[str, str]], 
        model_id: str, 
        detail_level: str = "high"
    ) -> Dict[str, Any]:
        """
        Create detailed token breakdown for multiple images.
        
        Args:
            images: List of (base64_data, image_type) tuples
            model_id: Model identifier for token calculation
            detail_level: Detail level for calculation
            
        Returns:
            Detailed breakdown dictionary
        """
        breakdown = {
            "model_id": model_id,
            "detail_level": detail_level,
            "images": [],
            "total_image_tokens": 0
        }
        
        for i, (image_base64, image_type) in enumerate(images):
            try:
                tokens = self.calculate_tokens_from_base64(image_base64, model_id, detail_level)
                breakdown["images"].append({
                    "index": i,
                    "type": image_type,
                    "tokens": tokens
                })
                breakdown["total_image_tokens"] += tokens
            except Exception as e:
                logger.error(f"Error calculating tokens for image {i}: {e}")
                fallback_tokens = 1000  # Conservative fallback
                breakdown["images"].append({
                    "index": i,
                    "type": image_type,
                    "tokens": fallback_tokens,
                    "error": str(e)
                })
                breakdown["total_image_tokens"] += fallback_tokens
        
        return breakdown


# ================================
# CONVENIENCE FUNCTIONS & BACKWARD COMPATIBILITY
# ================================

# Global instance for backward compatibility
_global_manager = None

def get_token_cost_manager() -> TokenCostManager:
    """Get the global TokenCostManager instance."""
    global _global_manager
    if _global_manager is None:
        _global_manager = TokenCostManager()
    return _global_manager

def get_image_token_calculator():
    """
    Backward compatibility function for existing image_token_calculator usage.
    Returns a TokenCostManager instance with legacy interface.
    """
    return get_token_cost_manager()

def _get_provider_for_model(model_id: str) -> str:
    """Get the correct provider for a model using explicit mappings from constants.py."""
    
    # Create mapping from model IDs to their explicitly defined providers
    model_to_provider = {
        IMG_EVAL_MODEL_ID: IMG_EVAL_MODEL_PROVIDER.lower(),
        STRATEGY_MODEL_ID: STRATEGY_MODEL_PROVIDER.lower(),
        STYLE_GUIDER_MODEL_ID: STYLE_GUIDER_MODEL_PROVIDER.lower(),
        CREATIVE_EXPERT_MODEL_ID: CREATIVE_EXPERT_MODEL_PROVIDER.lower(),
        IMAGE_ASSESSMENT_MODEL_ID: IMAGE_ASSESSMENT_MODEL_PROVIDER.lower(),
        IMAGE_GENERATION_MODEL_ID: "openai"  # gpt-image-1 is always OpenAI
    }
    
    provider = model_to_provider.get(model_id)
    if provider:
        return provider
        
    # Fallback: check if it's in MODEL_PRICING
    pricing_info = MODEL_PRICING.get(model_id, {})
    pricing_provider = pricing_info.get("provider", "").lower()
    if pricing_provider:
        return pricing_provider
        
    # Final fallback for unknown models
    if model_id.startswith('gpt-') or model_id.startswith('o1') or model_id.startswith('o3'):
        return 'openai'
    elif '/' in model_id:  # OpenRouter format (provider/model)
        return 'openrouter'
    else:
        return 'unknown'

def calculate_stage_cost_from_usage(
    stage_name: str, 
    llm_usage: Dict[str, Any], 
    usage_keys: List[str], 
    model_id: str
) -> Dict[str, Any]:
    """
    Calculate cost for a pipeline stage from LLM usage data.
    
    Args:
        stage_name: Name of the pipeline stage
        llm_usage: Dictionary containing LLM usage data from pipeline context
        usage_keys: List of keys to look for in llm_usage (e.g., ['strategy_niche_id', 'strategy_goal_gen'])
        model_id: Model ID for pricing lookup
        
    Returns:
        Dictionary with cost breakdown and details
    """
    try:
        total_prompt_tokens = 0
        total_completion_tokens = 0
        total_tokens = 0
        cost_details = []
        
        token_manager = get_token_cost_manager()
        
        for usage_key in usage_keys:
            if usage_key not in llm_usage:
                continue
                
            usage_data = llm_usage[usage_key]
            
            # Handle different formats: dictionary (standard) or array (image assessment)
            if isinstance(usage_data, dict):
                # Standard dictionary format
                prompt_tokens = usage_data.get("prompt_tokens", 0)
                completion_tokens = usage_data.get("completion_tokens", 0)
                tokens = usage_data.get("total_tokens", 0)
                
                total_prompt_tokens += prompt_tokens
                total_completion_tokens += completion_tokens
                total_tokens += tokens
                
                cost_details.append({
                    "usage_key": usage_key,
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": tokens,
                    "format": "dictionary"
                })
                
            elif isinstance(usage_data, list):
                # Array format (mainly for image assessment)
                for item in usage_data:
                    if isinstance(item, dict):
                        item_tokens = item.get("total_tokens", 0)
                        total_tokens += item_tokens
                        # For arrays, we don't have separate prompt/completion breakdown
                        total_prompt_tokens += item_tokens  # Treat as prompt tokens for pricing
                        
                        cost_details.append({
                            "usage_key": usage_key,
                            "prompt_tokens": item_tokens,
                            "completion_tokens": 0,
                            "total_tokens": item_tokens,
                            "format": "array_item",
                            "image_index": item.get("image_index", "unknown")
                        })
        
        if total_tokens == 0:
            return {
                "stage_name": stage_name,
                "model_id": model_id,
                "total_cost": 0.0,
                "cost_details": cost_details,
                "message": f"No token usage found for keys: {usage_keys}"
            }
        
        # Create TokenUsage object for cost calculation
        usage = TokenUsage(
            prompt_tokens=total_prompt_tokens,
            completion_tokens=total_completion_tokens,
            total_tokens=total_tokens,
            model=model_id,
            provider=_get_provider_for_model(model_id)
        )
        
        # Calculate cost
        cost_breakdown = token_manager.calculate_cost(usage)
        
        return {
            "stage_name": stage_name,
            "model_id": model_id,
            "total_cost": cost_breakdown.total_cost,
            "input_cost": cost_breakdown.input_cost,
            "output_cost": cost_breakdown.output_cost,
            "total_tokens": total_tokens,
            "prompt_tokens": total_prompt_tokens,
            "completion_tokens": total_completion_tokens,
            "cost_details": cost_details,
            "notes": cost_breakdown.notes
        }
        
    except Exception as e:
        logger.error(f"Stage cost calculation failed for {stage_name}: {e}")
        return {
            "stage_name": stage_name,
            "model_id": model_id,
            "total_cost": 0.0,
            "error": str(e),
            "message": f"Cost calculation failed for {stage_name}"
        } 