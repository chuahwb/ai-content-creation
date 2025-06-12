"""
Tests for Image Assessment Stage

This module tests the image assessment functionality that evaluates generated images
using multimodal LLM capabilities to assess concept adherence, subject preservation,
technical quality, and text rendering quality.
"""

import json
import tempfile
import os
from unittest.mock import Mock, patch, mock_open
from churns.pipeline.context import PipelineContext
from churns.stages.image_assessment import (
    run, 
    ImageAssessor,
    _create_simulation_fallback
)
from churns.core.constants import IMAGE_ASSESSMENT_MODEL_ID


class TestImageAssessmentStage:
    """Test the image assessment stage functionality."""
    
    def create_test_context(self, 
                          has_generated_images=True,
                          has_visual_concepts=True,
                          has_reference_image=False,
                          render_text=False,
                          creativity_level=2):
        """Create a test context for image assessment."""
        ctx = PipelineContext()
        ctx.creativity_level = creativity_level
        ctx.task_type = "2. Promotional Graphics & Announcements"
        ctx.target_platform = {
            "name": "Instagram Post (1:1 Square)",
            "resolution_details": {"width": 1080, "height": 1080, "aspect_ratio": "1:1"}
        }
        ctx.render_text = render_text
        
        if has_generated_images:
            ctx.generated_image_results = [
                {
                    "index": 0,
                    "status": "success",
                    "result_path": "/fake/path/strategy_0_image.png"
                },
                {
                    "index": 1,
                    "status": "success", 
                    "result_path": "/fake/path/strategy_1_image.png"
                }
            ]
        else:
            ctx.generated_image_results = []
            
        if has_visual_concepts:
            ctx.generated_image_prompts = [
                {
                    "source_strategy_index": 0,
                    "visual_concept": {
                        "main_subject": "Gourmet burger with artisan toppings",
                        "composition_and_framing": "45-degree angle close-up shot",
                        "background_environment": "rustic wooden table background", 
                        "lighting_and_mood": "warm appetizing natural light",
                        "color_palette": "rich browns and fresh greens"
                    }
                },
                {
                    "source_strategy_index": 1,
                    "visual_concept": {
                        "main_subject": "Artisanal coffee latte with foam art",
                        "composition_and_framing": "overhead view composition",
                        "background_environment": "marble counter background",
                        "lighting_and_mood": "soft morning lighting",
                        "color_palette": "cream and brown color tones"
                    }
                }
            ]
        else:
            ctx.generated_image_prompts = []
            
        if has_reference_image:
            ctx.image_reference = {
                "filename": "reference_burger.jpg",
                "image_content_base64": "fake_base64_content",
                "content_type": "image/jpeg"
            }
        else:
            ctx.image_reference = None
            
        return ctx
    
    def create_mock_assessment_result(self, scores=None, success=True):
        """Create a mock assessment result."""
        if not success:
            raise Exception("API Error")
            
        if scores is None:
            scores = {
                "concept_adherence": 8,
                "technical_quality": 7,
                "subject_preservation": 9
            }
        
        return {
            "assessment_scores": scores,
            "assessment_justification": {
                "concept_adherence": "Good alignment with the visual concept",
                "technical_quality": "High quality with minor artifacts",
                "subject_preservation": "Excellent preservation of subject features"
            },
            "general_score": 7.6,
            "needs_subject_repair": False,
            "needs_regeneration": False,
            "needs_text_repair": False,
            "_meta": {"tokens_used": 45000, "model": IMAGE_ASSESSMENT_MODEL_ID}
        }

    def test_successful_image_assessment(self):
        """Test successful image assessment for multiple images."""
        ctx = self.create_test_context()
        
        # Mock the ImageAssessor's assess_image method
        with patch('churns.stages.image_assessment.ImageAssessor.assess_image') as mock_assess:
            mock_assess.side_effect = [
                self.create_mock_assessment_result(),
                self.create_mock_assessment_result()
            ]
            
            # Run the stage
            run(ctx)
        
        # Verify results
        assert ctx.image_assessments is not None
        assert len(ctx.image_assessments) == 2
        
        result = ctx.image_assessments[0]
        assert "assessment_scores" in result
        assert "assessment_justification" in result
        assert "general_score" in result
        assert "needs_subject_repair" in result
        assert "needs_regeneration" in result
        assert "needs_text_repair" in result
        
        # Verify assessments were called
        assert mock_assess.call_count == 2

    def test_assessment_with_reference_image(self):
        """Test image assessment when reference image is available."""
        ctx = self.create_test_context(has_reference_image=True)
        
        scores_with_subject = {
            "concept_adherence": 8,
            "technical_quality": 7,
            "subject_preservation": 9
        }
        
        with patch('churns.stages.image_assessment.ImageAssessor.assess_image') as mock_assess:
            mock_assess.return_value = self.create_mock_assessment_result(scores=scores_with_subject)
            
            run(ctx)
        
        # Verify subject preservation was assessed
        assert ctx.image_assessments is not None
        result = ctx.image_assessments[0]
        assert result["assessment_scores"]["subject_preservation"] == 9

    def test_assessment_with_text_rendering(self):
        """Test image assessment when text rendering is enabled."""
        ctx = self.create_test_context(render_text=True)
        
        scores_with_text = {
            "concept_adherence": 8,
            "technical_quality": 7,
            "text_rendering_quality": 5
        }
        
        with patch('churns.stages.image_assessment.ImageAssessor.assess_image') as mock_assess:
            mock_assess.return_value = self.create_mock_assessment_result(scores=scores_with_text)
            
            run(ctx)
        
        # Verify text rendering was assessed
        assert ctx.image_assessments is not None
        result = ctx.image_assessments[0]
        assert result["assessment_scores"]["text_rendering_quality"] == 5

    def test_no_generated_images(self):
        """Test behavior when no generated images are available."""
        ctx = self.create_test_context(has_generated_images=False)
        
        run(ctx)
        
        # Should exit early with appropriate log
        assert any("No generated images found" in log for log in ctx.logs)
        assert ctx.image_assessments is None

    def test_no_visual_concepts(self):
        """Test behavior when no visual concepts are available."""
        ctx = self.create_test_context(has_visual_concepts=False)
        
        run(ctx)
        
        # Should exit early with appropriate log
        assert any("No visual concepts found" in log for log in ctx.logs)
        assert ctx.image_assessments is None

    def test_failed_image_generation_skipped(self):
        """Test that failed image generations are skipped during assessment."""
        ctx = self.create_test_context()
        ctx.generated_image_results = [
            {
                "index": 0,
                "status": "error",
                "result_path": None,
                "error_message": "Generation failed"
            },
            {
                "index": 1,
                "status": "success",
                "result_path": "/fake/path/strategy_1_image.png"
            }
        ]
        
        with patch('churns.stages.image_assessment.ImageAssessor.assess_image') as mock_assess:
            mock_assess.return_value = self.create_mock_assessment_result()
            
            run(ctx)
        
        # Should only assess the successful image
        assert mock_assess.call_count == 1
        assert any("Skipping assessment for failed image generation" in log for log in ctx.logs)

    def test_assessment_error_fallback(self):
        """Test handling of assessment errors with fallback to simulation."""
        ctx = self.create_test_context()
        
        with patch('churns.stages.image_assessment.ImageAssessor.assess_image') as mock_assess:
            mock_assess.side_effect = Exception("API Error")
            
            run(ctx)
        
        # Should still have results from simulation fallback
        assert ctx.image_assessments is not None
        result = ctx.image_assessments[0]
        
        assert result["_meta"]["fallback"] == True
        assert any("Unexpected error during assessment:" in log for log in ctx.logs)


class TestImageAssessorClass:
    """Test the ImageAssessor class functionality."""
    
    def test_image_assessor_initialization(self):
        """Test ImageAssessor initialization."""
        assessor = ImageAssessor()
        assert assessor.model_id == IMAGE_ASSESSMENT_MODEL_ID
        assert assessor.client is not None
        
        # Test with custom model
        custom_assessor = ImageAssessor(model_id="custom-model")
        assert custom_assessor.model_id == "custom-model"

    def test_load_image_as_base64(self):
        """Test image loading and base64 conversion."""
        assessor = ImageAssessor()
        
        # Test PNG image
        with patch('builtins.open', mock_open(read_data=b'fake_image_data')):
            result = assessor._load_image_as_base64('test.png')
            assert result is not None
            base64_data, content_type = result
            assert content_type == 'image/png'
            assert isinstance(base64_data, str)
        
        # Test JPEG image
        with patch('builtins.open', mock_open(read_data=b'fake_image_data')):
            result = assessor._load_image_as_base64('test.jpg')
            assert result is not None
            base64_data, content_type = result
            assert content_type == 'image/jpeg'

    def test_create_assessment_prompt(self):
        """Test assessment prompt creation with different configurations."""
        assessor = ImageAssessor()
        
        visual_concept = {
            "main_subject": "Test burger",
            "composition_and_framing": "Close-up shot"
        }
        
        # Test basic prompt
        prompt = assessor._create_assessment_prompt(
            visual_concept, 2, False, False, "Test Task", "Instagram"
        )
        
        assert "Test Task" in prompt
        assert "Instagram" in prompt
        assert "Creativity Level: 2" in prompt
        assert "concept_adherence" in prompt
        assert "technical_quality" in prompt
        
        # Test with reference image
        prompt_with_ref = assessor._create_assessment_prompt(
            visual_concept, 1, True, False, "Test Task", "Instagram"
        )
        
        assert "subject_preservation" in prompt_with_ref
        assert "Near-identical preservation expected" in prompt_with_ref
        
        # Test with text rendering
        prompt_with_text = assessor._create_assessment_prompt(
            visual_concept, 3, False, True, "Test Task", "Instagram"
        )
        
        assert "text_rendering_quality" in prompt_with_text

    def test_extract_json_from_response(self):
        """Test JSON extraction from various LLM response formats."""
        assessor = ImageAssessor()
        
        # Test markdown JSON block
        markdown_response = '''Here's the assessment:
        ```json
        {"assessment_scores": {"concept_adherence": 8}}
        ```
        That's my evaluation.'''
        
        result = assessor._extract_json_from_response(markdown_response)
        assert result == '{"assessment_scores": {"concept_adherence": 8}}'
        
        # Test direct JSON
        direct_json = '{"assessment_scores": {"concept_adherence": 8}}'
        result = assessor._extract_json_from_response(direct_json)
        assert result == direct_json
        
        # Test no JSON found
        no_json = "This is just text without any JSON."
        result = assessor._extract_json_from_response(no_json)
        assert result is None


class TestSimulationFallback:
    """Test simulation fallback functionality."""
    
    def test_simulation_fallback_basic(self):
        """Test basic simulation fallback."""
        result = _create_simulation_fallback(False, False)
        
        assert "assessment_scores" in result
        assert "assessment_justification" in result
        assert "general_score" in result
        assert result["assessment_scores"]["concept_adherence"] == 7
        assert result["assessment_scores"]["technical_quality"] == 8
        assert "subject_preservation" not in result["assessment_scores"]
        assert "text_rendering_quality" not in result["assessment_scores"]
        assert result["_meta"]["fallback"] == True
        
    def test_simulation_fallback_with_reference(self):
        """Test simulation fallback with reference image."""
        result = _create_simulation_fallback(True, False)
        assert "subject_preservation" in result["assessment_scores"]
        assert result["assessment_scores"]["subject_preservation"] == 8
        
    def test_simulation_fallback_with_text(self):
        """Test simulation fallback with text rendering."""
        result = _create_simulation_fallback(False, True)
        assert "text_rendering_quality" in result["assessment_scores"]
        assert result["assessment_scores"]["text_rendering_quality"] == 6


class TestImageAssessmentIntegration:
    """Integration tests for the image assessment stage."""
    
    def test_end_to_end_assessment_flow(self):
        """Test the complete flow from generated images to assessment results."""
        ctx = PipelineContext()
        
        # Set up complete context
        ctx.generated_image_results = [{
            "index": 0,
            "status": "success",
            "result_path": "/fake/path/image.png"
        }]
        
        ctx.generated_image_prompts = [{
            "source_strategy_index": 0,
            "visual_concept": {
                "main_subject": "Professional food photography",
                "composition_and_framing": "Close-up shot",
                "lighting_and_mood": "Natural lighting"
            }
        }]
        
        ctx.creativity_level = 2
        ctx.task_type = "Social Media Post"
        ctx.target_platform = {"name": "Instagram"}
        ctx.render_text = False
        ctx.image_reference = None
        
        # Mock the assessment
        mock_result = {
            "assessment_scores": {"concept_adherence": 8, "technical_quality": 9},
            "assessment_justification": {"concept_adherence": "Good", "technical_quality": "High"},
            "general_score": 8.4,
            "needs_subject_repair": False,
            "needs_regeneration": False,
            "needs_text_repair": False,
            "_meta": {"tokens_used": 45000, "model": IMAGE_ASSESSMENT_MODEL_ID}
        }
        
        with patch('churns.stages.image_assessment.ImageAssessor.assess_image') as mock_assess:
            mock_assess.return_value = mock_result
            
            run(ctx)
        
        # Verify complete flow
        assert ctx.image_assessments is not None
        assert len(ctx.image_assessments) == 1
        
        result = ctx.image_assessments[0]
        assert result["general_score"] == 8.4
        assert result["image_index"] == 0
        
        # Verify usage tracking
        assert "image_assessment" in ctx.llm_usage
        assert ctx.llm_usage["image_assessment"][0]["total_tokens"] == 45000 