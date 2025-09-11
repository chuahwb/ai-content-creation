from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, HttpUrl, field_validator
from datetime import datetime
from churns.api.database import RunStatus, StageStatus, RefinementType, PresetType
from churns.models import BrandKitInput
from churns.models.presets import StyleRecipeData, PipelineInputSnapshot, StyleRecipeEnvelope


class ParentPresetInfo(BaseModel):
    """Information about the parent preset for style adaptation runs"""
    id: str = Field(description="ID of the parent preset")
    name: str = Field(description="Name of the parent preset")
    image_url: Optional[str] = Field(None, description="Filename of the parent preset's reference image")
    source_run_id: Optional[str] = Field(None, description="ID of the run that created this preset")


class TextOverlay(BaseModel):
    """Text overlay configuration for the unified input system"""
    raw: Optional[str] = None
    
    class Config:
        extra = 'ignore'  # Ignore extra fields from older clients


class UnifiedBrief(BaseModel):
    """Unified brief that replaces the three legacy user inputs (prompt, imageInstruction, taskDescription)"""
    intentType: Literal[
        "fullGeneration", "defaultEdit", "instructedEdit", "styleAdaptation", "logoOnly"
    ]
    generalBrief: str
    editInstruction: Optional[str] = None
    textOverlay: Optional[TextOverlay] = None
    
    class Config:
        extra = 'ignore'  # Ignore extra fields from older clients


class ImageReferenceInput(BaseModel):
    """Image reference input data"""
    filename: str
    content_type: str
    size_bytes: int
    instruction: Optional[str] = None


class MarketingGoalsInput(BaseModel):
    """Marketing goals input"""
    target_audience: Optional[str] = None
    objective: Optional[str] = None
    voice: Optional[str] = None
    niche: Optional[str] = None


class PipelineRunRequest(BaseModel):
    """Request model for creating a new pipeline run"""
    # Core inputs
    mode: str = Field(description="Pipeline mode: easy_mode, custom_mode, or task_specific_mode")
    platform_name: str = Field(description="Target social media platform")
    creativity_level: int = Field(default=2, ge=1, le=3, description="Creativity level 1-3")
    num_variants: int = Field(default=3, ge=1, le=6, description="Number of strategy/image variants to generate")
    
    # Content inputs
    prompt: Optional[str] = Field(default=None, description="User's text prompt")
    task_type: Optional[str] = Field(default=None, description="Task type for task_specific_mode")
    task_description: Optional[str] = Field(default=None, description="Specific task content")
    
    # Image inputs
    image_reference: Optional[ImageReferenceInput] = Field(default=None, description="Reference image data")
    
    # Flags
    render_text: bool = Field(default=False, description="Whether to render text on image")
    apply_branding: bool = Field(default=False, description="Whether to apply branding")
    
    # Marketing goals (for custom/task_specific modes)
    marketing_goals: Optional[MarketingGoalsInput] = Field(default=None, description="Marketing strategy goals")
    
    # Language control
    language: Optional[str] = Field(default='en', description="ISO-639-1 code of desired output language")
    
    # Brand Preset support
    preset_id: Optional[str] = Field(default=None, description="ID of brand preset to apply")
    preset_type: Optional[str] = Field(default=None, description="Type of preset being applied")
    template_overrides: Optional[Dict[str, Any]] = Field(default=None, description="Field overrides for INPUT_TEMPLATE presets")
    adaptation_prompt: Optional[str] = Field(default=None, description="New prompt for STYLE_RECIPE adaptation")
    
    # Brand Kit data (UPDATED: replaced legacy fields with unified brand_kit)
    brand_kit: Optional[BrandKitInput] = Field(default=None, description="Brand kit with colors, voice, and logo")
    
    # NEW: Unified input system
    unifiedBrief: Optional[UnifiedBrief] = Field(default=None, description="Unified brief replacing prompt, imageInstruction, taskDescription")


class RefinementRequest(BaseModel):
    """Request model for image refinement"""
    refine_type: RefinementType = Field(description="Type of refinement: subject, text, or prompt")
    parent_image_id: str = Field(description="ID of the image to refine")
    parent_image_type: str = Field(default="original", description="'original' or 'refinement'")
    generation_index: Optional[int] = Field(None, description="Which of N original images (0-based)")
    
    # Refinement inputs
    prompt: Optional[str] = Field(None, description="Refinement prompt")
    instructions: Optional[str] = Field(None, description="Specific instructions")
    mask_data: Optional[str] = Field(None, description="JSON string of mask coordinates")
    
    # Reference image for subject repair
    reference_image: Optional[ImageReferenceInput] = Field(None, description="Reference image for subject repair")


class RefinementResponse(BaseModel):
    """Response model for refinement job creation"""
    job_id: str
    parent_run_id: str
    refinement_type: RefinementType
    status: RunStatus
    created_at: datetime
    refinement_summary: Optional[str] = None


class RefinementResult(BaseModel):
    """Result of a refinement job"""
    job_id: str
    parent_run_id: str
    refinement_type: RefinementType
    status: RunStatus
    parent_image_id: str
    parent_image_type: str
    generation_index: Optional[int] = None
    image_path: Optional[str] = None
    cost_usd: Optional[float] = None
    refinement_summary: Optional[str] = None
    needs_noise_reduction: Optional[bool] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None


class RefinementListResponse(BaseModel):
    """Response for listing refinements of a run"""
    refinements: List[RefinementResult]
    total_cost: float = 0.0
    total_refinements: int = 0


class StageProgressUpdate(BaseModel):
    """Progress update for a pipeline stage"""
    stage_name: str
    stage_order: int
    status: StageStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None
    message: str
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class PipelineRunResponse(BaseModel):
    """Response model for pipeline run status"""
    id: str
    status: RunStatus
    mode: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    total_duration_seconds: Optional[float] = None
    total_cost_usd: Optional[float] = None
    error_message: Optional[str] = None
    output_directory: Optional[str] = None
    metadata_file_path: Optional[str] = None
    
    # NEW FIELDS for Style Adaptation
    preset_id: Optional[str] = Field(None, description="ID of the applied preset")
    preset_type: Optional[str] = Field(None, description="Type of applied preset") 
    base_image_url: Optional[str] = Field(None, description="URL to the subject image for style adaptations")
    template_overrides: Optional[Dict[str, Any]] = Field(None, description="Template overrides applied")
    adaptation_prompt: Optional[str] = Field(None, description="Adaptation prompt used")
    parent_preset: Optional[ParentPresetInfo] = Field(None, description="Parent preset info for STYLE_RECIPE runs")


class PipelineRunDetail(PipelineRunResponse):
    """Detailed response model including stages and form inputs"""
    stages: List[StageProgressUpdate] = []
    
    # Form input data
    platform_name: Optional[str] = None
    task_type: Optional[str] = None
    prompt: Optional[str] = None
    creativity_level: int = 2
    render_text: bool = False
    apply_branding: bool = False
    has_image_reference: bool = False
    image_filename: Optional[str] = None
    image_instruction: Optional[str] = None
    task_description: Optional[str] = None
    marketing_audience: Optional[str] = None
    marketing_objective: Optional[str] = None
    marketing_voice: Optional[str] = None
    marketing_niche: Optional[str] = None
    language: Optional[str] = None

    # Brand Kit data (UPDATED: unified brand kit structure)
    brand_kit: Optional[Dict[str, Any]] = None
    
    # NEW: Unified input system
    unified_brief: Optional[UnifiedBrief] = None


class GeneratedImageResult(BaseModel):
    """Result of image generation"""
    strategy_index: int
    status: str  # "success" or "error"
    image_path: Optional[str] = None
    error_message: Optional[str] = None
    prompt_used: Optional[str] = None


class PipelineResults(BaseModel):
    """Complete pipeline results"""
    run_id: str
    status: RunStatus
    
    # Analysis results
    image_analysis: Optional[Dict[str, Any]] = None
    marketing_strategies: Optional[List[Dict[str, Any]]] = None
    style_guidance: Optional[List[Dict[str, Any]]] = None
    visual_concepts: Optional[List[Dict[str, Any]]] = None
    
    # Generated outputs
    final_prompts: Optional[List[Dict[str, Any]]] = None
    generated_images: Optional[List[GeneratedImageResult]] = None
    
    # NEW: Image assessments
    image_assessments: Optional[List[Dict[str, Any]]] = None
    
    # NEW: Refinements
    refinements: Optional[List[RefinementResult]] = None
    
    # Cost and performance
    total_cost_usd: Optional[float] = None
    total_duration_seconds: Optional[float] = None
    stage_costs: Optional[List[Dict[str, Any]]] = None


class RunListItem(BaseModel):
    """Simplified run item for listing"""
    id: str
    status: RunStatus
    mode: str
    platform_name: Optional[str] = None
    task_type: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    total_cost_usd: Optional[float] = None
    
    # NEW: Style Adaptation fields
    preset_type: Optional[str] = Field(None, description="Type of applied preset")
    parent_preset: Optional[ParentPresetInfo] = Field(None, description="Parent preset info for STYLE_RECIPE runs")


class RunListResponse(BaseModel):
    """Response for listing runs"""
    runs: List[RunListItem]
    total: int
    page: int
    page_size: int


# WebSocket message types
class WSMessageType(str):
    STAGE_UPDATE = "stage_update"
    RUN_COMPLETE = "run_complete"
    RUN_ERROR = "run_error"
    REFINEMENT_UPDATE = "refinement_update"
    REFINEMENT_COMPLETE = "refinement_complete"
    REFINEMENT_ERROR = "refinement_error"
    PING = "ping"


class WebSocketMessage(BaseModel):
    """WebSocket message structure"""
    type: str
    run_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: Dict[str, Any] = Field(default_factory=dict)


class ImageAnalysisResult(BaseModel):  
    """Image analysis result from text repair stage"""
    main_text: Optional[str]
    secondary_texts: Optional[List[str]]
    object_description: Optional[str]
    brand_name: Optional[str]
    corrections: Optional[Dict]


# Caption-related schemas
class CaptionSettings(BaseModel):
    """User settings for caption generation"""
    tone: Optional[str] = Field(None, description="Caption tone (e.g., 'Professional & Polished', 'Friendly & Casual')")
    call_to_action: Optional[str] = Field(None, description="User-defined call to action text")
    include_emojis: Optional[bool] = Field(True, description="Whether to include emojis in the caption")
    hashtag_strategy: Optional[str] = Field(None, description="Hashtag strategy ('None', 'Niche & Specific', 'Broad & Trending', 'Balanced Mix')")
    user_instructions: Optional[str] = Field(None, description="Direct user instructions for the caption generation")
    caption_length: Optional[Literal["Auto", "Short", "Medium", "Long"]] = Field("Auto", description="Desired caption length")
    generation_mode: Literal['Auto', 'Custom'] = Field('Auto', description="Auto or Custom - indicates how the settings were determined")
    processing_mode: Optional[Literal['Fast', 'Analytical']] = Field(None, description="Fast (quick response) or Analytical (thoughtful analysis) - determines model selection")


class CaptionModelOption(BaseModel):
    """Available caption model option"""
    id: str = Field(description="Model ID")
    name: str = Field(description="User-friendly model name")
    description: str = Field(description="Model description")
    strengths: List[str] = Field(description="Model strengths")
    best_for: str = Field(description="Best use cases")
    latency: str = Field(description="Latency level")
    creativity: str = Field(description="Creativity level")


class CaptionModelsResponse(BaseModel):
    """Response model for available caption models"""
    models: List[CaptionModelOption] = Field(description="Available caption models")
    default_model_id: str = Field(description="Default model ID")


class CaptionRequest(BaseModel):
    """Request model for caption generation"""
    settings: Optional[CaptionSettings] = Field(default=None, description="Caption generation settings")
    model_id: Optional[str] = Field(default=None, description="Selected model ID (uses default if not provided)")


class CaptionRegenerateRequest(BaseModel):
    """Request model for caption regeneration"""
    settings: Optional[CaptionSettings] = Field(default=None, description="New caption settings (if provided, runs full pipeline)")
    writer_only: bool = Field(default=True, description="If true and no new settings, only regenerates writer step")
    model_id: Optional[str] = Field(default=None, description="Selected model ID (uses previous model if not provided)")


class CaptionResponse(BaseModel):
    """Response model for caption generation"""
    caption_id: str = Field(description="Unique ID for this caption")
    image_id: str = Field(description="ID of the associated image")
    text: str = Field(description="The generated caption text")
    version: int = Field(description="Version number of this caption")
    settings_used: CaptionSettings = Field(description="Settings that were used to generate this caption")
    created_at: datetime = Field(description="When the caption was created")
    status: str = Field(description="Status of caption generation")


# Brand Preset schemas
class BrandPresetCreateRequest(BaseModel):
    """Request model for creating a brand preset"""
    name: str = Field(description="User-friendly name for the preset")
    preset_type: str = Field(description="Type of preset: INPUT_TEMPLATE or STYLE_RECIPE")
    
    # Brand Kit (UPDATED: unified brand kit structure)
    brand_kit: Optional[BrandKitInput] = Field(None, description="Brand kit with colors, voice, and logo")
    
    # Preset data (one of these should be provided based on preset_type)
    input_snapshot: Optional[PipelineInputSnapshot] = Field(None, description="Pipeline input snapshot for INPUT_TEMPLATE")
    style_recipe: Optional[StyleRecipeData] = Field(None, description="Style recipe data for STYLE_RECIPE")
    
    # Metadata
    preset_source_type: str = Field(description="Source type: 'user-input', 'brand-kit', or 'style-recipe'")
    pipeline_version: str = Field(description="Version of the pipeline used")


class BrandPresetUpdateRequest(BaseModel):
    """Request model for updating a brand preset"""
    name: Optional[str] = Field(None, description="Updated name")
    version: int = Field(description="Current version for optimistic locking")
    
    # Brand Kit (UPDATED: unified brand kit structure)
    brand_kit: Optional[BrandKitInput] = Field(None, description="Brand kit with colors, voice, and logo")


class BrandPresetResponse(BaseModel):
    """Response model for brand preset"""
    id: str = Field(description="Unique preset ID")
    name: str = Field(description="User-friendly name")
    preset_type: str = Field(description="Type of preset")
    version: int = Field(description="Current version")
    preset_source_type: str = Field(description="Source type: 'user-input', 'brand-kit', or 'style-recipe'")
    pipeline_version: str = Field(description="Pipeline version")
    usage_count: int = Field(description="Number of times used")
    created_at: datetime = Field(description="Creation timestamp")
    last_used_at: Optional[datetime] = Field(None, description="Last usage timestamp")
    
    # Brand Kit (UPDATED: unified brand kit structure)
    brand_kit: Optional[BrandKitInput] = Field(None, description="Brand kit with colors, voice, and logo")
    
    # Preset data
    input_snapshot: Optional[PipelineInputSnapshot] = Field(None, description="Input snapshot")
    style_recipe: Optional[StyleRecipeEnvelope] = Field(None, description="Style recipe envelope with context")


class BrandPresetListResponse(BaseModel):
    """Response model for listing brand presets"""
    presets: List[BrandPresetResponse]
    total: int = Field(description="Total number of presets")


class SavePresetFromResultRequest(BaseModel):
    """Request model for saving a preset from a pipeline result"""
    name: str = Field(description="Name for the new preset")
    generation_index: int = Field(description="Which generated image to save as preset (0-based)")
    
    # Brand Kit (UPDATED: unified brand kit structure)
    brand_kit: Optional[BrandKitInput] = Field(None, description="Brand kit with colors, voice, and logo")

class ImageAgentInput(BaseModel):
    """Input model for image processing"""
    image_path: str = Field(..., description="Path to the overlay image file")
    base_path: str = Field(..., description="Path to the base image file")

class ImageAgentOutput(BaseModel):
    """Output model for image processing"""
    image_path: str = Field(..., description="Path to the processed image file")
    message: str = Field(..., description="Message")

class PlanStep(BaseModel):
    """A single step in the tool execution plan."""
    tool: str = Field(..., description="Name of the tool to execute")
    args: Dict[str, Any] = Field(default_factory=dict, description="Arguments for the tool call")

class PromptOutput(BaseModel):
    """Output model for prompt generation agent."""
    prompt: str = Field(..., description="The generated prompt for image processing")
    hex_color: Optional[str] = Field(None, description="Hex color code for image processing")
    alpha_value: Optional[int] = Field(None, description="Transparency level (0-255)")
    position: Optional[List[int]] = Field(None, description="Position [x, y] for overlay")
    scale: Optional[float] = Field(None, description="Scale factor for the overlay")

    @field_validator('position')
    def validate_position(cls, v):
        if v is not None and (len(v) != 2 or not all(isinstance(i, int) for i in v)):
            raise ValueError("Position must be a list of two integers [x, y]")
        return v

class PlannerOutput(BaseModel):
    """Structured plan produced by the planner agent."""
    rationale: str
    steps: List[PlanStep]