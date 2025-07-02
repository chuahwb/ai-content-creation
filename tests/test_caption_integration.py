"""
Integration test for caption enhancement with task type optimization.
"""

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch
from churns.stages.caption import run
from churns.pipeline.context import PipelineContext
from churns.models import CaptionSettings, CaptionBrief


@pytest.mark.asyncio
async def test_caption_generation_with_task_type_optimization():
    """Test caption generation with task type optimization enabled."""
    
    # Create a mock context with all required data
    ctx = PipelineContext()
    ctx.task_type = "6. Recipes & Food Tips"
    ctx.enable_task_type_caption_optimization = True
    ctx.target_platform = {"name": "Instagram Post (1:1 Square)"}
    
    # Mock marketing strategies
    ctx.suggested_marketing_strategies = [
        {
            "target_audience": "Health-conscious millennials",
            "target_objective": "Educate about plant-based nutrition",
            "target_voice": "Friendly and informative",
            "target_niche": "Plant-Based Beverages"
        }
    ]
    
    # Mock style guidance sets
    ctx.style_guidance_sets = [
        {
            "style_keywords": ["natural", "organic", "wholesome"],
            "style_description": "Clean, natural aesthetic with warm tones"
        }
    ]
    
    # Mock generated image prompts
    ctx.generated_image_prompts = [
        {
            "visual_concept": {
                "main_subject": "Handcrafted soy milk bottle",
                "lighting_and_mood": "Soft natural lighting",
                "visual_style": "Clean minimalist photography",
                "creative_reasoning": "Emphasizes the artisanal quality and health benefits",
                "suggested_alt_text": "Bottle of handcrafted organic soy milk"
            },
            "source_strategy_index": 0
        }
    ]
    
    # Mock image analysis result
    ctx.image_analysis_result = {
        "main_subject": "Handcrafted soy milk bottle"
    }
    
    # Mock caption settings
    ctx.caption_settings = {
        "tone": None,  # Let it use auto mode
        "include_emojis": True,
        "hashtag_strategy": "Balanced Mix"
    }
    
    # Create the expected JSON response
    analyst_json_response = {
        "core_message": "Learn how to make a creamy golden turmeric soy milk latte at home.",
        "key_themes_to_include": ["plant-based nutrition", "homemade recipes", "turmeric benefits", "sustainable living"],
        "seo_keywords": ["soy milk recipe", "turmeric latte", "plant-based", "healthy drinks"],
        "target_emotion": "Educational and inspiring",
        "platform_optimizations": {
            "Instagram Post (1:1 Square)": {
                "caption_structure": "Hook + Value + CTA",
                "style_notes": "Use engaging questions and clear instructions"
            }
        },
        "primary_call_to_action": "Save this recipe and try it today! 🌱",
        "hashtags": ["#soymilk", "#plantbased", "#turmericlatte", "#healthyrecipes", "#homemade"],
        "emoji_suggestions": ["🌱", "☕", "✨"],
        "task_type_notes": "Optimize for Recipes & Food Tips: educate followers with practical recipes"
    }
    
    # Mock the LLM clients and responses
    mock_analyst_response = Mock()
    mock_analyst_response.choices = [Mock()]
    mock_analyst_response.choices[0].message.content = json.dumps(analyst_json_response)
    mock_analyst_response.usage = Mock()
    mock_analyst_response.usage.model_dump.return_value = {"prompt_tokens": 500, "completion_tokens": 200}
    
    mock_writer_response = Mock()
    mock_writer_response.choices = [Mock()]
    mock_writer_response.choices[0].message.content = """Save this recipe: Golden Turmeric Soy Milk Latte ☕✨

Transform your morning routine with this creamy, anti-inflammatory powerhouse! This homemade turmeric latte combines the plant-based goodness of handcrafted soy milk with warming spices for the ultimate healthy drink.

🌱 Why you'll love it:
• Rich in plant-based protein
• Anti-inflammatory turmeric benefits
• Naturally creamy without dairy
• Perfect for sustainable living

The secret? Quality soy milk makes all the difference. Look for that golden, creamy texture that only comes from artisanal craftsmanship.

Save this recipe and try it today! 🌱

#soymilk #plantbased #turmericlatte #healthyrecipes #homemade"""
    mock_writer_response.choices[0].finish_reason = "stop"
    mock_writer_response.usage = Mock()
    mock_writer_response.usage.model_dump.return_value = {"prompt_tokens": 300, "completion_tokens": 150}
    
    # Mock the LLM clients and global variables
    with patch('churns.stages.caption.instructor_client_caption', None), \
         patch('churns.stages.caption.base_llm_client_caption') as mock_base, \
         patch('churns.stages.caption.CAPTION_MODEL_ID', 'gpt-4'), \
         patch('churns.stages.caption.CAPTION_MODEL_PROVIDER', 'openai'), \
         patch('churns.stages.caption.should_use_manual_parsing', return_value=True):
        
        mock_base.chat.completions.create.side_effect = [mock_analyst_response, mock_writer_response]
        
        # Run the caption generation
        await run(ctx)
        
        # Verify that captions were generated
        assert hasattr(ctx, 'generated_captions')
        assert len(ctx.generated_captions) == 1
        
        caption_result = ctx.generated_captions[0]
        assert 'text' in caption_result
        assert 'brief_used' in caption_result
        assert 'settings_used' in caption_result
        
        # Verify the caption contains expected elements
        caption_text = caption_result['text']
        assert 'Golden Turmeric Soy Milk Latte' in caption_text
        assert '#soymilk' in caption_text
        assert '#plantbased' in caption_text
        assert '🌱' in caption_text
        
        # Verify the brief was used correctly
        brief_used = caption_result['brief_used']
        assert brief_used['task_type_notes'] == "Optimize for Recipes & Food Tips: educate followers with practical recipes"
        assert 'plant-based nutrition' in brief_used['key_themes_to_include']
        
        # Verify LLM was called with task type context
        calls = mock_base.chat.completions.create.call_args_list
        analyst_call = calls[0]
        analyst_prompt = analyst_call[1]['messages'][1]['content']
        
        assert "**Task Type Context:**" in analyst_prompt
        assert "Recipes & Food Tips" in analyst_prompt
        assert "Educate followers with practical recipes" in analyst_prompt
        assert "**Style Context:**" in analyst_prompt
        assert "natural, organic, wholesome" in analyst_prompt


@pytest.mark.asyncio 
async def test_caption_generation_without_task_type():
    """Test caption generation works when no task type is provided."""
    
    ctx = PipelineContext()
    ctx.task_type = None  # No task type
    ctx.target_platform = {"name": "Instagram Post (1:1 Square)"}
    
    # Minimal required data
    ctx.suggested_marketing_strategies = [
        {
            "target_audience": "General audience", 
            "target_objective": "Increase engagement"
        }
    ]
    
    ctx.generated_image_prompts = [
        {
            "visual_concept": {
                "main_subject": "Product photo",
                "suggested_alt_text": "Product image"
            },
            "source_strategy_index": 0
        }
    ]
    
    ctx.image_analysis_result = {"main_subject": "Product photo"}
    ctx.caption_settings = {}
    
    # Create the expected JSON response
    analyst_json_response = {
        "core_message": "Check out this amazing product.",
        "key_themes_to_include": ["quality", "value"],
        "seo_keywords": ["product", "quality"],
        "target_emotion": "Interested",
        "platform_optimizations": {
            "Instagram Post (1:1 Square)": {
                "caption_structure": "Hook + Value + CTA",
                "style_notes": "Keep it simple"
            }
        },
        "primary_call_to_action": "Learn more!",
        "hashtags": ["#product"],
        "emoji_suggestions": ["✨"],
        "task_type_notes": None
    }
    
    # Mock responses
    mock_analyst_response = Mock()
    mock_analyst_response.choices = [Mock()]
    mock_analyst_response.choices[0].message.content = json.dumps(analyst_json_response)
    mock_analyst_response.usage = Mock()
    mock_analyst_response.usage.model_dump.return_value = {"prompt_tokens": 300, "completion_tokens": 100}
    
    mock_writer_response = Mock()
    mock_writer_response.choices = [Mock()]
    mock_writer_response.choices[0].message.content = "Check out this amazing product! ✨ Learn more! #product"
    mock_writer_response.choices[0].finish_reason = "stop"
    mock_writer_response.usage = Mock()
    mock_writer_response.usage.model_dump.return_value = {"prompt_tokens": 200, "completion_tokens": 50}
    
    with patch('churns.stages.caption.instructor_client_caption', None), \
         patch('churns.stages.caption.base_llm_client_caption') as mock_base, \
         patch('churns.stages.caption.CAPTION_MODEL_ID', 'gpt-4'), \
         patch('churns.stages.caption.should_use_manual_parsing', return_value=True):
        
        mock_base.chat.completions.create.side_effect = [mock_analyst_response, mock_writer_response]
        
        await run(ctx)
        
        # Should still generate captions successfully
        assert hasattr(ctx, 'generated_captions')
        assert len(ctx.generated_captions) == 1
        
        # Verify no task type context was included
        calls = mock_base.chat.completions.create.call_args_list
        analyst_call = calls[0]
        analyst_prompt = analyst_call[1]['messages'][1]['content']
        
        assert "**Task Type Context:**" not in analyst_prompt
        
        # Verify task_type_notes is null
        caption_result = ctx.generated_captions[0]
        brief_used = caption_result['brief_used']
        assert brief_used['task_type_notes'] is None


if __name__ == "__main__":
    pytest.main([__file__]) 