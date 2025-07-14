from fastapi import Request
from churns.pipeline.executor import PipelineExecutor

def get_executor(request: Request) -> PipelineExecutor:
    """
    Dependency to get the shared PipelineExecutor instance.
    
    DEPRECATED: Use get_generation_executor() for new code.
    This function is maintained for backward compatibility.
    """
    return request.app.state.generation_executor

def get_generation_executor(request: Request) -> PipelineExecutor:
    """Dependency to get the shared generation PipelineExecutor instance."""
    return request.app.state.generation_executor

def get_refinement_executor(request: Request) -> PipelineExecutor:
    """Dependency to get the shared refinement PipelineExecutor instance."""
    return request.app.state.refinement_executor

def get_caption_executor(request: Request) -> PipelineExecutor:
    """Dependency to get the shared caption PipelineExecutor instance."""
    return request.app.state.caption_executor 