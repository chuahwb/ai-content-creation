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

# Global variables for API clients and configuration (injected by pipeline executor)
instructor_client_caption = None
base_llm_client_caption = None
CAPTION_MODEL_ID = None
CAPTION_MODEL_PROVIDER = None
FORCE_MANUAL_JSON_PARSE = False
INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS = []

# Initialize centralized JSON parser for this stage
_json_parser = RobustJSONParser(debug_mode=False)


def _get_analyst_system_prompt() -> str:
    """Returns the system prompt for the Analyst LLM."""
    # ============================
    # ===== ENHANCEMENT AREA =====
    # ============================
    # The original prompt was good. The enhanced version is more explicit about
    # the 'why' behind the SEO, focusing on creating 'save-worthy' content
    # and providing more detailed, actionable instructions for each platform.
    return """You are a master social media strategist and SEO expert. Your task is to analyze a comprehensive set of marketing and visual data and distill it into a structured JSON "Caption Brief" for a creative copywriter. You do not write the final caption yourself. Your ultimate goal is to create a brief for content so valuable and discoverable that users will **save** it for later.

**Instructions:**
- Carefully analyze all the provided CONTEXT_DATA.
- **Language Consistency:** Generate ALL fields in the `CaptionBrief` JSON object (including `core_message`, `key_themes_to_include`, `seo_keywords`, `target_emotion`, `primary_call_to_action`, and `hashtags`) in English as the primary language. However, preserve authentic cultural or aesthetic terms (e.g., "Japandi", "wabi-sabi", "matcha") when they add value and authenticity to the content. Only switch to a non-English primary language if the user's input data (marketing goals, task description, or explicit instructions) clearly indicates a different target language.
- Follow the USER_SETTINGS if they are provided. If a user setting conflicts with the context data (e.g., user-selected tone vs. target_voice), the user's choice MUST be prioritized.
- If a setting is not provided by the user, you must infer the optimal choice from the context data as per the AUTO_MODE_LOGIC.
- Generate a single, valid JSON object based on the CaptionBrief schema.
- The entire output must be only the JSON object, with no other text or explanation.
- ALL fields in the JSON schema are REQUIRED and must be included.

**Auto Mode Logic:**
- Auto-Tone Selection: Infer optimal tone by synthesizing target_voice from marketing strategy and lighting_and_mood from visual concept.
- Auto-CTA Generation: Generate context-aware CTA based on target_objective.
- Auto-Emoji Usage: Enable by default, use sparingly and match the selected tone.
- Auto-Hashtag Strategy: Default to "Balanced Mix" - extract keywords from style and subject for niche hashtags, supplement with 1-2 broader terms.

**Platform Optimizations (Enhanced for SEO):**
- **Instagram:** Structure as "Hook + Value + CTA". The `seo_keywords` are critical for the image's Alt Text. Encourage engagement with questions to earn comments and saves.
- **Facebook:** Focus on value-driven, longer-form content that sparks meaningful conversation and shares. Ensure the structure is friendly to outbound links if applicable.
- **Pinterest:** Treat this as a visual search engine. The caption must be a mini-blog post: a compelling, keyword-rich Title followed by a detailed, helpful description that makes it a top search result.
- **Xiaohongshu:** The caption title MUST be a hook-y, attention-grabbing long-tail keyword phrase (标题党 style). The body should be a helpful, authentic note, using emojis to enhance readability. The goal is to provide immense value to encourage saves (收藏) and comments.

**Required JSON Output Format:**
{
  "core_message": "A concise, one-sentence summary of the main message.",
  "key_themes_to_include": ["Array of 3-5 key themes or concepts"],
  "seo_keywords": ["Array of 3-5 important SEO keywords"],
  "target_emotion": "Primary emotion to evoke (e.g., 'Aspirational', 'Trustworthy')",
  "platform_optimizations": {
    "[PLATFORM_NAME]": {
      "caption_structure": "Brief instruction on structure for this platform",
      "style_notes": "Platform-specific style guidance"
    }
  },
  "primary_call_to_action": "The final call to action string",
  "hashtags": ["Array of hashtag strings with # symbol"],
  "emoji_suggestions": ["Array of 2-3 relevant emoji characters"]
}

**CRITICAL:** The platform_optimizations object must contain exactly one key matching the target platform name provided in the context."""


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
    alt_text: str
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
    
    prompt_parts = [
        f"**Target Platform:** {platform_name}",
        "",
        "**Marketing Strategy:**",
        f"- Target Audience: {strategy_data['target_audience']}",
        f"- Target Objective: {strategy_data['target_objective']}",
    ]
    
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
    
    prompt_parts.append("")
    prompt_parts.append("**User Settings:**")
    
    # Handle user settings vs auto mode
    if settings.tone:
        prompt_parts.append(f"- Caption Tone: {settings.tone} (USER OVERRIDE)")
    else:
        if strategy_data['target_voice'] and visual_data['lighting_mood']:
            prompt_parts.append(f"- Caption Tone: Auto mode - infer from target_voice ('{strategy_data['target_voice']}') and lighting_mood ('{visual_data['lighting_mood']}')")
        elif strategy_data['target_voice']:
            prompt_parts.append(f"- Caption Tone: Auto mode - infer from target_voice ('{strategy_data['target_voice']}')")
        else:
            prompt_parts.append("- Caption Tone: Auto mode - use friendly and engaging tone")
    
    if settings.call_to_action:
        prompt_parts.append(f"- Call to Action: {settings.call_to_action} (USER OVERRIDE)")
    else:
        prompt_parts.append(f"- Call to Action: Auto mode - generate based on target_objective ('{strategy_data['target_objective']}')")
    
    if settings.include_emojis is not None:
        emoji_status = "enabled" if settings.include_emojis else "disabled"
        prompt_parts.append(f"- Emojis: {emoji_status} (USER OVERRIDE)")
    else:
        prompt_parts.append("- Emojis: Auto mode - enabled by default, use appropriately")
    
    if settings.hashtag_strategy:
        prompt_parts.append(f"- Hashtag Strategy: {settings.hashtag_strategy} (USER OVERRIDE)")
    else:
        prompt_parts.append("- Hashtag Strategy: Auto mode - Balanced Mix")
    
    prompt_parts.extend([
        "",
        "**Important:** This content should be generated primarily in English. Preserve authentic cultural/aesthetic terms (like 'Japandi', 'matcha', 'wabi-sabi') that add authenticity, but ensure the primary language is English unless the user has explicitly requested a different target language.",
        "",
        "Based on this context, generate a CaptionBrief JSON object that will guide the caption writer.",
        "Focus on strategic analysis and provide clear, actionable guidance for the creative execution."
    ])
    
    return "\n".join(prompt_parts)


def _get_writer_system_prompt() -> str:
    """Returns the system prompt for the Writer LLM."""
    # ============================
    # ===== ENHANCEMENT AREA =====
    # ============================
    # The original prompt was good, but this version adds a **CRITICAL** instruction
    # to ensure the Writer LLM does not deviate from the Analyst's strategic
    # platform-specific structure. It makes the guidance non-negotiable.
    return """You are an expert social media copywriter with a flair for creative, authentic, and engaging storytelling. Your brand voice is natural and human-like.

**Instructions:**
- Your task is to write a compelling social media caption based on the provided Caption Brief.
- **Language Adherence:** Write your final caption primarily in English, but preserve authentic cultural, aesthetic, or brand terms from the brief that add authenticity and value (e.g., "Japandi", "matcha", "wabi-sabi", brand names). Only write in a non-English language if the `CaptionBrief` explicitly indicates the target audience expects content in that language.
- Read the entire brief carefully to understand the strategic goals.
- **CRITICAL:** You MUST strictly adhere to the `caption_structure` and `style_notes` provided in the `platform_optimizations` section of the brief. This structure is non-negotiable and is the key to the caption's success on that specific platform.
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
    
    return f"""Write a social media caption based on this strategic brief:

**Core Message:** {brief.core_message}

**Key Themes to Include:** {', '.join(brief.key_themes_to_include)}

**SEO Keywords:** {', '.join(brief.seo_keywords)}

**Target Emotion:** {brief.target_emotion}

**Platform Optimizations:** {json.dumps(brief.platform_optimizations, indent=2)}

**Call to Action:** {brief.primary_call_to_action}

{hashtag_instruction}

{emoji_instruction}

Create an engaging, authentic caption that incorporates these elements naturally."""


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
    
    system_prompt = _get_analyst_system_prompt()
    user_prompt = _get_analyst_user_prompt(ctx, settings, platform_name, strategy, visual_concept, alt_text)
    
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
        
        completion = client_to_use.chat.completions.create(**llm_args)
        
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
        
        # Track usage
        raw_response_obj = getattr(completion, '_raw_response', completion)
        if hasattr(raw_response_obj, 'usage') and raw_response_obj.usage:
            usage_info = raw_response_obj.usage.model_dump()
            ctx.log(f"Token Usage (Caption Analyst): {usage_info}")
            if "caption_analyst" not in ctx.llm_usage:
                ctx.llm_usage["caption_analyst"] = usage_info
        
        return CaptionBrief(**brief_dict)
        
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
    
    system_prompt = _get_writer_system_prompt()
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
        
        completion = client_to_use.chat.completions.create(**llm_args)
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
        
        # Track usage
        raw_response_obj = getattr(completion, '_raw_response', completion)
        if hasattr(raw_response_obj, 'usage') and raw_response_obj.usage:
            usage_info = raw_response_obj.usage.model_dump()
            ctx.log(f"Token Usage (Caption Writer): {usage_info}")
            if "caption_writer" not in ctx.llm_usage:
                ctx.llm_usage["caption_writer"] = usage_info
        
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
            main_subject = _extract_main_subject(ctx, visual_concept)
            _validate_required_data(strategy_data, visual_data, main_subject)
        except ValueError as e:
            ctx.log(f"ERROR: Cannot generate caption for image {i+1}: {e}")
            continue
        
        # Check if we should regenerate writer only (for regeneration calls)
        regenerate_writer_only = getattr(ctx, 'regenerate_writer_only', False)
        cached_brief = getattr(ctx, 'cached_caption_brief', None)
        
        if regenerate_writer_only and cached_brief:
            ctx.log("Using cached caption brief for regeneration")
            brief = cached_brief
        else:
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



