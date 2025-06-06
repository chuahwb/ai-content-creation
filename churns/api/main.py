import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from churns.api.routers import api_router
from churns.api.database import create_db_and_tables


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting Churns API...")
    
    # Create database tables
    create_db_and_tables()
    logger.info("Database tables created/verified")
    
    # Ensure data directories exist
    os.makedirs("./data/runs", exist_ok=True)
    logger.info("Data directories created/verified")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Churns API...")


# Create FastAPI application
app = FastAPI(
    title="Churns API",
    description="""
    A modular AI-powered social media content generation pipeline.
    
    This API provides endpoints for:
    - Creating and managing pipeline runs
    - Real-time progress tracking via WebSocket
    - Retrieving generated images and metadata
    - Configuration management
    
    The pipeline consists of 6 stages:
    1. Image Evaluation (Vision-LLM analysis)
    2. Marketing Strategy Generation
    3. Style Guidance Generation  
    4. Creative Expert (Visual concepts)
    5. Prompt Assembly
    6. Image Generation (DALL-E)
    """,
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js development server
        "http://127.0.0.1:3000",
        "http://frontend:3000",   # Docker service name
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error": str(exc) if os.getenv("ENV") == "development" else "An error occurred"
        }
    )


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "churns-api",
        "version": "1.0.0"
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Churns API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "api": "/api/v1"
    }


# Include API routes
app.include_router(api_router)


if __name__ == "__main__":
    import uvicorn
    
    # Run with uvicorn for development
    uvicorn.run(
        "churns.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    ) 