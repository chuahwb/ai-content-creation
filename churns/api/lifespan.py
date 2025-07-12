import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from churns.pipeline.executor import PipelineExecutor
from churns.api.database import create_db_and_tables
import logging

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events - startup and shutdown."""
    # Startup
    logger.info("🚀 Starting Churns API...")
    
    # Create database tables
    await create_db_and_tables()
    logger.info("Database tables created/verified")
    
    # Ensure data directories exist
    os.makedirs("./data/runs", exist_ok=True)
    logger.info("Data directories created/verified")
    
    try:
        # Initialize the shared PipelineExecutor instances for all modes
        logger.info("🔧 Initializing shared PipelineExecutor instances...")
        
        # Create executors for each mode
        app.state.generation_executor = PipelineExecutor(mode="generation")
        logger.info("✅ Generation executor initialized successfully")
        
        app.state.refinement_executor = PipelineExecutor(mode="refinement")
        logger.info("✅ Refinement executor initialized successfully")
        
        app.state.caption_executor = PipelineExecutor(mode="caption")
        logger.info("✅ Caption executor initialized successfully")
        
        # Log executor configuration summary
        executors = {
            "generation": app.state.generation_executor,
            "refinement": app.state.refinement_executor,
            "caption": app.state.caption_executor
        }
        
        total_configured = 0
        total_clients = 0
        
        for mode, executor in executors.items():
            client_summary = executor.get_client_summary()
            configured_count = sum(1 for status in client_summary.values() if "✅" in status)
            mode_total = len(client_summary)
            total_configured += configured_count
            total_clients += mode_total
            logger.info(f"📊 {mode.capitalize()} executor ready: {configured_count}/{mode_total} clients configured")
        
        logger.info(f"🎯 All executors ready: {total_configured}/{total_clients} total clients configured across 3 modes")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize PipelineExecutors: {e}")
        raise  # Fail fast - don't start the app if executors can't be created
    
    logger.info("🎉 Application startup completed successfully")
    
    yield
    
    # Shutdown (optional cleanup)
    logger.info("🛑 Shutting down Churns API...")
    # Note: PipelineExecutors don't require explicit cleanup currently
    logger.info("✅ Application shutdown completed") 