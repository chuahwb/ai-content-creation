"""Creative Expert Stage

This stage generates structured visual concepts for each marketing strategy
using the provided style guidance. It creates detailed ImageGenerationPrompt
objects that contain rich visual concept details for later prompt assembly.

Extracted from combined_pipeline.py with 100% fidelity.
"""

import json
import time
import traceback
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from pydantic import ValidationError

from churns.models import (
    ImageGenerationPrompt, 
    VisualConceptDetails, 
    StyleGuidance
)
from churns.pipeline.context import PipelineContext
from churns.core.json_parser import (
    RobustJSONParser, 
    JSONExtractionError,
    TruncatedResponseError,
    should_use_manual_parsing
)
from churns.core.brand_kit_utils import build_brand_palette_prompt

# Global variables for API clients and configuration (injected by pipeline executor)
instructor_client_creative_expert = None
base_llm_client_creative_expert = None
CREATIVE_EXPERT_MODEL_ID = None
CREATIVE_EXPERT_MODEL_PROVIDER = None
FORCE_MANUAL_JSON_PARSE = False
INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS = []


# Initialize centralized JSON parser for this stage
_json_parser = RobustJSONParser(debug_mode=False)


# Old manual JSON extraction function removed - now using centralized parser


def _map_to_supported_aspect_ratio_for_prompt(aspect_ratio: str) -> str:
    """Maps input aspect ratio to a supported aspect ratio string for use in prompts."""
    if aspect_ratio == "1:1": 
        return "1:1"
    elif aspect_ratio in ["9:16", "3:4", "2:3"]: 
        return "2:3"  # Vertical
    elif aspect_ratio == "16:9" or aspect_ratio == "1.91:1": 
        return "3:2"  # Horizontal
    else:
        return "1:1"


def _clean_platform_name(platform_name: str) -> str:
    """
    Removes aspect ratio information from platform names to avoid confusion.
    
    Examples:
    - "Instagram Story/Reel (9:16 Vertical)" -> "Instagram Story/Reel"
    - "Instagram Post (1:1 Square)" -> "Instagram Post"
    - "Pinterest Pin (2:3 Vertical)" -> "Pinterest Pin"
    """
    import re
    
    # Remove patterns like "(9:16 Vertical)", "(1:1 Square)", "(3:4 Vertical)", etc.
    pattern = r'\s*\([^)]*(?:\d+:\d+|Mixed)[^)]*\)\s*'
    cleaned_name = re.sub(pattern, '', platform_name).strip()
    
    return cleaned_name if cleaned_name else platform_name


def _get_creative_expert_system_prompt(
    creativity_level: int,
    task_type: str,
    use_instructor_parsing: bool,
    has_reference: bool,
    has_instruction: bool,
    render_text_flag: bool,
    apply_branding_flag: bool,
    platform_name: str,
    target_model_family: str = "openai",
    language: str = 'en'
) -> str:
    """Returns the system prompt for the Creative Expert agent."""
    
    # Clean platform name to remove aspect ratio information
    clean_platform_name = _clean_platform_name(platform_name)
    
    base_persona_ce = """
You are an expert Creative Director and Digital Marketing Strategist specializing in F&B social media visuals.
Your primary objective is to generate a highly detailed, exceptionally creative, and effective *structured visual concept* based on the provided marketing strategy, style guidance, and context.
This structured concept will later be used to generate a prompt for a text-to-image generation model.
Your goal is to provide concepts that are significantly value-added, pushing beyond generic interpretations and getting the user much closer to their ideal image on the first attempt.
"""
    
    # Language control instruction
    language_display = "SIMPLIFIED CHINESE" if language == 'zh' else language.upper()
    lang_note = (
        f"\n**Language Control (VERY IMPORTANT):**\n"
        f"- The `suggested_alt_text` field's entire content MUST be written in {language_display}.\n"
        f"- For `promotional_text_visuals` and `logo_visuals` fields: The description of *how* the text/logo should look (e.g., 'A bold, sans-serif font placed at the top', 'A subtle watermark in the corner') MUST remain in ENGLISH. Only the actual text content to be displayed in the image (e.g., the headline '夏日特惠' or brand name '元気森林') should be written in {language_display}.\n"
        f"- All other fields MUST be in ENGLISH to optimize LLM comprehension.\n"
    )
    
    input_refinement_ce = """
**Input Refinement:** Critically review ALL user inputs (Original User Prompt Hint, Specific Task Content/Description, Branding Guidelines, Image Instruction, and the provided Style Guidance). If any input is brief, vague, contains grammatical errors, or seems misaligned, you MUST interpret the user's likely intent, refine it, expand upon it creatively, and clearly explain your refined interpretation within the relevant structured output fields. Ensure the final concept is coherent and aligns with the marketing strategy and task type.
"""
    
    core_task_ce = """
**Core Task:** Embody maximum creativity and imagination, coupled with a deep understanding of visual design principles (color, composition, lighting, typography), F&B marketing trends, and image generation capabilities. Generate diverse, high-impact visual concepts tailored to the specific task type and marketing goals.
You will be provided with specific `Style Guidance` for this concept. Your `visual_style` field MUST be a detailed and rich elaboration of this provided style, adhering to its artistic boundaries and constraints. Use it as your primary stylistic foundation and creatively build upon it, ensuring all other visual elements harmonize with and bring this specific style to life. The goal is a harmonious blend where the artistic style is paramount but is applied to meet the functional needs of the task type.
"""
    
    # Task Type Guidance Map (distilled for clarity)
    task_type_guidance_map = {
        "1. Product Photography": {
            "keywords": ["Exceptional Clarity", "Product Details", "Textures", "Menu Spotlight", "Sales-Focused"],
            "platform_focus": "Vibrant product focus",
            "text_style": "Clear, bold sans-serif font",
            "branding_style": "Subtle integration"
        },
        "2. Promotional Graphics & Announcements": {
            "keywords": ["Immediate Visual Impact", "Attention-Grabbing", "High Engagement", "Shareable"],
            "platform_focus": "Bold, centered compositions for shareability",
            "text_style": "Large, bold headlines with clear hierarchy",
            "branding_style": "Integrated without clutter"
        },
        "3. Store Atmosphere & Decor": {
            "keywords": ["Immersive", "Environmental Storytelling", "Unique Mood", "Ambiance"],
            "platform_focus": "Dynamic ambiance suitable for the platform",
            "text_style": "Elegant serif font, subtle overlay",
            "branding_style": "Subtle integration within the scene"
        },
        "4. Menu Spotlights": {
            "keywords": ["Appetizing Appeal", "Close-up or Medium Shots", "Specific Menu Item"],
            "platform_focus": "Contextual lifestyle shots",
            "text_style": "Bold promotional text positioned to enhance the dish",
            "branding_style": "Integrated on tableware or as subtle elements"
        },
        "5. Cultural & Community Content": {
            "keywords": ["Symbolic Elements", "Culturally Inspired Palettes", "Lifestyle-Oriented"],
            "platform_focus": "Lifestyle visuals with cultural significance",
            "text_style": "Elegant script taglines that harmonize",
            "branding_style": "Integrated respectfully within cultural context"
        },
        "6. Recipes & Food Tips": {
            "keywords": ["Clarity", "Visual Instruction", "Appetite Appeal", "Educational"],
            "platform_focus": "Detailed compositions for instructional content",
            "text_style": "Concise, bold text for titles and instructions",
            "branding_style": "Integrated to tie to brand without distraction"
        },
        "7. Brand Story & Milestones": {
            "keywords": ["Evocative", "Narrative", "Celebratory", "Emotional Resonance"],
            "platform_focus": "Cinematic visuals with narrative flow",
            "text_style": "Elegant serif font as a focal point",
            "branding_style": "Integrated to reinforce identity in storytelling"
        },
        "8. Behind the Scenes Imagery": {
            "keywords": ["Authenticity", "Process", "Human Element", "Candid Visuals"],
            "platform_focus": "Authentic compositions",
            "text_style": "Playful or clean font, placed authentically",
            "branding_style": "Integrated naturally within the scene"
        }
    }
    
    # Get task guidance or use default
    task_key = task_type.split('.', 1)[-1].strip() if '.' in task_type else task_type
    task_guidance = task_type_guidance_map.get(task_type, {
        "keywords": [f"Adapt appropriately for '{task_type}'"],
        "platform_focus": f"Optimize for {clean_platform_name}",
        "text_style": "Handle text rendering as appropriate",
        "branding_style": "Handle branding as appropriate"
    })
    
    task_type_awareness_ce = f"""
**Task Type Adaptation (CRUCIAL):** The specified Task Type is '{task_type}'. Your visual concept must be expertly tailored to this task.
- Core Concepts: {', '.join(task_guidance['keywords'])}.
- Platform Optimization: {task_guidance['platform_focus']}.
"""
    
    # Add text and branding guidance based on flags
    text_branding_field_instruction_ce = "**Text & Branding Fields:**\n"
    if render_text_flag:
        text_branding_field_instruction_ce += (
            f"- `promotional_text_visuals`: {task_guidance['text_style']}. The user will provide a 'Specific Task Content/Description' for text overlay. You MUST interpret this input as follows:\n"
            "  - Text enclosed in **double quotes** (e.g., `\"Summer Special\"`) is **LITERAL CONTENT** that must appear on the image. Your description must specify this exact text.\n"
            "  - Text **outside** of double quotes is a **CONTENT AND CREATIVE BRIEF**. Use it to understand the user's intent for the text's style, tone, placement, and **most importantly, to generate the specific text to be rendered if the user has not provided it in quotes.**\n"
            "  - Your final output in the `promotional_text_visuals` field must be a cohesive description that synthesizes this brief and any literal text into a complete visual plan.\n"
        )
    else:
        text_branding_field_instruction_ce += "- `promotional_text_visuals`: This field MUST be omitted (set to null) as text rendering is disabled.\n"
    
    if apply_branding_flag:
        text_branding_field_instruction_ce += f"- `logo_visuals`: {task_guidance['branding_style']}. If no guidelines are provided, derive the branding style from the marketing strategy and task. The description MUST detail placement, scale, and integration of the brand logo based on the provided Brand Kit context.\n"
    else:
        text_branding_field_instruction_ce += "- `logo_visuals`: This field MUST be omitted (set to null) as branding application is disabled.\n"
    
    # Creativity level instructions
    creativity_instruction_ce = ""
    if creativity_level == 1:
        creativity_instruction_ce = """
**Creativity Guidance (Level 1 - Focused & Photorealistic):**
Prioritize clear, professional, photorealistic, or minimally stylized visuals that strictly adhere to inputs and marketing strategy.
Use standard compositions and proven styles.
**Constraint**: Use symmetrical composition or even, natural lighting to maximize clarity and product focus.
Avoid unconventional or artistic concepts to ensure reliability and broad appeal.
**Marketing Guardrail**: Ensure the visual prioritizes product or subject clarity to drive direct engagement or sales.
"""
    elif creativity_level == 3:
        creativity_instruction_ce = """
**Creativity Guidance (Level 3 - Abstract & Illustrative):**
Create exceptionally imaginative, memorable, and high-impact visual concepts using abstract or illustrative styles.
**Constraint**: Select one creative approach:
- Use a strictly monochromatic or duotone color scheme based on the strategy's mood
- Frame the composition as a specific art form (e.g., graphic novel panel, baroque oil painting)
- Depict the product as an abstract entity or symbolic character
- Integrate a strong visual metaphor tied to the brand's voice
- Place the subject in a surreal or fantastical setting
Explain the constraint's impact in `creative_reasoning`.
Aim for novel, shareable concepts while maintaining the task's marketing goal.
**Marketing Guardrail**: Even abstract styles must support the overall marketing objectives.
"""
    else:  # Level 2 (Default)
        creativity_instruction_ce = """
**Creativity Guidance (Level 2 - Impressionistic & Stylized):**
Generate visually appealing, marketable concepts with impressionistic or stylized flair.
Use cinematic lighting, dynamic angles, or textured stylization, avoiding generic photorealism.
**Constraint**: Incorporate impressionistic color blending, dynamic angles, or textured stylization to enhance visual interest.
**Guardrail**: Explicitly avoid fully illustrative, cartoonish, or abstract renderings unless specified by the Style Guidance.
Ensure concepts are memorable while aligning with the marketing strategy and task type.
**Marketing Guardrail**: Styles must balance creativity with clarity to support engagement and brand recognition.
"""
    
    # Image reference handling
    image_ref_handling_ce = "**Handling Image Reference (CRITICAL):**\n"
    if has_reference:
        if has_instruction:
            image_ref_handling_ce += "- An image reference IS provided WITH a specific user `instruction`: Interpret the instruction and apply it when describing the new concept. Populate all fields including `main_subject`.\n"
        else:
            image_ref_handling_ce += "- An image reference IS provided BUT has NO specific user `instruction`: The primary subject of the visual concept MUST be the one from the reference image. Your main creative task is to design the *context* around this subject. **Crucially, you MUST OMIT the `main_subject` field entirely (set to null) in your JSON output.** Focus ONLY on describing the context fields (background, lighting, etc.).\n"
    else:
        image_ref_handling_ce += "- NO image reference is provided: Generate the entire visual concept from scratch based on the marketing strategy and other inputs, including the `main_subject`.\n"
    
    reasoning_ce = "**Creative Reasoning:** In the `creative_reasoning` field, briefly explain how your key visual choices (style, composition, color) connect back to the marketing strategy, task type, and style guidance. Justify why this creative direction is effective for the marketing objectives."
    
    alt_text_ce = """
**Alt Text Generation:** Based on the final visual concept, you MUST generate a concise, descriptive alt text (100-125 characters) in the `suggested_alt_text` field for SEO and accessibility.
**IMPORTANT:** This text must describe the image's subject, setting, and key elements. Do NOT include hashtags, emojis, or promotional language.
"""
    
    # Output format instructions
    adherence_ce = ""
    if use_instructor_parsing and CREATIVE_EXPERT_MODEL_ID not in INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS:
        adherence_ce = "Adhere strictly to the requested Pydantic JSON output format (`ImageGenerationPrompt` containing `VisualConceptDetails`). Note that `main_subject`, `promotional_text_visuals`, and `logo_visuals` are optional and should be omitted (set to null) if the specific scenario instructs it. The `suggested_alt_text` field is mandatory. Ensure all other required descriptions are detailed enough to guide image generation effectively."
    else:
        adherence_ce = """
VERY IMPORTANT: Format your entire response *only* as a valid JSON object conforming to the structure described below. Do not include any introductory text, explanations, or markdown formatting outside the JSON structure itself.
JSON Structure:
{
  "visual_concept": {
    "main_subject": "string | null", // Omit (set to null) if default edit scenario
    "composition_and_framing": "string",
    "background_environment": "string",
    "foreground_elements": "string | null",
    "lighting_and_mood": "string",
    "color_palette": "string",
    "visual_style": "string", // Must elaborate on provided Style Guidance
    "promotional_text_visuals": "string | null", // Omit (set to null) if render_text_flag is false
    "logo_visuals": "string | null", // Omit (set to null) if apply_branding_flag is false
    "texture_and_details": "string | null",
    "negative_elements": "string | null",
    "creative_reasoning": "string | null",
    "suggested_alt_text": "string" // MANDATORY: 100-125 character SEO-friendly alt text
  },
  "source_strategy_index": "integer | null" // This will be added programmatically later
}
Ensure all descriptions are detailed enough to guide image generation effectively.
"""
    
    prompt_parts_ce = [
        base_persona_ce, lang_note, input_refinement_ce, core_task_ce, task_type_awareness_ce,
        creativity_instruction_ce, image_ref_handling_ce, text_branding_field_instruction_ce,
        reasoning_ce, alt_text_ce, adherence_ce
    ]
    
    if target_model_family == "qwen":
        prompt_parts_ce.append("   /no_thinking   ")
    
    return "\n".join(prompt_parts_ce)


def _get_creative_expert_user_prompt(
    platform_name: str,
    aspect_ratio_for_prompt: str,
    strategy: Dict[str, Any],
    task_type: str,
    user_prompt_original: Optional[str],
    task_description: Optional[str],
    brand_kit: Optional[Dict[str, Any]],
    render_text_flag: bool,
    apply_branding_flag: bool,
    has_image_reference: bool,
    saved_image_filename: Optional[str],
    image_subject_from_analysis: Optional[str],
    image_instruction: Optional[str],
    use_instructor_parsing: bool,
    is_default_edit: bool,
    style_guidance_item: Optional[StyleGuidance],
    language: str = 'en'
) -> str:
    """Constructs the user prompt for the Creative Expert agent."""
    
    # Clean platform name to remove aspect ratio information
    clean_platform_name = _clean_platform_name(platform_name)
    
    user_prompt_parts = [
        f"Generate a structured visual concept for an image targeting the '{clean_platform_name}' platform (intended visual aspect ratio for prompt: {aspect_ratio_for_prompt}).",
        f"The core marketing strategy for this image is:",
        f"- Target Audience: {strategy.get('target_audience', 'N/A')}",
        f"- Target Niche: {strategy.get('target_niche', 'N/A')}",
        f"- Target Objective: {strategy.get('target_objective', 'N/A')}",
        f"- Target Voice: {strategy.get('target_voice', 'N/A')}",
        f"\nConsider the overall task context:",
        f"- Task Type: {task_type} (Ensure the concept strongly reflects the requirements of this task type as detailed in the system prompt).",
    ]

    if style_guidance_item:
        user_prompt_parts.append("\n**Style Direction to Follow (Provided by Style Guider):**")
        user_prompt_parts.append(f"- Style Keywords: {', '.join(style_guidance_item.style_keywords if style_guidance_item.style_keywords else [])}")
        user_prompt_parts.append(f"- Style Description: {style_guidance_item.style_description if style_guidance_item.style_description else 'N/A'}")
        # user_prompt_parts.append(f"- Marketing Impact of this Style: {style_guidance_item.marketing_impact if style_guidance_item.marketing_impact else 'N/A'}")
        user_prompt_parts.append("   Your `visual_style` field description in the JSON output MUST be a detailed and creative elaboration of these provided style elements, adhering to its artistic boundaries and constraints.")
    else:
        user_prompt_parts.append("\n**Style Direction to Follow:** No specific style guidance provided by Style Guider; invent a style based on the creativity level (from system prompt) and other inputs.")

    if user_prompt_original:
        user_prompt_parts.append(f"- Original User Prompt Hint: '{user_prompt_original}' (Interpret and refine this hint if it's brief or unclear, integrating its essence into the concept).")
    
    text_render_status = "(Text rendering enabled by user)" if render_text_flag else "(Text rendering DISABLED by user)"
    if task_description:
        user_prompt_parts.append(f"- Specific Task Content/Description: '{task_description}' {text_render_status} (Interpret/refine content. If rendering enabled, describe visualization in `promotional_text_visuals` field of JSON output, following task-specific text guidance from system prompt).")
    elif render_text_flag:
        user_prompt_parts.append(f"- Specific Task Content/Description: Not provided, but text rendering is enabled. If relevant to task type, describe visualization in `promotional_text_visuals` field of JSON output, following task-specific text guidance from system prompt.")
    else:
        user_prompt_parts.append("- Specific Task Content/Description: Not provided, and text rendering is disabled.")

    if apply_branding_flag and brand_kit:
        user_prompt_parts.append("\n**Brand Kit Integration (CRITICAL):**")
        user_prompt_parts.append("The following brand kit MUST be integrated into your visual concept. You must describe logo placement in the `logo_visuals` field.")
        if brand_kit.get('colors'):
            colors = brand_kit.get('colors')
            if colors:
                if isinstance(colors[0], str):
                    user_prompt_parts.append("- **Brand Colors:**")
                    user_prompt_parts.append(f"  `{colors}`")
                else:
                    # Use centralized builder with conditional usage inclusion for CREATIVE layer
                    snippet = build_brand_palette_prompt(colors, layer="creative")
                    user_prompt_parts.append(snippet)
        
        user_prompt_parts.append(f"- In the `color_palette` field of your response, define a specific color scheme that prominently features or complements this full set of brand colors. Respect semantic roles; if a usage plan is given above, reflect it approximately, while using neutrals functionally for elements like text and backgrounds. The color scheme you define MUST be built from the provided Brand Colors. Non-brand colors should only be used sparingly as supporting functional shades (e.g., pure white for a background) if absolutely necessary. Adherence to the brand palette is a primary requirement.")

        if brand_kit.get('brand_voice_description'):
            user_prompt_parts.append(f"- **Brand Voice:** `'{brand_kit.get('brand_voice_description')}'`. The `lighting_and_mood` and overall `visual_style` must align with this voice.")
        if brand_kit.get('logo_analysis') and brand_kit['logo_analysis'].get('logo_style'):
            user_prompt_parts.append(f"- **Logo Details:** The user has provided a logo. Your task is to describe its placement and integration. The logo's style is: `'{brand_kit['logo_analysis']['logo_style']}'`.")
        
        # Add a more specific instruction for logo placement
        user_prompt_parts.append("\n**Your `logo_visuals` description should be specific and prioritize a watermark-style placement, such as:**")
        user_prompt_parts.append("- 'Subtly place the logo in the bottom-right corner, scaled to 5% of the image width. It should be rendered as a semi-transparent watermark to avoid distracting from the main subject.'")
        user_prompt_parts.append("- 'Position the brand logo as a discreet watermark in the top-left corner, using a color that complements the background.'")
        user_prompt_parts.append("**Avoid instructions that replace or alter the main subject with the logo unless explicitly requested by the user.**")
        
    elif apply_branding_flag:
        user_prompt_parts.append(f"\n- Branding Guidelines: Not provided, but branding application is enabled. Derive branding style from strategy/task and describe visualization in the `logo_visuals` field of the JSON output, following task-specific branding guidance from the system prompt.")
    else:
        user_prompt_parts.append("\n- Branding application DISABLED by user.")

    user_prompt_parts.append("\nImage Reference Context (as detailed in system prompt):")
    if has_image_reference:
        user_prompt_parts.append(f"- An image reference was provided (Filename: {saved_image_filename or 'N/A'}).")
        if image_subject_from_analysis:
            user_prompt_parts.append(f"- Analysis identified the main subject of reference as: '{image_subject_from_analysis}'.")
        if image_instruction:
            user_prompt_parts.append(f"- User Instruction for reference image: '{image_instruction}' (Interpret and refine this instruction. Apply it carefully when describing the visual concept fields for the *new* image, as per system prompt guidance for instructed edits).")
        else:
            user_prompt_parts.append(f"- No specific instruction provided for the reference image. **Default edit behavior applies: The primary subject MUST be the analyzed subject ('{image_subject_from_analysis or 'Unknown'}'). Your task is to design the surrounding context ONLY. DO NOT describe the main subject in the `main_subject` field of the output JSON (leave it null/omit it).**")
    else:
        user_prompt_parts.append("- No image reference was provided. Generate the full concept including the `main_subject`.")

    # Platform optimization guidance - updated to use cleaned platform names and consistent aspect ratios
    platform_guidance_map = {
        "Instagram Post": f"Optimize for Instagram Feed: Aim for a polished, visually cohesive aesthetic suitable for {aspect_ratio_for_prompt} format. Consider compositions suitable for feed posts. Ensure text placement is easily readable.",
        "Instagram Story/Reel": f"Optimize for Instagram Story/Reel: Focus on dynamic, attention-grabbing visuals for {aspect_ratio_for_prompt} vertical format. **Describe the visual as if it were a single, high-impact frame from a video Reel.** Incorporate a sense of motion or action in the `composition_and_framing` description (e.g., 'dynamic motion blur,' 'subject captured mid-action,' 'cinematic freeze-frame effect').",
        "Facebook Post": f"Optimize for Facebook Feed: Design for broad appeal and shareability in {aspect_ratio_for_prompt} format. Ensure clear branding and messaging for potential ad use.",
        "Pinterest Pin": f"Optimize for Pinterest: Create visually striking, informative vertical images in {aspect_ratio_for_prompt} format. **If text is enabled, the concept MUST include a prominent text overlay.** As per Pinterest best practices, the description in `promotional_text_visuals` should specify text that is **large, highly legible (e.g., bold sans-serif fonts), and contains primary keywords from the marketing strategy.**",
        "Xiaohongshu (Red Note)": f"""Optimize for Xiaohongshu: Create a concept embodying **'elevated reality'**—a blend of high-quality aesthetics and genuine authenticity for the {aspect_ratio_for_prompt} format. The visual style should feel like a polished but relatable post from a top creator, not a corporate ad.
- **Visual Style & Composition:** Favor natural lighting, clean backgrounds, and dynamic angles. Describe a clear, engaging visual story (e.g., 'a mini-tutorial in one frame,' 'the satisfying end result of a recipe'). The `visual_style` could be 'effortless chic', 'clean and minimalist', or 'vibrant and bold'.
- **Human Element:** The concept **must feature relatable people** interacting naturally with the product or scene.
- **Text Overlay (if enabled):** The `promotional_text_visuals` description is CRITICAL. It must detail a **catchy, keyword-rich title overlay**. Specify that the text should use **high-contrast, bold, and easily readable fonts** to create a strong visual hook for the feed.""",
    }
    platform_guidance_text = platform_guidance_map.get(clean_platform_name, f"Adapt the concept for the target platform '{clean_platform_name}' using {aspect_ratio_for_prompt} aspect ratio.")
    user_prompt_parts.append(f"\n**Platform Optimization (General Reminder):** {platform_guidance_text} (Detailed task-specific platform optimization is in system prompt).")

    # Language reminder  
    language_display = "Simplified Chinese" if language == 'zh' else language.upper()
    lang_reminder = (
        f"\n**Language Reminder (CRITICAL):**\n"
        f"For the text-based fields, follow these rules precisely:\n"
        f"- `suggested_alt_text`: Write the entire description in **{language_display}**.\n"
        f"- `promotional_text_visuals` & `logo_visuals`: Describe the visual style (font, color, placement) in **ENGLISH**. Write the actual text content (e.g., a headline or brand name) in **{language_display}**.\n"
        f"- All other fields must be in English.\n"
    )
    user_prompt_parts.append(lang_reminder)

    final_instruction = f"""
As the expert Creative Director, your final task is to synthesize ALL of the above context—especially the core marketing strategy, the provided Style Direction, and the task-specific guidance—and generate the complete `ImageGenerationPrompt` JSON object.
Ensure the nested `VisualConceptDetails` object is fully populated with rich, descriptive details to guide the image model effectively.

- `main_subject`: Describe the main subject clearly (unless this is a default edit on a reference image).
- `composition_and_framing`: Detail the composition and camera framing.
- `background_environment`: Describe the background environment.
- `foreground_elements`: Mention any important foreground elements.
- `lighting_and_mood`: Specify the lighting and overall mood.
- `color_palette`: Define the key colors.
- `visual_style`: Articulate the final visual style, ensuring it's a creative elaboration of the provided Style Guidance.
"""
    
    if render_text_flag:
        final_instruction += "- `promotional_text_visuals`: Describe the text content, style, and placement in detail.\n"
    else:
        final_instruction += "- `promotional_text_visuals`: This field MUST be omitted (set to null) as text rendering is disabled.\n"
    
    if apply_branding_flag:
        final_instruction += "- `logo_visuals`: Describe the branding logo elements and their integration.\n"
    else:
        final_instruction += "- `logo_visuals`: This field MUST be omitted (set to null) as branding application is disabled.\n"
    
    final_instruction += """
- `texture_and_details`: Add notes on texture and fine details if relevant.
- `negative_elements`: List any elements to strictly avoid.

**CRITICAL FINAL CHECKS:**
- **Provide `creative_reasoning`:** Briefly explain how the visual choices support the marketing goals.
- **Generate `suggested_alt_text`:** Provide concise, descriptive alt text for SEO (no promotional language).
- **Follow Image Reference Rules:** If a reference image was used, ensure you have correctly handled the `main_subject` field based on whether there was a specific instruction.
"""
    
    if not use_instructor_parsing or CREATIVE_EXPERT_MODEL_ID in INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS:
        final_instruction += "\nREMEMBER: Your entire response MUST be only the JSON object, starting with `{` and ending with `}`. Do not include any other text."

    user_prompt_parts.append(final_instruction)
    return "\n".join(user_prompt_parts)


async def _generate_visual_concept_for_strategy(
    ctx: PipelineContext,
    strategy: Dict[str, Any],
    strategy_index: int,
    style_guidance_item: Optional[StyleGuidance]
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, int]], Optional[str]]:
    """Generates a structured visual concept for a specific marketing strategy."""
    
    if not ImageGenerationPrompt or not VisualConceptDetails:
        return None, None, "Error: Pydantic models for Creative Expert not available."

    creativity_level = ctx.creativity_level
    task_type = ctx.task_type or "N/A"
    platform_name = ctx.target_platform.get("name", "N/A") if ctx.target_platform else "N/A"
    
    # Aspect ratio for prompt text (not API size)
    platform_aspect_ratio = "1:1"
    if ctx.target_platform and ctx.target_platform.get("resolution_details"):
        platform_aspect_ratio = ctx.target_platform["resolution_details"].get("aspect_ratio", "1:1")
    aspect_ratio_for_prompt_text = _map_to_supported_aspect_ratio_for_prompt(platform_aspect_ratio)

    user_prompt_original = ctx.prompt
    image_reference = ctx.image_reference
    brand_kit = ctx.brand_kit
    task_description = ctx.task_description
    render_text_flag = ctx.render_text
    apply_branding_flag = ctx.apply_branding

    image_analysis = ctx.image_analysis_result

    has_image_reference = image_reference is not None
    image_instruction = image_reference.get("instruction") if has_image_reference else None
    has_instruction_flag = bool(image_instruction)
    saved_image_filename = image_reference.get("filename") if has_image_reference else None
    image_subject_from_analysis = image_analysis.get("main_subject") if isinstance(image_analysis, dict) else None
    is_default_edit_case = has_image_reference and not has_instruction_flag

    # Use global client variables (injected by pipeline executor)
    # Determine parsing strategy using centralized logic
    use_manual_parsing = should_use_manual_parsing(CREATIVE_EXPERT_MODEL_ID)
    client_to_use_ce = base_llm_client_creative_expert if use_manual_parsing else instructor_client_creative_expert
    use_instructor_for_ce_call = bool(instructor_client_creative_expert and not use_manual_parsing)
    
    if not client_to_use_ce:
        return None, None, "LLM Client for Creative Expert not available."

    system_prompt_ce = _get_creative_expert_system_prompt(
        creativity_level, task_type, use_instructor_for_ce_call, has_image_reference, has_instruction_flag,
        render_text_flag, apply_branding_flag, platform_name,
        target_model_family=CREATIVE_EXPERT_MODEL_PROVIDER.lower(),
        language=ctx.language
    )
    
    user_prompt_ce = _get_creative_expert_user_prompt(
        platform_name, aspect_ratio_for_prompt_text, strategy, task_type, user_prompt_original,
        task_description, brand_kit, render_text_flag, apply_branding_flag,
        has_image_reference, saved_image_filename, image_subject_from_analysis,
        image_instruction, use_instructor_for_ce_call, is_default_edit_case, style_guidance_item,
        language=ctx.language
    )

    llm_args_ce = {
        "model": CREATIVE_EXPERT_MODEL_ID,
        "messages": [
            {"role": "system", "content": system_prompt_ce}, 
            {"role": "user", "content": user_prompt_ce}
        ],
        "temperature": 0.7, 
        "max_tokens": 5000, 
        "extra_body": {}
    }
    
    # Adjust temperature based on creativity level
    if creativity_level == 1:
        llm_args_ce["temperature"] = 0.4
    elif creativity_level == 3:
        llm_args_ce["temperature"] = 0.9

    if use_instructor_for_ce_call and ImageGenerationPrompt:
        llm_args_ce["response_model"] = ImageGenerationPrompt

    usage_info_ce = None
    error_details_ce = None
    prompt_data_ce = None
    raw_response_content_ce = None
    
    try:
        ctx.log(f"Generating structured prompt for Strategy {strategy_index} (Creativity: {creativity_level}) using {CREATIVE_EXPERT_MODEL_PROVIDER} model: {CREATIVE_EXPERT_MODEL_ID}")
        
        effective_client_ce = client_to_use_ce
        actually_use_instructor_parsing_ce = use_instructor_for_ce_call

        if use_instructor_for_ce_call and CREATIVE_EXPERT_MODEL_ID in INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS:
            ctx.log(f"Model {CREATIVE_EXPERT_MODEL_ID} is problematic with instructor tool mode. Forcing manual parse for this call.")
            actually_use_instructor_parsing_ce = False
            if "response_model" in llm_args_ce: 
                del llm_args_ce["response_model"]
            if "tools" in llm_args_ce: 
                del llm_args_ce["tools"]
            if "tool_choice" in llm_args_ce: 
                del llm_args_ce["tool_choice"]

        completion_ce = await asyncio.to_thread(effective_client_ce.chat.completions.create, **llm_args_ce)

        if actually_use_instructor_parsing_ce:
            prompt_data_ce = completion_ce.model_dump()
        else:  # Manual parse using centralized parser
            raw_response_content_ce = completion_ce.choices[0].message.content
            
            try:
                # Use centralized parser with fallback validation for promotional_text_visuals handling
                def fallback_validation(data: Dict[str, Any]) -> Dict[str, Any]:
                    """Handle special case where promotional_text_visuals might be returned as a dict."""
                    if ('visual_concept' in data and 
                        isinstance(data.get('visual_concept'), dict) and 
                        'promotional_text_visuals' in data['visual_concept'] and 
                        isinstance(data['visual_concept']['promotional_text_visuals'], dict)):

                        ptv_dict = data['visual_concept']['promotional_text_visuals']
                        description_parts = []
                        for ptv_key, ptv_value in ptv_dict.items():
                            formatted_ptv_key = ptv_key.replace('_', ' ').capitalize()
                            if isinstance(ptv_value, list):
                                item_strs = []
                                for item in ptv_value:
                                    if isinstance(item, dict) and 'type' in item and 'text' in item:
                                        item_strs.append(f"{item.get('type', '').capitalize()}: \"{item.get('text', '')}\"")
                                    elif isinstance(item, dict):
                                        item_strs.append(json.dumps(item))
                                    else:
                                        item_strs.append(str(item))
                                description_parts.append(f"{formatted_ptv_key}: [{'; '.join(item_strs)}]")
                            elif isinstance(ptv_value, dict):
                                description_parts.append(f"{formatted_ptv_key}: {json.dumps(ptv_value)}")
                            else:
                                description_parts.append(f"{formatted_ptv_key}: {str(ptv_value)}")

                        if description_parts:
                            data['visual_concept']['promotional_text_visuals'] = "; ".join(description_parts) + "."
                        else:
                            data['visual_concept']['promotional_text_visuals'] = json.dumps(ptv_dict)

                    # Validate with Pydantic model after transformation
                    validated_model = ImageGenerationPrompt(**data)
                    return validated_model.model_dump()
                
                prompt_data_ce = _json_parser.extract_and_parse(
                    raw_response_content_ce,
                    expected_schema=ImageGenerationPrompt,
                    fallback_validation=fallback_validation
                )
                
            except TruncatedResponseError as truncate_err_ce:
                current_max_tokens = llm_args_ce.get("max_tokens", 5000)
                error_details_ce = (
                    f"Creative Expert response was truncated mid-generation. "
                    f"Current max_tokens: {current_max_tokens}. "
                    f"Consider increasing max_tokens or trying a different model. "
                    f"Truncation details: {truncate_err_ce}\n"
                    f"Raw response preview: {raw_response_content_ce[:500]}..."
                )
                raise Exception(error_details_ce)
            except JSONExtractionError as extract_err_ce:
                error_details_ce = f"Creative Expert JSON extraction/parsing failed: {extract_err_ce}\nRaw: {raw_response_content_ce}"
                raise Exception(error_details_ce)

        if prompt_data_ce is None:
            raise Exception("Failed to obtain structured data from Creative Expert.")

        # Post-processing based on flags (important for both instructor and manual parse)
        vc_ce = prompt_data_ce.get("visual_concept", {})
        if is_default_edit_case and vc_ce.get("main_subject") is not None:
            vc_ce["main_subject"] = None
        if not render_text_flag and vc_ce.get("promotional_text_visuals") is not None:
            vc_ce["promotional_text_visuals"] = None
        if not apply_branding_flag and vc_ce.get("logo_visuals") is not None:
            vc_ce["logo_visuals"] = None
        prompt_data_ce["visual_concept"] = vc_ce
        prompt_data_ce['source_strategy_index'] = strategy_index

        ctx.log(f"Successfully generated structured prompt object for Strategy {strategy_index}.")
        
        # Extract usage information
        raw_response_ce_obj = getattr(completion_ce, '_raw_response', completion_ce)
        if hasattr(raw_response_ce_obj, 'usage') and raw_response_ce_obj.usage:
            usage_info_ce = raw_response_ce_obj.usage.model_dump()
            ctx.log(f"Token Usage (Creative Expert - Strategy {strategy_index}): {usage_info_ce}")
        else:
            ctx.log("Token usage data not available for Creative Expert.")
        
        return prompt_data_ce, usage_info_ce, None
        
    except Exception as e_ce:
        if not error_details_ce:
            error_details_ce = f"Creative Expert general error: {e_ce}\n{traceback.format_exc()}"
        if not use_instructor_for_ce_call and raw_response_content_ce and "Raw:" not in error_details_ce:
            error_details_ce += f"\nRaw Content (Creative Expert): {raw_response_content_ce}"
        ctx.log(f"ERROR (Creative Expert - Strategy {strategy_index}): {error_details_ce}")
        return None, None, error_details_ce


async def run(ctx: PipelineContext) -> None:
    """
    Generates structured visual concepts for all marketing strategies using style guidance.
    
    This stage takes the marketing strategies and style guidance from previous stages
    and generates detailed ImageGenerationPrompt objects for each strategy.
    """
    stage_name = "Creative Expert"
    ctx.log(f"Starting {stage_name} stage")
    
    # Check if required models are available
    if not ImageGenerationPrompt or not VisualConceptDetails:
        error_msg = "Error: Creative Expert Pydantic models not available."
        ctx.log(f"ERROR: {error_msg}")
        ctx.generated_image_prompts = None
        return

    # Get strategies and style guidance from previous stages
    strategies = ctx.suggested_marketing_strategies
    style_guidance_sets = ctx.style_guidance_sets
    
    if not strategies:
        ctx.log("No marketing strategies provided to Creative Expert")
        ctx.generated_image_prompts = []
        return
        
    if not style_guidance_sets:
        ctx.log("No style guidance provided to Creative Expert")
        ctx.generated_image_prompts = None
        return
        
    if len(strategies) != len(style_guidance_sets):
        ctx.log(f"ERROR: Mismatch between strategies ({len(strategies)}) and style guidance ({len(style_guidance_sets)})")
        ctx.generated_image_prompts = None
        return

    num_strategies = len(strategies)
    ctx.log(f"Generating visual concepts for {num_strategies} strategies")

    # Check if global client is available (injected by pipeline executor)
    if not instructor_client_creative_expert and not base_llm_client_creative_expert:
        error_msg = "LLM Client for Creative Expert not available."
        ctx.log(f"ERROR: {error_msg}")
        ctx.generated_image_prompts = None
        return

    generated_prompts_list = []
    all_concepts_generated = True
    
    # Prepare tasks for parallel execution
    tasks = []
    valid_strategies = []
    
    for idx, strategy_item in enumerate(strategies):
        style_item_dict = style_guidance_sets[idx]
        
        try:
            # Ensure style_item_dict can be parsed into StyleGuidance
            style_item_pydantic = StyleGuidance(**style_item_dict) if StyleGuidance else style_item_dict
            
            # Create async task for this strategy
            task = _generate_visual_concept_for_strategy(
                ctx, strategy_item, idx, style_item_pydantic
            )
            tasks.append(task)
            valid_strategies.append((idx, strategy_item))
            
        except ValidationError as ve:
            ctx.log(f"ERROR: Invalid style guidance format for strategy {idx}: {ve}. Skipping concept generation for this strategy.")
            all_concepts_generated = False
            continue

    if not tasks:
        ctx.log("No valid strategies to process")
        ctx.generated_image_prompts = []
        return

    # Execute all tasks in parallel
    ctx.log(f"Processing {len(tasks)} visual concepts in parallel...")
    
    try:
        # Run all tasks concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for i, result in enumerate(results):
            idx, strategy_item = valid_strategies[i]
            
            if isinstance(result, Exception):
                ctx.log(f"ERROR generating visual concept for Strategy {idx}: {result}")
                all_concepts_generated = False
                continue
                
            concept_dict, concept_usage, concept_error = result
            
            if concept_usage:
                # Store usage in llm_usage
                if not hasattr(ctx, 'llm_usage'):
                    ctx.llm_usage = {}
                ctx.llm_usage[f"creative_expert_strategy_{idx}"] = concept_usage
                
            if concept_error or not concept_dict:
                ctx.log(f"ERROR generating visual concept for Strategy {idx}: {concept_error}")
                all_concepts_generated = False
            else:
                generated_prompts_list.append(concept_dict)
                ctx.log(f"Visual Concept for Strategy {idx} (Source Strategy Index: {concept_dict.get('source_strategy_index')}) completed successfully")
                
    except Exception as e:
        ctx.log(f"ERROR during parallel processing: {e}")
        all_concepts_generated = False

    # Store results
    ctx.generated_image_prompts = generated_prompts_list
    
    if not all_concepts_generated and not generated_prompts_list:
        ctx.log(f"ERROR: No visual concepts generated")
        ctx.generated_image_prompts = None
    elif not all_concepts_generated:
        ctx.log("WARNING: One or more visual concepts failed to generate")
    else:
        ctx.log(f"{stage_name} stage completed successfully") 