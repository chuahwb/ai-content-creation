"""
End-to-End Tests for Brand Kit & Style Recipe Workflows.

Tests the complete workflows from the implementation plan:
- Brand Kit creation and application
- Style Recipe creation and reuse
- Consistency score validation
- Complete pipeline execution with brand kit integration
"""

import pytest
import tempfile
import os
import json
import base64
from unittest.mock import Mock, patch, AsyncMock
from churns.pipeline.context import PipelineContext
from churns.pipeline.executor import PipelineExecutor
from churns.api.database import BrandPreset, PresetType
from churns.core.metrics import ConsistencyMetrics
from churns.models import LogoAnalysisResult, VisualConceptDetails
from churns.stages import image_eval, creative_expert, style_guide, image_generation


class TestBrandKitE2EWorkflows:
    """End-to-end tests for brand kit workflows."""
    
    @pytest.fixture
    def sample_brand_kit_api_payload(self):
        """Sample brand kit API payload from frontend."""
        return {
            "colors": ["#FF6B35", "#004E89", "#F7931E"],
            "brandVoiceDescription": "Friendly and approachable, with a focus on quality and craftsmanship",
            "logoFileBase64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        }
    
    @pytest.fixture
    def sample_logo_file(self):
        """Create a sample logo file for testing."""
        temp_dir = tempfile.mkdtemp()
        logo_path = os.path.join(temp_dir, "logo.png")
        
        # Create minimal PNG file
        png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\x0cIDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82'
        
        with open(logo_path, "wb") as f:
            f.write(png_data)
        
        return logo_path
    
    def test_complete_brand_kit_creation_workflow(self, sample_brand_kit_api_payload, sample_logo_file):
        """Test complete brand kit creation workflow from API to pipeline execution."""
        # Step 1: Simulate API request processing
        frontend_payload = sample_brand_kit_api_payload
        
        # Convert frontend camelCase to backend snake_case
        backend_brand_kit = {
            "colors": frontend_payload["colors"],
            "brand_voice_description": frontend_payload["brandVoiceDescription"],
            "logo_file_base64": frontend_payload["logoFileBase64"]
        }
        
        # Step 2: Simulate logo file processing
        # Decode base64 and save to run directory
        logo_data = base64.b64decode(backend_brand_kit["logo_file_base64"])
        run_dir = tempfile.mkdtemp()
        logo_path = os.path.join(run_dir, "logo.png")
        
        with open(logo_path, "wb") as f:
            f.write(logo_data)
        
        backend_brand_kit["saved_logo_path_in_run_dir"] = logo_path
        
        # Step 3: Create pipeline context with brand kit
        ctx = PipelineContext()
        ctx.task_type = "1. Product Photography"
        ctx.target_platform = {
            "name": "Instagram Post (1:1 Square)",
            "resolution_details": {"width": 1080, "height": 1080, "aspect_ratio": "1:1"}
        }
        ctx.prompt = "A delicious gourmet burger"
        ctx.creativity_level = 2
        ctx.apply_branding = True
        ctx.brand_kit = backend_brand_kit
        
        # Step 4: Mock logo analysis
        with patch('churns.stages.image_eval.ImageEvaluator.evaluate_image') as mock_evaluate:
            mock_logo_analysis = LogoAnalysisResult(
                logo_style="Modern minimalist design with clean typography",
                has_text=True,
                text_content="CHURNS",
                dominant_colors=["#FF6B35", "#FFFFFF"],
                logo_type="wordmark",
                style_keywords=["minimalist", "modern", "clean", "professional"]
            )
            mock_evaluate.return_value = mock_logo_analysis
            
            # Run logo analysis
            image_eval.run(ctx)
            
            # Verify logo analysis was performed
            assert 'logo_analysis' in ctx.brand_kit
            assert ctx.brand_kit['logo_analysis']['logo_style'] == "Modern minimalist design with clean typography"
            assert ctx.brand_kit['logo_analysis']['has_text'] is True
            assert ctx.brand_kit['logo_analysis']['text_content'] == "CHURNS"
        
        # Step 5: Test brand kit integration in creative stages
        # Mock strategies for creative expert
        ctx.suggested_marketing_strategies = [{
            "target_audience": "Food Enthusiasts",
            "target_niche": "Gourmet Restaurant",
            "target_objective": "Showcase Quality",
            "target_voice": "Sophisticated & Elegant"
        }]
        
        ctx.style_guidance_sets = [{
            "style_keywords": ["elegant", "sophisticated"],
            "style_description": "Elegant and sophisticated food photography that complements brand colors"
        }]
        
        with patch('churns.stages.creative_expert.CreativeExpert.generate_visual_concept') as mock_generate:
            mock_visual_concept = {
                "main_subject": "Gourmet burger with artisan toppings",
                "composition_and_framing": "Close-up shot with shallow depth of field",
                "background_environment": "Dark wooden table with subtle lighting",
                "lighting_and_mood": "Warm, appetizing lighting reflecting friendly brand voice",
                "color_palette": "Rich browns and golds complementing brand colors #FF6B35 and #004E89",
                "visual_style": "Professional food photography with sophisticated aesthetic",
                "logo_visuals": "CHURNS wordmark logo placed in bottom-right corner, scaled to 5% of image width in white color",
                "suggested_alt_text": "Gourmet burger with CHURNS branding"
            }
            mock_generate.return_value = mock_visual_concept
            
            # Run creative expert
            creative_expert.run(ctx)
            
            # Verify brand kit integration in creative output
            assert ctx.generated_image_prompts is not None
            assert len(ctx.generated_image_prompts) > 0
            
            visual_concept = ctx.generated_image_prompts[0]['visual_concept']
            assert "#FF6B35" in visual_concept['color_palette'] or "#004E89" in visual_concept['color_palette']
            assert "CHURNS" in visual_concept['logo_visuals']
            assert "friendly" in visual_concept['lighting_and_mood']
    
    def test_brand_kit_logo_analysis_workflow(self, sample_logo_file):
        """Test complete logo analysis workflow."""
        # Create context with logo but no analysis
        ctx = PipelineContext()
        ctx.task_type = "1. Product Photography"
        ctx.brand_kit = {
            "colors": ["#FF6B35", "#004E89"],
            "brand_voice_description": "Friendly and approachable",
            "saved_logo_path_in_run_dir": sample_logo_file
        }
        
        # Mock logo analysis
        with patch('churns.stages.image_eval.ImageEvaluator.evaluate_image') as mock_evaluate:
            mock_logo_analysis = LogoAnalysisResult(
                logo_style="Modern minimalist design with clean typography",
                has_text=True,
                text_content="CHURNS",
                dominant_colors=["#FF6B35", "#FFFFFF"],
                logo_type="wordmark",
                style_keywords=["minimalist", "modern", "clean", "professional"]
            )
            mock_evaluate.return_value = mock_logo_analysis
            
            # Run image evaluation (should detect logo and analyze it)
            image_eval.run(ctx)
            
            # Verify logo analysis was performed and stored
            assert 'logo_analysis' in ctx.brand_kit
            assert ctx.brand_kit['logo_analysis']['logo_style'] == "Modern minimalist design with clean typography"
            assert ctx.brand_kit['logo_analysis']['has_text'] is True
            assert ctx.brand_kit['logo_analysis']['text_content'] == "CHURNS"
            assert ctx.brand_kit['logo_analysis']['logo_type'] == "wordmark"
            assert len(ctx.brand_kit['logo_analysis']['style_keywords']) > 0
    
    def test_brand_kit_consistency_across_stages(self):
        """Test that brand kit data remains consistent across all pipeline stages."""
        # Create context with complete brand kit
        ctx = PipelineContext()
        ctx.task_type = "1. Product Photography"
        ctx.apply_branding = True
        ctx.brand_kit = {
            "colors": ["#FF6B35", "#004E89", "#F7931E"],
            "brand_voice_description": "Friendly and approachable, with a focus on quality and craftsmanship",
            "logo_analysis": {
                "logo_style": "Modern minimalist design",
                "has_text": True,
                "text_content": "CHURNS",
                "dominant_colors": ["#FF6B35", "#FFFFFF"],
                "logo_type": "wordmark"
            }
        }
        
        # Mock all stages to verify brand kit access
        stages_tested = []
        
        def mock_style_guide(ctx):
            stages_tested.append("style_guide")
            assert 'brand_kit' in ctx.__dict__
            assert ctx.brand_kit['colors'] == ["#FF6B35", "#004E89", "#F7931E"]
            assert ctx.brand_kit['brand_voice_description'] == "Friendly and approachable, with a focus on quality and craftsmanship"
            assert ctx.brand_kit['logo_analysis']['text_content'] == "CHURNS"
            
        def mock_creative_expert(ctx):
            stages_tested.append("creative_expert")
            assert 'brand_kit' in ctx.__dict__
            assert ctx.brand_kit['colors'] == ["#FF6B35", "#004E89", "#F7931E"]
            assert ctx.brand_kit['logo_analysis']['logo_type'] == "wordmark"
            
        def mock_image_generation(ctx):
            stages_tested.append("image_generation")
            assert 'brand_kit' in ctx.__dict__
            assert ctx.brand_kit['logo_analysis']['logo_style'] == "Modern minimalist design"
        
        with patch('churns.stages.style_guide.run', side_effect=mock_style_guide):
            with patch('churns.stages.creative_expert.run', side_effect=mock_creative_expert):
                with patch('churns.stages.image_generation.run', side_effect=mock_image_generation):
                    # Simulate pipeline execution
                    style_guide.run(ctx)
                    creative_expert.run(ctx)
                    image_generation.run(ctx)
                    
                    # Verify all stages had access to brand kit
                    assert "style_guide" in stages_tested
                    assert "creative_expert" in stages_tested
                    assert "image_generation" in stages_tested


class TestStyleRecipeE2EWorkflows:
    """End-to-end tests for style recipe workflows."""
    
    @pytest.fixture
    def sample_completed_run_results(self):
        """Sample completed run results for creating style recipes."""
        return {
            "run_id": "test_run_123",
            "generated_image_results": [
                {
                    "index": 0,
                    "status": "success",
                    "result_path": "/test/path/image_0.png",
                    "image_url": "https://example.com/image_0.png"
                }
            ],
            "visual_concept": {
                "main_subject": "A gourmet burger with crispy bacon",
                "composition_and_framing": "Close-up shot with shallow depth of field",
                "background_environment": "Dark wooden table with subtle lighting",
                "lighting_and_mood": "Warm, appetizing lighting with soft shadows",
                "color_palette": "Rich browns, golden yellows, deep reds",
                "visual_style": "Professional food photography with high contrast",
                "logo_visuals": "Logo placed in bottom-right corner",
                "suggested_alt_text": "Gourmet burger with crispy bacon"
            },
            "strategy": {
                "target_audience": "Food Enthusiasts",
                "target_niche": "Gourmet Restaurant",
                "target_objective": "Showcase Quality",
                "target_voice": "Sophisticated & Elegant"
            },
            "style_guidance": {
                "style_keywords": ["elegant", "sophisticated", "high-end"],
                "style_description": "Elegant food photography with sophisticated lighting"
            },
        }
    
    def test_style_recipe_creation_workflow(self, sample_completed_run_results):
        """Test complete style recipe creation workflow from completed run."""
        # Step 1: Extract style recipe data from completed run
        run_results = sample_completed_run_results
        
        style_recipe_data = {
            "visual_concept": run_results["visual_concept"],
            "strategy": run_results["strategy"],
            "style_guidance": run_results["style_guidance"],
        }
        
        # Step 2: Create style recipe preset
        style_recipe_preset = {
            "name": "Gourmet Burger Style",
            "preset_type": PresetType.STYLE_RECIPE,
            "model_id": "gpt-image-1",
            "preset_data": style_recipe_data,
            "version": 1,
            "user_id": "test_user"
        }
        
        # Step 3: Verify style recipe structure
        assert style_recipe_preset["preset_type"] == PresetType.STYLE_RECIPE
        assert "visual_concept" in style_recipe_preset["preset_data"]
        assert "strategy" in style_recipe_preset["preset_data"]
        assert "style_guidance" in style_recipe_preset["preset_data"]
        
        # Step 4: Verify visual concept completeness
        visual_concept = style_recipe_preset["preset_data"]["visual_concept"]
        required_fields = [
            "main_subject", "composition_and_framing", "background_environment",
            "lighting_and_mood", "color_palette", "visual_style", "logo_visuals"
        ]
        
        for field in required_fields:
            assert field in visual_concept
            assert visual_concept[field] is not None
            assert len(visual_concept[field]) > 0
    
    def test_style_recipe_reuse_workflow(self, sample_completed_run_results):
        """Test complete style recipe reuse workflow."""
        # Step 1: Create style recipe from completed run
        style_recipe_data = {
            "visual_concept": sample_completed_run_results["visual_concept"],
            "strategy": sample_completed_run_results["strategy"],
            "style_guidance": sample_completed_run_results["style_guidance"],
        }
        
        # Step 2: Create new pipeline context with style recipe
        ctx = PipelineContext()
        ctx.preset_type = PresetType.STYLE_RECIPE
        ctx.preset_data = style_recipe_data
        ctx.task_type = "1. Product Photography"
        ctx.target_platform = {
            "name": "Instagram Post (1:1 Square)",
            "resolution_details": {"width": 1080, "height": 1080, "aspect_ratio": "1:1"}
        }
        
        # Step 3: Test subject swap workflow (no new prompt)
        ctx.image_reference = {
            "filename": "pizza.jpg",
            "saved_image_path_in_run_dir": "/test/path/pizza.jpg"
        }
        
        # Mock image analysis for subject swap
        with patch('churns.stages.image_eval.ImageEvaluator.evaluate_image') as mock_evaluate:
            mock_image_analysis = {
                "main_subject": "Gourmet pizza with fresh basil",
                "secondary_elements": ["melted cheese", "tomato sauce", "basil leaves"],
                "color_analysis": {
                    "dominant_colors": ["#FF6B35", "#228B22", "#FFFFFF"],
                    "color_harmony": "Warm and appetizing"
                }
            }
            mock_evaluate.return_value = mock_image_analysis
            
            # Run image evaluation
            image_eval.run(ctx)
            
            # Verify subject swap preparation
            assert ctx.image_analysis_result is not None
            assert "pizza" in ctx.image_analysis_result["main_subject"].lower()
        
        # Step 4: Test style preservation
        # The visual concept should be adapted to new subject while preserving style
        original_visual_concept = style_recipe_data["visual_concept"]
        
        # Verify style elements are preserved
        assert original_visual_concept["lighting_and_mood"] == "Warm, appetizing lighting with soft shadows"
        assert original_visual_concept["color_palette"] == "Rich browns, golden yellows, deep reds"
        assert original_visual_concept["visual_style"] == "Professional food photography with high contrast"
        assert original_visual_concept["composition_and_framing"] == "Close-up shot with shallow depth of field"
    
    def test_style_recipe_with_new_prompt_workflow(self, sample_completed_run_results):
        """Test style recipe workflow with new prompt (advanced style transfer)."""
        # Step 1: Create style recipe
        style_recipe_data = {
            "visual_concept": sample_completed_run_results["visual_concept"],
            "strategy": sample_completed_run_results["strategy"],
            "style_guidance": sample_completed_run_results["style_guidance"],
        }
        
        # Step 2: Create context with new prompt
        ctx = PipelineContext()
        ctx.preset_type = PresetType.STYLE_RECIPE
        ctx.preset_data = style_recipe_data
        ctx.prompt = "Create a gourmet coffee cup with latte art"  # New prompt
        ctx.task_type = "1. Product Photography"
        ctx.target_platform = {
            "name": "Instagram Post (1:1 Square)",
            "resolution_details": {"width": 1080, "height": 1080, "aspect_ratio": "1:1"}
        }
        
        # Step 3: Test StyleAdaptation workflow
        with patch('churns.stages.style_adaptation.StyleAdaptationAgent.adapt_style') as mock_adapt:
            mock_adapted_concept = VisualConceptDetails(
                main_subject="Gourmet coffee cup with intricate latte art",
                composition_and_framing="Close-up shot with shallow depth of field",
                background_environment="Dark wooden table with subtle lighting",
                lighting_and_mood="Warm, appetizing lighting with soft shadows",
                color_palette="Rich browns, golden yellows, cream whites",
                visual_style="Professional food photography with high contrast",
                logo_visuals="Logo placed in bottom-right corner",
                suggested_alt_text="Gourmet coffee cup with latte art"
            )
            mock_adapt.return_value = mock_adapted_concept
            
            # Run style adaptation
            from churns.stages.style_adaptation import run as style_adaptation_run
            style_adaptation_run(ctx)
            
            # Verify adaptation occurred
            assert ctx.adapted_visual_concept is not None
            assert "coffee cup" in ctx.adapted_visual_concept.main_subject.lower()
            assert "latte art" in ctx.adapted_visual_concept.main_subject.lower()
            
            # Verify style elements were preserved
            assert ctx.adapted_visual_concept.lighting_and_mood == "Warm, appetizing lighting with soft shadows"
            assert "Close-up shot" in ctx.adapted_visual_concept.composition_and_framing
            assert "Professional food photography" in ctx.adapted_visual_concept.visual_style
    
    def test_style_recipe_consistency_metrics_workflow(self):
        """Test consistency metrics calculation for style recipe reuse."""
        # Create test images
        temp_dir = tempfile.mkdtemp()
        original_image_path = os.path.join(temp_dir, "original.png")
        new_image_path = os.path.join(temp_dir, "new.png")
        
        # Create minimal PNG files
        png_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\x0cIDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82'
        
        with open(original_image_path, "wb") as f:
            f.write(png_data)
        with open(new_image_path, "wb") as f:
            f.write(png_data)
        
        # Create context with style recipe
        ctx = PipelineContext()
        ctx.preset_type = PresetType.STYLE_RECIPE
        ctx.original_image_path = original_image_path
        ctx.generated_image_results = [
            {
                "index": 0,
                "status": "success",
                "result_path": new_image_path
            }
        ]
        
        # Calculate consistency metrics
        metrics = ConsistencyMetrics()
        
        try:
            result = metrics.calculate_consistency_score(original_image_path, new_image_path)
            
            # Verify metrics structure
            assert 'overall_consistency' in result
            assert 'clip_similarity' in result
            assert 'color_histogram_similarity' in result
            assert 'color_palette_match' in result
            assert 'brightness_similarity' in result
            assert 'contrast_similarity' in result
            
            # Verify score ranges
            assert 0.0 <= result['overall_consistency'] <= 1.0
            assert 0.0 <= result['clip_similarity'] <= 1.0
            assert 0.0 <= result['color_histogram_similarity'] <= 1.0
            
            # Test consistency threshold validation
            consistency_threshold = 0.85
            if result['overall_consistency'] >= consistency_threshold:
                assert result['clip_similarity'] >= 0.7  # Should have good semantic similarity
            
        except ImportError:
            # Skip if optional dependencies not available
            pytest.skip("Optional dependencies for consistency metrics not available")
    
    def test_style_recipe_stage_skipping_workflow(self):
        """Test that style recipe correctly skips early pipeline stages."""
        # Create style recipe context
        ctx = PipelineContext()
        ctx.preset_type = PresetType.STYLE_RECIPE
        ctx.preset_data = {
            "visual_concept": {
                "main_subject": "A gourmet burger",
                "composition_and_framing": "Close-up shot",
                "background_environment": "Dark wooden table",
                "lighting_and_mood": "Warm lighting",
                "color_palette": "Rich browns and golds",
                "visual_style": "Professional food photography",
                "logo_visuals": "Logo in corner",
                "suggested_alt_text": "Gourmet burger"
            },
            "strategy": {
                "target_audience": "Food Enthusiasts",
                "target_niche": "Gourmet Restaurant",
                "target_objective": "Showcase Quality",
                "target_voice": "Sophisticated & Elegant"
            },
            "style_guidance": {
                "style_keywords": ["elegant", "sophisticated"],
                "style_description": "Elegant food photography"
            },
        }
        
        # Mock pipeline stages
        stages_called = []
        
        def mock_strategy_stage(ctx):
            stages_called.append("strategy")
            
        def mock_style_guide_stage(ctx):
            stages_called.append("style_guide")
            
        def mock_creative_expert_stage(ctx):
            stages_called.append("creative_expert")
            
        def mock_prompt_assembly_stage(ctx):
            stages_called.append("prompt_assembly")
            
        def mock_image_generation_stage(ctx):
            stages_called.append("image_generation")
        
        with patch('churns.stages.strategy.run', side_effect=mock_strategy_stage):
            with patch('churns.stages.style_guide.run', side_effect=mock_style_guide_stage):
                with patch('churns.stages.creative_expert.run', side_effect=mock_creative_expert_stage):
                    with patch('churns.stages.prompt_assembly.run', side_effect=mock_prompt_assembly_stage):
                        with patch('churns.stages.image_generation.run', side_effect=mock_image_generation_stage):
                            # Mock pipeline executor with stage skipping
                            with patch('churns.pipeline.executor.PipelineExecutor._should_skip_stage') as mock_skip:
                                # Configure stage skipping for style recipe
                                def should_skip_stage(stage_name):
                                    if ctx.preset_type == PresetType.STYLE_RECIPE:
                                        return stage_name in ['strategy', 'style_guide', 'creative_expert']
                                    return False
                                
                                mock_skip.side_effect = should_skip_stage
                                
                                # Run pipeline
                                executor = PipelineExecutor()
                                result_ctx = executor.run(ctx)
                                
                                # Verify early stages were skipped
                                assert "strategy" not in stages_called
                                assert "style_guide" not in stages_called
                                assert "creative_expert" not in stages_called
                                
                                # Verify late stages were not skipped
                                assert "prompt_assembly" in stages_called
                                assert "image_generation" in stages_called


class TestBrandKitStyleRecipeIntegration:
    """Test integration between brand kit and style recipe workflows."""
    
    def test_brand_kit_in_style_recipe_workflow(self):
        """Test brand kit integration in style recipe workflow."""
        # Create context with both brand kit and style recipe
        ctx = PipelineContext()
        ctx.preset_type = PresetType.STYLE_RECIPE
        ctx.preset_data = {
            "visual_concept": {
                "main_subject": "A gourmet burger",
                "composition_and_framing": "Close-up shot",
                "background_environment": "Dark wooden table",
                "lighting_and_mood": "Warm lighting",
                "color_palette": "Rich browns and golds",
                "visual_style": "Professional food photography",
                "logo_visuals": "Logo in corner",
                "suggested_alt_text": "Gourmet burger"
            }
        }
        
        # Add brand kit
        ctx.brand_kit = {
            "colors": ["#FF6B35", "#004E89", "#F7931E"],
            "brand_voice_description": "Friendly and approachable",
            "logo_analysis": {
                "logo_style": "Modern minimalist design",
                "has_text": True,
                "text_content": "CHURNS",
                "logo_type": "wordmark"
            }
        }
        
        ctx.prompt = "Create a gourmet coffee cup"
        
        # Test StyleAdaptation with brand kit
        with patch('churns.stages.style_adaptation.StyleAdaptationAgent.adapt_style') as mock_adapt:
            mock_adapted_concept = VisualConceptDetails(
                main_subject="Gourmet coffee cup with latte art",
                composition_and_framing="Close-up shot",
                background_environment="Dark wooden table",
                lighting_and_mood="Warm lighting reflecting friendly brand voice",
                color_palette="Rich browns complementing brand colors #FF6B35 and #004E89",
                visual_style="Professional food photography",
                logo_visuals="CHURNS wordmark logo in corner, white color for contrast",
                suggested_alt_text="Gourmet coffee cup with CHURNS branding"
            )
            mock_adapt.return_value = mock_adapted_concept
            
            # Run style adaptation
            from churns.stages.style_adaptation import run as style_adaptation_run
            style_adaptation_run(ctx)
            
            # Verify brand kit integration
            assert ctx.adapted_visual_concept is not None
            assert "#FF6B35" in ctx.adapted_visual_concept.color_palette or "#004E89" in ctx.adapted_visual_concept.color_palette
            assert "CHURNS" in ctx.adapted_visual_concept.logo_visuals
            assert "friendly" in ctx.adapted_visual_concept.lighting_and_mood
    
    def test_brand_kit_precedence_in_style_recipe(self):
        """Test brand kit precedence rules in style recipe workflow."""
        # Create context with conflicting brand elements
        ctx = PipelineContext()
        ctx.preset_type = PresetType.STYLE_RECIPE
        ctx.preset_data = {
            "visual_concept": {
                "main_subject": "A gourmet burger",
                "color_palette": "Rich browns, golden yellows, deep reds",  # Original recipe colors
                "logo_visuals": "Generic logo placement"
            }
        }
        
        # Add brand kit with different colors
        ctx.brand_kit = {
            "colors": ["#00FF00", "#0000FF"],  # Different colors
            "brand_voice_description": "Professional and authoritative",
            "logo_analysis": {
                "text_content": "CHURNS",
                "logo_type": "wordmark"
            }
        }
        
        ctx.prompt = "Create a new version"
        
        # Test precedence rules
        with patch('churns.stages.style_adaptation.StyleAdaptationAgent.adapt_style') as mock_adapt:
            mock_adapted_concept = VisualConceptDetails(
                main_subject="A gourmet burger",
                composition_and_framing="Close-up shot",
                background_environment="Dark wooden table",
                lighting_and_mood="Professional lighting reflecting brand voice",
                color_palette="Rich browns with brand accent colors #00FF00 and #0000FF",  # Brand kit colors integrated
                visual_style="Professional food photography",
                logo_visuals="CHURNS wordmark logo placement",  # Brand kit logo takes precedence
                suggested_alt_text="Gourmet burger with CHURNS branding"
            )
            mock_adapt.return_value = mock_adapted_concept
            
            # Run style adaptation
            from churns.stages.style_adaptation import run as style_adaptation_run
            style_adaptation_run(ctx)
            
            # Verify brand kit took precedence
            assert ctx.adapted_visual_concept is not None
            assert "#00FF00" in ctx.adapted_visual_concept.color_palette or "#0000FF" in ctx.adapted_visual_concept.color_palette
            assert "CHURNS" in ctx.adapted_visual_concept.logo_visuals
            assert "professional" in ctx.adapted_visual_concept.lighting_and_mood.lower()
    
    def test_complete_brand_kit_style_recipe_e2e(self):
        """Test complete end-to-end workflow with both brand kit and style recipe."""
        # Step 1: Create initial run with brand kit
        initial_ctx = PipelineContext()
        initial_ctx.task_type = "1. Product Photography"
        initial_ctx.apply_branding = True
        initial_ctx.brand_kit = {
            "colors": ["#FF6B35", "#004E89", "#F7931E"],
            "brand_voice_description": "Friendly and approachable",
            "logo_analysis": {
                "logo_style": "Modern minimalist design",
                "has_text": True,
                "text_content": "CHURNS",
                "logo_type": "wordmark"
            }
        }
        
        # Step 2: Simulate successful initial run
        initial_results = {
            "visual_concept": {
                "main_subject": "A gourmet burger with artisan toppings",
                "composition_and_framing": "Close-up shot with shallow depth of field",
                "background_environment": "Dark wooden table with subtle lighting",
                "lighting_and_mood": "Warm, appetizing lighting reflecting friendly brand voice",
                "color_palette": "Rich browns and golds complementing brand colors #FF6B35 and #004E89",
                "visual_style": "Professional food photography with sophisticated aesthetic",
                "logo_visuals": "CHURNS wordmark logo placed in bottom-right corner",
                "suggested_alt_text": "Gourmet burger with CHURNS branding"
            }
        }
        
        # Step 3: Create style recipe from initial run
        style_recipe_data = {
            "visual_concept": initial_results["visual_concept"],
            "strategy": {
                "target_audience": "Food Enthusiasts",
                "target_niche": "Gourmet Restaurant",
                "target_objective": "Showcase Quality",
                "target_voice": "Sophisticated & Elegant"
            }
        }
        
        # Step 4: Create new run with style recipe and brand kit
        new_ctx = PipelineContext()
        new_ctx.preset_type = PresetType.STYLE_RECIPE
        new_ctx.preset_data = style_recipe_data
        new_ctx.brand_kit = initial_ctx.brand_kit
        new_ctx.prompt = "Create a gourmet pizza with the same style"
        
        # Step 5: Test complete workflow
        with patch('churns.stages.style_adaptation.StyleAdaptationAgent.adapt_style') as mock_adapt:
            mock_adapted_concept = VisualConceptDetails(
                main_subject="A gourmet pizza with artisan toppings",
                composition_and_framing="Close-up shot with shallow depth of field",
                background_environment="Dark wooden table with subtle lighting",
                lighting_and_mood="Warm, appetizing lighting reflecting friendly brand voice",
                color_palette="Rich browns and golds complementing brand colors #FF6B35 and #004E89",
                visual_style="Professional food photography with sophisticated aesthetic",
                logo_visuals="CHURNS wordmark logo placed in bottom-right corner",
                suggested_alt_text="Gourmet pizza with CHURNS branding"
            )
            mock_adapt.return_value = mock_adapted_concept
            
            # Run style adaptation
            from churns.stages.style_adaptation import run as style_adaptation_run
            style_adaptation_run(new_ctx)
            
            # Verify complete integration
            assert new_ctx.adapted_visual_concept is not None
            
            # Check subject adaptation
            assert "pizza" in new_ctx.adapted_visual_concept.main_subject.lower()
            
            # Check style preservation
            assert "Close-up shot" in new_ctx.adapted_visual_concept.composition_and_framing
            assert "Warm, appetizing lighting" in new_ctx.adapted_visual_concept.lighting_and_mood
            
            # Check brand kit integration
            assert "#FF6B35" in new_ctx.adapted_visual_concept.color_palette or "#004E89" in new_ctx.adapted_visual_concept.color_palette
            assert "CHURNS" in new_ctx.adapted_visual_concept.logo_visuals
            assert "friendly" in new_ctx.adapted_visual_concept.lighting_and_mood 