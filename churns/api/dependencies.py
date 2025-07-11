from fastapi import Request
from churns.pipeline.executor import PipelineExecutor

def get_executor(request: Request) -> PipelineExecutor:
    """Dependency to get the shared PipelineExecutor instance."""
    return request.app.state.executor 