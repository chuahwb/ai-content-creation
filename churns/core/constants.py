"""
Constants for the AI Marketing Pipeline.
All constants copied verbatim from the original combined_pipeline.py
"""

from typing import Dict, List, Any

# --- LLM Configuration ---
MAX_LLM_RETRIES = 1
FORCE_MANUAL_JSON_PARSE = False  # Set to False to try Instructor first where applicable
VERBOSE_COST_LATENCY_SUMMARY = True  # Control verbosity of cost/latency summary

# --- Model Definitions ---
# Phase 1 Models
IMG_EVAL_MODEL_PROVIDER = "OpenRouter"  # "OpenRouter" or "Gemini"
IMG_EVAL_MODEL_ID = "openai/gpt-4.1-mini"  # E.g., "openai/gpt-4-vision-preview", "google/gemini-pro-vision"

STRATEGY_MODEL_PROVIDER = "OpenRouter"  # "OpenRouter" or "Gemini"
STRATEGY_MODEL_ID = "openai/gpt-4.1-mini"  # E.g., "openai/gpt-4-turbo", "google/gemini-1.5-pro-latest"

# Phase 2 Models
STYLE_GUIDER_MODEL_PROVIDER = "OpenRouter"  # "OpenRouter" or "Gemini"
STYLE_GUIDER_MODEL_ID = "google/gemini-2.5-pro-preview"  # "openai/o4-mini" "deepseek/deepseek-r1-0528" "qwen/qwen3-235b-a22b" "google/gemini-2.5-pro-preview"

CREATIVE_EXPERT_MODEL_PROVIDER = "OpenRouter"  # "OpenRouter" or "Gemini"
CREATIVE_EXPERT_MODEL_ID = "google/gemini-2.5-pro-preview"  # "openai/o4-mini" "deepseek/deepseek-r1-0528" "qwen/qwen3-235b-a22b" "google/gemini-2.5-pro-preview"

IMAGE_GENERATION_MODEL_ID = "gpt-image-1"

# Models known to have issues with instructor's default TOOLS mode via OpenRouter
INSTRUCTOR_TOOL_MODE_PROBLEM_MODELS = ["openai/o4-mini", "google/gemini-2.5-pro-preview"]

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
    "google/gemini-2.5-pro-preview": {  # Added pricing for this model
        "provider": "OpenRouter",  # Assuming OpenRouter access
        "input_cost_per_mtok": 1.25,  # Example: Gemini 1.5 Pro on OpenRouter
        "output_cost_per_mtok": 10.00,  # Example: Gemini 1.5 Pro on OpenRouter
        "currency": "USD",
        "notes": "Pricing for google/gemini-2.5-pro-preview via OpenRouter (using Gemini 1.5 Pro rates as proxy)."
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