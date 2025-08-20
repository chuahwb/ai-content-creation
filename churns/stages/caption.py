"""
Caption Stage - Generates context-aware, on-brand social media captions.

This stage implements a two-stage approach:
1. Analyst LLM - Produces a strategic Caption Brief
2. Writer LLM - Crafts the final caption based on the brief

Follows the existing stage pattern with centralized JSON parsing and error handling.

**CRITICAL:** The platform_optimizations object must contain exactly one key matching the target platform name provided in the context."""

import json
import time
import traceback
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
from openai import APIConnectionError, RateLimitError, APIStatusError
from openai.types.chat import ChatCompletionMessageParam
from tenacity import RetryError
from pydantic import ValidationError

from ..pipeline.context import PipelineContext
from ..models import CaptionBrief, CaptionSettings, CaptionResult
from ..core.json_parser import (
    RobustJSONParser, 
    JSONExtractionError,
    TruncatedResponseError,
    should_use_manual_parsing
)
from ..core.token_cost_manager import get_token_cost_manager, TokenUsage

# Global variables for API clients and configuration (injected by pipeline executor)
instructor_client_caption = None
base_llm_client_caption = None
CAPTION_MODEL_ID = None
CAPTION_MODEL_PROVIDER = None
FORCE_MANUAL_JSON_PARSE = False
INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS = []

# Initialize centralized JSON parser for this stage
_json_parser = RobustJSONParser(debug_mode=False)



# Task Type Caption Guidance Mapping
TASK_TYPE_CAPTION_GUIDANCE = {
    "1. Product Photography": {
        "captionObjective": "Showcase product features & craftsmanship to spark desire and perceived quality.",
        "toneHints": ["aspirational", "sensory", "detail-oriented"],
        "hookTemplate": "Up close with {product} —",
        "structuralHints": "Hook → Sensory description → Benefit → CTA"
    },
    "2. Promotional Graphics & Announcements": {
        "captionObjective": "Drive immediate awareness and action for time-sensitive offers or news.",
        "toneHints": ["urgent", "excited", "inclusive"],
        "hookTemplate": "Heads up! {promo_title} drops {date} —",
        "structuralHints": "Headline → Key offer → Scarcity line → CTA"
    },
    "3. Store Atmosphere & Decor": {
        "captionObjective": "Transport the audience into the ambience and evoke an in-store experience.",
        "toneHints": ["immersive", "inviting", "storytelling"],
        "hookTemplate": "Step into our space —",
        "structuralHints": "Hook → Atmosphere description → Feeling → CTA"
    },
    "4. Menu Spotlights": {
        "captionObjective": "Highlight a specific menu item with appetite appeal and encourage orders.",
        "toneHints": ["mouth-watering", "friendly", "tempting"],
        "hookTemplate": "Craving something {flavour}? Meet our {menu_item} —",
        "structuralHints": "Hook → Taste/ingredient details → Benefit → CTA"
    },
    "5. Cultural & Community Content": {
        "captionObjective": "Celebrate cultural roots or community stories to foster connection and authenticity.",
        "toneHints": ["warm", "respectful", "celebratory"],
        "hookTemplate": "From our community to yours —",
        "structuralHints": "Hook → Cultural story → Value → CTA"
    },
    "6. Recipes & Food Tips": {
        "captionObjective": "Educate followers with practical recipes or tips featuring the product.",
        "toneHints": ["educational", "encouraging", "practical"],
        "hookTemplate": "Save this recipe: {dish_name} —",
        "structuralHints": "Hook → Key step or tip → Benefit → CTA"
    },
    "7. Brand Story & Milestones": {
        "captionObjective": "Share brand journey or achievements to build emotional connection and trust.",
        "toneHints": ["inspirational", "authentic", "grateful"],
        "hookTemplate": "Our journey began with {origin} —",
        "structuralHints": "Hook → Narrative snippet → Milestone → CTA"
    },
    "8. Behind the Scenes Imagery": {
        "captionObjective": "Reveal the people and process behind the brand to humanise and build transparency.",
        "toneHints": ["candid", "relatable", "transparent"],
        "hookTemplate": "Behind the scenes at {brand} —",
        "structuralHints": "Hook → Process insight → Team mention → CTA"
    }
}


def _get_task_type_guidance(task_type: str) -> Optional[Dict[str, Any]]:
    """
    Safely retrieve task type guidance for caption generation.
    
    Args:
        task_type: The task type string from pipeline context
        
    Returns:
        Task type guidance dict or None if not found
    """
    return TASK_TYPE_CAPTION_GUIDANCE.get(task_type)


def _extract_style_context(ctx: PipelineContext, prompt_index: int) -> Dict[str, Any]:
    """
    Extract critical style context signals from pipeline data.
    
    Args:
        ctx: Pipeline context
        prompt_index: Index of the current image prompt being processed
        
    Returns:
        Dictionary containing style keywords, creative reasoning, and target niche
    """
    style_context = {
        "style_keywords": [],
        "creative_reasoning": None,
        "target_niche": None
    }
    
    # Extract style keywords from style guidance sets
    if ctx.style_guidance_sets and prompt_index < len(ctx.style_guidance_sets):
        style_guidance = ctx.style_guidance_sets[prompt_index]
        style_context["style_keywords"] = style_guidance.get("style_keywords", [])
    
    # Extract creative reasoning from visual concept
    if ctx.generated_image_prompts and prompt_index < len(ctx.generated_image_prompts):
        visual_concept = ctx.generated_image_prompts[prompt_index].get("visual_concept", {})
        style_context["creative_reasoning"] = visual_concept.get("creative_reasoning")
    
    # Extract target niche from corresponding strategy
    if ctx.suggested_marketing_strategies:
        strategy_index = 0
        if ctx.generated_image_prompts and prompt_index < len(ctx.generated_image_prompts):
            strategy_index = ctx.generated_image_prompts[prompt_index].get("source_strategy_index", 0)
        
        if strategy_index < len(ctx.suggested_marketing_strategies):
            strategy = ctx.suggested_marketing_strategies[strategy_index]
            style_context["target_niche"] = strategy.get("target_niche")
    
    return style_context


def _resolve_final_instructions(
    ctx: PipelineContext,
    settings: CaptionSettings,
    strategy_data: Dict[str, Any],
    visual_data: Dict[str, Any],
    brand_voice: Optional[str]
) -> Dict[str, str]:
    """
    Consolidates all conditional logic to determine the final, unambiguous
    instructions for the Analyst LLM. It faithfully replicates the original
    logic from the prompts.
    """
    instructions = {}

    # 1. Resolve Tone Instruction
    if settings.generation_mode == 'Custom' and settings.tone:
        instructions['tone'] = f"You MUST adopt this exact tone of voice: '{settings.tone}'."
    else:  # Auto mode
        base_voice = brand_voice or strategy_data.get('target_voice') or "a friendly and engaging tone"
        visual_mood = visual_data.get('lighting_mood')
        instruction = f"Your task is to synthesize a new, refined tone of voice. Start with the primary voice ('{base_voice}')"
        if visual_mood:
            instruction += f" and blend it with the visual mood ('{visual_mood}')."
        else:
            instruction += "."
        instructions['tone'] = instruction

    # 2. Resolve Call to Action Instruction
    if settings.generation_mode == 'Custom' and settings.call_to_action:
        instructions['cta'] = f"You MUST use this exact call to action: '{settings.call_to_action}'."
    else:  # Auto mode
        target_objective = strategy_data.get('target_objective', 'drive engagement')
        instructions['cta'] = f"Your task is to generate a context-aware call to action that directly supports the marketing objective: '{target_objective}'."

    # 3. Resolve Emoji Usage Instruction
    use_emojis = settings.include_emojis if settings.include_emojis is not None else True
    if use_emojis:
        instructions['emojis'] = "You should use emojis appropriately and sparingly to match the determined tone of voice."
    else:
        instructions['emojis'] = "You MUST NOT use any emojis in the caption."
        
    # 4. Resolve Hashtag Strategy Instruction
    hashtag_strategy = settings.hashtag_strategy or "Balanced Mix"
    if hashtag_strategy == "Balanced Mix":
        instructions['hashtags'] = "Your task is to generate a 'Balanced Mix' of hashtags. This involves extracting specific keywords from the provided style and subject matter to create niche hashtags, and then supplementing those with 1-2 broader, high-traffic terms."
    else:
        instructions['hashtags'] = f"You MUST follow this user-provided hashtag strategy precisely: '{hashtag_strategy}'."
    
    # 5. Resolve User Instructions
    if settings.user_instructions:
        instructions['user_request'] = f"You MUST prioritize and directly address the following user instruction in your brief. It should heavily influence the 'core_message' and 'key_themes_to_include'. User Instruction: '{settings.user_instructions}'"
    
    # 6. Resolve Caption Length Instruction
    if settings.caption_length and settings.caption_length != "Auto":
        if settings.caption_length == "Short":
            instructions['length'] = "The user has requested a 'Short' caption. Your task is to populate the `length_guidance` field in the JSON brief with a clear, firm instruction for the writer, such as: 'Generate a very concise, high-impact caption, under 125 characters. It must be a powerful hook or a direct question to grab attention immediately. This is ideal for visually-driven content where the message must be instant.'"
        elif settings.caption_length == "Medium":
            instructions['length'] = "The user has requested a 'Medium' caption. Your task is to populate the `length_guidance` field in the JSON brief with a clear, firm instruction for the writer, such as: 'Generate a balanced caption of about 3-5 sentences (around 125-500 characters). This length should provide valuable context, tell a mini-story, and encourage engagement without overwhelming the reader.'"
        elif settings.caption_length == "Long":
            instructions['length'] = "The user has requested a 'Long' caption. Your task is to populate the `length_guidance` field in the JSON brief with a clear, firm instruction for the writer, such as: 'Generate a detailed, long-form caption (500+ characters), like a micro-blog post. This must be used for in-depth storytelling or providing significant educational value. Structure it with line breaks for readability to create save-worthy content.'"

    return instructions


def _get_analyst_system_prompt(language: str = 'en') -> str:
    """Returns the system prompt for the Analyst LLM."""
    # ============================
    # ===== ENHANCEMENT AREA =====
    # ============================
    # The original prompt was good. The enhanced version is more explicit about
    # the 'why' behind the SEO, focusing on creating 'save-worthy' content
    # and providing more detailed, actionable instructions for each platform.
    
    # Map language codes to readable names
    language_names = {
        'en': 'ENGLISH',
        'zh': 'SIMPLIFIED CHINESE',
        'es': 'SPANISH',
        'fr': 'FRENCH',
        'ja': 'JAPANESE'
    }
    language_name = language_names.get(language, language.upper())
    
    return f"""You are a master social media strategist and SEO expert. Your task is to analyze a comprehensive set of marketing and visual data and distill it into a structured JSON "Caption Brief" for a creative copywriter. You will receive explicit instructions for how to handle creative elements like tone and CTAs. Your role is to follow those instructions and synthesize the provided data into the required JSON format. You do not write the final caption yourself.

**Instructions:**
- Carefully analyze all the provided CONTEXT_DATA.
- Follow the explicit INSTRUCTIONS_FOR_BRIEF that you are given. These are non-negotiable.
- Generate a single, valid JSON object based on the CaptionBrief schema. The entire output must be only the JSON object, with no other text or explanation.
- **Language Consistency:** The fields `core_message`, `primary_call_to_action`, `hashtags`, and `seo_keywords` MUST be generated in {language_name}.
- ALL fields in the JSON schema are REQUIRED and must be included.

**Platform Optimizations (Enhanced for SEO):**
- **Instagram:** Structure as "Hook + Value + CTA". The `seo_keywords` are critical for the image's Alt Text. Encourage engagement with questions to earn comments and saves.
- **Facebook:** Focus on value-driven, longer-form content that sparks meaningful conversation and shares. Ensure the structure is friendly to outbound links if applicable.
- **Pinterest:** Treat this as a visual search engine. The caption must be a mini-blog post: a compelling, keyword-rich Title followed by a detailed, helpful description that makes it a top search result.
- **Xiaohongshu:** The caption title MUST be a hook-y, attention-grabbing long-tail keyword phrase (标题党 style). The body should be a helpful, authentic note, using emojis to enhance readability. The goal is to provide immense value to encourage saves (收藏) and comments.

**CRITICAL JSON STRUCTURE REQUIREMENTS:**
You must output a valid JSON object with exactly these fields. Do not omit any field:

{{
  "core_message": "A concise, one-sentence summary of the main message.",
  "key_themes_to_include": ["Array of 3-5 key themes or concepts"],
  "seo_keywords": ["Array of 3-5 important SEO keywords"],
  "target_emotion": "Primary emotion to evoke (e.g., 'Aspirational', 'Trustworthy')",
  "tone_of_voice": "The specific tone the writer must adopt. This is derived from your instructions.",
  "platform_optimizations": {{
    "[EXACT_PLATFORM_NAME]": {{
      "caption_structure": "Brief instruction on structure for this platform",
      "style_notes": "Platform-specific style guidance"
    }}
  }},
  "primary_call_to_action": "The final call to action string, derived from your instructions.",
  "hashtags": ["Array of hashtag strings with # symbol, derived from your instructions"],
  "emoji_suggestions": ["Array of 2-3 relevant emoji characters, derived from your instructions"],
  "length_guidance": "Optional. A specific instruction for the writer regarding the desired length of the caption. Set to null if no specific length is requested.",
  "task_type_notes": "Optional concise note about task-type optimization. Set to null if no task type guidance was provided."
}}

**CRITICAL:** The platform_optimizations object must contain exactly one key matching the target platform name provided in the context. Use the EXACT platform name as given in the context (e.g., "Instagram Post (1:1 Square)", not just "Instagram"). This field is mandatory and cannot be omitted."""


def _extract_main_subject(ctx: PipelineContext, visual_concept: Dict[str, Any]) -> str:
    """
    Extract main subject, falling back to image analysis if visual concept has null/missing main_subject.
    
    Args:
        ctx: Pipeline context containing image analysis
        visual_concept: Visual concept dictionary from generated prompts
        
    Returns:
        Main subject string or raises ValueError if none found
    """
    # First try to get from visual concept
    main_subject = visual_concept.get('main_subject')
    
    # Check if main_subject is None, null, or empty string
    if main_subject and main_subject.lower() not in ['null', 'none', '']:
        return main_subject
    
    # Fall back to image analysis result
    if ctx.image_analysis_result:
        image_main_subject = ctx.image_analysis_result.get('main_subject')
        if image_main_subject and image_main_subject.lower() not in ['null', 'none', '']:
            ctx.log(f"Using main subject from image analysis: {image_main_subject}")
            return image_main_subject
    
    # If still no main subject found, this is an error condition
    raise ValueError("No valid main subject found in visual concept or image analysis")


def _safe_extract_strategy_data(strategy: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """
    Safely extract strategy data without defaults that could mislead caption generation.
    
    Args:
        strategy: Marketing strategy dictionary
        
    Returns:
        Dictionary with extracted values or None if missing
    """
    return {
        'target_audience': strategy.get('target_audience'),
        'target_objective': strategy.get('target_objective'), 
        'target_voice': strategy.get('target_voice'),
        'target_niche': strategy.get('target_niche')
    }


def _safe_extract_visual_data(visual_concept: Dict[str, Any]) -> Dict[str, Optional[str]]:
    """
    Safely extract visual concept data without defaults that could mislead caption generation.
    
    Args:
        visual_concept: Visual concept dictionary
        
    Returns:
        Dictionary with extracted values or None if missing
    """
    return {
        'lighting_mood': visual_concept.get('lighting_and_mood'),
        'visual_style': visual_concept.get('visual_style'),
        'promotional_text': visual_concept.get('promotional_text_visuals'),
        'suggested_alt_text': visual_concept.get('suggested_alt_text')
    }


def _validate_required_data(strategy_data: Dict[str, Optional[str]], visual_data: Dict[str, Optional[str]], main_subject: str) -> None:
    """
    Validate that we have minimum required data for caption generation.
    
    Args:
        strategy_data: Extracted strategy data
        visual_data: Extracted visual data  
        main_subject: Main subject string
        
    Raises:
        ValueError: If critical data is missing
    """
    # Check for critical strategy data
    if not strategy_data.get('target_audience'):
        raise ValueError("Missing required target_audience in marketing strategy")
    
    if not strategy_data.get('target_objective'):
        raise ValueError("Missing required target_objective in marketing strategy")
    
    # Main subject is already validated by _extract_main_subject
    if not main_subject:
        raise ValueError("Main subject is required for caption generation")


def _get_analyst_user_prompt(
    ctx: PipelineContext,
    settings: CaptionSettings,
    platform_name: str,
    strategy: Dict[str, Any],
    visual_concept: Dict[str, Any],
    alt_text: str,
    prompt_index: int = 0
) -> str:
    """Constructs the user prompt for the Analyst LLM."""
    
    # Safely extract data without misleading defaults
    strategy_data = _safe_extract_strategy_data(strategy)
    visual_data = _safe_extract_visual_data(visual_concept)
    
    # Extract main subject with fallback to image analysis
    try:
        main_subject = _extract_main_subject(ctx, visual_concept)
    except ValueError as e:
        ctx.log(f"ERROR: {e}")
        raise
    
    # Validate we have minimum required data
    _validate_required_data(strategy_data, visual_data, main_subject)
    
    # Extract Brand Kit voice if available
    brand_voice = None
    if hasattr(ctx, 'brand_kit') and ctx.brand_kit:
        brand_voice = ctx.brand_kit.get('brand_voice_description')
    
    # Map language codes to readable names
    language_names = {
        'en': 'English',
        'zh': 'Simplified Chinese',
        'es': 'Spanish',
        'fr': 'French',
        'ja': 'Japanese'
    }
    language_name = language_names.get(ctx.language, ctx.language.upper())
    
    prompt_parts = []
    if brand_voice:
        prompt_parts.extend([
            "**Brand Voice Guidelines:**",
            f'"{brand_voice}"',
            ""
        ])
    
    prompt_parts.extend([
        f"**Target Platform:** {platform_name}",
        "",
        "**Marketing Strategy:**",
        f"- Target Audience: {strategy_data['target_audience']}",
        f"- Target Objective: {strategy_data['target_objective']}",
    ])
    
    # Add optional strategy fields only if they exist
    if strategy_data['target_voice']:
        prompt_parts.append(f"- Target Voice: {strategy_data['target_voice']}")
    if strategy_data['target_niche']:
        prompt_parts.append(f"- Target Niche: {strategy_data['target_niche']}")
    
    prompt_parts.extend([
        "",
        "**Visual Context:**",
        f"- Main Subject: {main_subject}",
    ])
    
    # Add optional visual fields only if they exist
    if visual_data['lighting_mood']:
        prompt_parts.append(f"- Lighting and Mood: {visual_data['lighting_mood']}")
    if visual_data['visual_style']:
        prompt_parts.append(f"- Visual Style: {visual_data['visual_style']}")
    if alt_text and alt_text != 'Generated image':
        # Add a note about the importance of the alt text for context
        prompt_parts.append(f"- Alt Text (for SEO context): {alt_text}")
    if visual_data['promotional_text']:
        prompt_parts.append(f"- Text on Image: {visual_data['promotional_text']}")
    
    # Add Task Type Context if available and feature enabled
    enable_task_type_optimization = getattr(ctx, 'enable_task_type_caption_optimization', True)
    if enable_task_type_optimization and ctx.task_type:
        task_guidance = _get_task_type_guidance(ctx.task_type)
        task_type = ctx.task_type.split('.', 1)[-1].strip() if '.' in ctx.task_type else ctx.task_type
        if task_guidance:
            prompt_parts.extend([
                "",
                "**Task Type Context:**",
                f"You are crafting a caption for a **{task_type}** social-media asset. The goal is to {task_guidance['captionObjective']}. Adopt a tone that feels {', '.join(task_guidance['toneHints'])}. Use this guidance as inspiration, not a script.",
                "",
                "**Important Guidance Notes:**",
                "- Treat structural hints as inspiration. If the platform optimization already prescribes a structure, merge or defer to it. Do not duplicate or contradict.",
                f"- Example hook template: \"{task_guidance['hookTemplate']}\" - Use as a creative starting point only. Feel free to remix or craft a better hook that suits the overall context.",
                f"- Suggested structure: {task_guidance['structuralHints']} - Adapt as needed for platform requirements."
            ])
    
    # Add Style Context for critical signals
    style_context = _extract_style_context(ctx, prompt_index)
    if style_context['style_keywords'] or style_context['creative_reasoning']:
        prompt_parts.extend([
            "",
            "**Style Context:**"
        ])
        
        if style_context['style_keywords']:
            prompt_parts.append(f"The accompanying image was designed with these style cues: {', '.join(style_context['style_keywords'])}. Channel this aesthetic subtly in the copy.")
        
        if style_context['creative_reasoning']:
            prompt_parts.append(f"The creative reasoning emphasizes: \"{style_context['creative_reasoning']}\"")
    
    # Get direct, final instructions from the new resolver function
    final_instructions = _resolve_final_instructions(ctx, settings, strategy_data, visual_data, brand_voice)

    prompt_parts.extend([
        "",
        "**INSTRUCTIONS_FOR_BRIEF**",
        "Based on all the CONTEXT_DATA above, you must follow these explicit instructions to generate the CaptionBrief JSON object:",
    ])
    
    # Add user request instruction first if present (highest priority)
    if 'user_request' in final_instructions:
        prompt_parts.append(f"- User Request Instruction: {final_instructions['user_request']}")
    
    prompt_parts.extend([
        f"- Tone of Voice Instruction: {final_instructions['tone']}",
        f"- Call to Action Instruction: {final_instructions['cta']}",
        f"- Emoji Usage Instruction: {final_instructions['emojis']}",
        f"- Hashtag Strategy Instruction: {final_instructions['hashtags']}",
    ])
    
    # Add length instruction if present
    if 'length' in final_instructions:
        prompt_parts.append(f"- Length Instruction: {final_instructions['length']}")
    
    prompt_parts.extend([
        "",
        f"**Important (Language Control):** The fields `core_message`, `primary_call_to_action`, `hashtags`, and `seo_keywords` should be written in {language_name.upper()}. Other guidance fields remain in English.",
        "",
        f"**CRITICAL REMINDER:** In your JSON response, the `platform_optimizations` field must contain exactly one key: \"{platform_name}\". Do not use a shortened or translated version of this platform name.",
        "",
        "Based on this context, generate a CaptionBrief JSON object that will guide the caption writer.",
        "Focus on strategic analysis and provide clear, actionable guidance for the creative execution."
    ])
    
    return "\n".join(prompt_parts)


def _get_writer_system_prompt(language: str = 'en') -> str:
    """Returns the system prompt for the Writer LLM."""
    # ============================
    # ===== ENHANCEMENT AREA =====
    # ============================
    # The original prompt was good, but this version adds a **CRITICAL** instruction
    # to ensure the Writer LLM does not deviate from the Analyst's strategic
    # platform-specific structure. It makes the guidance non-negotiable.
    
    # Map language codes to readable names
    language_names = {
        'en': 'ENGLISH',
        'zh': 'SIMPLIFIED CHINESE',
        'es': 'SPANISH',
        'fr': 'FRENCH',
        'ja': 'JAPANESE'
    }
    language_name = language_names.get(language, language.upper())
    
    return f"""You are an expert social media copywriter with a flair for creative, authentic, and engaging storytelling. Your brand voice is natural and human-like.

**Instructions:**
- Your task is to write a compelling social media caption based on the provided Caption Brief.
- **Language Adherence:** Write the final caption in {language_name}, keeping cultural/brand terms as-is. Only use a different language if explicitly present in those terms.
- **CRITICAL TONE OF VOICE:** You MUST adopt the following tone: **{{brief.tone_of_voice}}**. This is the most important instruction and is non-negotiable.
- **CRITICAL STRUCTURE:** You MUST strictly adhere to the `caption_structure` and `style_notes` provided in the `platform_optimizations` section of the brief. This structure is key to the caption's success on that specific platform.
- **CRITICAL LENGTH:** If a 'Length Requirement' is provided in the brief, you MUST strictly adhere to it. This is a non-negotiable instruction.
- Read the entire brief carefully to understand the strategic goals.
- Write a caption that feels authentic and human, not like it was written by an AI.
- Seamlessly integrate the `seo_keywords` into the text without making it sound forced.
- End with the `primary_call_to_action` and the provided `hashtags`.
- Your output should be ONLY the final caption text. Do not include the brief or any other commentary.

**Style Guidelines:**
- Use natural, conversational language.
- Vary sentence lengths for readability.
- Include line breaks where appropriate for platform readability.
- **CRITICAL:** Strictly follow the emoji usage instructions provided. If told not to use emojis, do NOT include any emojis whatsoever.
- **CRITICAL:** Strictly follow the hashtag usage instructions provided. If told not to use hashtags, do NOT include any hashtags whatsoever.
- When hashtags are provided, make them feel organic and naturally integrated at the end of the caption."""


def _get_writer_user_prompt(brief: CaptionBrief) -> str:
    """Constructs the user prompt for the Writer LLM."""
    
    # Handle emoji instructions explicitly
    if brief.emoji_suggestions:
        emoji_instruction = f"**Emoji Suggestions:** {' '.join(brief.emoji_suggestions)}\n**Emoji Usage:** Use the suggested emojis naturally and sparingly throughout the caption."
    else:
        emoji_instruction = "**Emoji Usage:** DO NOT use any emojis in this caption. The user has disabled emoji usage."
    
    # Handle hashtag instructions explicitly
    if brief.hashtags:
        hashtag_instruction = f"**Hashtags:** {' '.join(brief.hashtags)}\n**Hashtag Usage:** Include the provided hashtags at the end of the caption."
    else:
        hashtag_instruction = "**Hashtag Usage:** DO NOT include any hashtags in this caption. The user has disabled hashtag usage."
    
    prompt_parts = [
        "Write a social media caption based on this strategic brief:",
        "",
        f"**Core Message:** {brief.core_message}",
        f"**Tone of Voice:** {brief.tone_of_voice}"
    ]
    
    # Add task type notes if available
    if getattr(brief, 'task_type_notes', None):
        prompt_parts.append(f"**Task Note:** {brief.task_type_notes}")
    
    # Add length requirement if present
    if getattr(brief, 'length_guidance', None):
        prompt_parts.append(f"**Length Requirement:** {brief.length_guidance}")
    
    prompt_parts.extend([
        f"**Key Themes to Include:** {', '.join(brief.key_themes_to_include)}",
        f"**SEO Keywords:** {', '.join(brief.seo_keywords)}",
        f"**Target Emotion:** {brief.target_emotion}",
        f"**Platform Optimizations:** {json.dumps(brief.platform_optimizations, indent=2)}",
        f"**Call to Action:** {brief.primary_call_to_action}",
        "",
        hashtag_instruction,
        "",
        emoji_instruction,
        "",
        "Create an engaging, authentic caption that incorporates these elements naturally."
    ])
    
    return "\n".join(prompt_parts)


async def _run_analyst(
    ctx: PipelineContext,
    settings: CaptionSettings,
    platform_name: str,
    strategy: Dict[str, Any],
    visual_concept: Dict[str, Any],
    alt_text: str
) -> Optional[CaptionBrief]:
    """Runs the Analyst LLM to generate a Caption Brief."""
    
    # Determine parsing strategy
    use_manual_parsing = should_use_manual_parsing(CAPTION_MODEL_ID)
    client_to_use = base_llm_client_caption if use_manual_parsing else instructor_client_caption
    use_instructor_for_call = bool(instructor_client_caption and not use_manual_parsing)
    
    if not client_to_use:
        ctx.log("ERROR: Caption LLM client not available")
        return None
    
    system_prompt = _get_analyst_system_prompt(ctx.language)
    # Get the prompt index for style context extraction
    prompt_index = getattr(ctx, 'current_prompt_index', 0)
    user_prompt = _get_analyst_user_prompt(ctx, settings, platform_name, strategy, visual_concept, alt_text, prompt_index)
    
    llm_args = {
        "model": CAPTION_MODEL_ID,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 3000,
    }
    
    if use_instructor_for_call:
        llm_args["response_model"] = CaptionBrief
    
    try:
        ctx.log(f"Running Analyst LLM for caption brief using {CAPTION_MODEL_PROVIDER} model: {CAPTION_MODEL_ID}")
        ctx.log(f"Target platform for caption: {platform_name}")
        
        start_time = time.time()
        completion = client_to_use.chat.completions.create(**llm_args)
        end_time = time.time()
        
        if use_instructor_for_call:
            brief_dict = completion.model_dump()
        else:  # Manual parsing
            raw_content = completion.choices[0].message.content
            try:
                brief_dict = _json_parser.extract_and_parse(
                    raw_content,
                    expected_schema=CaptionBrief
                )
            except TruncatedResponseError as truncate_err:
                current_max_tokens = llm_args.get("max_tokens", 1500)
                ctx.log(f"ERROR: Caption Analyst response was truncated: {truncate_err}")
                ctx.log(f"Current max_tokens: {current_max_tokens}. Consider increasing max_tokens.")
                ctx.log(f"Raw Analyst content preview: {raw_content[:300]}...")
                return None
            except JSONExtractionError as extract_err:
                ctx.log(f"ERROR: JSON extraction/parsing failed for Analyst response: {extract_err}")
                ctx.log(f"Raw Analyst content: {raw_content}")
                return None
        
        # Track usage with enhanced cost calculation
        raw_response_obj = getattr(completion, '_raw_response', completion)
        if hasattr(raw_response_obj, 'usage') and raw_response_obj.usage:
            base_usage_info = raw_response_obj.usage.model_dump()
            
            # Extract cached tokens if available
            cached_tokens = 0
            if hasattr(raw_response_obj, 'usage') and hasattr(raw_response_obj.usage, 'prompt_tokens_details'):
                details = raw_response_obj.usage.prompt_tokens_details
                if hasattr(details, 'cached_tokens'):
                    cached_tokens = getattr(details, 'cached_tokens', 0)
            
            # Calculate latency
            latency_seconds = round(end_time - start_time, 3)
            latency_ms = round(latency_seconds * 1000, 1)
            
            # Use TokenCostManager for detailed cost calculation
            token_manager = get_token_cost_manager()
            usage = TokenUsage(
                prompt_tokens=base_usage_info.get("prompt_tokens", 0),
                completion_tokens=base_usage_info.get("completion_tokens", 0),
                total_tokens=base_usage_info.get("total_tokens", 0),
                cached_tokens=cached_tokens,
                model=CAPTION_MODEL_ID,
                provider=CAPTION_MODEL_PROVIDER
            )
            cost_breakdown = token_manager.calculate_cost(usage)
            
            # Create enhanced usage info with cost and latency
            enhanced_usage_info = {
                **base_usage_info,
                "latency_seconds": latency_seconds,
                "latency_ms": latency_ms,
                "model": CAPTION_MODEL_ID,
                "provider": CAPTION_MODEL_PROVIDER,
                "cost_breakdown": {
                    "input_cost": round(cost_breakdown.input_cost, 6),
                    "output_cost": round(cost_breakdown.output_cost, 6),
                    "total_cost": round(cost_breakdown.total_cost, 6),
                    "currency": cost_breakdown.currency,
                    "input_rate": cost_breakdown.input_rate,
                    "output_rate": cost_breakdown.output_rate,
                    "notes": cost_breakdown.notes
                }
            }
            
            ctx.log(f"Caption Analyst: {enhanced_usage_info['total_tokens']} tokens, "
                   f"${enhanced_usage_info['cost_breakdown']['total_cost']:.6f}, "
                   f"{latency_ms}ms")
            
            if "caption_analyst" not in ctx.llm_usage:
                ctx.llm_usage["caption_analyst"] = enhanced_usage_info
        
        return CaptionBrief(**brief_dict)
        
    except ValidationError as ve:
        # Handle specific validation errors (especially missing platform_optimizations)
        ctx.log(f"ERROR: Caption Analyst validation failed: {ve}")
        
        # If instructor failed due to validation, try fallback to manual parsing
        if use_instructor_for_call and base_llm_client_caption:
            ctx.log("Attempting fallback to manual JSON parsing...")
            try:
                # Get raw response using base client
                fallback_args = llm_args.copy()
                if "response_model" in fallback_args:
                    del fallback_args["response_model"]
                
                fallback_completion = base_llm_client_caption.chat.completions.create(**fallback_args)
                raw_content = fallback_completion.choices[0].message.content
                
                ctx.log(f"Raw LLM response for manual parsing: {raw_content[:500]}...")
                
                # Try manual parsing
                brief_dict = _json_parser.extract_and_parse(
                    raw_content,
                    expected_schema=CaptionBrief
                )
                
                # If manual parsing succeeds, return the result
                ctx.log("✅ Fallback manual parsing succeeded")
                return CaptionBrief(**brief_dict)
                
            except Exception as fallback_err:
                ctx.log(f"❌ Fallback manual parsing also failed: {fallback_err}")
        
        return None
        
    except Exception as e:
        ctx.log(f"ERROR: Caption Analyst LLM call failed: {e}")
        ctx.log(traceback.format_exc())
        return None


async def _run_writer(ctx: PipelineContext, brief: CaptionBrief) -> Optional[str]:
    """Runs the Writer LLM to generate the final caption."""
    
    # Use same client configuration as analyst
    use_manual_parsing = should_use_manual_parsing(CAPTION_MODEL_ID)
    client_to_use = base_llm_client_caption if use_manual_parsing else instructor_client_caption
    
    if not client_to_use:
        ctx.log("ERROR: Caption LLM client not available")
        return None
    
    system_prompt = _get_writer_system_prompt(ctx.language)
    user_prompt = _get_writer_user_prompt(brief)
    
    llm_args = {
        "model": CAPTION_MODEL_ID,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 3000,
    }
    
    try:
        ctx.log("Running Writer LLM for final caption")
        
        start_time = time.time()
        completion = client_to_use.chat.completions.create(**llm_args)
        end_time = time.time()
        
        raw_content = completion.choices[0].message.content
        
        # Check for truncated responses and retry if needed
        if hasattr(completion, 'choices') and completion.choices:
            finish_reason = getattr(completion.choices[0], 'finish_reason', None)
            if finish_reason == 'length':
                ctx.log("⚠️ Response truncated, retrying with higher token limit...")
                
                # Retry with higher token limit
                retry_args = llm_args.copy()
                retry_args['max_tokens'] = 3500
                
                try:
                    retry_completion = client_to_use.chat.completions.create(**retry_args)
                    retry_content = retry_completion.choices[0].message.content
                    retry_finish_reason = getattr(retry_completion.choices[0], 'finish_reason', None)
                    
                    if retry_finish_reason != 'length' and retry_content:
                        ctx.log(f"✅ Retry successful, got complete response ({len(retry_content)} chars)")
                        raw_content = retry_content
                        completion = retry_completion  # Update for usage tracking
                    else:
                        ctx.log("⚠️ Retry still truncated, using original response")
                        
                except Exception as retry_error:
                    ctx.log(f"❌ Retry failed: {retry_error}")
                    # Continue with original truncated response
        
        # Use the raw response as the caption (models generate clean captions directly)
        caption_text = raw_content.strip() if raw_content else ""
        
        # Track usage with enhanced cost calculation
        raw_response_obj = getattr(completion, '_raw_response', completion)
        if hasattr(raw_response_obj, 'usage') and raw_response_obj.usage:
            base_usage_info = raw_response_obj.usage.model_dump()
            
            # Extract cached tokens if available
            cached_tokens = 0
            if hasattr(raw_response_obj, 'usage') and hasattr(raw_response_obj.usage, 'prompt_tokens_details'):
                details = raw_response_obj.usage.prompt_tokens_details
                if hasattr(details, 'cached_tokens'):
                    cached_tokens = getattr(details, 'cached_tokens', 0)
            
            # Calculate latency
            latency_seconds = round(end_time - start_time, 3)
            latency_ms = round(latency_seconds * 1000, 1)
            
            # Use TokenCostManager for detailed cost calculation
            token_manager = get_token_cost_manager()
            usage = TokenUsage(
                prompt_tokens=base_usage_info.get("prompt_tokens", 0),
                completion_tokens=base_usage_info.get("completion_tokens", 0),
                total_tokens=base_usage_info.get("total_tokens", 0),
                cached_tokens=cached_tokens,
                model=CAPTION_MODEL_ID,
                provider=CAPTION_MODEL_PROVIDER
            )
            cost_breakdown = token_manager.calculate_cost(usage)
            
            # Create enhanced usage info with cost and latency
            enhanced_usage_info = {
                **base_usage_info,
                "latency_seconds": latency_seconds,
                "latency_ms": latency_ms,
                "model": CAPTION_MODEL_ID,
                "provider": CAPTION_MODEL_PROVIDER,
                "cost_breakdown": {
                    "input_cost": round(cost_breakdown.input_cost, 6),
                    "output_cost": round(cost_breakdown.output_cost, 6),
                    "total_cost": round(cost_breakdown.total_cost, 6),
                    "currency": cost_breakdown.currency,
                    "input_rate": cost_breakdown.input_rate,
                    "output_rate": cost_breakdown.output_rate,
                    "notes": cost_breakdown.notes
                }
            }
            
            ctx.log(f"Caption Writer: {enhanced_usage_info['total_tokens']} tokens, "
                   f"${enhanced_usage_info['cost_breakdown']['total_cost']:.6f}, "
                   f"{latency_ms}ms")
            
            if "caption_writer" not in ctx.llm_usage:
                ctx.llm_usage["caption_writer"] = enhanced_usage_info
        
        return caption_text
        
    except Exception as e:
        ctx.log(f"ERROR: Caption Writer LLM call failed: {e}")
        ctx.log(traceback.format_exc())
        return None


async def run(ctx: PipelineContext) -> None:
    """Main entry point for caption generation stage."""
    ctx.log("Starting caption generation stage")
    
    # Validate required context
    if not ctx.generated_image_prompts:
        ctx.log("ERROR: No generated image prompts available for caption generation")
        return
    
    if not ctx.suggested_marketing_strategies:
        ctx.log("ERROR: No marketing strategies available for caption generation")
        return
    
    # Get user settings from context (will be passed via API call)
    settings_dict = getattr(ctx, 'caption_settings', {})
    settings = CaptionSettings(**settings_dict)
    
    # Get platform info
    platform_name = ctx.target_platform.get("name", "Social Media") if ctx.target_platform else "Social Media"
    
    # Check if we're processing a specific image (API mode) or all images (pipeline mode)
    target_image_index = getattr(ctx, 'target_image_index', None)
    
    if target_image_index is not None:
        # API mode: process only the specific image
        if target_image_index < 0 or target_image_index >= len(ctx.generated_image_prompts):
            ctx.log(f"ERROR: Invalid target image index {target_image_index}. Available: 0-{len(ctx.generated_image_prompts)-1}")
            return
        
        prompts_to_process = [(target_image_index, ctx.generated_image_prompts[target_image_index])]
        ctx.log(f"Processing single image at index {target_image_index}")
    else:
        # Pipeline mode: process all images
        prompts_to_process = list(enumerate(ctx.generated_image_prompts))
        ctx.log(f"Processing all {len(prompts_to_process)} images")
    
    # Process the selected images
    captions_generated = 0
    for i, prompt_data in prompts_to_process:
        strategy_index = prompt_data.get('source_strategy_index', 0)
        strategy = ctx.suggested_marketing_strategies[strategy_index] if strategy_index < len(ctx.suggested_marketing_strategies) else ctx.suggested_marketing_strategies[0]
        
        visual_concept = prompt_data.get('visual_concept', {})
        
        # Safely extract alt text without misleading defaults
        visual_data = _safe_extract_visual_data(visual_concept)
        alt_text = visual_data['suggested_alt_text'] or 'Generated image'
        
        ctx.log(f"Generating caption for image {i+1} (strategy {strategy_index})")
        
        # Validate we have the required data before proceeding
        try:
            strategy_data = _safe_extract_strategy_data(strategy)
            # Remove duplicate call - _extract_main_subject is already called in _get_analyst_user_prompt
            # main_subject = _extract_main_subject(ctx, visual_concept)
            # Just validate strategy data here since main_subject validation happens in _get_analyst_user_prompt
            if not strategy_data.get('target_audience'):
                raise ValueError("Missing required target_audience in marketing strategy")
            if not strategy_data.get('target_objective'):
                raise ValueError("Missing required target_objective in marketing strategy")
            # _validate_required_data(strategy_data, visual_data, main_subject)
        except ValueError as e:
            ctx.log(f"ERROR: Cannot generate caption for image {i+1}: {e}")
            continue
        
        # Check if we should regenerate writer only (for regeneration calls)
        regenerate_writer_only = getattr(ctx, 'regenerate_writer_only', False)
        cached_brief = getattr(ctx, 'cached_caption_brief', None)
        
        # === DETERMINE GENERATION MODE UPFRONT ===
        # Determine generation mode UPFRONT based on original user input
        original_settings = getattr(ctx, 'caption_settings', {})
        user_provided_settings = bool(
            original_settings.get('tone') or 
            original_settings.get('call_to_action') or 
            original_settings.get('hashtag_strategy') or 
            original_settings.get('include_emojis') is False or
            original_settings.get('user_instructions') or
            (original_settings.get('caption_length') and original_settings.get('caption_length') != 'Auto')
        )
        # This ensures the settings object passed to the resolver has the correct mode
        settings.generation_mode = 'Custom' if user_provided_settings else 'Auto'
        # ==========================================

        if regenerate_writer_only and cached_brief:
            ctx.log("Using cached caption brief for regeneration")
            brief = cached_brief
        else:
            # Set current prompt index for style context extraction
            ctx.current_prompt_index = i
            
            # Run Analyst LLM
            brief = None
            try:
                brief = await _run_analyst(ctx, settings, platform_name, strategy, visual_concept, alt_text)
            except Exception as e:
                ctx.log(f"ERROR: Failed to run analyst: {e}")
                continue
            
            if not brief:
                ctx.log(f"Failed to generate caption brief for image {i+1}")
                continue
            
            # Cache the brief for potential regeneration
            ctx.cached_caption_brief = brief
        
        # Run Writer LLM
        caption_text = None
        try:
            caption_text = await _run_writer(ctx, brief)
        except Exception as e:
            ctx.log(f"ERROR: Failed to run writer: {e}")
            continue
        
        if not caption_text:
            ctx.log(f"Failed to generate caption text for image {i+1}")
            continue
        
        # If running in auto-mode, update the settings object with the Analyst's choices for transparency.
        if not settings.tone and brief.tone_of_voice:
            settings.tone = brief.tone_of_voice
        if not settings.call_to_action and brief.primary_call_to_action:
            settings.call_to_action = brief.primary_call_to_action
        # This makes the auto-generated settings visible in the UI and pre-populates them for regeneration.
        
        # Processing mode should already be set by upstream logic (background_tasks.py)
        # If not set, infer from the current model being used
        if not settings.processing_mode:
            model_id = CAPTION_MODEL_ID or 'unknown'
            # Simple inference based on known model characteristics
            if 'gpt-4.1' in model_id.lower():
                settings.processing_mode = 'Fast'
            elif 'gemini-2.5-pro' in model_id.lower():
                settings.processing_mode = 'Analytical'
            else:
                settings.processing_mode = 'Analytical'  # Default to analytical for unknown models
        
        # Create caption result
        caption_result = CaptionResult(
            text=caption_text,
            version=getattr(ctx, 'caption_version', 0),
            settings_used=settings,
            brief_used=brief,
            created_at=datetime.now(timezone.utc).isoformat()
        )
        
        # Store in context
        if not hasattr(ctx, 'generated_captions'):
            ctx.generated_captions = []
        
        ctx.generated_captions.append(caption_result.model_dump())
        captions_generated += 1
        
        ctx.log(f"Successfully generated caption for image {i+1}")
    
    ctx.log(f"Caption generation stage completed. Generated {captions_generated} captions")



