#!/usr/bin/env python
"""Caption Model Benchmark Script - Enhanced with Task Type Optimization

Runs the Analyst → Writer two-step caption pipeline against a hard-coded
input for every model in the INTERNAL_MATRIX below, then writes results to
``caption_benchmark_results.json`` in the script directory.

This script is **self-contained** – it copies the core logic & prompts from
``churns/stages/caption.py`` (Dec 2024 enhanced version) so it can run outside the
full Churns code-base.  Only the ``openai`` package (>=1.3.5) and
``pydantic`` (>=2) are required.

**ENHANCEMENTS INCLUDED:**
- Task Type Caption Optimization (8 task types with guidance)
- Style Context Integration (style keywords, creative reasoning)
- Enhanced Prompts with conflict-avoidance logic
- task_type_notes field in CaptionBrief schema

Usage
-----
$ python scripts/benchmark_caption_models.py  # results saved to JSON

**Note:** Fill in the EVAL_DATA placeholders with your test data before running.
"""
from __future__ import annotations

print("🚀 Starting Caption Model Benchmark Script...")
print("📦 Loading dependencies...")

import asyncio
import json
import os
import time
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List

print("✅ Basic imports loaded")

try:
    from pydantic import BaseModel, Field, ValidationError
    print("✅ Pydantic loaded")
except ImportError as e:
    print(f"❌ Failed to import pydantic: {e}")
    exit(1)

try:
    # Use the same import pattern as the main app
    from openai import OpenAI, APIConnectionError, RateLimitError, APIStatusError
    print("✅ OpenAI SDK loaded")
    
    # Force import of OpenAI resources to avoid lazy loading during first API call
    print("🔄 Pre-loading OpenAI resources...")
    try:
        # Create a dummy client to force all imports
        dummy_client = OpenAI(api_key="dummy", base_url="https://api.openai.com/v1")
        # Access the chat property to trigger lazy imports
        _ = dummy_client.chat
        print("✅ OpenAI resources pre-loaded")
    except Exception as e:
        print(f"⚠️ Pre-loading warning (expected): {e}")
        print("✅ OpenAI resources will load on first use")
        
except ImportError as e:
    print(f"❌ Failed to import openai: {e}")
    print("💡 Install with: pip install openai>=1.3.5")
    exit(1)

#######################################################################
# 0 ── CONFIGURATION ###################################################
#######################################################################

print("🔧 Loading configuration...")

#######################################################################
# 0.1 ── Pydantic helpers (mirrors churns.models) #####################
#######################################################################
class CaptionSettings(BaseModel):
    """User settings for caption generation - matches churns/api/schemas.py exactly"""
    tone: str | None = Field(None, description="Caption tone (e.g., 'Professional & Polished', 'Friendly & Casual')")
    call_to_action: str | None = Field(None, description="User-defined call to action text")
    include_emojis: bool | None = Field(True, description="Whether to include emojis in the caption")
    hashtag_strategy: str | None = Field(None, description="Hashtag strategy ('None', 'Niche & Specific', 'Broad & Trending', 'Balanced Mix')")


class CaptionBrief(BaseModel):
    core_message: str
    key_themes_to_include: List[str]
    seo_keywords: List[str]
    target_emotion: str
    platform_optimizations: Dict[str, Any]
    primary_call_to_action: str
    hashtags: List[str]
    emoji_suggestions: List[str]
    task_type_notes: str | None = Field(None, description="Optional task-type specific guidance notes for the writer.")

# 0.2  Target models to evaluate – all using OpenRouter
INTERNAL_MATRIX: List[Dict[str, str]] = [
    {"provider": "OpenRouter", "model_id": "openai/gpt-4.1"},
    {"provider": "OpenRouter", "model_id": "openai/gpt-4.1-mini"},
    {"provider": "OpenRouter", "model_id": "openai/o4-mini"},
    {"provider": "OpenRouter", "model_id": "x-ai/grok-3-mini"},
    {"provider": "OpenRouter", "model_id": "x-ai/grok-3"},
    {"provider": "OpenRouter", "model_id": "google/gemini-2.5-pro"},
    {"provider": "OpenRouter", "model_id": "google/gemini-2.5-flash"},
    {"provider": "OpenRouter", "model_id": "google/gemini-2.5-flash-preview-05-20"},
    {"provider": "OpenRouter", "model_id": "qwen/qwen3-30b-a3b"},
]

print(f"📊 Configured {len(INTERNAL_MATRIX)} models for testing")

# 0.2.1 Models that support reasoning effort parameter
REASONING_EFFORT_MODELS = [
    "x-ai/grok-3-mini",
    "google/gemini-2.5-flash"
]

# 0.2.2 Benchmark configuration
MAX_RETRIES = 3
RESUME_FROM_CHECKPOINT = True  # Set to False to start fresh
RETRY_FAILED_ONLY = True  # Set to True to only retry previously failed models

# Task Type Caption Guidance Mapping (copied from caption.py)
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


def _get_task_type_guidance(task_type: str) -> Dict[str, Any] | None:
    """
    Safely retrieve task type guidance for caption generation.
    
    Args:
        task_type: The task type string from pipeline context
        
    Returns:
        Task type guidance dict or None if not found
    """
    return TASK_TYPE_CAPTION_GUIDANCE.get(task_type)


def _extract_style_context(style_guidance_sets: List[Dict[str, Any]] | None, 
                          generated_image_prompts: List[Dict[str, Any]] | None,
                          suggested_marketing_strategies: List[Dict[str, Any]] | None,
                          prompt_index: int = 0) -> Dict[str, Any]:
    """
    Extract critical style context signals from pipeline data.
    
    Args:
        style_guidance_sets: Style guidance sets from pipeline
        generated_image_prompts: Generated image prompts from pipeline
        suggested_marketing_strategies: Marketing strategies from pipeline
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
    if style_guidance_sets and prompt_index < len(style_guidance_sets):
        style_guidance = style_guidance_sets[prompt_index]
        style_context["style_keywords"] = style_guidance.get("style_keywords", [])
    
    # Extract creative reasoning from visual concept
    if generated_image_prompts and prompt_index < len(generated_image_prompts):
        visual_concept = generated_image_prompts[prompt_index].get("visual_concept", {})
        style_context["creative_reasoning"] = visual_concept.get("creative_reasoning")
    
    # Extract target niche from corresponding strategy
    if suggested_marketing_strategies:
        strategy_index = 0
        if generated_image_prompts and prompt_index < len(generated_image_prompts):
            strategy_index = generated_image_prompts[prompt_index].get("source_strategy_index", 0)
        
        if strategy_index < len(suggested_marketing_strategies):
            strategy = suggested_marketing_strategies[strategy_index]
            style_context["target_niche"] = strategy.get("target_niche")
    
    return style_context


# 0.3  Hard-coded evaluation input (PLACEHOLDER - fill in manually).
EVAL_DATA: Dict[str, Any] = {
    # PLACEHOLDER - Fill in your test data manually
    "task_type": "7. Brand Story & Milestones",  # e.g., "6. Recipes & Food Tips" or None
    "enable_task_type_caption_optimization": True,  # Feature flag
    "strategy": {
        # Fill in your marketing strategy data
        "target_audience": "Health-focused individuals seeking natural, nutritious, and dairy-free beverage options",
        "target_niche": "Artisanal Dairy Alternatives",
        "target_objective": "Highlight the health benefits, natural ingredients, and unique story of the handcrafted soy milk to increase engagement and brand trust",
        "target_voice": "Informative, warm, and approachable with an emphasis on wellness and quality"
    },
    "visual_concept": {
        # Fill in your visual concept data
        "main_subject": "Bottle of handcrafted soy milk with a black and white label",
        "composition_and_framing": "A cinematic, eye-level, perfectly centered 1:1 square composition. The product (the soy milk bottle) stands as the undisputed hero in the middle of the frame, creating a sense of importance and celebration. The framing is intimate yet grand, with ethereal elements subtly wrapping around the edges of the frame, drawing the viewer's eye inward to the central subject and the promotional text.",
          "background_environment": "A dreamlike, non-descript environment composed of an out-of-focus, soft-textured gradient. The gradient transitions seamlessly from a warm, creamy peach at the bottom to a soft, dusty lavender at the top, evoking the gentle light of dawn or dusk. The background is filled with soft, circular bokeh effects that shimmer and subtly shift in color, enhancing the magical and serene atmosphere without distracting from the main subject.",
          "foreground_elements": "Delicate, impressionistic soybean plants and leaves appear to grow into the frame from the bottom left and right corners. They are rendered in a soft-focus, painterly style, glowing with a faint internal luminescence. Floating, ethereal motes of light, like dust caught in a sunbeam or magical pollen, drift slowly through the air, catching the prismatic light and adding a layer of dynamic, gentle movement to the scene.",
          "lighting_and_mood": "The lighting is the key narrative element, creating a serene, magical, and celebratory mood. The soy milk bottle itself is the primary light source, emitting a soft, warm, luminous aura that envelops it. This central glow casts painterly, prismatic light rays that refract through the air and across the foreground botanicals, creating soft, rainbow-like caustics and lens flares. The overall lighting is cinematic and warm, reminiscent of golden hour, but elevated with an ethereal, spiritual quality.",
          "color_palette": "A sophisticated and warm pastel palette designed to feel nurturing and pure. The dominant colors are soft peach, creamy vanilla-white, dusty rose, and a gentle touch of muted lavender. These are accented by the warm, golden-white of the central light source and the subtle, prismatic flashes of soft cyan, magenta, and yellow within the light refractions.",
          "visual_style": "An ethereal and luminous visual style inspired by early 20th-century spirit photography and impressionistic painting. The core of the style is the 'luminous aura,' where the product glows from within, symbolizing vitality and purity. Light is treated as a tangible, painterly substance, with soft-focus refractions and prismatic beams that create a dreamlike, cinematic warmth. Botanical elements are not photorealistic but are instead impressionistic\u2014defined by blended color and light rather than sharp lines. The entire scene is bathed in a soft-focus haze, with a subtle, velvety texture throughout, creating a visual that feels both nostalgic and timelessly pure.",
          "promotional_text_visuals": "The tagline 'Our Story, Bottled.' is elegantly rendered in the upper third of the image, centered horizontally. The font is a classic, warm serif with delicate ligatures, presented in a soft, dark charcoal grey\u2014not pure black\u2014to blend harmoniously with the warm pastel palette. The text itself has a very subtle outer glow, making it appear as if it's catching the ethereal light of the scene, ensuring it feels integrated rather than overlaid.",
          "branding_visuals": None,
          "texture_and_details": "The visual features a rich interplay of soft textures. The background has a smooth, velvety gradient texture. The botanical elements have a painterly, canvas-like texture with visible but soft brushstroke effects. The light itself has texture, appearing as soft, glowing particles and volumetric rays. The glass of the bottle has a smooth, clean surface that contrasts with the softer textures surrounding it.",
          "negative_elements": "Avoid any harsh shadows, sharp edges, or photorealistic clarity. Exclude any modern, urban, or distracting background elements. Do not use overly saturated or neon colors. The text should not be bold or use sans-serif fonts. The overall feeling should be magical and pure, not clinical or commercial.",
          "creative_reasoning": "This concept directly addresses the 'Brand Story & Milestones' task by creating a celebratory and narrative visual. The luminous, ethereal style, derived from the Style Guidance, elevates the soy milk, positioning it as a culmination of a pure, natural journey\u2014perfect for the 'artisanal' niche and 'brand trust' objective. The impressionistic botanicals visually communicate the 'natural ingredients' story, while the warm, serene mood and 'Our Story, Bottled.' tagline evoke a sense of heritage and care. By making the bottle the glowing focal point, we celebrate it as a milestone. The entire aesthetic is designed to be thumb-stopping on Instagram for a health-focused audience seeking beauty and wellness.",
          "suggested_alt_text": "A bottle of handcrafted soy milk glows with a warm, luminous aura, surrounded by impressionistic, softly lit soybean plants."
    },
    "style_guidance_sets": [
        # Fill in your style guidance data (optional)
        {
            "style_keywords": [
                "luminous aura",
                "prismatic light",
                "impressionistic botanicals",
                "pastel gradients",
                "cinematic warmth"
                ]
        }
    ],
    "generated_image_prompts": [
        # Fill in your image prompt data (optional)
        {
            "visual_concept": {
                "creative_reasoning": "This concept directly addresses the 'Brand Story & Milestones' task by creating a celebratory and narrative visual. The luminous, ethereal style, derived from the Style Guidance, elevates the soy milk, positioning it as a culmination of a pure, natural journey\u2014perfect for the 'artisanal' niche and 'brand trust' objective. The impressionistic botanicals visually communicate the 'natural ingredients' story, while the warm, serene mood and 'Our Story, Bottled.' tagline evoke a sense of heritage and care. By making the bottle the glowing focal point, we celebrate it as a milestone. The entire aesthetic is designed to be thumb-stopping on Instagram for a health-focused audience seeking beauty and wellness."
            },
            "source_strategy_index": 1
        }
    ],
    "suggested_marketing_strategies": [
        # Fill in your marketing strategies (optional)
        {
            "target_niche": "Artisanal Dairy Alternatives"
        }
    ],
    "platform_name": "Xiaohongshu",  # e.g., "Instagram Post (1:1 Square)", "Xiaohongshu"
    # Caption settings - configure these to test different scenarios
    "settings": CaptionSettings(
        tone=None,  # Options: None (auto), "Professional & Polished", "Friendly & Casual", "Inspirational & Motivating", "Edgy & Bold"
        call_to_action=None,  # None (auto) or custom CTA text
        include_emojis=True,  # True, False, or None (auto - defaults to True)
        hashtag_strategy=None  # Options: None (auto), "None", "Niche & Specific", "Broad & Trending", "Balanced Mix"
    ),
}

# Alternative test configurations - uncomment to test different scenarios:
# 
# # Test 1: Professional tone with no emojis
# "settings": CaptionSettings(
#     tone="Professional & Polished",
#     call_to_action=None,
#     include_emojis=False,
#     hashtag_strategy="Niche & Specific"
# ),
#
# # Test 2: Casual tone with custom CTA
# "settings": CaptionSettings(
#     tone="Friendly & Casual", 
#     call_to_action="Shop our latest collection now!",
#     include_emojis=True,
#     hashtag_strategy="Balanced Mix"
# ),
#
# # Test 3: No hashtags, inspirational tone
# "settings": CaptionSettings(
#     tone="Inspirational & Motivating",
#     call_to_action=None,
#     include_emojis=True,
#     hashtag_strategy="None"
# ),

# 0.5  Output files and checkpoint functionality
RESULT_PATH = os.path.join(os.path.dirname(__file__), "caption_benchmark_results.json")
CHECKPOINT_PATH = os.path.join(os.path.dirname(__file__), "caption_benchmark_checkpoint.json")

def load_checkpoint() -> List[Dict[str, Any]]:
    """Load previous results from checkpoint file or results file."""
    # First try to load from checkpoint
    if RESUME_FROM_CHECKPOINT and os.path.exists(CHECKPOINT_PATH):
        try:
            with open(CHECKPOINT_PATH, "r") as f:
                checkpoint_data = json.load(f)
                print(f"📂 Loaded checkpoint with {len(checkpoint_data)} previous results")
                return checkpoint_data
        except Exception as e:
            print(f"⚠️ Failed to load checkpoint: {e}")
    
    # If in retry-failed-only mode and no checkpoint, try to load from results file
    if RETRY_FAILED_ONLY and os.path.exists(RESULT_PATH):
        try:
            with open(RESULT_PATH, "r") as f:
                results_data = json.load(f)
                print(f"📂 Loaded previous results from {RESULT_PATH} with {len(results_data)} entries")
                return results_data
        except Exception as e:
            print(f"⚠️ Failed to load results file: {e}")
    
    return []

def save_checkpoint(results: List[Dict[str, Any]]) -> None:
    """Save current results to checkpoint file."""
    try:
        with open(CHECKPOINT_PATH, "w") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️ Failed to save checkpoint: {e}")

def get_completed_models(results: List[Dict[str, Any]]) -> set:
    """Get set of model IDs that have already been completed successfully."""
    return {r["model_id"] for r in results if r.get("success", False)}

def get_failed_models(results: List[Dict[str, Any]]) -> set:
    """Get set of model IDs that have failed and need retry."""
    return {r["model_id"] for r in results if not r.get("success", False)}

def remove_failed_results(results: List[Dict[str, Any]], failed_models: set) -> List[Dict[str, Any]]:
    """Remove failed results from the list so they can be replaced with new attempts."""
    return [r for r in results if r["model_id"] not in failed_models]

# 0.4  Environment validation
print("🔑 Checking environment...")
OPENROUTER_API_KEY = "REDACTED_API_KEY"
if not OPENROUTER_API_KEY:
    print("❌ OPENROUTER_API_KEY environment variable is required")
    print("💡 Set it with: export OPENROUTER_API_KEY='your_key_here'")
    exit(1)
else:
    print(f"✅ OpenRouter API key found (length: {len(OPENROUTER_API_KEY)})")

print("✅ Configuration loaded successfully")

#######################################################################
# 1 ── Utility extraction helpers (copied from caption.py) #############
#######################################################################

def _safe_extract_strategy_data(strategy: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "target_audience": strategy.get("target_audience"),
        "target_objective": strategy.get("target_objective"),
        "target_voice": strategy.get("target_voice"),
        "target_niche": strategy.get("target_niche"),
    }


def _safe_extract_visual_data(visual_concept: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "lighting_mood": visual_concept.get("lighting_and_mood"),
        "visual_style": visual_concept.get("visual_style"),
        "promotional_text": visual_concept.get("promotional_text_visuals"),
        "suggested_alt_text": visual_concept.get("suggested_alt_text"),
    }


def _extract_main_subject(visual_concept: Dict[str, Any]) -> str:
    main_subject = visual_concept.get("main_subject")
    if main_subject and main_subject.lower() not in {"null", "none", ""}:
        return main_subject
    raise ValueError("No valid main subject found in visual concept")


def _validate_required_data(strategy_data: Dict[str, Any], visual_data: Dict[str, Any], main_subject: str) -> None:
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
    if not strategy_data.get("target_audience"):
        raise ValueError("Missing required target_audience in marketing strategy")
    
    if not strategy_data.get("target_objective"):
        raise ValueError("Missing required target_objective in marketing strategy")
    
    # Main subject is already validated by _extract_main_subject
    if not main_subject:
        raise ValueError("Main subject is required for caption generation")


#######################################################################
# 2 ── Prompt builders (verbatim from caption.py) ######################
#######################################################################

def _get_analyst_system_prompt() -> str:
    """Exact copy of analyst system prompt from churns/stages/caption.py (Dec 2024)."""
    return (
        "You are a master social media strategist and SEO expert. Your task is to analyze a comprehensive set of marketing and visual data and distill it into a structured JSON \"Caption Brief\" for a creative copywriter. You do not write the final caption yourself. Your ultimate goal is to create a brief for content so valuable and discoverable that users will **save** it for later.\n\n"
        "**Instructions:**\n"
        "- Carefully analyze all the provided CONTEXT_DATA.\n"
        "- **Language Consistency:** Generate ALL fields in the `CaptionBrief` JSON object (including `core_message`, `key_themes_to_include`, `seo_keywords`, `target_emotion`, `primary_call_to_action`, and `hashtags`) in English as the primary language. However, preserve authentic cultural or aesthetic terms (e.g., \"Japandi\", \"wabi-sabi\", \"matcha\") when they add value and authenticity to the content. Only switch to a non-English primary language if the user's input data clearly indicates a different target language.\n"
        "- Follow the USER_SETTINGS if they are provided. If a user setting conflicts with the context data (e.g., user-selected tone vs. target_voice), the user's choice MUST be prioritized.\n"
        "- If a setting is not provided by the user, you must infer the optimal choice from the context data as per the AUTO_MODE_LOGIC.\n"
        "- Generate a single, valid JSON object based on the CaptionBrief schema.\n"
        "- The entire output must be only the JSON object, with no other text or explanation.\n"
        "- ALL fields in the JSON schema are REQUIRED and must be included.\n\n"
        "**Auto Mode Logic:**\n"
        "- Auto-Tone Selection: Infer optimal tone by synthesizing target_voice from marketing strategy and lighting_and_mood from visual concept.\n"
        "- Auto-CTA Generation: Generate context-aware CTA based on target_objective.\n"
        "- Auto-Emoji Usage: Enable by default, use sparingly and match the selected tone.\n"
        "- Auto-Hashtag Strategy: Default to \"Balanced Mix\" - extract keywords from style and subject for niche hashtags, supplement with 1-2 broader terms.\n\n"
        "**Platform Optimizations (Enhanced for SEO):**\n"
        "- **Instagram:** Structure as \"Hook + Value + CTA\". The `seo_keywords` are critical for the image's Alt Text. Encourage engagement with questions to earn comments and saves.\n"
        "- **Facebook:** Focus on value-driven, longer-form content that sparks meaningful conversation and shares.\n"
        "- **Pinterest:** Treat this as a visual search engine. The caption must be a mini-blog post: a compelling, keyword-rich Title followed by a detailed, helpful description that makes it a top search result.\n"
        "- **Xiaohongshu:** The caption title MUST be a hook-y, attention-grabbing long-tail keyword phrase (标题党 style). The body should be a helpful, authentic note, using emojis to enhance readability. The goal is to provide immense value to encourage saves (收藏) and comments.\n\n"
        "**Required JSON Output Format:**\n"
        "{\n  \"core_message\": \"A concise, one-sentence summary of the main message.\",\n  \"key_themes_to_include\": [\"Array of 3-5 key themes or concepts\"],\n  \"seo_keywords\": [\"Array of 3-5 important SEO keywords\"],\n  \"target_emotion\": \"Primary emotion to evoke (e.g., 'Aspirational', 'Trustworthy')\",\n  \"platform_optimizations\": {\n    \"[PLATFORM_NAME]\": {\n      \"caption_structure\": \"Brief instruction on structure for this platform\",\n      \"style_notes\": \"Platform-specific style guidance\"\n    }\n  },\n  \"primary_call_to_action\": \"The final call to action string\",\n  \"hashtags\": [\"Array of hashtag strings with # symbol\"],\n  \"emoji_suggestions\": [\"Array of 2-3 relevant emoji characters\"],\n  \"task_type_notes\": \"Optional concise note about task-type optimization (e.g., 'Optimize for Product Photography: showcase features & craftsmanship'). Set to null if no task type guidance was provided.\"\n}\n\n"
        "**CRITICAL:** The platform_optimizations object must contain exactly one key matching the target platform name provided in the context."
    )


def _get_writer_system_prompt() -> str:
    """Exact copy of writer system prompt from churns/stages/caption.py (Dec 2024)."""
    return (
        "You are an expert social media copywriter with a flair for creative, authentic, and engaging storytelling. Your brand voice is natural and human-like.\n\n"
        "**Instructions:**\n"
        "- Your task is to write a compelling social media caption based on the provided Caption Brief.\n"
        "- **Language Adherence:** Write your final caption primarily in English, but preserve authentic cultural, aesthetic, or brand terms from the brief that add authenticity and value (e.g., 'Japandi', 'matcha', 'wabi-sabi', brand names). Only write in a non-English language if the `CaptionBrief` explicitly indicates the target audience expects content in that language.\n"
        "- Read the entire brief carefully to understand the strategic goals.\n"
        "- **CRITICAL:** You MUST strictly adhere to the `caption_structure` and `style_notes` provided in the `platform_optimizations` section of the brief. This structure is non-negotiable and is the key to the caption's success on that specific platform.\n"
        "- Write a caption that feels authentic and human, not like it was written by an AI.\n"
        "- Seamlessly integrate the `seo_keywords` into the text without making it sound forced.\n"
        "- End with the `primary_call_to_action` and the provided `hashtags`.\n"
        "- Your output should be ONLY the final caption text. Do not include the brief or any other commentary.\n\n"
        "**Style Guidelines:**\n"
        "- Use natural, conversational language.\n"
        "- Vary sentence lengths for readability.\n"
        "- Include line breaks where appropriate for platform readability.\n"
        "- **CRITICAL:** Strictly follow the emoji usage instructions provided. If told not to use emojis, do NOT include any emojis whatsoever.\n"
        "- **CRITICAL:** Strictly follow the hashtag usage instructions provided. If told not to use hashtags, do NOT include any hashtags whatsoever.\n"
        "- When hashtags are provided, make them feel organic and naturally integrated at the end of the caption."
    )


def _get_analyst_user_prompt(
    settings: CaptionSettings,
    platform_name: str,
    strategy: Dict[str, Any],
    visual_concept: Dict[str, Any],
    alt_text: str,
    task_type: str | None = None,
    enable_task_type_optimization: bool = True,
    style_guidance_sets: List[Dict[str, Any]] | None = None,
    generated_image_prompts: List[Dict[str, Any]] | None = None,
    suggested_marketing_strategies: List[Dict[str, Any]] | None = None,
    prompt_index: int = 0
) -> str:
    """Constructs the user prompt for the Analyst LLM (enhanced with task type optimization)."""
    
    # Safely extract data without misleading defaults
    strategy_data = _safe_extract_strategy_data(strategy)
    visual_data = _safe_extract_visual_data(visual_concept)
    
    # Extract main subject with fallback to image analysis
    main_subject = _extract_main_subject(visual_concept)
    
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
        prompt_parts.append(f"- Alt Text (for SEO context): {alt_text}")
    if visual_data['promotional_text']:
        prompt_parts.append(f"- Text on Image: {visual_data['promotional_text']}")
    
    # Add Task Type Context if available and feature enabled
    if enable_task_type_optimization and task_type:
        task_guidance = _get_task_type_guidance(task_type)
        task_type = task_type.split('.', 1)[-1].strip() if '.' in task_type else task_type
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
    style_context = _extract_style_context(style_guidance_sets, generated_image_prompts, suggested_marketing_strategies, prompt_index)
    if style_context['style_keywords'] or style_context['creative_reasoning']:
        prompt_parts.extend([
            "",
            "**Style Context:**"
        ])
        
        if style_context['style_keywords']:
            prompt_parts.append(f"The accompanying image was designed with these style cues: {', '.join(style_context['style_keywords'])}. Channel this aesthetic subtly in the copy.")
        
        if style_context['creative_reasoning']:
            prompt_parts.append(f"The creative reasoning emphasizes: \"{style_context['creative_reasoning']}\"")
    
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


def _get_writer_user_prompt(brief: CaptionBrief) -> str:
    """Constructs the user prompt for the Writer LLM (enhanced with task type support)."""
    
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
        f"**Core Message:** {brief.core_message}"
    ]
    
    # Add task type notes if available
    if getattr(brief, 'task_type_notes', None):
        prompt_parts.append(f"**Task Note:** {brief.task_type_notes}")
    
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


#######################################################################
# 3 ── LLM Client Setup & Execution ####################################
#######################################################################

def _setup_openrouter_client() -> OpenAI:
    """Setup OpenRouter client with API key from environment."""
    print("🔌 Setting up OpenRouter client...")
    
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )


async def _run_analyst_llm(
    client: OpenAI,
    model_id: str,
    settings: CaptionSettings,
    platform_name: str,
    strategy: Dict[str, Any],
    visual_concept: Dict[str, Any],
    alt_text: str,
    task_type: str | None = None,
    enable_task_type_optimization: bool = True,
    style_guidance_sets: List[Dict[str, Any]] | None = None,
    generated_image_prompts: List[Dict[str, Any]] | None = None,
    suggested_marketing_strategies: List[Dict[str, Any]] | None = None,
    retry_count: int = 0
) -> tuple[CaptionBrief | None, Dict[str, Any], float]:
    """Run the Analyst LLM and return brief, usage info, and latency."""
    
    system_prompt = _get_analyst_system_prompt()
    user_prompt = _get_analyst_user_prompt(
        settings, platform_name, strategy, visual_concept, alt_text,
        task_type, enable_task_type_optimization, style_guidance_sets,
        generated_image_prompts, suggested_marketing_strategies
    )
    
    llm_args = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 3000,
        "timeout": 120,  # 2 minute timeout
    }
    
    # Add model-specific parameters
    if model_id in REASONING_EFFORT_MODELS:
        llm_args["extra_body"] = {
            "reasoning": {
                "effort": "high"
            }
        }
        print(f"🧠 Using high reasoning effort for {model_id}")
    
    start_time = time.perf_counter()
    try:
        print(f"⏳ Making API call to {model_id}...")
        completion = await asyncio.wait_for(
            asyncio.to_thread(client.chat.completions.create, **llm_args),
            timeout=180  # 3 minute total timeout
        )
        latency = time.perf_counter() - start_time
        print(f"✅ API call completed in {latency:.2f}s")
        
        raw_content = completion.choices[0].message.content
        usage_info = completion.usage.model_dump() if completion.usage else {}
        
        # Parse JSON response manually
        try:
            # Clean up response - remove any markdown formatting
            json_str = raw_content.strip()
            if json_str.startswith("```json"):
                json_str = json_str[7:]
            if json_str.endswith("```"):
                json_str = json_str[:-3]
            json_str = json_str.strip()
            
            brief_dict = json.loads(json_str)
            brief = CaptionBrief(**brief_dict)
            return brief, usage_info, latency
            
        except (json.JSONDecodeError, ValidationError) as e:
            print(f"❌ Failed to parse analyst response for {model_id}: {e}")
            print(f"Raw response: {raw_content[:200]}...")
            
            # Retry logic for parsing errors
            if retry_count < MAX_RETRIES:
                print(f"🔄 Retrying analyst call for {model_id} (attempt {retry_count + 1}/{MAX_RETRIES})")
                await asyncio.sleep(2 ** retry_count)  # Exponential backoff
                return await _run_analyst_llm(client, model_id, settings, platform_name, strategy, visual_concept, alt_text, task_type, enable_task_type_optimization, style_guidance_sets, generated_image_prompts, suggested_marketing_strategies, retry_count + 1)
            
            return None, usage_info, latency
            
    except asyncio.TimeoutError:
        latency = time.perf_counter() - start_time
        print(f"❌ Timeout error for {model_id} after {latency:.2f}s")
        
        # Retry logic for timeout errors
        if retry_count < MAX_RETRIES:
            wait_time = 2 ** retry_count
            print(f"🔄 Retrying analyst call for {model_id} in {wait_time}s (attempt {retry_count + 1}/{MAX_RETRIES})")
            await asyncio.sleep(wait_time)
            return await _run_analyst_llm(client, model_id, settings, platform_name, strategy, visual_concept, alt_text, task_type, enable_task_type_optimization, style_guidance_sets, generated_image_prompts, suggested_marketing_strategies, retry_count + 1)
        
        return None, {}, latency
    except (APIConnectionError, RateLimitError, APIStatusError) as e:
        latency = time.perf_counter() - start_time
        print(f"❌ API error for {model_id}: {e}")
        
        # Retry logic for API errors
        if retry_count < MAX_RETRIES:
            wait_time = 2 ** retry_count
            print(f"🔄 Retrying analyst call for {model_id} in {wait_time}s (attempt {retry_count + 1}/{MAX_RETRIES})")
            await asyncio.sleep(wait_time)
            return await _run_analyst_llm(client, model_id, settings, platform_name, strategy, visual_concept, alt_text, task_type, enable_task_type_optimization, style_guidance_sets, generated_image_prompts, suggested_marketing_strategies, retry_count + 1)
        
        return None, {}, latency
    except Exception as e:
        latency = time.perf_counter() - start_time
        print(f"❌ Unexpected error for {model_id}: {e}")
        return None, {}, latency


async def _run_writer_llm(
    client: OpenAI,
    model_id: str,
    brief: CaptionBrief,
    retry_count: int = 0
) -> tuple[str | None, Dict[str, Any], float]:
    """Run the Writer LLM and return caption text, usage info, and latency."""
    
    system_prompt = _get_writer_system_prompt()
    user_prompt = _get_writer_user_prompt(brief)
    
    llm_args = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.7,
        "max_tokens": 3000,
        "timeout": 120,  # 2 minute timeout
    }
    
    # Add model-specific parameters
    if model_id in REASONING_EFFORT_MODELS:
        llm_args["extra_body"] = {
            "reasoning": {
                "effort": "high"
            }
        }
    
    start_time = time.perf_counter()
    try:
        print(f"⏳ Making Writer API call to {model_id}...")
        completion = await asyncio.wait_for(
            asyncio.to_thread(client.chat.completions.create, **llm_args),
            timeout=180  # 3 minute total timeout
        )
        latency = time.perf_counter() - start_time
        print(f"✅ Writer API call completed in {latency:.2f}s")
        
        caption_text = completion.choices[0].message.content.strip()
        usage_info = completion.usage.model_dump() if completion.usage else {}
        
        return caption_text, usage_info, latency
        
    except asyncio.TimeoutError:
        latency = time.perf_counter() - start_time
        print(f"❌ Writer timeout error for {model_id} after {latency:.2f}s")
        
        # Retry logic for timeout errors
        if retry_count < MAX_RETRIES:
            wait_time = 2 ** retry_count
            print(f"🔄 Retrying writer call for {model_id} in {wait_time}s (attempt {retry_count + 1}/{MAX_RETRIES})")
            await asyncio.sleep(wait_time)
            return await _run_writer_llm(client, model_id, brief, retry_count + 1)
        
        return None, {}, latency
    except (APIConnectionError, RateLimitError, APIStatusError) as e:
        latency = time.perf_counter() - start_time
        print(f"❌ Writer API error for {model_id}: {e}")
        
        # Retry logic for API errors
        if retry_count < MAX_RETRIES:
            wait_time = 2 ** retry_count
            print(f"🔄 Retrying writer call for {model_id} in {wait_time}s (attempt {retry_count + 1}/{MAX_RETRIES})")
            await asyncio.sleep(wait_time)
            return await _run_writer_llm(client, model_id, brief, retry_count + 1)
        
        return None, {}, latency
    except Exception as e:
        latency = time.perf_counter() - start_time
        print(f"❌ Writer unexpected error for {model_id}: {e}")
        return None, {}, latency


#######################################################################
# 4 ── Main Benchmark Loop #############################################
#######################################################################

async def run_benchmark():
    """Main benchmark execution function."""
    print("\n" + "=" * 60)
    print("🚀 STARTING CAPTION MODEL BENCHMARK")
    print("=" * 60)
    print(f"📊 Testing {len(INTERNAL_MATRIX)} models")
    print(f"🎯 Platform: {EVAL_DATA['platform_name']}")
    print(f"📝 Test scenario: {EVAL_DATA['visual_concept']['main_subject']}")
    print(f"🔄 Max retries per model: {MAX_RETRIES}")
    print(f"🧠 Models with reasoning effort: {len(REASONING_EFFORT_MODELS)}")
    print("=" * 60)
    
    # Setup client
    client = _setup_openrouter_client()
    print("✅ OpenRouter client initialized")
    
    # Load checkpoint if resuming
    results = load_checkpoint()
    completed_models = get_completed_models(results)
    failed_models = get_failed_models(results)
    
    if RETRY_FAILED_ONLY and failed_models:
        print(f"🔄 RETRY FAILED ONLY MODE: Re-running {len(failed_models)} failed models")
        for model_id in failed_models:
            print(f"  🔄 {model_id}")
        # Remove failed results so they can be replaced
        results = remove_failed_results(results, failed_models)
        models_to_test = [m for m in INTERNAL_MATRIX if m["model_id"] in failed_models]
        print(f"📝 Retrying {len(models_to_test)} failed models")
    elif completed_models:
        print(f"📂 Resuming from checkpoint: {len(completed_models)} models already completed")
        for model_id in completed_models:
            print(f"  ✅ {model_id}")
        models_to_test = [m for m in INTERNAL_MATRIX if m["model_id"] not in completed_models]
    else:
        models_to_test = INTERNAL_MATRIX
    
    # Extract test data
    strategy = EVAL_DATA["strategy"]
    visual_concept = EVAL_DATA["visual_concept"]
    platform_name = EVAL_DATA["platform_name"]
    settings = EVAL_DATA["settings"]
    alt_text = visual_concept["suggested_alt_text"]
    
    # Extract enhancement data
    task_type = EVAL_DATA.get("task_type")
    enable_task_type_optimization = EVAL_DATA.get("enable_task_type_caption_optimization", True)
    style_guidance_sets = EVAL_DATA.get("style_guidance_sets")
    generated_image_prompts = EVAL_DATA.get("generated_image_prompts")
    suggested_marketing_strategies = EVAL_DATA.get("suggested_marketing_strategies")
    
    print(f"🔧 Caption settings: tone={settings.tone}, emojis={settings.include_emojis}, hashtags={settings.hashtag_strategy}")
    
    # Run benchmark for each model
    total_models = len(INTERNAL_MATRIX)
    
    if RETRY_FAILED_ONLY and failed_models:
        print(f"\n🔄 Failed models to retry: {len(models_to_test)}/{len(failed_models)}")
    else:
        print(f"\n🎯 Models to test: {len(models_to_test)}/{total_models}")
    
    for i, model_config in enumerate(models_to_test, 1):
        model_id = model_config["model_id"]
        provider = model_config["provider"]
        
        # Calculate overall progress
        if RETRY_FAILED_ONLY and failed_models:
            overall_progress = i
            total_progress = len(models_to_test)
            print(f"\n🔄 [{overall_progress}/{total_progress}] Retrying {model_id}")
        else:
            overall_progress = len(completed_models) + i
            print(f"\n📝 [{overall_progress}/{total_models}] Testing {model_id}")
        
        if model_id in REASONING_EFFORT_MODELS:
            print(f"🧠 This model will use high reasoning effort (fixed extra_body)")
        print("-" * 50)
        
        result = {
            "model_id": model_id,
            "provider": provider,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "success": False,
            "error": None,
            "retry_count": 0,
        }
        
        try:
            # Step 1: Run Analyst
            print("🔍 Running Analyst stage...")
            brief, analyst_usage, analyst_latency = await _run_analyst_llm(
                client, model_id, settings, platform_name, strategy, visual_concept, alt_text,
                task_type, enable_task_type_optimization, style_guidance_sets, 
                generated_image_prompts, suggested_marketing_strategies
            )
            
            result["analyst_latency"] = round(analyst_latency, 3)
            result["analyst_usage"] = analyst_usage
            
            if not brief:
                result["error"] = "Analyst stage failed after all retries"
                results.append(result)
                print("❌ Analyst stage failed, skipping Writer stage")
                save_checkpoint(results)  # Save progress
                continue
            
            print(f"✅ Analyst completed in {analyst_latency:.2f}s")
            result["brief"] = brief.model_dump()
            
            # Step 2: Run Writer
            print("✍️ Running Writer stage...")
            caption, writer_usage, writer_latency = await _run_writer_llm(client, model_id, brief)
            
            result["writer_latency"] = round(writer_latency, 3)
            result["writer_usage"] = writer_usage
            
            if not caption:
                result["error"] = "Writer stage failed after all retries"
                results.append(result)
                print("❌ Writer stage failed")
                save_checkpoint(results)  # Save progress
                continue
            
            print(f"✅ Writer completed in {writer_latency:.2f}s")
            result["caption"] = caption
            result["total_latency"] = round(analyst_latency + writer_latency, 3)
            result["success"] = True
            
            # Calculate total tokens
            total_tokens = (analyst_usage.get("total_tokens", 0) + writer_usage.get("total_tokens", 0))
            result["total_tokens"] = total_tokens
            
            print(f"📊 Total: {result['total_latency']}s, {total_tokens} tokens")
            print(f"📝 Caption preview: {caption[:100]}{'...' if len(caption) > 100 else ''}")
            
        except Exception as e:
            result["error"] = str(e)
            print(f"❌ Unexpected error: {e}")
            traceback.print_exc()
        
        results.append(result)
        save_checkpoint(results)  # Save progress after each model
        
        # Small delay between requests to be respectful
        if i < len(models_to_test):  # Don't wait after the last model
            print("⏳ Waiting 2s before next model...")
            await asyncio.sleep(2)
    
    # Save final results
    print(f"\n💾 Saving final results to {RESULT_PATH}")
    with open(RESULT_PATH, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    # Only clean up checkpoint file if ALL models succeeded
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    
    if len(failed) == 0 and os.path.exists(CHECKPOINT_PATH):
        try:
            os.remove(CHECKPOINT_PATH)
            print("🧹 Cleaned up checkpoint file - all models successful")
        except Exception as e:
            print(f"⚠️ Failed to clean up checkpoint: {e}")
    elif len(failed) > 0:
        # Keep checkpoint for potential retry
        save_checkpoint(results)
        print(f"💾 Keeping checkpoint for {len(failed)} failed models")
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 BENCHMARK SUMMARY")
    print("=" * 60)
    
    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]
    
    print(f"✅ Successful: {len(successful)}/{len(results)}")
    print(f"❌ Failed: {len(failed)}/{len(results)}")
    
    if successful:
        print("\n🏆 PERFORMANCE RANKINGS:")
        successful_sorted = sorted(successful, key=lambda x: x["total_latency"])
        
        for i, result in enumerate(successful_sorted, 1):
            model_name = result["model_id"].split("/")[-1]
            latency = result["total_latency"]
            tokens = result["total_tokens"]
            reasoning_icon = "🧠" if result["model_id"] in REASONING_EFFORT_MODELS else "  "
            print(f"{i:2d}. {reasoning_icon} {model_name:<25} | {latency:>6.2f}s | {tokens:>6,} tokens")
    
    if failed:
        print(f"\n❌ FAILED MODELS:")
        for result in failed:
            model_name = result["model_id"].split("/")[-1]
            error = result["error"]
            print(f"   • {model_name:<25} | {error}")
    
    print(f"\n💾 Full results saved to: {RESULT_PATH}")
    
    # Show models with reasoning effort
    if REASONING_EFFORT_MODELS:
        print(f"\n🧠 Models tested with high reasoning effort:")
        for model_id in REASONING_EFFORT_MODELS:
            status = "✅" if model_id in [r["model_id"] for r in successful] else "❌"
            print(f"   {status} {model_id}")


if __name__ == "__main__":
    asyncio.run(run_benchmark()) 