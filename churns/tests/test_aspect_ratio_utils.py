"""
Unit tests for aspect ratio resolver utility.
Tests mapping matrix for OpenAI and Gemini providers.
"""
import pytest
from churns.core.aspect_ratio_utils import (
    resolveAspectRatio,
    parseAspectStringToFloat,
    nearestAspect,
    AspectResolution
)


class TestParseAspectStringToFloat:
    """Test aspect string parsing to float ratios."""
    
    def test_standard_ratios(self):
        """Test standard aspect ratio formats."""
        assert parseAspectStringToFloat("1:1") == 1.0
        assert parseAspectStringToFloat("16:9") == pytest.approx(1.778, rel=1e-3)
        assert parseAspectStringToFloat("9:16") == pytest.approx(0.5625, rel=1e-3)
        assert parseAspectStringToFloat("3:2") == 1.5
        assert parseAspectStringToFloat("2:3") == pytest.approx(0.667, rel=1e-3)
        assert parseAspectStringToFloat("4:3") == pytest.approx(1.333, rel=1e-3)
        assert parseAspectStringToFloat("3:4") == 0.75
    
    def test_decimal_ratios(self):
        """Test decimal aspect ratio formats."""
        assert parseAspectStringToFloat("1.91:1") == 1.91
        assert parseAspectStringToFloat("1:1.5") == pytest.approx(0.667, rel=1e-3)
    
    def test_invalid_formats(self):
        """Test handling of invalid aspect ratio formats."""
        assert parseAspectStringToFloat("abc") == 1.0  # Default fallback
        assert parseAspectStringToFloat("") == 1.0     # Default fallback
        assert parseAspectStringToFloat("16") == 1.0   # Missing colon


class TestNearestAspect:
    """Test nearest aspect ratio matching."""
    
    def test_exact_match(self):
        """Test exact aspect ratio matches."""
        candidates = ["1:1", "16:9", "9:16"]
        aspect, delta = nearestAspect(1.0, candidates)
        assert aspect == "1:1"
        assert delta == 0.0
    
    def test_nearest_match(self):
        """Test nearest aspect ratio selection."""
        candidates = ["1:1", "3:2", "2:3"]
        # 1.91:1 should be closest to 3:2 (1.5)
        aspect, delta = nearestAspect(1.91, candidates)
        assert aspect == "3:2"
        assert delta == pytest.approx(0.41, rel=1e-2)
    
    def test_tie_breaking(self):
        """Test preference order for ties."""
        # When multiple candidates have same delta, prefer order: 1:1, 9:16, 16:9, 3:4, 4:3, 2:3, 3:2
        candidates = ["3:2", "2:3", "1:1"]  # All equidistant from some middle value
        aspect, delta = nearestAspect(1.2, candidates)
        # Should prefer 1:1 in tie-breaking
        assert aspect == "1:1"


class TestResolveAspectRatioOpenAI:
    """Test aspect ratio resolution for OpenAI provider."""
    
    def test_exact_openai_mappings(self):
        """Test exact OpenAI aspect ratio mappings."""
        # 1:1 → prompt 1:1, size 1024x1024
        result = resolveAspectRatio("1:1", "OpenAI", "gpt-image-1")
        assert result.promptAspect == "1:1"
        assert result.openaiSize == "1024x1024"
        assert result.fallbackReason is None
        
        # 2:3 → prompt 2:3, size 1024x1536
        result = resolveAspectRatio("2:3", "OpenAI", "gpt-image-1")
        assert result.promptAspect == "2:3"
        assert result.openaiSize == "1024x1536"
        assert result.fallbackReason is None
        
        # 3:2 → prompt 3:2, size 1536x1024
        result = resolveAspectRatio("3:2", "OpenAI", "gpt-image-1")
        assert result.promptAspect == "3:2"
        assert result.openaiSize == "1536x1024"
        assert result.fallbackReason is None
    
    def test_openai_fallback_mappings(self):
        """Test OpenAI fallback mappings for unsupported ratios."""
        # 9:16 → prompt 2:3, size 1024x1536 (nearest match)
        result = resolveAspectRatio("9:16", "OpenAI", "gpt-image-1")
        assert result.promptAspect == "2:3"
        assert result.openaiSize == "1024x1536"
        assert result.fallbackReason is not None
        
        # 3:4 → prompt 2:3, size 1024x1536 (nearest match)
        result = resolveAspectRatio("3:4", "OpenAI", "gpt-image-1")
        assert result.promptAspect == "2:3"
        assert result.openaiSize == "1024x1536"
        assert result.fallbackReason is not None
        
        # 1.91:1 → prompt 3:2, size 1536x1024 (nearest match)
        result = resolveAspectRatio("1.91:1", "OpenAI", "gpt-image-1")
        assert result.promptAspect == "3:2"
        assert result.openaiSize == "1536x1024"
        assert result.fallbackReason is not None


class TestResolveAspectRatioGemini:
    """Test aspect ratio resolution for Gemini provider."""
    
    def test_exact_gemini_mappings(self):
        """Test exact Gemini aspect ratio mappings."""
        # 1:1 → prompt 1:1, size None
        result = resolveAspectRatio("1:1", "Gemini", "gemini-2.5-flash-image-preview")
        assert result.promptAspect == "1:1"
        assert result.openaiSize is None
        assert result.fallbackReason is None
        
        # 9:16 → prompt 9:16, size None
        result = resolveAspectRatio("9:16", "Gemini", "gemini-2.5-flash-image-preview")
        assert result.promptAspect == "9:16"
        assert result.openaiSize is None
        assert result.fallbackReason is None
        
        # 16:9 → prompt 16:9, size None
        result = resolveAspectRatio("16:9", "Gemini", "gemini-2.5-flash-image-preview")
        assert result.promptAspect == "16:9"
        assert result.openaiSize is None
        assert result.fallbackReason is None
        
        # 3:4 → prompt 3:4, size None
        result = resolveAspectRatio("3:4", "Gemini", "gemini-2.5-flash-image-preview")
        assert result.promptAspect == "3:4"
        assert result.openaiSize is None
        assert result.fallbackReason is None
        
        # 4:3 → prompt 4:3, size None
        result = resolveAspectRatio("4:3", "Gemini", "gemini-2.5-flash-image-preview")
        assert result.promptAspect == "4:3"
        assert result.openaiSize is None
        assert result.fallbackReason is None
    
    def test_gemini_fallback_mappings(self):
        """Test Gemini fallback mappings for unsupported ratios."""
        # 2:3 → prompt 3:4, size None (nearest match)
        result = resolveAspectRatio("2:3", "Gemini", "gemini-2.5-flash-image-preview")
        assert result.promptAspect == "3:4"
        assert result.openaiSize is None
        assert result.fallbackReason is not None
        
        # 1.91:1 → prompt 16:9, size None (nearest match)
        result = resolveAspectRatio("1.91:1", "Gemini", "gemini-2.5-flash-image-preview")
        assert result.promptAspect == "16:9"
        assert result.openaiSize is None
        assert result.fallbackReason is not None


class TestResolveAspectRatioEdgeCases:
    """Test edge cases and error handling."""
    
    def test_unknown_aspect_string(self):
        """Test handling of unknown aspect ratio strings."""
        result = resolveAspectRatio("unknown", "OpenAI", "gpt-image-1")
        assert result.promptAspect == "1:1"
        assert result.openaiSize == "1024x1024"
        assert result.fallbackReason is not None
        assert "unknown" in result.fallbackReason.lower()
    
    def test_malformed_aspect_string(self):
        """Test handling of malformed aspect ratio strings."""
        result = resolveAspectRatio("abc", "OpenAI", "gpt-image-1")
        assert result.promptAspect == "1:1"
        assert result.openaiSize == "1024x1024"
        assert result.fallbackReason is not None
    
    def test_empty_aspect_string(self):
        """Test handling of empty aspect ratio string."""
        result = resolveAspectRatio("", "OpenAI", "gpt-image-1")
        assert result.promptAspect == "1:1"
        assert result.openaiSize == "1024x1024"
        assert result.fallbackReason is not None
    
    def test_unknown_provider(self):
        """Test handling of unknown provider."""
        result = resolveAspectRatio("1:1", "UnknownProvider")
        assert result.promptAspect == "1:1"
        assert result.openaiSize is None
        assert result.fallbackReason is not None
    
    def test_result_metadata(self):
        """Test that result contains correct metadata."""
        result = resolveAspectRatio("16:9", "Gemini", "gemini-2.5-flash-image-preview")
        assert result.sourcePlatformAspect == "16:9"
        assert result.provider == "Gemini"
        assert result.modelId == "gemini-2.5-flash-image-preview"
