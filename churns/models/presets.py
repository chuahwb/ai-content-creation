"""
Pydantic models for Brand Preset & Style Memory feature.
These models support both 'Input Templates' and 'Style Recipes' workflows.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from churns.models import VisualConceptDetails, MarketingGoalSetFinal, StyleGuidance


class PipelineInputSnapshot(BaseModel):
    """
    Mirrors the structure of the main pipeline form for 'Input Templates'.
    Captures user's raw form inputs in a structured model.
    """
    # Core inputs
    prompt: Optional[str] = Field(None, description="User's text prompt")
    creativity_level: int = Field(2, ge=1, le=3, description="Creativity level 1-3")
    platform_name: str = Field(..., description="Target social media platform")
    num_variants: int = Field(3, ge=1, le=6, description="Number of strategy/image variants to generate")
    
    # Content inputs
    task_type: Optional[str] = Field(None, description="Task type for task_specific_mode")
    task_description: Optional[str] = Field(None, description="Specific task content")
    branding_elements: Optional[str] = Field(None, description="Branding guidelines")
    image_instruction: Optional[str] = Field(None, description="Image reference instruction")
    
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
    final_prompt: str = Field(..., description="The exact prompt sent to the image generation model")
    
    # Optional fields for enhanced consistency
    generation_seed: Optional[str] = Field(None, description="Deterministic seed if supported by the model")
    model_parameters: Optional[Dict[str, Any]] = Field(None, description="Model-specific parameters used")


class BrandColors(BaseModel):
    """Brand color palette configuration"""
    colors: List[str] = Field(..., description="Array of HEX color strings (e.g., ['#1A2B3C', '#FFD700'])")
    primary_color: Optional[str] = Field(None, description="Primary brand color (HEX)")
    secondary_color: Optional[str] = Field(None, description="Secondary brand color (HEX)")


class LogoAnalysis(BaseModel):
    """Analysis of uploaded logo asset"""
    filename: str = Field(..., description="Original filename of the logo")
    file_size_kb: int = Field(..., description="File size in KB")
    dimensions: Optional[str] = Field(None, description="Image dimensions (e.g., '512x512')")
    format: Optional[str] = Field(None, description="File format (e.g., 'PNG', 'SVG')")
    preview_path: Optional[str] = Field(None, description="Path to optimized preview (<200KB)")
    analysis_notes: Optional[str] = Field(None, description="AI-generated analysis of logo characteristics")


class PresetMetadata(BaseModel):
    """Metadata for preset versioning and compatibility"""
    created_at: str = Field(..., description="ISO timestamp when preset was created")
    model_id: str = Field(..., description="Model identifier used (e.g., 'dall-e-3')")
    pipeline_version: str = Field(..., description="Version of the pipeline used")
    last_used_at: Optional[str] = Field(None, description="ISO timestamp when preset was last used")
    usage_count: int = Field(0, description="Number of times preset has been used") 