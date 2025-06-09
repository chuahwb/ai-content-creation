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

# Global variables for API clients and configuration (injected by pipeline executor)
instructor_client_creative_expert = None
base_llm_client_creative_expert = None
CREATIVE_EXPERT_MODEL_ID = None
CREATIVE_EXPERT_MODEL_PROVIDER = None
FORCE_MANUAL_JSON_PARSE = False
INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS = []


def _extract_json_from_llm_response(raw_text: str) -> Optional[str]:
    """
    Extracts a JSON string from an LLM's raw text response.
    Handles markdown code blocks and attempts to parse direct JSON.
    """
    import re
    
    if not isinstance(raw_text, str):
        return None

    # 1. Try to find JSON within ```json ... ```
    match_md_json = re.search(r"```json\s*([\s\S]+?)\s*```", raw_text, re.IGNORECASE)
    if match_md_json:
        json_str = match_md_json.group(1).strip()
        try:
            json.loads(json_str)  # Validate
            return json_str
        except json.JSONDecodeError:
            pass

    # 2. Try to find JSON within ``` ... ``` (generic code block)
    match_md_generic = re.search(r"```\s*([\s\S]+?)\s*```", raw_text, re.IGNORECASE)
    if match_md_generic:
        potential_json = match_md_generic.group(1).strip()
        if (potential_json.startswith('{') and potential_json.endswith('}')) or \
           (potential_json.startswith('[') and potential_json.endswith(']')):
            try:
                json.loads(potential_json)
                return potential_json
            except json.JSONDecodeError:
                pass

    # 3. Try to parse the stripped raw_text directly
    stripped_text = raw_text.strip()
    if not stripped_text:
        return None

    try:
        json.loads(stripped_text)
        return stripped_text
    except json.JSONDecodeError as e:
        if "Extra data" in str(e) and e.pos > 0:
            potential_json_substring = stripped_text[:e.pos]
            try:
                json.loads(potential_json_substring)
                return potential_json_substring.strip()
            except json.JSONDecodeError:
                pass

    # 4. Fallback: find the first '{' to the last '}' or first '[' to last ']'
    first_brace = stripped_text.find('{')
    last_brace = stripped_text.rfind('}')
    first_bracket = stripped_text.find('[')
    last_bracket = stripped_text.rfind(']')

    json_candidate = None

    if first_brace != -1 and last_brace != -1 and first_brace < last_brace:
        potential_obj_str = stripped_text[first_brace : last_brace + 1]
        try:
            json.loads(potential_obj_str)
            json_candidate = potential_obj_str
        except json.JSONDecodeError:
            pass

    if first_bracket != -1 and last_bracket != -1 and first_bracket < last_bracket:
        potential_arr_str = stripped_text[first_bracket : last_bracket + 1]
        try:
            json.loads(potential_arr_str)
            if json_candidate:
                if not (first_bracket > first_brace and last_bracket < last_brace):
                     json_candidate = potential_arr_str
            else:
                json_candidate = potential_arr_str
        except json.JSONDecodeError:
            pass

    return json_candidate


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
    target_model_family: str = "openai"
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
    
    input_refinement_ce = """
**Input Refinement:** Critically review ALL user inputs (Original User Prompt Hint, Specific Task Content/Description, Branding Guidelines, Image Instruction, and the provided Style Guidance). If any input is brief, vague, contains grammatical errors, or seems misaligned, you MUST interpret the user's likely intent, refine it, expand upon it creatively, and clearly explain your refined interpretation within the relevant structured output fields. Ensure the final concept is coherent and aligns with the marketing strategy and task type.
"""
    
    core_task_ce = """
**Core Task:** Embody maximum creativity and imagination, coupled with a deep understanding of visual design principles (color, composition, lighting, typography), F&B marketing trends, and image generation capabilities. Generate diverse, high-impact visual concepts tailored to the specific task type and marketing goals.
**You will be provided with specific `Style Guidance` (keywords, description, marketing impact) for this concept. Your `visual_style` field MUST be a detailed and rich elaboration of this provided style, adhering to its artistic boundaries and constraint.** Use it as your primary stylistic foundation and creatively build upon it, ensuring all other visual elements (composition, lighting, color, main_subject description) harmonize with and bring this specific style to life in a way that is relevant to the task type and marketing strategy.
**Style and Task Synthesis:** The `Style Guidance` dictates the primary artistic treatment. You must creatively adapt the specific visual elements mentioned in the `Task Type Adaptation` guidance to fit *within* this overarching artistic style. For example, if the style is 'surrealist illustration' and the task is 'Product Photography' (which typically calls for clear product focus), interpret this to mean clear, dramatic, or stylized elements that enhance the surrealist illustration while still ensuring the product is recognizable and appealing, as guided by the task's Creativity Guardrail. The goal is a harmonious blend where the artistic style is paramount but is applied to meet the functional needs of the task type.
Fill in all the fields of the requested Pydantic JSON output format (`ImageGenerationPrompt` containing `VisualConceptDetails`). Be extremely specific, descriptive, and justify design choices implicitly through the descriptions. The `main_subject` field should describe all key subjects and their interaction clearly (unless instructed otherwise for default edits).
"""
    
    # Task Type Guidance Map (simplified version for this stage)
    task_type_guidance_map = {
        "1. Product Photography": {
            "description": "Create visuals with exceptional clarity to showcase the product's details, textures, and qualities for menu spotlight or sales.",
            "platform_optimization": f"For {clean_platform_name}, use compositions with vibrant product focus",
            "text_guidance": "If text is enabled, place promotional text in a clear, bold sans-serif font",
            "branding_guidance": "If branding is enabled, integrate branding elements subtly"
        },
        "2. Promotional Graphics & Announcements": {
            "description": "Design for immediate visual impact and attention-grabbing power to drive engagement.",
            "platform_optimization": f"For {clean_platform_name}, ensure bold, centered compositions for shareability",
            "text_guidance": "If text is enabled, use large, bold headlines with clear hierarchy",
            "branding_guidance": "If branding is enabled, integrate branding without cluttering the promotional message"
        },
        "3. Store Atmosphere & Decor": {
            "description": "Focus on immersive environmental storytelling to capture the unique mood and ambiance.",
            "platform_optimization": f"For {clean_platform_name}, capture dynamic ambiance suitable for the platform",
            "text_guidance": "If text is enabled, place taglines in an elegant serif font as subtle overlay",
            "branding_guidance": "If branding is enabled, integrate branding subtly within the scene"
        },
        "4. Menu Spotlights": {
            "description": "Favor close-up or medium shots to highlight a specific menu item with appetizing appeal.",
            "platform_optimization": f"For {clean_platform_name}, create contextual lifestyle shots that make the dish look appealing",
            "text_guidance": "If text is enabled, suggest bold promotional text positioned to enhance the dish",
            "branding_guidance": "If branding is enabled, integrate branding on tableware or as subtle elements"
        },
        "5. Cultural & Community Content": {
            "description": "Favor compositions with symbolic elements and culturally inspired color palettes.",
            "platform_optimization": f"For {clean_platform_name}, create lifestyle-oriented visuals with cultural significance",
            "text_guidance": "If text is enabled, suggest elegant script taglines that harmonize with visual elements",
            "branding_guidance": "If branding is enabled, integrate branding in a way that honors the cultural context"
        },
        "6. Recipes & Food Tips": {
            "description": "Prioritize clarity, visual instruction, and appetite appeal for educational content.",
            "platform_optimization": f"For {clean_platform_name}, use detailed compositions suitable for instructional content",
            "text_guidance": "If text is enabled, use concise, bold text for step titles and clear instructions",
            "branding_guidance": "If branding is enabled, integrate branding to tie to brand identity without distraction"
        },
        "7. Brand Story & Milestones": {
            "description": "Create evocative, narrative, or celebratory visuals to resonate emotionally.",
            "platform_optimization": f"For {clean_platform_name}, create cinematic visuals with narrative flow",
            "text_guidance": "If text is enabled, place taglines in elegant serif font as focal point",
            "branding_guidance": "If branding is enabled, integrate branding to reinforce identity within storytelling"
        },
        "8. Behind the Scenes Imagery": {
            "description": "Convey authenticity, process, and human element with professional yet candid visuals.",
            "platform_optimization": f"For {clean_platform_name}, use authentic compositions suitable for the platform",
            "text_guidance": "If text is enabled, place captions in playful or clean font authentically",
            "branding_guidance": "If branding is enabled, integrate branding naturally within the scene"
        }
    }
    
    # Get task guidance or use default
    task_key = task_type.split('.', 1)[-1].strip() if '.' in task_type else task_type
    task_guidance = task_type_guidance_map.get(task_type, {
        "description": f"Adapt the visual concept appropriately for '{task_type}'",
        "platform_optimization": f"Optimize for {clean_platform_name}",
        "text_guidance": "Handle text rendering as appropriate",
        "branding_guidance": "Handle branding as appropriate"
    })
    
    task_type_awareness_ce = f"""
**Task Type Adaptation (CRUCIAL):** The specified Task Type is '{task_type}'. Your visual concept must be expertly tailored to this task.
- {task_guidance['description']}
- Platform Optimization: {task_guidance['platform_optimization']}
"""
    
    # Add text and branding guidance based on flags
    text_branding_field_instruction_ce = "**Text & Branding (JSON Output Fields):**\n"
    if render_text_flag:
        text_branding_field_instruction_ce += f"- For `promotional_text_visuals` field: {task_guidance['text_guidance']}. Describe text content, visual style, font characteristics, placement hierarchy, and integration with the visual.\n"
    else:
        text_branding_field_instruction_ce += "- The `promotional_text_visuals` field in the JSON output MUST be omitted (set to null) as text rendering is disabled.\n"
    
    if apply_branding_flag:
        text_branding_field_instruction_ce += f"- For `branding_visuals` field: {task_guidance['branding_guidance']}. If no guidelines are provided, derive branding style from strategy and task.\n"
    else:
        text_branding_field_instruction_ce += "- The `branding_visuals` field in the JSON output MUST be omitted (set to null) as branding application is disabled.\n"
    
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
            image_ref_handling_ce += "- An image reference IS provided AND a specific user `instruction` IS given: Interpret the instruction and apply it when describing the concept. Populate all fields including `main_subject`.\n"
        else:
            image_ref_handling_ce += "- An image reference IS provided BUT NO specific user `instruction` is given: The **primary subject** of the visual concept MUST be the analyzed subject from the reference image. Your main creative task is to design the *context* around this subject aligned with the marketing strategy. **Crucially, you MUST OMIT the `main_subject` field entirely (set it to null) in your JSON output.** Focus ONLY on describing the context fields.\n"
    else:
        image_ref_handling_ce += "- NO image reference is provided: Generate the entire visual concept based on the marketing strategy and other inputs, including the `main_subject`.\n"
    
    reasoning_ce = "**Creative Reasoning:** After defining the visual concept, provide a brief explanation in the `creative_reasoning` field, connecting the key visual choices (style, mood, composition, subject focus, color palette) back to the core marketing strategy (audience, niche, objective, voice), the specific Task Type, the provided Style Guidance, and any significant user inputs or refinements made, especially noting how the image reference was handled. **Justify why the chosen creative direction is effective and aligns with the overall marketing objectives from the strategy.**"
    
    # Output format instructions
    adherence_ce = ""
    if use_instructor_parsing and CREATIVE_EXPERT_MODEL_ID not in INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS:
        adherence_ce = "Adhere strictly to the requested Pydantic JSON output format (`ImageGenerationPrompt` containing `VisualConceptDetails`). Note that `main_subject`, `promotional_text_visuals`, and `branding_visuals` are optional and should be omitted (set to null) if the specific scenario instructs it. Ensure all other required descriptions are detailed enough to guide image generation effectively."
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
    "branding_visuals": "string | null", // Omit (set to null) if apply_branding_flag is false
    "texture_and_details": "string | null",
    "negative_elements": "string | null",
    "creative_reasoning": "string | null"
  },
  "source_strategy_index": "integer | null" // This will be added programmatically later
}
Ensure all descriptions are detailed enough to guide image generation effectively.
"""
    
    prompt_parts_ce = [
        base_persona_ce, input_refinement_ce, core_task_ce, task_type_awareness_ce,
        creativity_instruction_ce, image_ref_handling_ce, text_branding_field_instruction_ce,
        reasoning_ce, adherence_ce
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
    branding_elements: Optional[str],
    render_text_flag: bool,
    apply_branding_flag: bool,
    has_image_reference: bool,
    saved_image_filename: Optional[str],
    image_subject_from_analysis: Optional[str],
    image_instruction: Optional[str],
    use_instructor_parsing: bool,
    is_default_edit: bool,
    style_guidance_item: Optional[StyleGuidance]
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
        user_prompt_parts.append(f"- Marketing Impact of this Style: {style_guidance_item.marketing_impact if style_guidance_item.marketing_impact else 'N/A'}")
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

    branding_apply_status = "(Branding application enabled by user)" if apply_branding_flag else "(Branding application DISABLED by user)"
    if branding_elements:
        user_prompt_parts.append(f"- Branding Guidelines: '{branding_elements}' {branding_apply_status} (Interpret/refine guidelines. If application enabled, describe visualization in `branding_visuals` field of JSON output, following task-specific branding guidance from system prompt).")
    elif apply_branding_flag:
        user_prompt_parts.append(f"- Branding Guidelines: Not Provided, but branding application is enabled. Derive branding style from strategy/task and describe visualization in `branding_visuals` field of JSON output, following task-specific branding guidance from system prompt.")
    else:
        user_prompt_parts.append("- Branding Guidelines: Not Provided, and branding application is disabled.")

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
        "Instagram Story/Reel": f"Optimize for Instagram Story/Reel: Focus on dynamic, attention-grabbing visuals for {aspect_ratio_for_prompt} vertical format. Consider bold text, trendy effects, or concepts suitable for short video loops or interactive elements.",
        "Facebook Post": f"Optimize for Facebook Feed: Design for broad appeal and shareability in {aspect_ratio_for_prompt} format. Ensure clear branding and messaging for potential ad use.",
        "Pinterest Pin": f"Optimize for Pinterest: Create visually striking, informative vertical images in {aspect_ratio_for_prompt} format. Focus on aesthetics, clear subject matter, and potential for text overlays that add value.",
        "Xiaohongshu (Red Note)": f"Optimize for Xiaohongshu: Focus on authentic, aesthetically pleasing, informative, and often lifestyle-oriented visuals in {aspect_ratio_for_prompt} vertical format. Use high-quality imagery, potentially with integrated text overlays in a blog-post style.",
    }
    platform_guidance_text = platform_guidance_map.get(clean_platform_name, f"Adapt the concept for the target platform '{clean_platform_name}' using {aspect_ratio_for_prompt} aspect ratio.")
    user_prompt_parts.append(f"\n**Platform Optimization (General Reminder):** {platform_guidance_text} (Detailed task-specific platform optimization is in system prompt).")

    final_instruction = f"""
\nBased on ALL the above context (especially the core marketing strategy, the provided Style Direction, and the task-specific guidance from the system prompt) and your expertise (refining user inputs as needed), generate the `ImageGenerationPrompt` JSON object.
Ensure the nested `VisualConceptDetails` object is fully populated with rich, descriptive details suitable for guiding a text-to-image model.
"""
    
    if is_default_edit:
        final_instruction += "- **IMPORTANT REMINDER: Since this is a default edit scenario (reference image provided, no specific user instruction), OMIT the `main_subject` field (set to null) in your JSON response. Focus ONLY on describing the context fields.**\n"
    else:
        final_instruction += "- Describe the `main_subject` clearly (following image reference logic from system prompt if applicable). This field should encompass all key subjects in the scene and their interactions.\n"

    final_instruction += """
- Detail the `composition_and_framing`.
- Describe the `background_environment`.
- Mention any important `foreground_elements`.
- Specify the `lighting_and_mood`.
- Define the `color_palette`.
- Articulate the `visual_style`. This field MUST comprehensively describe the desired aesthetic, being a detailed and creative elaboration of the provided Style Guidance. If no style guidance was given, invent a style according to the creativity level set in the system prompt.
"""
    
    if render_text_flag:
        final_instruction += "- If text is being rendered, ensure your description for `promotional_text_visuals` is detailed and creative, following any task-specific text guidance provided in the system prompt.\n"
    else:
        final_instruction += "- Omit `promotional_text_visuals` field (set to null) in JSON as text rendering is disabled.\n"
    
    if apply_branding_flag:
        final_instruction += "- If branding is being applied, ensure your description for `branding_visuals` is detailed and creative, following any task-specific branding guidance provided in the system prompt. Handle the case where no branding guidelines were provided.\n"
    else:
        final_instruction += "- Omit `branding_visuals` field (set to null) in JSON as branding application is disabled.\n"
    
    final_instruction += """
- Add notes on `texture_and_details` if relevant.
- List any `negative_elements` to avoid.
- **Provide a brief `creative_reasoning` explaining how the main visual choices connect to the core marketing strategy (especially the `target_objective`), user inputs, task type, and style guidance.**

Ensure the overall visual concept aligns strongly with the core marketing strategy, task type '{task_type}', and incorporates the image reference context as instructed in the system prompt.
The `source_strategy_index` field in the JSON will be added programmatically later.
"""
    
    if not use_instructor_parsing or CREATIVE_EXPERT_MODEL_ID in INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS:
        final_instruction += "\nVERY IMPORTANT: Your entire response MUST be only the JSON object described in the system prompt (Creative Expert section), starting with `{` and ending with `}`. Do not include any other text or formatting."

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
    branding_elements = ctx.branding_elements
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
    client_to_use_ce = instructor_client_creative_expert if instructor_client_creative_expert and not FORCE_MANUAL_JSON_PARSE else base_llm_client_creative_expert
    use_instructor_for_ce_call = bool(instructor_client_creative_expert and not FORCE_MANUAL_JSON_PARSE and CREATIVE_EXPERT_MODEL_ID not in INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS)
    
    if not client_to_use_ce:
        return None, None, "LLM Client for Creative Expert not available."

    system_prompt_ce = _get_creative_expert_system_prompt(
        creativity_level, task_type, use_instructor_for_ce_call, has_image_reference, has_instruction_flag,
        render_text_flag, apply_branding_flag, platform_name,
        target_model_family=CREATIVE_EXPERT_MODEL_PROVIDER.lower()
    )
    
    user_prompt_ce = _get_creative_expert_user_prompt(
        platform_name, aspect_ratio_for_prompt_text, strategy, task_type, user_prompt_original,
        task_description, branding_elements, render_text_flag, apply_branding_flag,
        has_image_reference, saved_image_filename, image_subject_from_analysis,
        image_instruction, use_instructor_for_ce_call, is_default_edit_case, style_guidance_item
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
        else:  # Manual parse
            raw_response_content_ce = completion_ce.choices[0].message.content
            json_string_ce = _extract_json_from_llm_response(raw_response_content_ce)
            if not json_string_ce:
                error_details_ce = f"Creative Expert JSON extraction failed.\nRaw: {raw_response_content_ce}"
                raise Exception(error_details_ce)
            
            try:
                parsed_json_ce = json.loads(json_string_ce)

                # Handle special case where promotional_text_visuals might be returned as a dict
                if ('visual_concept' in parsed_json_ce and 
                    isinstance(parsed_json_ce.get('visual_concept'), dict) and 
                    'promotional_text_visuals' in parsed_json_ce['visual_concept'] and 
                    isinstance(parsed_json_ce['visual_concept']['promotional_text_visuals'], dict)):

                    ptv_dict = parsed_json_ce['visual_concept']['promotional_text_visuals']
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
                        parsed_json_ce['visual_concept']['promotional_text_visuals'] = "; ".join(description_parts) + "."
                    else:
                        parsed_json_ce['visual_concept']['promotional_text_visuals'] = json.dumps(ptv_dict)

                validated_model_ce = ImageGenerationPrompt(**parsed_json_ce)
                prompt_data_ce = validated_model_ce.model_dump()
            except (json.JSONDecodeError, ValidationError) as val_err_ce:
                error_details_ce = f"Creative Expert Pydantic/JSON validation error: {val_err_ce}\nExtracted JSON: {json_string_ce}\nRaw: {raw_response_content_ce}"
                raise Exception(error_details_ce)

        if prompt_data_ce is None:
            raise Exception("Failed to obtain structured data from Creative Expert.")

        # Post-processing based on flags (important for both instructor and manual parse)
        vc_ce = prompt_data_ce.get("visual_concept", {})
        if is_default_edit_case and vc_ce.get("main_subject") is not None:
            vc_ce["main_subject"] = None
        if not render_text_flag and vc_ce.get("promotional_text_visuals") is not None:
            vc_ce["promotional_text_visuals"] = None
        if not apply_branding_flag and vc_ce.get("branding_visuals") is not None:
            vc_ce["branding_visuals"] = None
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