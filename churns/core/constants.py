"""
Constants for the AI Marketing Pipeline.
=======================================

🎯 CENTRALIZED CONFIGURATION - Single Source of Truth
-----------------------------------------------------
This file serves as the ONLY place to define:
- Model configurations (providers, IDs, pricing)
- LLM settings (retries, parsing modes)
- Platform definitions and task types
- All other system constants

⚠️  DO NOT duplicate these constants in other files!
   Other modules should import from here to maintain consistency.

Design Pattern:
- Pipeline stages have placeholder variables (set to None)
- PipelineExecutor injects actual values from this file
- API clients get configuration through ClientConfig class
- Background tasks import pricing/model info directly

All constants copied verbatim from the original combined_pipeline.py
"""

from typing import Dict, List, Any

# --- LLM Configuration ---
MAX_LLM_RETRIES = 3
FORCE_MANUAL_JSON_PARSE = False  # Set to False to try Instructor first where applicable
VERBOSE_COST_LATENCY_SUMMARY = True  # Control verbosity of cost/latency summary

# --- Model Definitions ---
# Phase 1 Models
IMG_EVAL_MODEL_PROVIDER = "OpenRouter"  # "OpenRouter" or "Gemini"
IMG_EVAL_MODEL_ID = "openai/gpt-4.1"  # E.g., "openai/gpt-4-vision-preview", "google/gemini-pro-vision"

STRATEGY_MODEL_PROVIDER = "OpenRouter"  # "OpenRouter" or "Gemini"
STRATEGY_MODEL_ID = "openai/gpt-4.1-mini"  # E.g., "openai/gpt-4-turbo", "google/gemini-1.5-pro-latest"

# Phase 2 Models
STYLE_GUIDER_MODEL_PROVIDER = "OpenRouter"  # "OpenRouter" or "Gemini"
STYLE_GUIDER_MODEL_ID = "google/gemini-2.5-pro"  # "openai/o4-mini" "deepseek/deepseek-r1-0528" "qwen/qwen3-235b-a22b" "google/gemini-2.5-pro-preview"

CREATIVE_EXPERT_MODEL_PROVIDER = "OpenRouter"  # "OpenRouter" or "Gemini"
CREATIVE_EXPERT_MODEL_ID = "google/gemini-2.5-pro"  # "openai/o4-mini" "deepseek/deepseek-r1-0528" "qwen/qwen3-235b-a22b" "google/gemini-2.5-pro-preview"

# Image Assessment Model (dedicated for image quality evaluation)
IMAGE_ASSESSMENT_MODEL_PROVIDER = "OpenRouter"  # Direct OpenAI for reliable multi-image processing
IMAGE_ASSESSMENT_MODEL_ID = "openai/o4-mini"  # OpenAI native client for vision tasks

# StyleAdaptation Model (for style transfer and adaptation)
STYLE_ADAPTATION_MODEL_PROVIDER = "OpenRouter"  # "OpenRouter" or "OpenAI"
STYLE_ADAPTATION_MODEL_ID = "openai/gpt-4o"  # High-quality model for creative adaptation

# Caption Generation Model (for social media caption creation)
CAPTION_MODEL_PROVIDER = "OpenRouter"  # "OpenRouter" or "OpenAI"

# Caption Model Options with characteristics
CAPTION_MODEL_OPTIONS = {
    "openai/gpt-4.1": {
        "id": "openai/gpt-4.1",
        "name": "Quick Response",
        "description": "Fast generation with efficient processing for immediate results",
        "strengths": ["Fastest response time", "Reliable output", "Efficient processing"],
        "best_for": "Time-sensitive posts, quick iterations",
        "latency": "Low",
        "creativity": "Efficient"
    },
    "google/gemini-2.5-pro": {
        "id": "google/gemini-2.5-pro", 
        "name": "Thoughtful Analysis",
        "description": "Deeper reasoning and analysis for more nuanced captions",
        "strengths": ["Comprehensive analysis", "Nuanced understanding", "Creative reasoning"],
        "best_for": "Complex campaigns, premium content",
        "latency": "Higher",
        "creativity": "Analytical"
    }
}

# Default caption model
CAPTION_MODEL_ID = "openai/gpt-4.1"  # Default model ID

IMAGE_GENERATION_MODEL_ID = "gpt-image-1"

# Models known to have issues with instructor's default TOOLS mode via OpenRouter
INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS = ["openai/o4-mini", "google/gemini-2.5-pro", "openai/o4-mini-high"]

# --- Image Token Calculation Parameters ---
# Two different calculation methods based on model family
IMAGE_TOKEN_CALCULATION_METHODS = {
    # Method 1: 32px patch-based calculation (GPT-4.1-mini, GPT-4.1-nano, o4-mini)
    "patch_based": {
        "patch_size": 32,
        "max_patches": 1536,
        "model_multipliers": {
            "gpt-4.1-mini": 1.62,
            "gpt-4.1-nano": 2.46, 
            "o4-mini": 1.72,
            "o4-mini-high": 1.72
        }
    },
    
    # Method 2: Tile-based calculation (GPT-4o, GPT-4.1, GPT-4o-mini, CUA, o-series except o4-mini)
    "tile_based": {
        "max_square": 2048,
        "shortest_side_target": 768,
        "tile_size": 512,
        "model_costs": {
            "gpt-4o": {"base_tokens": 85, "tile_tokens": 170},
            "gpt-4.1": {"base_tokens": 85, "tile_tokens": 170},
            "gpt-4.5": {"base_tokens": 85, "tile_tokens": 170},
            "gpt-4o-mini": {"base_tokens": 2833, "tile_tokens": 5667},
            "o1": {"base_tokens": 75, "tile_tokens": 150},
            "o1-pro": {"base_tokens": 75, "tile_tokens": 150},
            "o3": {"base_tokens": 75, "tile_tokens": 150},
            "computer-use-preview": {"base_tokens": 65, "tile_tokens": 129}
        }
    }
}

# Model family classification for image token calculation
IMAGE_TOKEN_MODEL_FAMILIES = {
    # Patch-based models (32px patches with multipliers)
    "patch_based": ["gpt-4.1-mini", "gpt-4.1-nano", "o4-mini", "o4-mini-high"],
    
    # Tile-based models (512px tiles with base + tile costs)
    "tile_based": ["gpt-4o", "gpt-4.1", "gpt-4.5", "gpt-4o-mini", "o1", "o1-pro", "o3", "computer-use-preview"]
}

# --- Model Pricing (USD) ---
# Prices per 1 Million tokens for text, per image for image models
# Source: OpenRouter for text models, OpenAI for DALL-E 3 (as of June 2025 - placeholder)
# User should verify current pricing from respective providers.
MODEL_PRICING = {
    "openai/o4-mini": {  # Used for Style Guider, Creative Expert
        "provider": "OpenRouter",
        "input_cost_per_mtok": 1.10,
        "output_cost_per_mtok": 4.40,
        "currency": "USD",
        "notes": "Pricing for openai/o4-mini via OpenRouter."
    },
    "openai/o4-mini-high": {  # Used for Style Guider, Creative Expert
        "provider": "OpenRouter",
        "input_cost_per_mtok": 1.10,
        "output_cost_per_mtok": 4.40,
        "currency": "USD",
        "notes": "Pricing for openai/o4-mini-high via OpenRouter."
    },
    "openai/gpt-4.1-mini": {  # Used for Image Eval, Niche ID, Strategy Gen
        "provider": "OpenRouter",  # Assuming this is an OpenRouter model ID
        "input_cost_per_mtok": 0.40,
        "output_cost_per_mtok": 1.20,
        "currency": "USD",
        "notes": "Pricing for openai/gpt-4.1-mini via OpenRouter."
    },
    "deepseek/deepseek-r1-0528": {  # Explicitly adding for reference if needed
        "provider": "OpenRouter",
        "input_cost_per_mtok": 0.50,
        "output_cost_per_mtok": 2.150,
        "currency": "USD",
        "notes": "Pricing for deepseek/deepseek-r1-0528 via OpenRouter."
    },
    "qwen/qwen3-235b-a22b": {  # Explicitly adding for reference if needed
        "provider": "OpenRouter",
        "input_cost_per_mtok": 0.14,
        "output_cost_per_mtok": 2,
        "currency": "USD",
        "notes": "Pricing for qwen/qwen3-235b-a22b via OpenRouter."
    },
    "google/gemini-2.5-pro": {  # Added pricing for this model
        "provider": "OpenRouter",  # Assuming OpenRouter access
        "input_cost_per_mtok": 1.25,  # Example: Gemini 1.5 Pro on OpenRouter
        "output_cost_per_mtok": 10.00,  # Example: Gemini 1.5 Pro on OpenRouter
        "currency": "USD",
        "notes": "Pricing for google/gemini-2.5-pro-preview via OpenRouter (using Gemini 1.5 Pro rates as proxy)."
    },
    "gpt-4.1": {  # Used for Image Assessment (vision tasks)
        "provider": "OpenAI",
        "input_cost_per_mtok": 2,  # $0.150 per 1M input tokens
        "output_cost_per_mtok": 8,  # $0.600 per 1M output tokens
        "currency": "USD",
        "notes": "Pricing for gpt-4.1 via OpenAI native client (vision capabilities)."
    },
    "o4-mini": {  # Used for Image Assessment (vision tasks)
        "provider": "OpenAI",
        "input_cost_per_mtok": 1.1,  # $0.150 per 1M input tokens
        "output_cost_per_mtok": 4.4,  # $0.600 per 1M output tokens
        "currency": "USD",
        "notes": "Pricing for gpt-4.1 via OpenAI native client (vision capabilities)."
    },
    "openai/gpt-4o-mini": {  # Used for Caption Generation
        "provider": "OpenRouter",
        "input_cost_per_mtok": 0.15,  # $0.15 per 1M input tokens via OpenRouter
        "output_cost_per_mtok": 0.60,  # $0.60 per 1M output tokens via OpenRouter
        "currency": "USD",
        "notes": "Pricing for openai/gpt-4o-mini via OpenRouter (cost-effective for caption generation)."
    },
    "openai/gpt-4o": {  # Used for StyleAdaptation
        "provider": "OpenRouter",
        "input_cost_per_mtok": 5.00,  # $5.00 per 1M input tokens via OpenRouter
        "output_cost_per_mtok": 15.00,  # $15.00 per 1M output tokens via OpenRouter
        "currency": "USD",
        "notes": "Pricing for openai/gpt-4o via OpenRouter (high-quality for creative adaptation)."
    },
    "gpt-image-1": {
        "provider": "OpenAI",
        "currency": "USD",
        "input_text_cost_per_mtok": 5.00,  # Text input tokens: $5.00 per 1M tokens
        "input_image_cost_per_mtok": 10.00,  # Image input tokens: $10.00 per 1M tokens
        "output_image_cost_per_mtok": 40.00,  # Image output tokens: $40.00 per 1M tokens
        "cached_input_discount": 0.75,  # 75% discount for cached input tokens
        "token_counts_by_quality": {  # Approximate image output token counts by quality/size
            "low": {
                "1024x1024": 272,    # ~$0.01088 at $40/1M tokens
                "1024x1536": 408,    # ~$0.01632 at $40/1M tokens
                "1536x1024": 400     # ~$0.01600 at $40/1M tokens
            },
            "medium": {
                "1024x1024": 1056,   # ~$0.04224 at $40/1M tokens
                "1024x1536": 1584,   # ~$0.06336 at $40/1M tokens
                "1536x1024": 1568    # ~$0.06272 at $40/1M tokens
            },
            "high": {
                "1024x1024": 4160,   # ~$0.16640 at $40/1M tokens
                "1024x1536": 6240,   # ~$0.24960 at $40/1M tokens
                "1536x1024": 6208    # ~$0.24832 at $40/1M tokens
            }
        },
        "notes": "Token-based pricing for gpt-image-1 via OpenAI Responses SDK. All billing is per token: $5/1M text input, $10/1M image input, $40/1M image output tokens."
    },
}

# --- Task Types ---
TASK_TYPES = [
    'Select Task...',
    '1. Product Photography',
    '2. Promotional Graphics & Announcements',
    '3. Store Atmosphere & Decor',
    '4. Menu Spotlights',
    '5. Cultural & Community Content',
    '6. Recipes & Food Tips',
    '7. Brand Story & Milestones',
    '8. Behind the Scenes Imagery'
]

# --- Social Media Platforms ---
SOCIAL_MEDIA_PLATFORMS = {
    'Select Platform...': None,
    'Instagram Post (1:1 Square)': {'width': 1080, 'height': 1080, 'aspect_ratio': '1:1'},
    'Instagram Story/Reel (9:16 Vertical)': {'width': 1080, 'height': 1920, 'aspect_ratio': '9:16'},
    'Facebook Post (Mixed)': {'width': 1200, 'height': 630, 'aspect_ratio': '1.91:1'},  # More common FB link preview
    'Pinterest Pin (2:3 Vertical)': {'width': 1024, 'height': 1536, 'aspect_ratio': '2:3'},  # Common Pinterest
    'Xiaohongshu (Red Note) (3:4 Vertical)': {'width': 1080, 'height': 1440, 'aspect_ratio': '3:4'},
}
PLATFORM_DISPLAY_NAMES = list(SOCIAL_MEDIA_PLATFORMS.keys())

# --- Marketing Task Pools ---
TASK_GROUP_POOLS = {
    "product_focus": {
        "audience": ["Foodies/Bloggers", "Local Residents", "Health-Conscious Eaters", "Vegetarians/Vegans", "Budget-Conscious Diners", "Luxury Seekers", "Specific Dietary Needs (e.g., Gluten-Free, Nut-Free)", "Tourists/Visitors", "Young Professionals (25-35)", "Families with Children", "Online Order Customers", "Takeaway Customers", "Diners seeking specific cuisine"],
        "niche": ["Casual Dining", "Fine Dining", "Cafe/Coffee Shop", "Bakery/Patisserie", "Fast Food/QSR", "Ethnic Cuisine (e.g., Italian, Thai, Mexican, Japanese, Indian)", "Specialty (e.g., Vegan, Seafood, Steakhouse, Organic)", "Brunch Spot", "Dessert Place", "Takeaway/Delivery Focused", "Gourmet Burger Joint", "Artisan Pizza Place", "Healthy Bowls/Salads"],
        "objective": ["Create Appetite Appeal", "Showcase Quality/Freshness", "Promote Specific Menu Item", "Highlight Ingredients/Sourcing", "Increase Online Orders/Reservations", "Drive Trial of New Item", "Attract New Customers", "Generate User-Generated Content (e.g., encourage photos)", "Justify Price Point", "Visually Explain Complex Dish", "Feature Seasonal Specials", "Differentiate from Competitors"],
        "voice": ["Mouth-watering & Descriptive", "Sophisticated & Elegant", "Fresh & Vibrant", "Authentic & Honest", "Simple & Direct", "Playful & Fun", "Informative & Helpful", "Artistic & Aspirational", "Clean & Minimalist", "Rustic & Homely"]
    },
    "promotion": {
        "audience": ["Budget-Conscious Diners", "Local Residents", "Students", "Young Professionals (25-35)", "Families with Children", "Existing Customers", "New Customers", "Loyalty Program Members", "Social Media Followers", "Event Attendees (for future events)"],
        "niche": ["Casual Dining", "Cafe/Coffee Shop", "Bakery/Patisserie", "Fast Food/QSR", "Takeaway/Delivery Focused", "Family Restaurant", "Bar/Pub", "Pizza Place", "Burger Joint"],
        "objective": ["Drive Short-Term Sales", "Increase Foot Traffic (Weekday/Weekend)", "Boost Online Orders", "Announce Special Offer/Discount", "Promote Event (e.g., Live Music, Quiz Night)", "Create Urgency (Limited Time Offer)", "Drive Trial of New Item/Offer", "Reward Loyal Customers", "Attract New Customers", "Increase Average Order Value (e.g., combo deals)"],
        "voice": ["Urgent & Exciting", "Friendly & Casual", "Clear & Direct", "Playful & Fun", "Value-Oriented", "Exclusive (for loyalty)", "Benefit-Driven", "Enthusiastic & Bold"]
    },
    "brand_atmosphere": {
        "audience": ["Local Residents", "Tourists/Visitors", "Young Professionals (25-35)", "Couples", "Foodies/Bloggers", "Remote Workers", "Event Planners", "Potential Employees", "Community Groups", "Art/Music Lovers (if relevant)"],
        "niche": ["Casual Dining", "Fine Dining", "Cafe/Coffee Shop", "Bakery/Patisserie", "Bar/Pub", "Ethnic Cuisine", "Specialty", "Romantic Restaurant", "Community Hub", "Venue with View", "Pet-Friendly Spot"],
        "objective": ["Increase Brand Awareness", "Highlight Atmosphere/Ambience/Decor", "Build Community", "Showcase Brand Personality/Values", "Build Emotional Connection", "Increase Brand Loyalty", "Attract Talent (BTS)", "Generate Interest for Events/Bookings", "Show Authenticity/Transparency (BTS)", "Tell Founder's Story", "Celebrate Milestone", "Feature Staff/Team", "Highlight Local Partnerships/Sourcing"],
        "voice": ["Warm & Welcoming", "Cozy & Comforting", "Sophisticated & Elegant", "Trendy & Energetic", "Authentic & Honest", "Community-Focused", "Aspirational & Inspiring", "Behind-the-Scenes & Candid", "Passionate & Dedicated", "Nostalgic & Reflective (for story)"]
    },
    "informative": {
         "audience": ["Home Cooks", "Foodies/Bloggers", "Health-Conscious Eaters", "Families with Children", "Budget-Conscious Diners", "Specific Dietary Needs", "Cooking Enthusiasts", "Beginner Cooks"],
         "niche": ["General F&B", "Cafe/Coffee Shop", "Bakery/Patisserie", "Ethnic Cuisine", "Specialty (e.g., Vegan)", "Health Food Store", "Cooking School", "Restaurant Blog", "Ingredient Supplier"],
         "objective": ["Educate Customers", "Provide Value/Utility", "Establish Expertise/Authority", "Increase Engagement on Social Media", "Drive Website/Blog Traffic", "Promote Specific Ingredients/Products", "Build Community around Food/Cooking", "Encourage Home Cooking (with brand ingredients)", "Simplify Complex Techniques", "Inspire Creativity"],
         "voice": ["Informative & Helpful", "Authoritative & Expert", "Friendly & Approachable", "Inspiring & Creative", "Clear & Concise", "Authentic & Passionate", "Step-by-Step & Practical", "Encouraging & Supportive"]
    },
    "default": {
        "audience": ["Local Residents", "Young Professionals (25-35)", "Families with Children", "Foodies/Bloggers", "General Social Media Users", "Tourists/Visitors", "Budget-Conscious Diners", "Health-Conscious Eaters"],
        "niche": ["Casual Dining", "Cafe/Coffee Shop", "Takeaway/Delivery Focused", "Bakery/Patisserie", "Fast Food/QSR", "General F&B"],
        "objective": ["Increase Brand Awareness", "Drive Foot Traffic", "Increase Engagement on Social Media", "Attract New Customers", "Showcase Product/Service", "Create Appetite Appeal", "Build Community"],
        "voice": ["Friendly & Casual", "Warm & Welcoming", "Authentic & Honest", "Clear & Direct", "Engaging & Vibrant"]
    }
} 