"""
Pipeline context for maintaining state across stages.
Replaces the nested pipeline_data dict from the original monolith.
"""

import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PipelineContext:
    """
    Context object that maintains pipeline state across all stages.
    This replaces the nested pipeline_data dict from the original monolith.
    """
    
    # Pipeline settings
    run_id: str = field(default_factory=lambda: datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    creativity_level: int = 1
    num_variants: int = 3
    
    # Request details
    mode: str = "easy_mode"
    task_type: Optional[str] = None
    target_platform: Optional[Dict[str, Any]] = None
    
    # User inputs
    prompt: Optional[str] = None
    image_reference: Optional[Dict[str, Any]] = None
    render_text: bool = False
    apply_branding: bool = False
    branding_elements: Optional[str] = None
    task_description: Optional[str] = None
    marketing_goals: Optional[Dict[str, Any]] = None
    
    # === REFINEMENT PROPERTIES ===
    # Pipeline mode ("generation" or "refinement")
    pipeline_mode: str = "generation"
    
    # Parent information for refinements
    parent_run_id: Optional[str] = None
    parent_image_id: Optional[str] = None
    parent_image_type: str = "original"
    generation_index: Optional[int] = None
    base_image_path: Optional[str] = None
    
    # Refinement specifics
    refinement_type: Optional[str] = None  # "subject", "text", "prompt"
    mask_coordinates: Optional[List] = None
    reference_image_path: Optional[str] = None
    instructions: Optional[str] = None
    
    # Refinement results
    refinement_result: Optional[Dict[str, Any]] = None
    refinement_cost: Optional[float] = None
    
    # Processing results
    image_analysis_result: Optional[Dict[str, Any]] = None
    suggested_marketing_strategies: Optional[List[Dict[str, Any]]] = None
    style_guidance_sets: Optional[List[Dict[str, Any]]] = None
    generated_image_prompts: List[Dict[str, Any]] = field(default_factory=list)
    final_assembled_prompts: List[Dict[str, Any]] = field(default_factory=list)
    generated_image_results: List[Dict[str, Any]] = field(default_factory=list)
    image_assessments: Optional[List[Dict[str, Any]]] = None
    
    # Usage tracking
    llm_usage: Dict[str, Any] = field(default_factory=dict)
    cost_summary: Optional[Dict[str, Any]] = None
    
    # Logs and output
    logs: List[str] = field(default_factory=list)
    output_directory: Optional[str] = None
    
    # Client injection for API calls
    # Image evaluation clients
    image_eval_instructor_client: Optional[Any] = None
    image_eval_base_client: Optional[Any] = None
    
    # Strategy generation clients
    strategy_instructor_client: Optional[Any] = None
    strategy_base_client: Optional[Any] = None
    
    # Style guide client
    style_guide_client: Optional[Any] = None
    
    # Creative expert client
    creative_expert_client: Optional[Any] = None
    
    # Creative expert clients (for future use)
    creative_expert_instructor_client: Optional[Any] = None
    creative_expert_base_client: Optional[Any] = None
    
    # Image generation client (for future use)
    image_generation_client: Optional[Any] = None
    
    def log(self, message: str) -> None:
        """Add a log message with timestamp."""
        timestamp = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
        log_entry = f"[{timestamp}] {message}"
        self.logs.append(log_entry)
        print(log_entry)  # Also print to console for now
    
    def add_image_assessment(self, assessment_data: Dict[str, Any]) -> None:
        """Add assessment data for an image."""
        if self.image_assessments is None:
            self.image_assessments = []
        self.image_assessments.append(assessment_data)
    
    def get_assessment_for_image(self, image_index: int) -> Optional[Dict[str, Any]]:
        """Get assessment data for a specific image."""
        if self.image_assessments is None:
            return None
        for assessment in self.image_assessments:
            if assessment.get('image_index') == image_index:
                return assessment
        return None
    
    def is_refinement_mode(self) -> bool:
        """Check if this is a refinement context."""
        return self.pipeline_mode == "refinement"
    
    def set_refinement_context(
        self, 
        parent_run_id: str,
        parent_image_id: str,
        parent_image_type: str,
        refinement_type: str,
        base_image_path: str,
        generation_index: Optional[int] = None,
        mask_coordinates: Optional[List] = None,
        reference_image_path: Optional[str] = None,
        instructions: Optional[str] = None
    ) -> None:
        """Set refinement context properties."""
        self.pipeline_mode = "refinement"
        self.parent_run_id = parent_run_id
        self.parent_image_id = parent_image_id
        self.parent_image_type = parent_image_type
        self.refinement_type = refinement_type
        self.base_image_path = base_image_path
        self.generation_index = generation_index
        self.mask_coordinates = mask_coordinates
        self.reference_image_path = reference_image_path
        self.instructions = instructions
    
    @property
    def data(self) -> Dict[str, Any]:
        """
        Property that returns the data in the legacy dict format.
        This allows stages to access ctx.data["processing_context"] etc.
        """
        return self.to_dict()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary format (for compatibility with original monolith)."""
        base_dict = {
            "pipeline_settings": {
                "run_timestamp": self.run_id,
                "creativity_level_selected": self.creativity_level,
                "num_variants": self.num_variants,
                "pipeline_mode": self.pipeline_mode
            },
            "request_details": {
                "mode": self.mode,
                "task_type": self.task_type,
                "target_platform": self.target_platform
            },
            "user_inputs": {
                "prompt": self.prompt,
                "image_reference": self.image_reference,
                "render_text": self.render_text,
                "apply_branding": self.apply_branding,
                "branding_elements": self.branding_elements,
                "task_description": self.task_description,
                "marketing_goals": self.marketing_goals
            },
            "processing_context": {
                "image_analysis_result": self.image_analysis_result,
                "suggested_marketing_strategies": self.suggested_marketing_strategies,
                "style_guidance_sets": self.style_guidance_sets,
                "generated_image_prompts": self.generated_image_prompts,
                "final_assembled_prompts": self.final_assembled_prompts,
                "generated_image_results": self.generated_image_results,
                **({} if self.image_assessments is None else {"image_assessment": self.image_assessments}),
                "llm_call_usage": self.llm_usage,
                "cost_summary": self.cost_summary
            }
        }
        
        # Add refinement context if in refinement mode
        if self.is_refinement_mode():
            base_dict["refinement_context"] = {
                "parent_run_id": self.parent_run_id,
                "parent_image_id": self.parent_image_id,
                "parent_image_type": self.parent_image_type,
                "generation_index": self.generation_index,
                "base_image_path": self.base_image_path,
                "refinement_type": self.refinement_type,
                "mask_coordinates": self.mask_coordinates,
                "reference_image_path": self.reference_image_path,
                "instructions": self.instructions,
                "refinement_result": self.refinement_result,
                "refinement_cost": self.refinement_cost
            }
        
        return base_dict
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PipelineContext':
        """Create context from dictionary format (for compatibility with original monolith)."""
        pipeline_settings = data.get("pipeline_settings", {})
        request_details = data.get("request_details", {})
        user_inputs = data.get("user_inputs", {})
        processing_context = data.get("processing_context", {})
        refinement_context = data.get("refinement_context", {})
        
        ctx = cls(
            run_id=pipeline_settings.get("run_timestamp", datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")),
            creativity_level=pipeline_settings.get("creativity_level_selected", 2),
            num_variants=pipeline_settings.get("num_variants", 3),
            pipeline_mode=pipeline_settings.get("pipeline_mode", "generation"),
            mode=request_details.get("mode", "easy_mode"),
            task_type=request_details.get("task_type"),
            target_platform=request_details.get("target_platform"),
            prompt=user_inputs.get("prompt"),
            image_reference=user_inputs.get("image_reference"),
            render_text=user_inputs.get("render_text", False),
            apply_branding=user_inputs.get("apply_branding", False),
            branding_elements=user_inputs.get("branding_elements"),
            task_description=user_inputs.get("task_description"),
            marketing_goals=user_inputs.get("marketing_goals"),
            image_analysis_result=processing_context.get("image_analysis_result"),
            suggested_marketing_strategies=processing_context.get("suggested_marketing_strategies"),
            style_guidance_sets=processing_context.get("style_guidance_sets"),
            generated_image_prompts=processing_context.get("generated_image_prompts", []),
            final_assembled_prompts=processing_context.get("final_assembled_prompts", []),
            generated_image_results=processing_context.get("generated_image_results", []),
            image_assessments=processing_context.get("image_assessment"),
            llm_usage=processing_context.get("llm_call_usage", {}),
            cost_summary=processing_context.get("cost_summary")
        )
        
        # Set refinement context if present
        if refinement_context:
            ctx.parent_run_id = refinement_context.get("parent_run_id")
            ctx.parent_image_id = refinement_context.get("parent_image_id")
            ctx.parent_image_type = refinement_context.get("parent_image_type", "original")
            ctx.generation_index = refinement_context.get("generation_index")
            ctx.base_image_path = refinement_context.get("base_image_path")
            ctx.refinement_type = refinement_context.get("refinement_type")
            ctx.mask_coordinates = refinement_context.get("mask_coordinates")
            ctx.reference_image_path = refinement_context.get("reference_image_path")
            ctx.instructions = refinement_context.get("instructions")
            ctx.refinement_result = refinement_context.get("refinement_result")
            ctx.refinement_cost = refinement_context.get("refinement_cost")
        
        return ctx

    def __post_init__(self):
        """Initialize cost summary after creation."""
        if self.cost_summary is None:
            try:
                # Dynamically import to avoid circular imports
                from ..models import PipelineCostSummary
                self.cost_summary = PipelineCostSummary().model_dump()
            except Exception:
                self.cost_summary = {} 