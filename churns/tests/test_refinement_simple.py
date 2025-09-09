#!/usr/bin/env python3
"""
Simplified Refinement Testing

Direct validation of refinement stages with temporary client injection.
This test confirms the stages work correctly before Phase 2.
"""

import os
import sys
import asyncio

# Add the churns package to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from churns.pipeline.context import PipelineContext
from churns.stages import text_repair


# def test_subject_repair():
#     """Test subject repair stage."""
#     print("🔧 Testing Subject Repair...")
    
#     # Create test context
#     ctx = PipelineContext()
#     ctx.run_id = "test_subject_123"
#     ctx.parent_run_id = "parent_123"
#     ctx.parent_image_id = "image_0"
#     ctx.parent_image_type = "original"
#     ctx.generation_index = 0
#     ctx.refinement_type = "subject"
#     ctx.instructions = "Replace subject with modern version"
#     ctx.cost_summary = {"stage_costs": []}
    
#     # Create test images
#     test_dir = tempfile.mkdtemp()
#     ctx.base_image_path = create_test_image(os.path.join(test_dir, "base.png"))
#     ctx.reference_image_path = create_test_image(os.path.join(test_dir, "ref.png"))
    
#     # Inject mock client
#     original_client = image_generation.image_gen_client
#     image_generation.image_gen_client = create_mock_client()
    
#     try:
#         # Run the stage
#         subject_repair.run(ctx)
        
#         # Validate results
#         assert ctx.refinement_result is not None
#         assert ctx.refinement_result["type"] == "subject_repair"
#         assert ctx.refinement_result["status"] == "completed"
#         assert ctx.refinement_cost > 0
        
#         print("   ✅ Subject repair completed successfully")
#         return True
        
#     except Exception as e:
#         print(f"   ❌ Subject repair failed: {e}")
#         return False
#     finally:
#         # Restore original client
#         image_generation.image_gen_client = original_client


async def test_text_repair():
    """Test text repair stage."""
    print("🔧 Testing Text Repair...")
    
    # Create test context
    ctx = PipelineContext()
    ctx.run_id = "f02a8587-3f11-4fcd-b44b-8272af68bbba"
    ctx.parent_run_id = "parent_123"
    ctx.parent_image_id = "image_0"
    ctx.parent_image_type = "original"
    ctx.base_image_path = "./data/runs/f02a8587-3f11-4fcd-b44b-8272af68bbba/edited_image_strategy_0.png"
    ctx.generation_index = 0
    ctx.refinement_type = "text"
    ctx.instructions = "Fix spelling and improve clarity"
    ctx.cost_summary = {"stage_costs": []}
    
    # Add original pipeline data for context enhancement
    ctx.original_pipeline_data = {
        "processing_context": {
            "image_analysis_result": {
            "main_subject": "Bottle of handcrafted soy milk",
            "secondary_elements": None,
            "setting_environment": None,
            "style_mood": None,
            "extracted_text": None
            },
            "suggested_marketing_strategies": [
            {
                "target_audience": "Eco-conscious millennials and Gen Z consumers who prioritize sustainable, plant-based diets and are active on social media platforms like Instagram.",
                "target_niche": "Plant-Based Beverages",
                "target_objective": "Increase brand awareness and engagement by highlighting the handcrafted quality and environmental benefits of the soy milk through visually appealing and informative Instagram posts.",
                "target_voice": "Authentic, friendly, and inspiring with a focus on sustainability, craftsmanship, and health-conscious living to connect deeply with the target audience."
            }
            ],
            "style_guidance_sets": [
            {
                "style_keywords": [
                "Bright Natural Light",
                "Minimalist Composition",
                "Neutral Earth Tones",
                "Scandinavian Still Life",
                "Product Focus"
                ],
                "style_description": "This style captures a bright and airy morning aesthetic, reminiscent of clean Scandinavian design. The focus is on crisp, natural lighting from a single source and a neutral color palette of whites, creams, and soft beiges, perhaps with a simple linen or ceramic prop. The artistic constraint is to maintain a minimalist composition with ample negative space to make the product the hero.",
                "marketing_impact": "The clean, authentic aesthetic builds trust with eco-conscious consumers by appearing transparent and unpretentious, aligning with the brand's authentic voice. The bright, high-quality visuals are highly effective for stopping the scroll on Instagram, driving engagement and reinforcing the premium, natural quality of the soy milk.",
                "source_strategy_index": 0
            }
            ],
            "generated_image_prompts": [
            {
                "visual_concept": {
                "main_subject": None,
                "composition_and_framing": "A perfectly centered, eye-level shot adhering to a symmetrical composition. The frame is a tight 1:1 square, focusing attention directly on the central subject area. The composition utilizes significant negative space around the subject, creating a clean, uncluttered, and breathable feel that allows the product to be the undisputed hero of the image.",
                "background_environment": "The background is a minimalist, light-toned surface, such as a whitewashed oak wood tabletop with a visible but subtle grain. The surface is clean and free of any distracting elements, contributing to the overall bright and airy Scandinavian aesthetic. In the far background, out of focus, is a plain, off-white wall, adding depth without complexity.",
                "foreground_elements": "In the immediate foreground, slightly to the side but not obscuring the main subject, rests a single, simple, handle-less ceramic tumbler in a matte bone-white finish. A small, artfully crumpled piece of natural, unbleached linen fabric sits partially under the tumbler, its texture adding a touch of organic softness to the scene. A few scattered, raw, dried soybeans are tastefully placed on the wooden surface to subtly hint at the product's natural origin.",
                "lighting_and_mood": "The scene is illuminated by bright, soft, natural morning light streaming from a single large window to the left of the frame. This creates gentle, elongated shadows to the right, adding depth and dimension without being harsh. The overall mood is serene, calm, pure, and authentic, evoking a sense of a peaceful, mindful morning ritual.",
                "color_palette": "A strictly neutral and earthy color palette dominated by shades of off-white, cream, soft beige from the linen, and the pale greyish-white of the ceramic and wood. The only accent colors are the pale, buttery yellow of the raw soybeans and the creamy white of the soy milk itself, creating a harmonious and sophisticated visual.",
                "visual_style": "Ultra-photorealistic Scandinavian Still Life. This style emphasizes hyper-clarity and a clean, minimalist aesthetic. The image is exceptionally bright and airy, achieved through the use of natural, directional light that feels authentic and un-staged. The focus is on the interplay of natural textures\u2014the subtle grain of the wood, the weave of the linen, the matte finish of the ceramic\u2014against the smooth, cool glass of the bottle. The composition is deliberate and balanced, using ample negative space to create a sense of calm and focus, making the product feel premium, transparent, and trustworthy.",
                "promotional_text_visuals": "Simple, elegant text is overlaid in the upper third of the image, placed within the negative space to ensure readability. The text reads 'Purely Plant-Based. Simply Handcrafted.' in a clean, minimalist, and slightly thin sans-serif font (like Montserrat Light). The color of the text is a soft, dark grey (charcoal) to stand out against the light background without being jarring. The typography is understated and sophisticated, reinforcing the brand's authentic voice.",
                "logo_visuals": None,
                "texture_and_details": "High-fidelity textures are crucial: the fine weave of the linen napkin, the subtle grain of the whitewashed wood, the matte, slightly porous surface of the ceramic cup, and crisp condensation beading on the cold glass bottle. Every detail is sharp and in focus, enhancing the tactile and premium quality of the scene.",
                "negative_elements": "Avoid any harsh, artificial lighting, deep shadows, vibrant or saturated colors, plastic materials, cluttered backgrounds, or overly complex props. The scene must remain minimalist and natural.",
                "creative_reasoning": "This concept directly addresses the marketing strategy by creating a visual that embodies the brand's voice: authentic, sustainable, and focused on craftsmanship. The Scandinavian Still Life style, with its bright natural light and minimalist composition, appeals directly to the eco-conscious millennial and Gen Z audience who value transparency and clean aesthetics. By placing the referenced soy milk bottle in this serene, premium context, we elevate its perceived quality and reinforce the 'handcrafted' message. The photorealistic clarity and product focus meet the Level 1 Creativity Guidance, ensuring the visual is effective for increasing brand awareness and engagement on Instagram. The text reinforces the key value propositions in a simple, elegant manner.",
                "suggested_alt_text": "A bottle of handcrafted soy milk sits on a light wooden table in soft morning light, next to a simple ceramic cup and linen."
                },
                "source_strategy_index": 0
            }
            ],
            "final_assembled_prompts": [
            {
                "index": 0,
                "prompt": "Edit the provided image. Preserve the main subject exactly as it is in the original image. Modify only the surrounding context (background, lighting, style, composition, etc.) to match this description: A perfectly centered, eye-level shot adhering to a symmetrical composition. The frame is a tight 1:1 square, focusing attention directly on the central subject area. The composition utilizes significant negative space around the subject, creating a clean, uncluttered, and breathable feel that allows the product to be the undisputed hero of the image. Background: The background is a minimalist, light-toned surface, such as a whitewashed oak wood tabletop with a visible but subtle grain. The surface is clean and free of any distracting elements, contributing to the overall bright and airy Scandinavian aesthetic. In the far background, out of focus, is a plain, off-white wall, adding depth without complexity. Foreground elements: In the immediate foreground, slightly to the side but not obscuring the main subject, rests a single, simple, handle-less ceramic tumbler in a matte bone-white finish. A small, artfully crumpled piece of natural, unbleached linen fabric sits partially under the tumbler, its texture adding a touch of organic softness to the scene. A few scattered, raw, dried soybeans are tastefully placed on the wooden surface to subtly hint at the product's natural origin. Lighting & Mood: The scene is illuminated by bright, soft, natural morning light streaming from a single large window to the left of the frame. This creates gentle, elongated shadows to the right, adding depth and dimension without being harsh. The overall mood is serene, calm, pure, and authentic, evoking a sense of a peaceful, mindful morning ritual. Color Palette: A strictly neutral and earthy color palette dominated by shades of off-white, cream, soft beige from the linen, and the pale greyish-white of the ceramic and wood. The only accent colors are the pale, buttery yellow of the raw soybeans and the creamy white of the soy milk itself, creating a harmonious and sophisticated visual. Visual Style: Ultra-photorealistic Scandinavian Still Life. This style emphasizes hyper-clarity and a clean, minimalist aesthetic. The image is exceptionally bright and airy, achieved through the use of natural, directional light that feels authentic and un-staged. The focus is on the interplay of natural textures\u2014the subtle grain of the wood, the weave of the linen, the matte finish of the ceramic\u2014against the smooth, cool glass of the bottle. The composition is deliberate and balanced, using ample negative space to create a sense of calm and focus, making the product feel premium, transparent, and trustworthy. Textures & Details: High-fidelity textures are crucial: the fine weave of the linen napkin, the subtle grain of the whitewashed wood, the matte, slightly porous surface of the ceramic cup, and crisp condensation beading on the cold glass bottle. Every detail is sharp and in focus, enhancing the tactile and premium quality of the scene. Promotional Text Visuals: Simple, elegant text is overlaid in the upper third of the image, placed within the negative space to ensure readability. The text reads 'Purely Plant-Based. Simply Handcrafted.' in a clean, minimalist, and slightly thin sans-serif font (like Montserrat Light). The color of the text is a soft, dark grey (charcoal) to stand out against the light background without being jarring. The typography is understated and sophisticated, reinforcing the brand's authentic voice. Avoid the following elements: Avoid any harsh, artificial lighting, deep shadows, vibrant or saturated colors, plastic materials, cluttered backgrounds, or overly complex props. The scene must remain minimalist and natural. IMPORTANT: Ensure the image strictly adheres to a 1:1 aspect ratio.",
                "assembly_type": "default_edit",
                "platform_aspect_ratio": "1:1",
                "supported_aspect_ratio": "1:1"
            }
            ],
            "generated_image_results": [
            {
                "index": 0,
                "status": "success",
                "result_path": "edited_image_strategy_0.png",
                "error_message": None,
                "prompt_tokens": 592
            }
            ],
            "image_assessment": [
            {
                "image_index": 0,
                "image_path": "data/runs/f02a8587-3f11-4fcd-b44b-8272af68bbba/edited_image_strategy_0.png",
                "assessment_scores": {
                "concept_adherence": 5,
                "subject_preservation": 3,
                "technical_quality": 5,
                "text_rendering_quality": 5
                },
                "assessment_justification": {
                "concept_adherence": "The image precisely follows the specified concept: a perfectly centered, eye-level 1:1 square composition with ample negative space. The light-toned wood grain surface and off-white background create the Scandinavian minimalist aesthetic. The handle-less matte bone-white ceramic tumbler, natural linen fabric, and scattered soybeans are all correctly placed and styled. Bright, soft natural light from the left produces gentle shadows and a serene, calm mood. The neutral earthy color palette and ultra-photorealistic textures align flawlessly with the visual reference.",
                "subject_preservation": "The soy milk bottle\u2019s shape, cap, liquid color, and general label design concept are recognizable and closely mirror the reference subject. However, the label\u2019s text at the bottom is distorted and unreadable, and the typography on the bottle differs noticeably from the reference. These inaccuracies affect the fidelity of the brand identity and detailed label elements.",
                "technical_quality": "The image exhibits flawless technical execution: high resolution, crisp focus on all key textures (wood grain, linen weave, ceramic finish), natural and even lighting, and no visible artifacts or distortions. The aspect ratio is correct, and the rendering is ultra-photorealistic.",
                "text_rendering_quality": "The overlaid promotional text is perfectly legible, correctly spelled, and well integrated into the negative space. The simple, clean font and subdued charcoal color maintain readability without distracting from the minimalist aesthetic, reinforcing the brand\u2019s authentic voice."
                },
                "general_score": 5.0,
                "needs_regeneration": False,
                "needs_subject_repair": True,
                "needs_text_repair": False
            }
            ],
            "llm_call_usage": {
            "image_eval": {
                "completion_tokens": 10,
                "prompt_tokens": 1914,
                "total_tokens": 1924,
                "completion_tokens_details": {
                "accepted_prediction_tokens": None,
                "audio_tokens": 0,
                "reasoning_tokens": 0,
                "rejected_prediction_tokens": None
                },
                "prompt_tokens_details": {
                "audio_tokens": 0,
                "cached_tokens": 1536
                }
            },
            "strategy_niche_id": {
                "completion_tokens": 25,
                "prompt_tokens": 267,
                "total_tokens": 292,
                "completion_tokens_details": {
                "accepted_prediction_tokens": None,
                "audio_tokens": 0,
                "reasoning_tokens": 0,
                "rejected_prediction_tokens": None
                },
                "prompt_tokens_details": {
                "audio_tokens": 0,
                "cached_tokens": 0
                }
            },
            "strategy_goal_gen": {
                "completion_tokens": 94,
                "prompt_tokens": 804,
                "total_tokens": 898,
                "completion_tokens_details": {
                "accepted_prediction_tokens": None,
                "audio_tokens": 0,
                "reasoning_tokens": 0,
                "rejected_prediction_tokens": None
                },
                "prompt_tokens_details": {
                "audio_tokens": 0,
                "cached_tokens": 0
                }
            },
            "style_guider": {
                "completion_tokens": 1250,
                "prompt_tokens": 892,
                "total_tokens": 2142,
                "completion_tokens_details": {
                "accepted_prediction_tokens": None,
                "audio_tokens": 0,
                "reasoning_tokens": 0,
                "rejected_prediction_tokens": None
                },
                "prompt_tokens_details": {
                "audio_tokens": 0,
                "cached_tokens": 0
                }
            },
            "creative_expert_strategy_0": {
                "completion_tokens": 2501,
                "prompt_tokens": 2553,
                "total_tokens": 5054,
                "completion_tokens_details": {
                "accepted_prediction_tokens": None,
                "audio_tokens": 0,
                "reasoning_tokens": 0,
                "rejected_prediction_tokens": None
                },
                "prompt_tokens_details": {
                "audio_tokens": 0,
                "cached_tokens": 0
                }
            },
            "image_assessment": {
                "prompt_tokens": 5676,
                "completion_tokens": 1290,
                "total_tokens": 6966,
                "image_tokens": 3281,
                "text_tokens": 2395,
                "model": "openai/o4-mini",
                "assessment_count": 1,
                "individual_assessments": [
                {
                    "image_index": 0,
                    "prompt_tokens": 5676,
                    "completion_tokens": 1290,
                    "total_tokens": 6966,
                    "image_tokens": 3281,
                    "text_tokens": 2395,
                    "image_breakdown": {
                    "model_id": "openai/o4-mini",
                    "detail_level": "high",
                    "images": [
                        {
                        "type": "assessment_target",
                        "tokens": 1761
                        },
                        {
                        "type": "reference_image",
                        "tokens": 1520
                        }
                    ],
                    "total_image_tokens": 3281
                    }
                }
                ]
            }
            },
            "cost_summary": {
            "total_pipeline_cost_usd": 0.10038464999999999,
            "stage_costs": [
                {
                "stage_name": "image_eval",
                "cost_usd": 0.0007775999999999999,
                "duration_seconds": 1.6263062953948975
                },
                {
                "stage_name": "strategy",
                "cost_usd": 0.0005712,
                "duration_seconds": 3.7758796215057373
                },
                {
                "stage_name": "style_guide",
                "cost_usd": 0.013615,
                "duration_seconds": 13.50437307357788
                },
                {
                "stage_name": "creative_expert",
                "cost_usd": 0.02820125,
                "duration_seconds": 26.68468165397644
                },
                {
                "stage_name": "prompt_assembly",
                "cost_usd": 0.0001,
                "duration_seconds": 0.09391260147094727
                },
                {
                "stage_name": "image_generation",
                "cost_usd": 0.0452,
                "duration_seconds": 21.42761731147766
                },
                {
                "stage_name": "image_assessment",
                "cost_usd": 0.0119196,
                "duration_seconds": 15.123861074447632
                }
            ],
            "total_pipeline_duration_seconds": 82.2366316318512
            }
        }
    }
    
    ctx.user_inputs = {
        "prompt": None,
        "image_reference": {
            "filename": "eesoy.jpeg",
            "content_type": "image/jpeg",
            "size_bytes": 40684,
            "instruction": None,
            "saved_image_path_in_run_dir": "data/runs/f02a8587-3f11-4fcd-b44b-8272af68bbba/input_eesoy.jpeg",
            "image_content_base64": "[[Removed for save]]"
        },
        "render_text": True,
        "apply_branding":  True,
        "branding_elements": 'WAVE EESOY',
        "task_description": 'Handcrafted plant based soy milk',
        "marketing_goals": None
    }
    try:
        # Run the stage
        await text_repair.run(ctx)
        
        # Validate results
        assert ctx.refinement_result is not None
        assert ctx.refinement_result["type"] == "text_repair"
        assert ctx.refinement_result["status"] == "completed"
        assert ctx.refinement_cost > 0
        
        print("   ✅ Text repair completed successfully")
        return True
        
    except Exception as e:
        print(f"   ❌ Text repair failed: {e}")
        return False



# def test_utilities():
#     """Test utility functions."""
#     print("🔧 Testing Shared Utilities...")
    
#     from churns.stages.refinement_utils import (
#         calculate_refinement_cost,
#         create_mask_from_coordinates,
#     )
    
#     try:
#         # Test cost calculation
#         ctx = PipelineContext()
#         cost = calculate_refinement_cost(ctx, "test prompt")
#         assert cost > 0
        
#         # Test mask creation
#         ctx.mask_coordinates = json.dumps({
#             "type": "rectangle",
#             "x1": 0.25, "y1": 0.25,
#             "x2": 0.75, "y2": 0.75
#         })
#         mask = create_mask_from_coordinates(ctx, (200, 200))
#         assert mask is not None
        
        
#         print("   ✅ All utilities working correctly")
#         return True
        
#     except Exception as e:
#         print(f"   ❌ Utilities test failed: {e}")
#         return False


async def main():
    """Run all tests."""
    print("🧪 Running Simplified Refinement Tests")
    print("=" * 50)
    
    tests = [
        test_text_repair, 
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if await test():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"   💥 Test {test.__name__} crashed: {e}")
            failed += 1
    
    print("\n" + "=" * 50)
    print("📊 FINAL RESULTS")
    print("=" * 50)
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    
    if failed == 0:
        print("\n🎉 ALL TESTS PASSED!")
        print("✅ Refinement stages are working correctly")
        print("🚀 Ready to proceed with Phase 2!")
    else:
        print(f"\n⚠️  {failed} tests failed")
        print("🔍 Check the error messages above")
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    asyncio.run(main()) 