from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, HttpUrl
from datetime import datetime
from churns.api.database import RunStatus, StageStatus


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
    PING = "ping"


class WebSocketMessage(BaseModel):
    """WebSocket message structure"""
    type: str
    run_id: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    data: Dict[str, Any] = Field(default_factory=dict) 