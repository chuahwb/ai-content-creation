"""
Input normalizer for the unified input system.
Maps the new UnifiedBrief object to the legacy PipelineContext fields.
"""

from churns.pipeline.context import PipelineContext
from churns.api.schemas import UnifiedBrief


def normalize_unified_brief_into_context(brief: UnifiedBrief, ctx: PipelineContext) -> None:
    """
    Populates the pipeline context from the new unified brief.
    
    This function maps the new UnifiedBrief fields to the existing PipelineContext
    fields to maintain backward compatibility with the existing pipeline stages.
    
    The normalizer is designed to be tolerant of field changes:
    - Removed fields (like textOverlay.language, styleHints) are ignored
    - Only processes fields that are currently defined in the schema
    
    Args:
        brief: The unified brief containing the new input structure
        ctx: The pipeline context to populate
    """
    # Map generalBrief to the main prompt field
    ctx.prompt = brief.generalBrief
    
    # Handle edit instructions for image editing scenarios
    if brief.intentType == "instructedEdit" and brief.editInstruction:
        if ctx.image_reference is None:
            ctx.image_reference = {}
        ctx.image_reference["instruction"] = brief.editInstruction
    
    # Handle text overlay - map to task_description for literal text rendering
    if brief.textOverlay and brief.textOverlay.raw:
        ctx.task_description = brief.textOverlay.raw
        
        # Language is now handled globally, not per-textOverlay
        # (textOverlay.language field has been removed)
    
    # Style guidance is handled by dedicated Style Guide stage in the pipeline
    # Users can include style preferences directly in the generalBrief
