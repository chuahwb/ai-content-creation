from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime
from churns.api.database import RunStatus, StageStatus, RefinementType


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
    branding_elements: Optional[str] = Field(default=None, description="Branding guidelines")
    
    # Image inputs
    image_reference: Optional[ImageReferenceInput] = Field(default=None, description="Reference image data")
    
    # Flags
    render_text: bool = Field(default=False, description="Whether to render text on image")
    apply_branding: bool = Field(default=False, description="Whether to apply branding")
    
    # Marketing goals (for custom/task_specific modes)
    marketing_goals: Optional[MarketingGoalsInput] = Field(default=None, description="Marketing strategy goals")
    
    # Language control
    language: Optional[str] = Field(default='en', description="ISO-639-1 code of desired output language")


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
    branding_elements: Optional[str] = None
    task_description: Optional[str] = None
    marketing_audience: Optional[str] = None
    marketing_objective: Optional[str] = None
    marketing_voice: Optional[str] = None
    marketing_niche: Optional[str] = None
    language: Optional[str] = None


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
    main_text: str
    secondary_texts: List[str]
    object_description: str
    brand_name: str
    corrections: Dict


# Caption-related schemas
class CaptionSettings(BaseModel):
    """User settings for caption generation"""
    tone: Optional[str] = Field(None, description="Caption tone (e.g., 'Professional & Polished', 'Friendly & Casual')")
    call_to_action: Optional[str] = Field(None, description="User-defined call to action text")
    include_emojis: Optional[bool] = Field(True, description="Whether to include emojis in the caption")
    hashtag_strategy: Optional[str] = Field(None, description="Hashtag strategy ('None', 'Niche & Specific', 'Broad & Trending', 'Balanced Mix')")


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
