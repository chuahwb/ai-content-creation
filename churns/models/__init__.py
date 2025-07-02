"""
Pydantic models for the AI Marketing Pipeline.
All models copied verbatim from the original combined_pipeline.py
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

# --- Models from Upstream (user_input_and_image_eval) ---
class ImageAnalysisResult(BaseModel):
    """Structured result of the objective visual analysis of the image."""
    main_subject: str = Field(..., description="The single, primary subject of the image (e.g., 'Gourmet Burger', 'Latte Art', 'Restaurant Interior'). Should be concise and based SOLELY on visual content.")
    secondary_elements: Optional[List[str]] = Field(None, description="List other notable objects or elements visually present in the image that SURROUND the main subject. Do not include elements that are ON the main subject (e.g., for a burger, list the fries and drink next to it, not the sesame seeds on the bun). Omit if not applicable or if analysis is focused only on main_subject.")
    angle_orientation: Optional[str] = Field(None, description="Describe the camera angle or orientation from which the main subject is viewed (e.g., 'eye-level shot', 'top-down view', '45-degree angle shot', 'side view').")
    setting_environment: Optional[str] = Field(None, description="Describe the background or setting of the image as visually observed. Omit if not applicable or if analysis is focused only on main_subject.")
    style_mood: Optional[str] = Field(None, description="Describe the inferred visual style, mood, or atmosphere of the image based SOLELY on its visual content. Omit if not applicable or if analysis is focused only on main_subject.")
    extracted_text: Optional[str] = Field(None, description="Extract any visible text from the image. Omit if no text is visible or if analysis is focused only on main_subject.")

class RelevantNicheList(BaseModel):
    """Identifies a list of relevant F&B niches for the given context."""
    relevant_niches: List[str] = Field(..., description="A list of 3-5 diverse but highly relevant F&B niches based on the input context (e.g., ['Ethnic Cuisine (Thai)', 'Casual Dining', 'Takeaway/Delivery Focused']). Prioritize niches directly related to the image subject or task description.")

class MarketingGoalSetStage2(BaseModel):
    """Represents a set of marketing goals (audience, objective, voice) aligned with a specific niche."""
    target_audience: str = Field(..., description="Specific target audience group, generated based on context and relevant to the predetermined niche.")
    target_objective: str = Field(..., description="The primary marketing objective for this asset, generated based on context and relevant to the predetermined niche/task.")
    target_voice: str = Field(..., description="The desired brand voice or tone, generated based on context and relevant to the predetermined niche/audience.")

class MarketingStrategyOutputStage2(BaseModel):
     """Container for N suggested marketing goal combinations (audience, objective, voice)."""
     strategies: List[MarketingGoalSetStage2] = Field(..., description="A list of N diverse and strategically sound marketing goal combinations (audience, objective, voice) aligned with a predetermined niche.")

# This is the final structure for a strategy used throughout the pipeline
class MarketingGoalSetFinal(BaseModel):
    """Represents a complete set of marketing goals for a creative direction."""
    target_audience: str
    target_niche: str
    target_objective: str
    target_voice: str

# --- Models from Downstream (creative_prompt_to_image_gen) ---
class VisualConceptDetails(BaseModel):
    """Detailed breakdown of the visual concept."""
    main_subject: Optional[str] = Field(None, description="Detailed description of the primary subject(s) and their interaction within the scene. This field should be omitted (set to null) if a reference image is provided and the default behavior (use reference subject) is intended.")
    composition_and_framing: str = Field(..., description="Description of the composition, camera angle, shot type (e.g., close-up, wide shot), and framing.")
    background_environment: str = Field(..., description="Description of the background, setting, or environment.")
    foreground_elements: Optional[str] = Field(None, description="Description of any significant foreground elements.")
    lighting_and_mood: str = Field(..., description="Description of the lighting style (e.g., natural, studio, dramatic) and the overall mood or atmosphere.")
    color_palette: str = Field(..., description="Description of the key colors, color harmony (e.g., analogous, complementary), and overall color tone.")
    visual_style: str = Field(..., description="Description of the artistic or visual style (e.g., photorealistic, illustration, graphic design, vintage). This should include key style descriptors and be highly creative if user input is minimal.")
    promotional_text_visuals: Optional[str] = Field(None, description="Description of how promotional text (from task_description) should be visualized, including content, style, font characteristics, and placement suggestions. Omit (set to null) if user input 'render_text' is false.")
    branding_visuals: Optional[str] = Field(None, description="Description of how branding elements (logo placeholders, taglines, specific brand fonts/colors mentioned in branding_elements input) should be visually incorporated. Omit (set to null) if user input 'apply_branding' is false.")
    texture_and_details: Optional[str] = Field(None, description="Specific notes on textures, materials, or fine details.")
    negative_elements: Optional[str] = Field(None, description="Specific elements or concepts to actively avoid in the image.")
    creative_reasoning: Optional[str] = Field(None, description="Brief explanation connecting the key visual choices (style, mood, composition, subject focus) back to the marketing strategy (audience, niche, objective, voice) and user inputs.")
    suggested_alt_text: str = Field(..., description="Concise, descriptive alt text (100-125 characters) for SEO and accessibility. Should clearly describe the image's subject, setting, and any important actions or text, naturally incorporating primary keywords from the marketing strategy.")

class StyleGuidance(BaseModel):
    """Defines a specific style direction for a visual concept."""
    style_keywords: List[str] = Field(..., description="A list of 3-5 concise keywords defining the core visual style (e.g., 'photorealistic', 'impressionist', 'surreal').")
    style_description: str = Field(..., description="A detailed (2-3 sentence) description elaborating on the feeling, key characteristics, and specific artistic references or constraints of the style suggested by the keywords.")
    marketing_impact: str = Field(..., description="A brief explanation of how this style supports social media marketing goals (e.g., shareability, engagement, brand recall) for the target audience and platform.")
    source_strategy_index: int = Field(..., description="The index of the marketing strategy this style guidance corresponds to.")

class StyleGuidanceList(BaseModel):
    """A list of style guidance sets, one for each marketing strategy."""
    style_guidance_sets: List[StyleGuidance]

class ImageGenerationPrompt(BaseModel):
    """
    Structured prompt details generated by the Creative Expert agent,
    containing a breakdown of the visual concept. This structure will be
    processed later to create the final prompt for the text-to-image model.
    """
    visual_concept: VisualConceptDetails = Field(..., description="The detailed, structured breakdown of the visual concept.")
    # aspect_ratio is handled during prompt assembly and image generation call, not stored here directly
    source_strategy_index: Optional[int] = Field(None, description="Index linking back to the source marketing strategy in the input JSON.")

class CostDetail(BaseModel):
    """Details of cost for a specific pipeline stage or model call."""
    stage_name: str
    model_id: str
    provider: Optional[str] = None
    duration_seconds: Optional[float] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    input_cost_usd: Optional[float] = None
    output_cost_usd: Optional[float] = None
    # For images
    images_generated: Optional[int] = None
    resolution: Optional[str] = None
    quality: Optional[str] = None
    image_cost_usd: Optional[float] = None
    total_stage_cost_usd: float = 0.0
    cost_calculation_notes: Optional[str] = None

class PipelineCostSummary(BaseModel):
    """Overall cost summary for the pipeline run."""
    stage_costs: List[CostDetail] = []
    total_pipeline_cost_usd: float = 0.0
    total_pipeline_duration_seconds: float = 0.0
    currency: str = "USD"
    pricing_info_url: str = "Note: Prices are estimates based on known rates at the time of implementation (June 2025) and may vary. Check provider (OpenRouter/OpenAI) for current rates."
    cost_calculation_error: Optional[str] = None

class ImageAssessmentResult(BaseModel):
    """Structured result of image quality assessment."""
    assessment_scores: Dict[str, int] = Field(..., description="Scores for different assessment criteria (1-5 scale)")
    assessment_justification: Dict[str, str] = Field(..., description="Detailed justification for each score")

# --- Models for Caption Feature ---
class CaptionBrief(BaseModel):
    """Strategic brief generated by the Analyst LLM for caption creation."""
    core_message: str = Field(..., description="A concise, one-sentence summary of the main message.")
    key_themes_to_include: List[str] = Field(..., description="An array of 3-5 key themes or concepts to weave into the caption.")
    seo_keywords: List[str] = Field(..., description="An array of 3-5 important SEO keywords to integrate naturally.")
    target_emotion: str = Field(..., description="The primary emotion the caption should evoke in the reader (e.g., 'Aspirational', 'Trustworthy', 'Excited').")
    platform_optimizations: Dict[str, Dict[str, Any]] = Field(..., description="Platform-specific optimization instructions.")
    primary_call_to_action: str = Field(..., description="The final call to action string.")
    hashtags: List[str] = Field(..., description="An array of generated hashtag strings, including the # symbol.")
    emoji_suggestions: List[str] = Field(..., description="An array of 2-3 relevant emoji characters to consider.")
    task_type_notes: Optional[str] = Field(None, description="Optional task-type specific guidance notes for the writer.")

class CaptionSettings(BaseModel):
    """User settings for caption generation."""
    tone: Optional[str] = Field(None, description="Caption tone (e.g., 'Professional & Polished', 'Friendly & Casual', 'Witty & Playful', 'Inspirational & Aspirational', 'Direct & Sales-focused')")
    call_to_action: Optional[str] = Field(None, description="User-defined call to action text")
    include_emojis: Optional[bool] = Field(True, description="Whether to include emojis in the caption")
    hashtag_strategy: Optional[str] = Field(None, description="Hashtag strategy ('None', 'Niche & Specific', 'Broad & Trending', 'Balanced Mix')")

class CaptionResult(BaseModel):
    """Final caption result with metadata."""
    text: str = Field(..., description="The final caption text")
    version: int = Field(..., description="Version number of this caption")
    settings_used: CaptionSettings = Field(..., description="Settings that were used to generate this caption")
    brief_used: CaptionBrief = Field(..., description="The strategic brief that was used")
    created_at: str = Field(..., description="ISO timestamp when caption was created")
