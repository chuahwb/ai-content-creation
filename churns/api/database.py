from typing import Optional, Callable, TypeVar, Any
from sqlalchemy import Column, DateTime, Text, JSON, text, event
from sqlalchemy.sql import func
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import OperationalError
from sqlmodel import SQLModel, Field
import uuid
from datetime import datetime
from enum import Enum
from churns.models.presets import PipelineInputSnapshot, StyleRecipeData
from churns.models import LogoAnalysisResult
import logging
import asyncio
import random


logger = logging.getLogger(__name__)

T = TypeVar('T')


async def retry_db_operation(
    operation: Callable[[], T], 
    max_retries: int = 5,
    base_delay: float = 0.1,
    max_delay: float = 2.0,
    operation_name: str = "database operation"
) -> T:
    """
    Retry database operations with exponential backoff to handle SQLite lock contention.
    
    Args:
        operation: Async callable that performs the database operation
        max_retries: Maximum number of retry attempts
        base_delay: Base delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        operation_name: Name of the operation for logging
    
    Returns:
        Result of the successful operation
        
    Raises:
        OperationalError: If all retries are exhausted
    """
    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            return await operation()
        except OperationalError as e:
            if "database is locked" not in str(e).lower():
                # If it's not a lock error, don't retry
                raise
            
            last_error = e
            
            if attempt == max_retries:
                logger.error(f"Failed to execute {operation_name} after {max_retries} retries. Last error: {e}")
                raise
            
            # Calculate delay with exponential backoff and jitter
            delay = min(base_delay * (2 ** attempt), max_delay)
            jitter = random.uniform(0, delay * 0.1)  # Add up to 10% jitter
            total_delay = delay + jitter
            
            logger.warning(f"Database locked during {operation_name}, retrying in {total_delay:.2f}s (attempt {attempt + 1}/{max_retries})")
            await asyncio.sleep(total_delay)
    
    # This should never be reached, but just in case
    if last_error:
        raise last_error
    else:
        raise RuntimeError(f"Unexpected error in retry_db_operation for {operation_name}")


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
    
    # NEW: Unified input system storage
    unified_brief: Optional[str] = Field(default=None, sa_column=Column(JSON), description="JSON string of UnifiedBrief for new input system")

    # NEW: Preset and Style Adaptation fields
    preset_id: Optional[str] = Field(default=None, description="ID of applied brand preset")
    preset_type: Optional[str] = Field(default=None, description="Type of applied preset (INPUT_TEMPLATE or STYLE_RECIPE)")
    base_image_url: Optional[str] = Field(default=None, description="URL to the subject image for style adaptations")
    template_overrides: Optional[str] = Field(default=None, sa_column=Column(JSON), description="JSON string of template field overrides for INPUT_TEMPLATE presets")
    adaptation_prompt: Optional[str] = Field(default=None, description="New prompt for STYLE_RECIPE adaptation")

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
    
    # Noise assessment result
    needs_noise_reduction: Optional[bool] = Field(default=None, description="Noise assessment result: None=not assessed, True=noisy, False=clean")
    
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
    preset_source_type: str = Field(description="Source type of preset: 'user-input', 'brand-kit', or 'style-recipe'")
    pipeline_version: str = Field(description="Version of the pipeline used")
    
    # NEW: Source tracking for Style Recipes
    source_run_id: Optional[str] = Field(default=None, description="Run ID that this preset was created from")
    source_image_path: Optional[str] = Field(default=None, description="Path to the source image within the run directory")
    
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


# Database configuration - Updated to use async with improved settings
DATABASE_URL = "sqlite+aiosqlite:///./data/runs.db"
engine = create_async_engine(
    DATABASE_URL, 
    echo=False,
    connect_args={
        "check_same_thread": False,
    },
    pool_size=20,
    max_overflow=0,
    pool_pre_ping=True,
    pool_recycle=300,
)


# Configure SQLite pragmas for better performance and concurrency
async def setup_sqlite_pragmas(connection):
    """Setup SQLite pragmas for optimal performance with async operations"""
    try:
        # Enable WAL mode for better concurrent access
        await connection.execute(text("PRAGMA journal_mode=WAL"))
        # Set larger cache size (64MB)
        await connection.execute(text("PRAGMA cache_size=-64000"))
        # Enable foreign key constraints
        await connection.execute(text("PRAGMA foreign_keys=ON"))
        # Set synchronous mode to NORMAL for better performance
        await connection.execute(text("PRAGMA synchronous=NORMAL"))
        # Use memory for temporary storage
        await connection.execute(text("PRAGMA temp_store=MEMORY"))
        # Enable memory-mapped I/O (128MB)
        await connection.execute(text("PRAGMA mmap_size=134217728"))
        logger.info("SQLite pragmas configured successfully")
    except Exception as e:
        logger.warning(f"Failed to configure SQLite pragmas: {e}")


# Set up event listener to configure pragmas on new connections
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    """Set SQLite pragmas on new connections (sync version for compatibility)"""
    try:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA cache_size=-64000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA mmap_size=134217728")
        cursor.close()
    except Exception as e:
        logger.warning(f"Failed to set SQLite pragmas on connection: {e}")


# Create async session factory
async_session_factory = sessionmaker(
    engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)


async def migrate_brand_presets_add_source_fields():
    """Migration to add source_run_id and source_image_path fields to brand_presets table"""
    try:
        async with engine.begin() as conn:
            # Check if columns already exist
            result = await conn.execute(text("PRAGMA table_info(brand_presets)"))
            columns = [row[1] for row in result.fetchall()]
            
            if 'source_run_id' not in columns:
                await conn.execute(text("ALTER TABLE brand_presets ADD COLUMN source_run_id TEXT"))
                logger.info("Added source_run_id column to brand_presets table")
            
            if 'source_image_path' not in columns:
                await conn.execute(text("ALTER TABLE brand_presets ADD COLUMN source_image_path TEXT"))
                logger.info("Added source_image_path column to brand_presets table")
                
    except Exception as e:
        logger.error(f"Failed to migrate brand_presets table: {e}")
        # Don't raise the error to avoid breaking the app startup


async def migrate_pipeline_runs_preset_fields():
    """Migration to rename overrides to template_overrides and add adaptation_prompt field"""
    try:
        async with engine.begin() as conn:
            # Check if columns exist
            result = await conn.execute(text("PRAGMA table_info(pipeline_runs)"))
            columns = [row[1] for row in result.fetchall()]
            
            # Add new columns if they don't exist
            if 'template_overrides' not in columns:
                await conn.execute(text("ALTER TABLE pipeline_runs ADD COLUMN template_overrides TEXT"))
                logger.info("Added template_overrides column to pipeline_runs table")
                
                # Migrate data from old overrides column if it exists
                if 'overrides' in columns:
                    await conn.execute(text("UPDATE pipeline_runs SET template_overrides = overrides WHERE overrides IS NOT NULL"))
                    logger.info("Migrated data from overrides to template_overrides column")
            
            if 'adaptation_prompt' not in columns:
                await conn.execute(text("ALTER TABLE pipeline_runs ADD COLUMN adaptation_prompt TEXT"))
                logger.info("Added adaptation_prompt column to pipeline_runs table")
                
            # Drop old overrides column if it exists and new column was created successfully
            if 'overrides' in columns and 'template_overrides' in columns:
                # Verify data was migrated before dropping
                result = await conn.execute(text("SELECT COUNT(*) FROM pipeline_runs WHERE overrides IS NOT NULL AND template_overrides IS NULL"))
                unmigrated_count = result.scalar()
                
                if unmigrated_count == 0:
                    # Safe to drop old column (SQLite doesn't support DROP COLUMN directly, so we'll leave it)
                    # await conn.execute(text("ALTER TABLE pipeline_runs DROP COLUMN overrides"))
                    logger.info("Old overrides column left in place (SQLite limitation). Data successfully migrated to template_overrides.")
                else:
                    logger.warning(f"Found {unmigrated_count} rows with unmigrated data. Keeping both columns.")
                
    except Exception as e:
        logger.error(f"Failed to migrate pipeline_runs table: {e}")
        # Don't raise the error to avoid breaking the app startup


async def create_db_and_tables():
    """Create database and tables, including migrations"""
    async with engine.begin() as conn:
        # Set up SQLite pragmas for this connection
        await setup_sqlite_pragmas(conn)
        await conn.run_sync(SQLModel.metadata.create_all)
    
    # Run migrations for existing installations
    await migrate_brand_presets_add_source_fields()
    await migrate_pipeline_runs_preset_fields()
    
    logger.info("Database tables created and migrations applied")


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