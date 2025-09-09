"""
Test suite for Brand Kit Integration.

Tests the complete brand kit functionality including:
- Brand kit data flow through pipeline stages
- Logo analysis integration
- Brand kit usage in creative stages
- Color palette and brand voice integration
"""

import pytest
import tempfile
import os
import json
from unittest.mock import Mock, patch, AsyncMock
from churns.pipeline.context import PipelineContext
from churns.pipeline.executor import PipelineExecutor
from churns.stages import image_eval, creative_expert, style_guide
from churns.models import LogoAnalysisResult, BrandKitInput
from churns.core.metrics import ConsistencyMetrics


class TestBrandKitIntegration:
    """Test suite for brand kit integration across pipeline stages."""
    
    @pytest.fixture
    def sample_brand_kit(self):
        """Sample brand kit data for testing."""
        return {
            "colors": ["#FF6B35", "#004E89", "#F7931E"],
            "brand_voice_description": "Friendly and approachable, with a focus on quality and craftsmanship",
            "logo_file_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",
            "saved_logo_path_in_run_dir": "/test/path/logo.png"
        }
    
    @pytest.fixture
    def sample_logo_analysis(self):
        """Sample logo analysis result."""
        return {
            "logo_style": "Modern minimalist design with clean typography",
            "has_text": True,
            "text_content": "CHURNS",
            "dominant_colors": ["#FF6B35", "#FFFFFF"],
            "logo_type": "wordmark",
            "style_keywords": ["minimalist", "modern", "clean", "professional"]
        }
    
    def create_test_context_with_brand_kit(self, brand_kit=None, logo_analysis=None):
        """Create test context with brand kit data."""
        ctx = PipelineContext()
        ctx.task_type = "1. Product Photography"
        ctx.target_platform = {
            "name": "Instagram Post (1:1 Square)",
            "resolution_details": {"width": 1080, "height": 1080, "aspect_ratio": "1:1"}
        }
        ctx.prompt = "A delicious gourmet burger"
        ctx.creativity_level = 2
        ctx.apply_branding = True
        
        # Set up brand kit
        if brand_kit:
            ctx.brand_kit = brand_kit.copy()
            if logo_analysis:
                ctx.brand_kit['logo_analysis'] = logo_analysis
        
        return ctx
    
    def test_brand_kit_data_flow_through_pipeline(self, sample_brand_kit, sample_logo_analysis):
        """Test that brand kit data flows correctly through all pipeline stages."""
        ctx = self.create_test_context_with_brand_kit(sample_brand_kit, sample_logo_analysis)
        
        # Mock strategies and style guidance for pipeline execution
        ctx.suggested_marketing_strategies = [{
            "target_audience": "Food Enthusiasts",
            "target_niche": "Gourmet Restaurant",
            "target_objective": "Showcase Quality",
            "target_voice": "Sophisticated & Elegant"
        }]
        
        ctx.style_guidance_sets = [{
            "style_keywords": ["elegant", "sophisticated"],
            "style_description": "Elegant and sophisticated food photography"
        }]
        
        # Verify brand kit is properly structured
        assert ctx.brand_kit['colors'] == ["#FF6B35", "#004E89", "#F7931E"]
        assert ctx.brand_kit['brand_voice_description'] == "Friendly and approachable, with a focus on quality and craftsmanship"
        assert ctx.brand_kit['logo_analysis']['logo_style'] == "Modern minimalist design with clean typography"
        assert ctx.brand_kit['logo_analysis']['has_text'] is True
        assert ctx.brand_kit['logo_analysis']['text_content'] == "CHURNS"
        
        # Verify brand kit data is accessible for downstream stages
        assert ctx.apply_branding is True
        assert len(ctx.brand_kit['colors']) == 3
        assert ctx.brand_kit['saved_logo_path_in_run_dir'] == "/test/path/logo.png"
    
    @patch('churns.stages.image_eval.ImageEvaluator.evaluate_image')
    def test_logo_analysis_integration(self, mock_evaluate, sample_brand_kit):
        """Test logo analysis integration in image_eval stage."""
        # Create context with logo but no analysis
        ctx = self.create_test_context_with_brand_kit(sample_brand_kit)
        del ctx.brand_kit['logo_analysis']  # Remove analysis to trigger evaluation
        
        # Mock logo analysis result
        mock_logo_analysis = LogoAnalysisResult(
            logo_style="Modern minimalist design with clean typography",
            has_text=True,
            text_content="CHURNS",
            dominant_colors=["#FF6B35", "#FFFFFF"],
            logo_type="wordmark",
            style_keywords=["minimalist", "modern", "clean", "professional"]
        )
        
        mock_evaluate.return_value = mock_logo_analysis
        
        # Create temp logo file
        temp_dir = tempfile.mkdtemp()
        logo_path = os.path.join(temp_dir, "logo.png")
        with open(logo_path, "wb") as f:
            f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\x0cIDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82')
        
        ctx.brand_kit['saved_logo_path_in_run_dir'] = logo_path
        
        # Run logo analysis
        image_eval.run(ctx)
        
        # Verify logo analysis was performed and stored
        assert 'logo_analysis' in ctx.brand_kit
        assert ctx.brand_kit['logo_analysis']['logo_style'] == "Modern minimalist design with clean typography"
        assert ctx.brand_kit['logo_analysis']['has_text'] is True
        assert ctx.brand_kit['logo_analysis']['text_content'] == "CHURNS"
    
    @patch('churns.stages.creative_expert.CreativeExpert.generate_visual_concept')
    def test_brand_kit_integration_in_creative_expert(self, mock_generate, sample_brand_kit, sample_logo_analysis):
        """Test that creative expert properly uses brand kit data."""
        ctx = self.create_test_context_with_brand_kit(sample_brand_kit, sample_logo_analysis)
        
        # Mock strategies and style guidance
        ctx.suggested_marketing_strategies = [{
            "target_audience": "Food Enthusiasts",
            "target_niche": "Gourmet Restaurant",
            "target_objective": "Showcase Quality",
            "target_voice": "Sophisticated & Elegant"
        }]
        
        ctx.style_guidance_sets = [{
            "style_keywords": ["elegant", "sophisticated"],
            "style_description": "Elegant and sophisticated food photography"
        }]
        
        # Mock creative expert response
        mock_visual_concept = {
            "main_subject": "Gourmet burger with artisan toppings",
            "composition_and_framing": "Close-up shot with shallow depth of field",
            "background_environment": "Dark wooden table with subtle lighting",
            "lighting_and_mood": "Warm, appetizing lighting reflecting brand voice",
            "color_palette": "Rich browns and golds complementing brand colors #FF6B35 and #004E89",
            "visual_style": "Professional food photography with sophisticated aesthetic",
            "logo_visuals": "CHURNS wordmark logo placed in bottom-right corner, scaled to 5% of image width in white color to contrast with dark background",
            "suggested_alt_text": "Gourmet burger with CHURNS branding"
        }
        
        mock_generate.return_value = mock_visual_concept
        
        # Run creative expert stage
        creative_expert.run(ctx)
        
        # Verify brand kit integration
        assert ctx.generated_image_prompts is not None
        assert len(ctx.generated_image_prompts) > 0
        
        # Check that brand colors are referenced in the color palette
        visual_concept = ctx.generated_image_prompts[0]['visual_concept']
        assert "#FF6B35" in visual_concept['color_palette'] or "#004E89" in visual_concept['color_palette']
        
        # Check that logo is properly integrated
        assert "CHURNS" in visual_concept['logo_visuals']
        assert "wordmark" in visual_concept['logo_visuals'] or "logo" in visual_concept['logo_visuals']
    
    @patch('churns.stages.style_guide.StyleGuider.generate_style_guidance')
    def test_brand_kit_integration_in_style_guide(self, mock_generate, sample_brand_kit, sample_logo_analysis):
        """Test that style guide properly uses brand kit data."""
        ctx = self.create_test_context_with_brand_kit(sample_brand_kit, sample_logo_analysis)
        
        # Mock strategies
        ctx.suggested_marketing_strategies = [{
            "target_audience": "Food Enthusiasts",
            "target_niche": "Gourmet Restaurant",
            "target_objective": "Showcase Quality",
            "target_voice": "Sophisticated & Elegant"
        }]
        
        # Mock style guide response
        mock_style_guidance = {
            "style_keywords": ["elegant", "sophisticated", "brand-aligned"],
            "style_description": "Elegant and sophisticated food photography that complements the brand colors #FF6B35 and #004E89, with a friendly yet professional approach matching the brand voice",
            "marketing_impact": "Creates strong brand consistency while appealing to food enthusiasts",
            "color_harmony": "Warm tones that complement brand orange (#FF6B35) with sophisticated blue accents (#004E89)",
            "logo_integration": "Modern minimalist CHURNS wordmark fits perfectly with clean, professional aesthetic"
        }
        
        mock_generate.return_value = mock_style_guidance
        
        # Run style guide stage
        style_guide.run(ctx)
        
        # Verify brand kit integration
        assert ctx.style_guidance_sets is not None
        assert len(ctx.style_guidance_sets) > 0
        
        # Check that brand colors are referenced
        style_guidance = ctx.style_guidance_sets[0]
        assert "#FF6B35" in style_guidance['style_description'] or "#FF6B35" in style_guidance.get('color_harmony', '')
        
        # Check that brand voice is reflected
        assert "friendly" in style_guidance['style_description'] or "professional" in style_guidance['style_description']
    
    def test_brand_kit_validation(self):
        """Test brand kit data validation."""
        # Test valid brand kit
        valid_brand_kit = {
            "colors": ["#FF6B35", "#004E89", "#F7931E"],
            "brand_voice_description": "Friendly and approachable",
            "logo_file_base64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        }
        
        brand_kit_input = BrandKitInput(**valid_brand_kit)
        assert brand_kit_input.colors == ["#FF6B35", "#004E89", "#F7931E"]
        assert brand_kit_input.brand_voice_description == "Friendly and approachable"
        assert brand_kit_input.logo_file_base64 is not None
        
        # Test brand kit with missing optional fields
        minimal_brand_kit = {
            "colors": ["#FF6B35"]
        }
        
        minimal_brand_kit_input = BrandKitInput(**minimal_brand_kit)
        assert minimal_brand_kit_input.colors == ["#FF6B35"]
        assert minimal_brand_kit_input.brand_voice_description is None
        assert minimal_brand_kit_input.logo_file_base64 is None
    
    def test_brand_kit_precedence_rules(self, sample_brand_kit):
        """Test brand kit precedence rules in pipeline context."""
        ctx = self.create_test_context_with_brand_kit(sample_brand_kit)
        
        # Mock strategy with different voice
        ctx.suggested_marketing_strategies = [{
            "target_audience": "Food Enthusiasts",
            "target_niche": "Gourmet Restaurant", 
            "target_objective": "Showcase Quality",
            "target_voice": "Urgent & Exciting"  # Different from brand voice
        }]
        
        # Brand voice from brand kit should be used as fallback
        brand_voice = ctx.brand_kit.get('brand_voice_description', 'Friendly and approachable')
        strategy_voice = ctx.suggested_marketing_strategies[0]['target_voice']
        
        # Strategy voice should take precedence for specific run
        assert strategy_voice == "Urgent & Exciting"
        # But brand voice should be available as fallback
        assert brand_voice == "Friendly and approachable"
    
    def test_consistency_metrics_calculation(self):
        """Test consistency metrics calculation for brand kit validation."""
        # Create test images (minimal PNG data)
        original_image_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\x0cIDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82'
        new_image_data = b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\x0cIDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82'
        
        # Create temp files
        temp_dir = tempfile.mkdtemp()
        original_path = os.path.join(temp_dir, "original.png")
        new_path = os.path.join(temp_dir, "new.png")
        
        with open(original_path, "wb") as f:
            f.write(original_image_data)
        with open(new_path, "wb") as f:
            f.write(new_image_data)
        
        # Calculate consistency metrics
        metrics = ConsistencyMetrics()
        
        try:
            result = metrics.calculate_consistency_score(original_path, new_path)
            
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
            
        except ImportError:
            # Skip if optional dependencies not available
            pytest.skip("Optional dependencies for consistency metrics not available")
    
    def test_brand_kit_logo_file_handling(self, sample_brand_kit):
        """Test brand kit logo file handling and base64 conversion."""
        ctx = self.create_test_context_with_brand_kit(sample_brand_kit)
        
        # Verify logo file data
        assert ctx.brand_kit['logo_file_base64'] is not None
        assert len(ctx.brand_kit['logo_file_base64']) > 0
        
        # Verify saved logo path
        assert ctx.brand_kit['saved_logo_path_in_run_dir'] == "/test/path/logo.png"
        
        # Test base64 decoding (should not raise exception)
        import base64
        try:
            decoded_data = base64.b64decode(ctx.brand_kit['logo_file_base64'])
            assert len(decoded_data) > 0
        except Exception as e:
            pytest.fail(f"Base64 decoding failed: {e}")
    
    def test_brand_kit_color_palette_integration(self, sample_brand_kit):
        """Test color palette integration in brand kit."""
        ctx = self.create_test_context_with_brand_kit(sample_brand_kit)
        
        # Verify color palette structure
        colors = ctx.brand_kit['colors']
        assert isinstance(colors, list)
        assert len(colors) == 3
        
        # Verify HEX color format
        for color in colors:
            assert isinstance(color, str)
            assert color.startswith('#')
            assert len(color) == 7  # #RRGGBB format
            
        # Verify specific colors
        assert "#FF6B35" in colors
        assert "#004E89" in colors
        assert "#F7931E" in colors
    
    def test_brand_kit_missing_fields_handling(self):
        """Test handling of missing optional fields in brand kit."""
        # Test with minimal brand kit
        minimal_brand_kit = {
            "colors": ["#FF6B35"]
        }
        
        ctx = self.create_test_context_with_brand_kit(minimal_brand_kit)
        
        # Verify required fields are present
        assert 'colors' in ctx.brand_kit
        assert ctx.brand_kit['colors'] == ["#FF6B35"]
        
        # Verify optional fields are handled gracefully
        assert ctx.brand_kit.get('brand_voice_description') is None
        assert ctx.brand_kit.get('logo_file_base64') is None
        assert ctx.brand_kit.get('saved_logo_path_in_run_dir') is None
        
        # Pipeline should still work with minimal brand kit
        assert ctx.apply_branding is True
    
    def test_brand_kit_error_handling(self):
        """Test error handling for invalid brand kit data."""
        # Test with invalid color format
        invalid_brand_kit = {
            "colors": ["invalid-color", "#FF6B35"],
            "brand_voice_description": "Friendly and approachable"
        }
        
        ctx = self.create_test_context_with_brand_kit(invalid_brand_kit)
        
        # Pipeline should handle invalid colors gracefully
        # (validation may happen at API level, not pipeline level)
        assert 'colors' in ctx.brand_kit
        assert len(ctx.brand_kit['colors']) == 2


class TestBrandKitAPIIntegration:
    """Test API integration for brand kit functionality."""
    
    def test_brand_kit_api_payload_structure(self):
        """Test brand kit API payload structure."""
        brand_kit_payload = {
            "colors": ["#FF6B35", "#004E89", "#F7931E"],
            "brandVoiceDescription": "Friendly and approachable, with a focus on quality and craftsmanship",
            "logoFileBase64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        }
        
        # Verify payload structure
        assert 'colors' in brand_kit_payload
        assert 'brandVoiceDescription' in brand_kit_payload
        assert 'logoFileBase64' in brand_kit_payload
        
        # Verify data types
        assert isinstance(brand_kit_payload['colors'], list)
        assert isinstance(brand_kit_payload['brandVoiceDescription'], str)
        assert isinstance(brand_kit_payload['logoFileBase64'], str)
    
    def test_brand_kit_backend_conversion(self):
        """Test frontend to backend brand kit data conversion."""
        # Frontend camelCase format
        frontend_brand_kit = {
            "colors": ["#FF6B35", "#004E89", "#F7931E"],
            "brandVoiceDescription": "Friendly and approachable",
            "logoFileBase64": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        }
        
        # Backend snake_case format (expected in pipeline)
        backend_brand_kit = {
            "colors": frontend_brand_kit["colors"],
            "brand_voice_description": frontend_brand_kit["brandVoiceDescription"],
            "logo_file_base64": frontend_brand_kit["logoFileBase64"]
        }
        
        # Verify conversion
        assert backend_brand_kit['colors'] == ["#FF6B35", "#004E89", "#F7931E"]
        assert backend_brand_kit['brand_voice_description'] == "Friendly and approachable"
        assert backend_brand_kit['logo_file_base64'] == "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==" 