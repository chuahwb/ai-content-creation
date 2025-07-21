"""
Model Selection Utilities

Provides functions for selecting appropriate models based on user preferences and requirements.
"""

from typing import Optional
from .constants import CAPTION_MODEL_OPTIONS, CAPTION_MODEL_ID


def get_caption_model_for_processing_mode(processing_mode: Optional[str]) -> str:
    """
    Map processing mode to appropriate caption model ID based on CAPTION_MODEL_OPTIONS.
    
    Args:
        processing_mode: 'Fast', 'Analytical', or None
        
    Returns:
        Model ID string
    """
    if processing_mode == 'Fast':
        # Find the model with "Low" latency 
        for model_id, config in CAPTION_MODEL_OPTIONS.items():
            if config.get('latency') == 'Low':
                return model_id
    elif processing_mode == 'Analytical':
        # Find the model with "Higher" latency (analytical)
        for model_id, config in CAPTION_MODEL_OPTIONS.items():
            if config.get('latency') == 'Higher':
                return model_id
    
    # Default fallback - return the default caption model
    return CAPTION_MODEL_ID 