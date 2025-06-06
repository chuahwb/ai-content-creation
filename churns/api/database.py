from typing import Optional
from sqlalchemy import create_engine, Column, DateTime, Text
from sqlalchemy.sql import func
from sqlmodel import SQLModel, Field, Session
import uuid
from datetime import datetime
from enum import Enum


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
    
    # Optional inputs
    branding_elements: Optional[str] = Field(default=None)
    task_description: Optional[str] = Field(default=None)
    marketing_audience: Optional[str] = Field(default=None)
    marketing_objective: Optional[str] = Field(default=None)
    marketing_voice: Optional[str] = Field(default=None)
    marketing_niche: Optional[str] = Field(default=None)
    
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


# Database configuration
DATABASE_URL = "sqlite:///./data/runs.db"
engine = create_engine(DATABASE_URL, echo=False)


def create_db_and_tables():
    """Create database tables"""
    SQLModel.metadata.create_all(engine)


def get_session():
    """Get database session"""
    with Session(engine) as session:
        yield session 