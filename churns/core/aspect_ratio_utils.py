"""
Centralized aspect ratio resolution utility for image generation providers.
Provides consistent aspect ratio mapping across OpenAI and Gemini models.
"""
from dataclasses import dataclass
from typing import Optional
import re
import logging

logger = logging.getLogger(__name__)


@dataclass
class AspectResolution:
    """Result of aspect ratio resolution for a specific provider/model."""
    promptAspect: str                 # e.g., "2:3", "3:2", "9:16", etc.
    openaiSize: Optional[str] = None  # e.g., "1024x1536"; None when not applicable
    sourcePlatformAspect: str = ""
    provider: str = ""
    modelId: Optional[str] = None
    fallbackReason: Optional[str] = None


def resolveAspectRatio(platformAspect: str, provider: str, modelId: Optional[str] = None) -> AspectResolution:
    """
    Resolves platform aspect ratio to provider-specific prompt aspect and size.
    
    Args:
        platformAspect: Input aspect string (e.g., "1:1", "9:16", "1.91:1")
        provider: Provider name ("OpenAI" or "Gemini")
        modelId: Optional model identifier
        
    Returns:
        AspectResolution with resolved prompt aspect and optional OpenAI size
    """
    # Provider capability tables
    OPENAI_CAPABILITIES = {
        "supported_aspects": ["1:1", "2:3", "3:2"],
        "size_mapping": {
            "1:1": "1024x1024",
            "2:3": "1024x1536", 
            "3:2": "1536x1024"
        }
    }
    
    GEMINI_CAPABILITIES = {
        "supported_aspects": ["1:1", "9:16", "16:9", "3:4", "4:3"],
        "size_mapping": {}  # No size mapping for Gemini
    }
    
    # Parse input aspect ratio
    target_ratio = parseAspectStringToFloat(platformAspect)
    fallback_reason = None
    
    # Check if input was malformed/invalid (parseAspectStringToFloat returns 1.0 for invalid input)
    is_valid_input = platformAspect and ':' in platformAspect
    if is_valid_input:
        try:
            parts = platformAspect.split(':')
            float(parts[0])
            float(parts[1])
        except (ValueError, IndexError):
            is_valid_input = False
    
    # Determine provider capabilities
    if provider.lower() == "openai":
        capabilities = OPENAI_CAPABILITIES
    elif provider.lower() == "gemini":
        capabilities = GEMINI_CAPABILITIES
    else:
        # Unknown provider - default to 1:1
        return AspectResolution(
            promptAspect="1:1",
            openaiSize=None,
            sourcePlatformAspect=platformAspect,
            provider=provider,
            modelId=modelId,
            fallbackReason=f"Unknown provider '{provider}', defaulting to 1:1"
        )
    
    supported_aspects = capabilities["supported_aspects"]
    size_mapping = capabilities["size_mapping"]
    
    # Check for exact match first
    if platformAspect in supported_aspects and is_valid_input:
        chosen_aspect = platformAspect
    else:
        # Find nearest match
        chosen_aspect, delta = nearestAspect(target_ratio, supported_aspects)
        
        # Set fallback reason
        if not is_valid_input:
            fallback_reason = f"Invalid aspect ratio format '{platformAspect}', defaulting to '{chosen_aspect}'"
        elif delta > 0:
            fallback_reason = f"Platform aspect '{platformAspect}' not supported, using nearest match '{chosen_aspect}'"
    
    # Get OpenAI size if applicable
    openai_size = size_mapping.get(chosen_aspect) if provider.lower() == "openai" else None
    
    return AspectResolution(
        promptAspect=chosen_aspect,
        openaiSize=openai_size,
        sourcePlatformAspect=platformAspect,
        provider=provider,
        modelId=modelId,
        fallbackReason=fallback_reason
    )


def parseAspectStringToFloat(aspectStr: str) -> float:
    """
    Parse aspect ratio string to float ratio.
    
    Args:
        aspectStr: Aspect ratio string like "16:9", "1.91:1", etc.
        
    Returns:
        Float ratio (width/height)
    """
    try:
        if not aspectStr or ':' not in aspectStr:
            return 1.0  # Default fallback
            
        parts = aspectStr.split(':')
        if len(parts) != 2:
            return 1.0  # Default fallback
            
        width = float(parts[0])
        height = float(parts[1])
        
        if height == 0:
            return 1.0  # Avoid division by zero
            
        return width / height
        
    except (ValueError, ZeroDivisionError):
        return 1.0  # Default fallback for any parsing errors


def nearestAspect(target: float, candidates: list[str]) -> tuple[str, float]:
    """
    Find nearest aspect ratio from candidates.
    
    Args:
        target: Target aspect ratio as float
        candidates: List of candidate aspect ratio strings
        
    Returns:
        Tuple of (best_candidate, delta)
    """
    if not candidates:
        return "1:1", 0.0
        
    # Tie-breaking preference order
    preference_order = ["1:1", "9:16", "16:9", "3:4", "4:3", "2:3", "3:2"]
    
    best_candidate = candidates[0]
    best_delta = abs(parseAspectStringToFloat(best_candidate) - target)
    
    for candidate in candidates:
        candidate_ratio = parseAspectStringToFloat(candidate)
        delta = abs(candidate_ratio - target)
        
        # Check if this is a better match
        is_better = False
        
        if delta < best_delta:
            # Clearly better (smaller delta)
            is_better = True
        elif delta == best_delta:
            # Tie - use preference order
            try:
                current_pref = preference_order.index(candidate)
                best_pref = preference_order.index(best_candidate)
                if current_pref < best_pref:
                    is_better = True
            except ValueError:
                # If not in preference order, keep current best
                pass
        
        if is_better:
            best_candidate = candidate
            best_delta = delta
    
    return best_candidate, best_delta
