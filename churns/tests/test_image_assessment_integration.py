"""
Image Assessment Stage Integration Tests

Tests complete integration of image assessment stage with pipeline execution,
cost tracking, and data flow validation.
"""

import pytest
import tempfile
import os
import asyncio
from unittest.mock import Mock, patch
from churns.pipeline.context import PipelineContext
from churns.pipeline.executor import PipelineExecutor
from churns.api.database import StageStatus
from churns.core.constants import IMAGE_ASSESSMENT_MODEL_ID


class TestImageAssessmentIntegration:
    """Test image assessment stage integration."""
    
    def create_test_context_with_images(self):
        """Create test context with generated images."""
        ctx = PipelineContext(
            mode="custom_mode",
            task_type="Product Photography",
            target_platform={
                "name": "Instagram Post (1:1 Square)",
                "resolution_details": {"width": 1080, "height": 1080, "aspect_ratio": "1:1"}
            },
            prompt="A delicious gourmet burger",
            creativity_level=2,
            render_text=True,
            apply_branding=False
        )
        
        # Create temp image file
        temp_dir = tempfile.mkdtemp()
        image_path = os.path.join(temp_dir, "test_burger.png")
        with open(image_path, "wb") as f:
            # Minimal PNG
            f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\x0cIDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82')
        
        # Mock previous stage outputs
        ctx.generated_image_prompts = [{
            "visual_concept": {
                "main_subject": "Gourmet burger",
                "composition_and_framing": "Close-up shot",
                "technical_quality": "High resolution"
            },
            "source_strategy_index": 0
        }]
        
        ctx.generated_image_results = [{
            "index": 0,
            "status": "success",
            "result_path": image_path
        }]
        
        ctx.output_directory = temp_dir
        return ctx
    
    def test_stage_execution_order(self):
        """Test image assessment runs after image generation."""
        executor = PipelineExecutor()
        
        img_gen_pos = executor.stages.index('image_generation')
        img_assess_pos = executor.stages.index('image_assessment')
        
        assert img_assess_pos > img_gen_pos
        assert img_assess_pos == img_gen_pos + 1
        
        print("✅ Image assessment positioned correctly after image generation")
    
    def test_data_flow_integration(self):
        """Test data flows correctly from image generation to assessment."""
        ctx = self.create_test_context_with_images()
        
        from churns.stages.image_assessment import run as run_assessment
        
        # Mock the assessment call
        with patch('churns.stages.image_assessment.ImageAssessor.assess_image') as mock_assess:
            mock_assess.return_value = {
                "assessment_scores": {"concept_adherence": 8, "technical_quality": 9},
                "assessment_justification": {"concept_adherence": "Good", "technical_quality": "High"},
                "general_score": 8.4,
                "needs_subject_repair": False,
                "needs_regeneration": False,
                "needs_text_repair": False,
                "_meta": {"tokens_used": 45000, "model": IMAGE_ASSESSMENT_MODEL_ID}
            }
            
            run_assessment(ctx)
            
            # Verify assessment was called with correct data
            mock_assess.assert_called_once()
            call_args = mock_assess.call_args
            assert call_args[1]['image_path'] == ctx.generated_image_results[0]['result_path']
            assert call_args[1]['visual_concept'] == ctx.generated_image_prompts[0]['visual_concept']
            
            # Verify results stored
            assert ctx.image_assessments is not None
            assert len(ctx.image_assessments) == 1
            assert ctx.image_assessments[0]['general_score'] == 8.4
            
            print("✅ Data flow integration works correctly")
    
    def test_cost_tracking(self):
        """Test cost tracking for image assessment."""
        ctx = self.create_test_context_with_images()
        
        from churns.stages.image_assessment import run as run_assessment
        
        with patch('churns.stages.image_assessment.ImageAssessor.assess_image') as mock_assess:
            mock_assess.return_value = {
                "assessment_scores": {"concept_adherence": 8, "technical_quality": 9},
                "assessment_justification": {"concept_adherence": "Good", "technical_quality": "High"},
                "general_score": 8.4,
                "needs_subject_repair": False,
                "needs_regeneration": False,
                "needs_text_repair": False,
                "_meta": {"tokens_used": 52000, "model": IMAGE_ASSESSMENT_MODEL_ID}
            }
            
            run_assessment(ctx)
            
            # Verify usage tracking
            assert "image_assessment" in ctx.llm_usage
            usage = ctx.llm_usage["image_assessment"][0]
            assert usage["total_tokens"] == 52000
            assert usage["model"] == IMAGE_ASSESSMENT_MODEL_ID
            assert usage["image_index"] == 0
            
            print("✅ Cost tracking works correctly") 
    
    async def test_async_execution_with_progress(self):
        """Test async execution with progress tracking."""
        ctx = self.create_test_context_with_images()
        executor = PipelineExecutor()
        
        # Track stage updates
        updates = []
        
        async def progress_callback(stage_name, stage_order, status, message, output_data, error_message, duration_seconds):
            updates.append({
                "stage": stage_name,
                "status": status,
                "duration": duration_seconds
            })
        
        # Mock assessment
        with patch('churns.stages.image_assessment.ImageAssessor.assess_image') as mock_assess:
            mock_assess.return_value = {
                "assessment_scores": {"concept_adherence": 8, "technical_quality": 9},
                "assessment_justification": {"concept_adherence": "Good", "technical_quality": "High"},
                "general_score": 8.4,
                "needs_subject_repair": False,
                "needs_regeneration": False,
                "needs_text_repair": False,
                "_meta": {"tokens_used": 48000, "model": IMAGE_ASSESSMENT_MODEL_ID}
            }
            
            # Run only image assessment stage
            executor.stages = ['image_assessment']
            
            result_ctx = await executor.run_async(ctx, progress_callback)
            
            # Verify execution updates
            assessment_updates = [u for u in updates if u["stage"] == "image_assessment"]
            assert len(assessment_updates) >= 2  # RUNNING and COMPLETED
            
            statuses = [u["status"] for u in assessment_updates]
            assert StageStatus.RUNNING in statuses
            assert StageStatus.COMPLETED in statuses
            
            # Verify results
            assert result_ctx.image_assessments is not None
            assert len(result_ctx.image_assessments) == 1
            
            print("✅ Async execution with progress tracking works")
    
    def test_error_handling_fallback(self):
        """Test error handling with simulation fallback."""
        ctx = self.create_test_context_with_images()
        
        from churns.stages.image_assessment import run as run_assessment
        
        # Mock assessment to fail
        with patch('churns.stages.image_assessment.ImageAssessor.assess_image') as mock_assess:
            mock_assess.side_effect = Exception("API Error")
            
            run_assessment(ctx)
            
            # Should use fallback, not crash
            assert ctx.image_assessments is not None
            assert len(ctx.image_assessments) == 1
            assert ctx.image_assessments[0]["_meta"]["fallback"] == True
            
            # Should log error
            error_logs = [log for log in ctx.logs if "Unexpected error during assessment:" in log]
            assert len(error_logs) > 0
            
            print("✅ Error handling with fallback works")
    
    def test_multi_image_processing(self):
        """Test processing multiple generated images."""
        ctx = self.create_test_context_with_images()
        
        # Add second image
        temp_dir = ctx.output_directory
        image_path_2 = os.path.join(temp_dir, "test_burger_2.png")
        with open(image_path_2, "wb") as f:
            f.write(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\tpHYs\x00\x00\x0b\x13\x00\x00\x0b\x13\x01\x00\x9a\x9c\x18\x00\x00\x00\x0cIDATx\x9cc\xf8\x00\x00\x00\x01\x00\x01\x00\x00\x00\x00IEND\xaeB`\x82')
        
        ctx.generated_image_results.append({
            "index": 1,
            "status": "success",
            "result_path": image_path_2
        })
        
        ctx.generated_image_prompts.append({
            "visual_concept": {"main_subject": "Premium burger"},
            "source_strategy_index": 1
        })
        
        from churns.stages.image_assessment import run as run_assessment
        
        # Mock two assessments
        with patch('churns.stages.image_assessment.ImageAssessor.assess_image') as mock_assess:
            mock_assess.side_effect = [
                {
                    "assessment_scores": {"concept_adherence": 8, "technical_quality": 9},
                    "assessment_justification": {"concept_adherence": "Good", "technical_quality": "High"},
                    "general_score": 8.4,
                    "needs_subject_repair": False,
                    "needs_regeneration": False,
                    "needs_text_repair": False,
                    "_meta": {"tokens_used": 48000, "model": IMAGE_ASSESSMENT_MODEL_ID}
                },
                {
                    "assessment_scores": {"concept_adherence": 7, "technical_quality": 8},
                    "assessment_justification": {"concept_adherence": "Good", "technical_quality": "Good"},
                    "general_score": 7.4,
                    "needs_subject_repair": False,
                    "needs_regeneration": False,
                    "needs_text_repair": False,
                    "_meta": {"tokens_used": 45000, "model": IMAGE_ASSESSMENT_MODEL_ID}
                }
            ]
            
            run_assessment(ctx)
            
            # Verify both assessments
            assert len(ctx.image_assessments) == 2
            assert mock_assess.call_count == 2
            
            assert ctx.image_assessments[0]["image_index"] == 0
            assert ctx.image_assessments[1]["image_index"] == 1
            
            # Verify usage tracking
            assert len(ctx.llm_usage["image_assessment"]) == 2
            
            print("✅ Multi-image processing works correctly")


def test_cost_calculation_accuracy():
    """Test cost calculation accuracy for different token amounts."""
    test_cases = [
        {"tokens": 45000, "expected_min": 0.008, "expected_max": 0.009},
        {"tokens": 75000, "expected_min": 0.014, "expected_max": 0.015},
    ]
    
    for case in test_cases:
        tokens = case["tokens"]
        input_tokens = int(tokens * 0.9)
        output_tokens = int(tokens * 0.1)
        cost = (input_tokens / 1_000_000) * 0.150 + (output_tokens / 1_000_000) * 0.600
        
        assert case["expected_min"] <= cost <= case["expected_max"]
        print(f"✅ {tokens:,} tokens → ${cost:.6f}")


if __name__ == "__main__":
    test_class = TestImageAssessmentIntegration()
    
    # Run sync tests
    test_class.test_stage_execution_order()
    test_class.test_data_flow_integration()
    test_class.test_cost_tracking()
    test_class.test_error_handling_fallback()
    test_class.test_multi_image_processing()
    
    # Run async test
    asyncio.run(test_class.test_async_execution_with_progress())
    
    # Run cost test
    test_cost_calculation_accuracy()
    
    print("\n🎉 All image assessment integration tests passed!") 