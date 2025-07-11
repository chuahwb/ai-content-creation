from contextlib import asynccontextmanager
from fastapi import FastAPI
from churns.pipeline.executor import PipelineExecutor
import logging

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events - startup and shutdown."""
    # Startup
    logger.info("🚀 Starting application initialization...")
    
    try:
        # Initialize the shared PipelineExecutor instance
        logger.info("🔧 Initializing shared PipelineExecutor...")
        app.state.executor = PipelineExecutor()
        logger.info("✅ PipelineExecutor initialized successfully")
        
        # Log executor configuration summary
        client_summary = app.state.executor.get_client_summary()
        configured_count = sum(1 for status in client_summary.values() if "✅" in status)
        total_count = len(client_summary)
        logger.info(f"📊 Executor ready: {configured_count}/{total_count} clients configured")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize PipelineExecutor: {e}")
        raise  # Fail fast - don't start the app if executor can't be created
    
    logger.info("🎉 Application startup completed successfully")
    
    yield
    
    # Shutdown (optional cleanup)
    logger.info("🛑 Application shutdown initiated")
    # Note: PipelineExecutor doesn't require explicit cleanup currently
    logger.info("✅ Application shutdown completed") 