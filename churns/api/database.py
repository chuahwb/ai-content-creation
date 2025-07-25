from typing import Optional
from sqlalchemy import Column, DateTime, Text, JSON
from sqlalchemy.sql import func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, Field
import uuid
from datetime import datetime
from enum import Enum
from churns.models.presets import PipelineInputSnapshot, StyleRecipeData
from churns.models import LogoAnalysisResult


class RunStatus(str, Enum):
    """Pipeline run status enumeration"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class StageStatus(str, Enum):
    """Pipeline stage status enumeration"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class RefinementType(str, Enum):
    """Refinement type enumeration"""
    SUBJECT = "subject"
    PROMPT = "prompt"


class PresetType(str, Enum):
    """Brand preset type enumeration"""
    INPUT_TEMPLATE = "INPUT_TEMPLATE"
    STYLE_RECIPE = "STYLE_RECIPE"


class PipelineRun(SQLModel, table=True):
    """Database model for pipeline runs"""
    __tablename__ = "pipeline_runs"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    status: RunStatus = Field(default=RunStatus.PENDING)
    mode: str = Field(description="Pipeline mode (easy_mode, custom_mode, task_specific_mode)")
    
    # User inputs
    platform_name: Optional[str] = Field(default=None)
    task_type: Optional[str] = Field(default=None)
    prompt: Optional[str] = Field(default=None)
    creativity_level: int = Field(default=2)
    render_text: bool = Field(default=False)
    apply_branding: bool = Field(default=False)
    
    # Image reference
    has_image_reference: bool = Field(default=False)
    image_filename: Optional[str] = Field(default=None)
    image_instruction: Optional[str] = Field(default=None)

    # Brand Kit data (UPDATED: unified brand kit structure)
    brand_kit: Optional[str] = Field(default=None, sa_column=Column(JSON), description="JSON string of BrandKitInput including colors, voice, and logo analysis")

    # Optional inputs
    task_description: Optional[str] = Field(default=None)
    marketing_audience: Optional[str] = Field(default=None)
    marketing_objective: Optional[str] = Field(default=None)
    marketing_voice: Optional[str] = Field(default=None)
    marketing_niche: Optional[str] = Field(default=None)
    language: Optional[str] = Field(default='en', description="ISO-639-1 language code for output")
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime(timezone=True), server_default=func.now()))
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    
    # Results
    total_cost_usd: Optional[float] = Field(default=None)
    total_duration_seconds: Optional[float] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    
    # File paths
    output_directory: Optional[str] = Field(default=None)
    metadata_file_path: Optional[str] = Field(default=None)


class RefinementJob(SQLModel, table=True):
    """Database model for image refinement jobs"""
    __tablename__ = "refinement_jobs"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    parent_run_id: str = Field(foreign_key="pipeline_runs.id")
    
    # Parent tracking
    parent_image_id: Optional[str] = Field(None, description="Points to another refinement or original")
    parent_image_type: str = Field("original", description="'original' | 'refinement'")
    parent_image_path: Optional[str] = Field(None, description="Direct path to parent image")
    generation_index: Optional[int] = Field(None, description="Which of N original images (0-based)")
    
    # Core refinement data
    refinement_type: RefinementType = Field(description="subject|text|prompt")
    status: RunStatus = Field(default=RunStatus.PENDING)
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime(timezone=True), server_default=func.now()))
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    cost_usd: Optional[float] = Field(default=None)
    
    # Results
    image_path: Optional[str] = Field(None, description="Path to refined image")
    error_message: Optional[str] = Field(default=None)
    
    # Input summary for UI
    refinement_summary: Optional[str] = Field(None, description="Brief description for display")
    
    # Refinement inputs
    prompt: Optional[str] = Field(None, description="User refinement prompt")
    instructions: Optional[str] = Field(None, description="Specific instructions")
    mask_data: Optional[str] = Field(None, sa_column=Column(Text), description="JSON string of mask coordinates")
    reference_image_path: Optional[str] = Field(None, description="Path to reference image for subject repair")


class PipelineStage(SQLModel, table=True):
    """Database model for individual pipeline stages"""
    __tablename__ = "pipeline_stages"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    run_id: str = Field(foreign_key="pipeline_runs.id")
    stage_name: str = Field(description="Name of the pipeline stage")
    stage_order: int = Field(description="Order of execution")
    status: StageStatus = Field(default=StageStatus.PENDING)
    
    # Execution details
    started_at: Optional[datetime] = Field(default=None)
    completed_at: Optional[datetime] = Field(default=None)
    duration_seconds: Optional[float] = Field(default=None)
    
    # Cost tracking
    model_id: Optional[str] = Field(default=None)
    provider: Optional[str] = Field(default=None)
    input_tokens: Optional[int] = Field(default=None)
    output_tokens: Optional[int] = Field(default=None)
    images_generated: Optional[int] = Field(default=None)
    stage_cost_usd: Optional[float] = Field(default=None)
    
    # Results and errors
    output_data: Optional[str] = Field(default=None, sa_column=Column(Text))  # JSON string
    error_message: Optional[str] = Field(default=None)
    error_traceback: Optional[str] = Field(default=None, sa_column=Column(Text))


class BrandPreset(SQLModel, table=True):
    """Database model for brand presets and style memory"""
    __tablename__ = "brand_presets"
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str = Field(description="User-friendly name for the preset")
    user_id: str = Field(description="User ID (non-nullable for security)")
    
    # Versioning and metadata
    version: int = Field(default=1, description="Version number for optimistic locking")
    model_id: str = Field(description="Model identifier used (e.g., 'dall-e-3')")
    pipeline_version: str = Field(description="Version of the pipeline used")
    
    # Brand Kit fields (UPDATED: unified brand kit structure)
    brand_kit: Optional[str] = Field(default=None, sa_column=Column(JSON), description="JSON string of BrandKitInput, which includes colors, voice, and logo analysis.")
    
    # Preset data fields
    preset_type: PresetType = Field(description="Type of preset: INPUT_TEMPLATE or STYLE_RECIPE")
    input_snapshot: Optional[str] = Field(default=None, sa_column=Column(Text), description="JSON string of PipelineInputSnapshot")
    style_recipe: Optional[str] = Field(default=None, sa_column=Column(Text), description="JSON string of StyleRecipeData")
    
    # Usage tracking
    usage_count: int = Field(default=0, description="Number of times preset has been used")
    last_used_at: Optional[datetime] = Field(default=None, description="When preset was last used")
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow, sa_column=Column(DateTime(timezone=True), server_default=func.now()))
    updated_at: Optional[datetime] = Field(default=None, sa_column=Column(DateTime(timezone=True), onupdate=func.now()))


# Database configuration - Updated to use async
DATABASE_URL = "sqlite+aiosqlite:///./data/runs.db"
engine = create_async_engine(DATABASE_URL, echo=False)

# Create async session factory
async_session_factory = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)


async def create_db_and_tables():
    """Create database tables asynchronously"""
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def get_session():
    """Get async database session"""
    async with async_session_factory() as session:
        yield session


# Backward compatibility function for scripts that need sync access
def get_sync_session():
    """Get synchronous database session for scripts/utilities"""
    import warnings
    from sqlalchemy import create_engine
    from sqlmodel import Session
    
    warnings.warn(
        "get_sync_session is deprecated. Use get_session() with async/await instead.",
        DeprecationWarning,
        stacklevel=2
    )
    
    sync_engine = create_engine("sqlite:///./data/runs.db", echo=False)
    with Session(sync_engine) as session:
        yield session 