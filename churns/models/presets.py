"""
Pydantic models for Brand Preset & Style Memory feature.
These models support both 'Input Templates' and 'Style Recipes' workflows.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from churns.models import VisualConceptDetails, MarketingGoalSetFinal, StyleGuidance, BrandKitInput


class PipelineInputSnapshot(BaseModel):
    """
    Mirrors the structure of the main pipeline form for 'Input Templates'.
    Captures user's raw form inputs in a structured model.
    """
    # Core inputs
    mode: str = Field('easy_mode', description="Pipeline mode (easy_mode, custom_mode, task_specific_mode)")
    prompt: Optional[str] = Field(None, description="User's text prompt")
    creativity_level: int = Field(2, ge=1, le=3, description="Creativity level 1-3")
    platform_name: str = Field(..., description="Target social media platform")
    num_variants: int = Field(3, ge=1, le=6, description="Number of strategy/image variants to generate")
    
    # Content inputs
    task_type: Optional[str] = Field(None, description="Task type for task_specific_mode")
    task_description: Optional[str] = Field(None, description="Specific task content")
    image_instruction: Optional[str] = Field(None, description="Image reference instruction")
    
    # Brand Kit - UPDATED: Replace branding_elements with brand_kit
    brand_kit: Optional[BrandKitInput] = Field(None, description="Structured brand kit with colors, voice, and logo")
    
    # Marketing goals
    marketing_audience: Optional[str] = Field(None, description="Target audience")
    marketing_objective: Optional[str] = Field(None, description="Marketing objective")
    marketing_voice: Optional[str] = Field(None, description="Brand voice")
    marketing_niche: Optional[str] = Field(None, description="Target niche")
    
    # Flags
    render_text: bool = Field(False, description="Whether to render text on image")
    apply_branding: bool = Field(False, description="Whether to apply branding")
    
    # Language control
    language: str = Field('en', description="ISO-639-1 code of desired output language")


class StyleRecipeData(BaseModel):
    """
    Stores the complete, structured output of the creative stages for 'Style Recipes'.
    This ensures all data needed for high-fidelity reproduction is captured.
    """
    visual_concept: VisualConceptDetails = Field(..., description="The detailed visual concept breakdown")
    strategy: MarketingGoalSetFinal = Field(..., description="The marketing strategy used")
    style_guidance: StyleGuidance = Field(..., description="The style guidance applied")
    
    # Optional fields for enhanced consistency
    generation_seed: Optional[str] = Field(None, description="Deterministic seed if supported by the model")
    model_parameters: Optional[Dict[str, Any]] = Field(None, description="Model-specific parameters used")


class StyleRecipeEnvelope(BaseModel):
    """
    A complete snapshot of the context required to reproduce or adapt a style.
    This will be the new structure for the 'style_recipe' JSON field.
    """
    recipe_data: StyleRecipeData = Field(..., description="The core AI-generated creative assets.")
    render_text: bool = Field(..., description="The 'render_text' setting from the original run.")
    apply_branding: bool = Field(..., description="The 'apply_branding' setting from the original run.")
    source_platform: str = Field(..., description="The 'platform_name' from the original run.")
    language: str = Field(default='en', description="The language (ISO 639-1) from the original run.")


class PresetMetadata(BaseModel):
    """Metadata for preset versioning and compatibility"""
    created_at: str = Field(..., description="ISO timestamp when preset was created")
    model_id: str = Field(..., description="Model identifier used (e.g., 'dall-e-3')")
    pipeline_version: str = Field(..., description="Version of the pipeline used")
    last_used_at: Optional[str] = Field(None, description="ISO timestamp when preset was last used")
    usage_count: int = Field(0, description="Number of times preset has been used") 