"""
Tests for Refinement Stages (Subject Repair, Text Repair, Prompt Refine)

Tests the refinement functionality with temporary fallbacks to validate
pipeline execution, shared utilities, cost calculation, and file management
without requiring actual OpenAI API calls.
"""

import pytest
import os
import tempfile
import json
from unittest.mock import Mock, patch, mock_open
from pathlib import Path
from PIL import Image

from churns.pipeline.context import PipelineContext
from churns.stages import subject_repair, text_repair, prompt_refine
from churns.stages.refinement_utils import (
    validate_refinement_inputs,
    load_and_prepare_image,
    calculate_refinement_cost,
    create_mask_from_coordinates,
)


class TestRefinementStageBase:
    """Base class with common test utilities for refinement stages."""
    
    def create_test_context(self, refinement_type="subject", has_mask=False):
        """Create a test context for refinement stages."""
        ctx = PipelineContext()
        
        # Basic refinement context
        ctx.run_id = "refinement_test_123"
        ctx.parent_run_id = "parent_run_456"
        ctx.parent_image_id = "image_0"
        ctx.parent_image_type = "original"
        ctx.generation_index = 0
        ctx.refinement_type = refinement_type
        ctx.creativity_level = 2
        
        # Set up temporary directories
        ctx.base_run_dir = tempfile.mkdtemp()
        ctx.base_image_path = os.path.join(ctx.base_run_dir, "test_image.png")
        
        # Create a test image file
        self._create_test_image(ctx.base_image_path)
        
        # Type-specific setup
        if refinement_type == "subject":
            ctx.instructions = "Replace the main subject with a modern version"
            ctx.reference_image_path = os.path.join(ctx.base_run_dir, "reference.png")
            self._create_test_image(ctx.reference_image_path)
        elif refinement_type == "text":
            ctx.instructions = "Fix spelling errors and improve text clarity"
        elif refinement_type == "prompt":
            ctx.prompt = "Add sunset lighting and warmer tones"
            if has_mask:
                ctx.mask_coordinates = json.dumps({
                    "type": "rectangle",
                    "x1": 0.2, "y1": 0.2,
                    "x2": 0.8, "y2": 0.8
                })
        
        # Original pipeline data for context
        ctx.original_pipeline_data = {
            "processing_context": {
                "generated_image_prompts": [
                    {
                        "main_subject": "modern smartphone",
                        "visual_concept": {
                            "composition_and_framing": "centered product shot",
                            "background_environment": "clean studio background",
                            "foreground_elements": "minimal props",
                            "lighting_and_mood": "bright professional lighting",
                            "color_palette": "neutral with accent colors",
                            "visual_style": "modern minimalist",
                            "texture_and_details": "sleek smooth surfaces",
                            "creative_reasoning": "emphasizing product features",
                            "promotional_text_visuals": "clean sans-serif typography",
                            "branding_visuals": "subtle logo placement"
                        }
                    }
                ],
                "image_analysis_result": {
                    "main_subject": "modern smartphone"
                },
                "style_guidance_sets": [
                    {"style_keywords": ["modern", "minimalist", "clean"]}
                ],
                "suggested_marketing_strategies": [
                    {"target_audience": "young professionals"}
                ]
            },
            "user_inputs": {
                "task_description": "Create a modern product image",
                "render_text": True,
                "apply_branding": True,
                "branding_elements": "TechBrand"
            }
        }
        
        # Initialize cost tracking
        ctx.cost_summary = {"stage_costs": []}
        
        return ctx
    
    def _create_test_image(self, path):
        """Create a simple test image file."""
        # Create a simple 100x100 RGB image
        img = Image.new('RGB', (100, 100), color='red')
        img.save(path, 'PNG')
    
    def create_mock_api_response(self, success=True):
        """Create a mock OpenAI API response."""
        if not success:
            raise Exception("API Error")
        
        mock_response = Mock()
        mock_image_data = Mock()
        
        # Simple 1x1 PNG base64 data
        mock_image_data.b64_json = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        mock_response.data = [mock_image_data]
        
        return mock_response


class TestSubjectRepairStage(TestRefinementStageBase):
    """Test subject repair stage functionality."""
    
    @patch('churns.stages.subject_repair.image_gen_client')
    def test_successful_subject_repair(self, mock_image_gen_client):
        """Test successful subject repair execution."""
        ctx = self.create_test_context("subject")
        
        # Mock the image generation client  
        mock_image_gen_client.images.edit.return_value = self.create_mock_api_response(success=True)
        
        # Run the stage
        import asyncio
        asyncio.run(subject_repair.run(ctx))
        
        # Verify results
        assert ctx.refinement_result is not None
        assert ctx.refinement_result["type"] == "subject_repair"
        assert ctx.refinement_result["status"] == "completed"
        assert ctx.refinement_result["output_path"] is not None
        assert ctx.refinement_result["modifications"]["subject_replaced"] is True
        
        # Verify cost calculation
        assert ctx.refinement_cost is not None
        assert ctx.refinement_cost > 0
        
        # Verify API call
        mock_image_gen_client.images.edit.assert_called_once()
    
    def test_subject_repair_missing_reference(self):
        """Test subject repair with missing reference image."""
        ctx = self.create_test_context("subject")
        ctx.reference_image_path = "/nonexistent/path.png"
        
        # Should raise validation error
        import asyncio
        with pytest.raises(ValueError, match="Reference image path is required"):
            asyncio.run(subject_repair.run(ctx))
    
    def test_subject_repair_prompt_enhancement(self):
        """Test subject repair prompt enhancement."""
        ctx = self.create_test_context("subject")
        
        # Test prompt enhancement
        enhanced_prompt = subject_repair._prepare_subject_repair_prompt(ctx)
        
        assert "Replace the main subject" in enhanced_prompt
        assert "preserving the background" in enhanced_prompt
        assert "moderate modifications" in enhanced_prompt  # creativity level 2
        assert "high quality" in enhanced_prompt


class TestTextRepairStage(TestRefinementStageBase):
    """Test text repair stage functionality."""
    
    @patch('churns.stages.text_repair._perform_text_analysis')
    @patch('churns.stages.text_repair.image_gen_client')
    def test_successful_text_repair(self, mock_image_gen_client, mock_text_analysis):
        """Test successful text repair execution."""
        ctx = self.create_test_context("text")
        
        # Mock the text analysis function
        mock_text_analysis.return_value = {
            "main_text": "HELLO WORLD",
            "brand_name": "TechBrand",
            "object_description": "Premium product",
            "corrections": {}
        }
        
        # Mock the image generation client
        mock_image_gen_client.images.edit.return_value = self.create_mock_api_response(success=True)
        
        # Run the stage
        import asyncio
        asyncio.run(text_repair.run(ctx))
        
        # Verify results
        assert ctx.refinement_result is not None
        assert ctx.refinement_result["type"] == "text_repair" 
        assert ctx.refinement_result["status"] == "completed"
        assert ctx.refinement_result["modifications"]["text_corrected"] is True
        
        # Verify cost tracking
        assert ctx.refinement_cost is not None
        assert ctx.refinement_cost > 0
    
    def test_text_repair_default_instructions(self):
        """Test text repair with default instructions."""
        ctx = self.create_test_context("text")
        ctx.instructions = None
        
        # Validate inputs (should set default)
        text_repair._validate_text_repair_inputs(ctx)
        
        assert ctx.instructions == "Fix and improve text elements in the image"
    
    def test_text_repair_prompt_enhancement(self):
        """Test text repair prompt enhancement with marketing context."""
        ctx = self.create_test_context("text")
        
        enhanced_prompt = text_repair._prepare_text_repair_prompt(ctx)
        
        assert "Fix any text elements" in enhanced_prompt
        assert "spelling errors" in enhanced_prompt
        assert "young professionals" in enhanced_prompt  # marketing context
        assert "clear" in enhanced_prompt and "readable" in enhanced_prompt


class TestPromptRefineStage(TestRefinementStageBase):
    """Test prompt refinement stage functionality."""
    
    @patch('churns.stages.refinement_utils.image_generation')
    def test_successful_prompt_refine_global(self, mock_image_gen):
        """Test successful global prompt refinement (no mask)."""
        ctx = self.create_test_context("prompt", has_mask=False)
        
        # Mock the image generation client
        mock_client = Mock()
        mock_client.images.edit.return_value = self.create_mock_api_response(success=True)
        mock_image_gen.image_gen_client = mock_client
        
        # Run the stage
        prompt_refine.run(ctx)
        
        # Verify results
        assert ctx.refinement_result is not None
        assert ctx.refinement_result["type"] == "prompt_refinement"
        assert ctx.refinement_result["modifications"]["mask_applied"] is False
        assert ctx.refinement_result["modifications"]["regional_edit"] is False
        
        # Verify API call without mask
        mock_client.images.edit.assert_called_once()
    
    @patch('churns.stages.refinement_utils.image_generation')
    def test_successful_prompt_refine_regional(self, mock_image_gen):
        """Test successful regional prompt refinement (with mask)."""
        ctx = self.create_test_context("prompt", has_mask=True)
        
        # Mock the image generation client
        mock_client = Mock()
        mock_client.images.edit.return_value = self.create_mock_api_response(success=True)
        mock_image_gen.image_gen_client = mock_client
        
        # Run the stage
        prompt_refine.run(ctx)
        
        # Verify results
        assert ctx.refinement_result["modifications"]["mask_applied"] is True
        assert ctx.refinement_result["modifications"]["regional_edit"] is True
        
        # Verify API call with mask
        mock_client.images.edit.assert_called_once()
    
    def test_prompt_refine_missing_prompt(self):
        """Test prompt refinement with missing prompt."""
        ctx = self.create_test_context("prompt")
        ctx.prompt = None
        
        # Should raise validation error
        with pytest.raises(ValueError, match="Refinement prompt is required"):
            prompt_refine.run(ctx)
    
    def test_prompt_refine_with_style_context(self):
        """Test prompt refinement with style context integration."""
        ctx = self.create_test_context("prompt")
        
        enhanced_prompt = prompt_refine._prepare_refinement_prompt(ctx)
        
        assert "Add sunset lighting" in enhanced_prompt
        assert "modern, minimalist, clean" in enhanced_prompt  # style context
        assert "young professionals" in enhanced_prompt  # marketing context


class TestRefinementUtils:
    """Test shared refinement utilities."""
    
    def test_validate_refinement_inputs(self):
        """Test common input validation."""
        ctx = PipelineContext()
        ctx.base_image_path = "/nonexistent/path.png"
        ctx.refinement_type = "subject"
        
        # Should raise error for missing base image
        with pytest.raises(ValueError, match="Base image path is required and must exist"):
            validate_refinement_inputs(ctx, "subject")
        
        # Test with wrong refinement type
        ctx.base_image_path = __file__  # Use this file as a dummy existing file
        ctx.refinement_type = "wrong_type"
        with pytest.raises(ValueError, match="Invalid refinement type"):
            validate_refinement_inputs(ctx, "subject")
    
    def test_load_and_prepare_image(self):
        """Test image loading and preparation."""
        ctx = PipelineContext()
        
        # Create a test image
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
            img = Image.new('RGB', (100, 100), color='blue')
            img.save(tmp_file.name, 'PNG')
            ctx.base_image_path = tmp_file.name
        
        try:
            # Test loading base image
            loaded_image = load_and_prepare_image(ctx, 'base')
            assert loaded_image.mode == 'RGB'
            assert loaded_image.size == (100, 100)
        finally:
            os.unlink(ctx.base_image_path)
    
    def test_calculate_refinement_cost(self):
        """Test cost calculation with different parameters."""
        ctx = PipelineContext()
        ctx.base_image_metadata = {"width": 1024, "height": 1024}
        
        # Test base cost calculation
        cost = calculate_refinement_cost(ctx, "test prompt", has_mask=False)
        assert cost > 0
        
        # Test with mask (should be slightly higher)
        cost_with_mask = calculate_refinement_cost(ctx, "test prompt", has_mask=True)
        assert cost_with_mask > cost
        
        # Test different refinement types
        cost_subject = calculate_refinement_cost(ctx, "test prompt", has_mask=False, refinement_type="subject repair")
        assert cost_subject > 0
    
    def test_create_mask_from_coordinates(self):
        """Test mask creation from different coordinate types."""
        image_size = (200, 200)
        base_run_dir = tempfile.mkdtemp()
        
        try:
            # Test rectangle mask
            mask_data = {
                "type": "rectangle",
                "x1": 0.25, "y1": 0.25,
                "x2": 0.75, "y2": 0.75
            }
            
            mask_path = create_mask_from_coordinates(mask_data, image_size, base_run_dir)
            assert mask_path is not None
            assert os.path.exists(mask_path)
            
            # Verify the mask image
            from PIL import Image
            mask = Image.open(mask_path)
            assert mask.mode == 'L'
            assert mask.size == image_size
            
            # Test circle mask
            mask_data = {
                "type": "circle",
                "cx": 0.5, "cy": 0.5,
                "radius": 0.25
            }
            
            mask_path = create_mask_from_coordinates(mask_data, image_size, base_run_dir)
            assert mask_path is not None
            assert os.path.exists(mask_path)
            
            # Test no mask
            mask_path = create_mask_from_coordinates(None, image_size, base_run_dir)
            assert mask_path is None
            
        finally:
            # Cleanup
            import shutil
            shutil.rmtree(base_run_dir, ignore_errors=True)


class TestRefinementIntegration:
    """Integration tests for refinement pipeline."""
    
    @patch('churns.stages.refinement_utils.image_generation')
    def test_end_to_end_refinement_flow(self, mock_image_gen):
        """Test complete refinement flow from context to result."""
        # Mock the image generation client
        mock_client = Mock()
        mock_client.images.edit.return_value = Mock(
            data=[Mock(
                b64_json="iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
            )]
        )
        mock_image_gen.image_gen_client = mock_client
        
        # Test each refinement type
        for refinement_type in ["subject", "text", "prompt"]:
            ctx = TestRefinementStageBase().create_test_context(refinement_type)
            
            # Run appropriate stage
            if refinement_type == "subject":
                subject_repair.run(ctx)
            elif refinement_type == "text":
                text_repair.run(ctx)
            elif refinement_type == "prompt":
                prompt_refine.run(ctx)
            
            # Verify common results
            assert ctx.refinement_result is not None
            assert ctx.refinement_result["status"] == "completed"
            assert ctx.refinement_result["output_path"] is not None
            assert ctx.refinement_cost is not None
            assert ctx.refinement_cost > 0
    
    def test_cost_tracking_integration(self):
        """Test integration with cost tracking system."""
        ctx = TestRefinementStageBase().create_test_context("text")
        
        # Test cost calculation
        cost = calculate_refinement_cost(ctx, "test prompt for cost tracking")
        assert cost > 0
        
        # Test cost tracking (mock the track function)
        with patch('churns.stages.refinement_utils.track_refinement_cost') as mock_track:
            mock_track.return_value = None  # Just verify it's called
            
            from churns.stages.refinement_utils import track_refinement_cost
            track_refinement_cost(ctx, "test_stage", "test prompt")
            mock_track.assert_called_once()


def run_fallback_tests():
    """
    Convenience function to run all refinement tests with fallbacks.
    This can be called directly for quick validation.
    """
    print("🧪 Running Refinement Stage Tests with Fallbacks...")
    
    # Run tests programmatically
    test_classes = [
        TestSubjectRepairStage(),
        TestTextRepairStage(),
        TestPromptRefineStage(),
        TestRefinementUtils(),
        TestRefinementIntegration()
    ]
    
    passed = 0
    failed = 0
    
    for test_class in test_classes:
        class_name = test_class.__class__.__name__
        print(f"\n📋 Testing {class_name}...")
        
        # Get all test methods
        test_methods = [method for method in dir(test_class) 
                       if method.startswith('test_') and callable(getattr(test_class, method))]
        
        for method_name in test_methods:
            try:
                method = getattr(test_class, method_name)
                method()
                print(f"  ✅ {method_name}")
                passed += 1
            except Exception as e:
                print(f"  ❌ {method_name}: {e}")
                failed += 1
    
    print(f"\n📊 Test Results: {passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    # Run tests when executed directly
    success = run_fallback_tests()
    exit(0 if success else 1) 