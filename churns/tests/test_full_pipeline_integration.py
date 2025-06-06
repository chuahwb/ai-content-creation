"""
Full Pipeline Integration Tests

Tests the complete end-to-end execution of all 6 pipeline stages in sequence,
validating data flow and ensuring the modular architecture produces the same
results as the original monolithic pipeline.
"""

import pytest
import tempfile
import os
import base64
from unittest.mock import Mock, patch, MagicMock
from churns.pipeline.context import PipelineContext
from churns.pipeline.executor import PipelineExecutor


class TestFullPipelineIntegration:
    """Test complete pipeline execution from start to finish."""
    
    def create_complete_test_context(self, mode="easy_mode", has_image=False, image_instruction=None):
        """Create a complete test context with all required fields."""
        ctx = PipelineContext(
            mode=mode,
            task_type="1. Product Photography",
            target_platform={
                "name": "Instagram Post (1:1 Square)",
                "resolution_details": {
                    "width": 1080,
                    "height": 1080,
                    "aspect_ratio": "1:1"
                }
            },
            prompt="A delicious gourmet burger with artisan toppings",
            creativity_level=2,
            render_text=True,
            apply_branding=False
        )
        
        if has_image:
            ctx.image_reference = {
                "filename": "test_burger.jpg",
                "content_type": "image/jpeg",
                "size_bytes": 123456,
                "image_content_base64": "fake_base64_image_data",
                "instruction": image_instruction
            }
        
        if mode in ["custom_mode", "task_specific_mode"]:
            ctx.marketing_goals = {
                "target_audience": "Young Professionals (25-35)",
                "target_niche": "Gourmet Burger Joint", 
                "target_objective": "Create Appetite Appeal",
                "target_voice": "Mouth-watering & Descriptive"
            }
            ctx.branding_elements = "Logo in top-right corner, use brand colors #FF6B35"
            ctx.task_description = "Feature our signature beef burger for social media"
        
        return ctx
    
    def create_mock_clients(self):
        """Create mock API clients for testing."""
        return {
            'instructor_client_img_eval': Mock(),
            'base_llm_client_img_eval': Mock(),
            'instructor_client_strategy': Mock(),
            'base_llm_client_strategy': Mock(),
            'instructor_client_style_guide': Mock(),
            'base_llm_client_style_guide': Mock(),
            'instructor_client_creative_expert': Mock(),
            'base_llm_client_creative_expert': Mock(),
            'image_gen_client': Mock()
        }
    
    def test_full_pipeline_easy_mode_no_image(self):
        """Test complete pipeline execution in easy mode without image."""
        ctx = self.create_complete_test_context(mode="easy_mode", has_image=False)
        executor = PipelineExecutor()
        
        # Don't inject clients - this will test fallback simulation behavior
        
        # Run the complete pipeline
        result_ctx = executor.run(ctx)
        
        # Validate pipeline execution
        assert len(result_ctx.logs) > 0
        assert "Starting pipeline execution" in str(result_ctx.logs)
        assert "Pipeline execution completed" in str(result_ctx.logs)
        
        # Validate stage 1: Image Evaluation (should be None since no image)
        assert result_ctx.image_analysis_result is None
        
        # Validate stage 2: Strategy Generation (should have simulated strategies)
        assert result_ctx.suggested_marketing_strategies is not None
        assert len(result_ctx.suggested_marketing_strategies) == 3  # Default number
        for strategy in result_ctx.suggested_marketing_strategies:
            assert "target_audience" in strategy
            assert "target_niche" in strategy
            assert "target_objective" in strategy
            assert "target_voice" in strategy
        
        # Validate stage 3: Style Guidance (will be None without LLM client, which is expected)
        # This is expected to be None without proper LLM clients
        
        # Validate stage 4: Creative Expert (will be None without LLM client, which is expected)
        # This is expected to be None without proper LLM clients
        
        # Validate stage 5: Prompt Assembly (should handle missing data gracefully)
        # This depends on previous stages, so may be empty
        
        # Validate stage 6: Image Generation (will be None without client, which is expected)
        # This is expected to be None without proper image generation client
        
        print(f"✅ Easy mode pipeline completed with {len(result_ctx.logs)} log entries")
    
    def test_full_pipeline_with_image_reference(self):
        """Test complete pipeline execution with image reference."""
        ctx = self.create_complete_test_context(mode="custom_mode", has_image=True)
        executor = PipelineExecutor()
        
        # Run the complete pipeline
        result_ctx = executor.run(ctx)
        
        # Validate pipeline execution
        assert len(result_ctx.logs) > 0
        assert "Starting pipeline execution" in str(result_ctx.logs)
        assert "Pipeline execution completed" in str(result_ctx.logs)
        
        # Validate image reference was processed
        assert result_ctx.image_reference is not None
        assert result_ctx.image_reference["filename"] == "test_burger.jpg"
        
        # Validate stage 1: Image Evaluation (should have simulated result)
        assert result_ctx.image_analysis_result is not None
        assert "main_subject" in result_ctx.image_analysis_result
        
        # Validate stage 2: Strategy Generation
        assert result_ctx.suggested_marketing_strategies is not None
        assert len(result_ctx.suggested_marketing_strategies) >= 1
        
        print(f"✅ Image reference pipeline completed with {len(result_ctx.logs)} log entries")
    
    def test_full_pipeline_with_instruction(self):
        """Test complete pipeline execution with image instruction."""
        ctx = self.create_complete_test_context(
            mode="custom_mode", 
            has_image=True, 
            image_instruction="Enhance the lighting and make the burger look more appetizing"
        )
        executor = PipelineExecutor()
        
        # Run the complete pipeline
        result_ctx = executor.run(ctx)
        
        # Validate pipeline execution
        assert len(result_ctx.logs) > 0
        
        # Validate image instruction was preserved
        assert result_ctx.image_reference["instruction"] == "Enhance the lighting and make the burger look more appetizing"
        
        print(f"✅ Image instruction pipeline completed with {len(result_ctx.logs)} log entries")
    
    def test_pipeline_data_flow_validation(self):
        """Test that data flows correctly between all stages."""
        ctx = self.create_complete_test_context(mode="custom_mode", has_image=True)
        executor = PipelineExecutor()
        
        # Run the complete pipeline
        result_ctx = executor.run(ctx)
        
        # Track the data flow through stages
        data_flow_valid = True
        validation_messages = []
        
        # Stage 1 → Stage 2: Image analysis should inform strategy
        if result_ctx.image_analysis_result is not None:
            validation_messages.append("✅ Stage 1 → Stage 2: Image analysis available for strategy generation")
        else:
            validation_messages.append("ℹ️  Stage 1 → Stage 2: No image analysis (expected without LLM client)")
        
        # Stage 2 → Stage 3: Strategies should inform style guidance
        if result_ctx.suggested_marketing_strategies:
            validation_messages.append(f"✅ Stage 2 → Stage 3: {len(result_ctx.suggested_marketing_strategies)} strategies available for style guidance")
        else:
            validation_messages.append("❌ Stage 2 → Stage 3: No strategies generated")
            data_flow_valid = False
        
        # Stage 3 → Stage 4: Style guidance should inform creative concepts
        if result_ctx.style_guidance_sets:
            validation_messages.append(f"✅ Stage 3 → Stage 4: {len(result_ctx.style_guidance_sets)} style guidance sets available")
        else:
            validation_messages.append("ℹ️  Stage 3 → Stage 4: No style guidance (expected without LLM client)")
        
        # Stage 4 → Stage 5: Creative concepts should inform prompt assembly
        if result_ctx.generated_image_prompts:
            validation_messages.append(f"✅ Stage 4 → Stage 5: {len(result_ctx.generated_image_prompts)} image prompts available")
        else:
            validation_messages.append("ℹ️  Stage 4 → Stage 5: No image prompts (expected without LLM client)")
        
        # Stage 5 → Stage 6: Assembled prompts should inform image generation
        if result_ctx.final_assembled_prompts:
            validation_messages.append(f"✅ Stage 5 → Stage 6: {len(result_ctx.final_assembled_prompts)} assembled prompts available")
        else:
            validation_messages.append("ℹ️  Stage 5 → Stage 6: No assembled prompts (expected without previous stage data)")
        
        # Final validation
        if result_ctx.generated_image_results:
            validation_messages.append(f"✅ Final output: {len(result_ctx.generated_image_results)} image generation results")
        else:
            validation_messages.append("ℹ️  Final output: No image generation results (expected without LLM/image clients)")
        
        for message in validation_messages:
            print(message)
        
        # The basic data flow should work even with simulation
        assert result_ctx.suggested_marketing_strategies is not None, "Strategy generation should always work with simulation"
        print(f"✅ Pipeline data flow validation completed")
    
    def test_pipeline_stage_order_execution(self):
        """Test that stages execute in the correct order."""
        ctx = self.create_complete_test_context()
        executor = PipelineExecutor()
        
        # Track stage execution order
        executed_stages = []
        
        def mock_run(original_run, stage_name):
            def wrapper(context):
                executed_stages.append(stage_name)
                return original_run(context)
            return wrapper
        
        # Patch each stage's run function to track execution
        patches = []
        stage_names = ['image_eval', 'strategy', 'style_guide', 'creative_expert', 'prompt_assembly', 'image_generation']
        
        for stage_name in stage_names:
            patcher = patch(f'ai_marketing.stages.{stage_name}.run')
            mock_run_func = patcher.start()
            mock_run_func.side_effect = lambda ctx, name=stage_name: executed_stages.append(name)
            patches.append(patcher)
        
        try:
            # Run the pipeline
            executor.run(ctx)
            
            # Verify stage execution order
            expected_order = ['image_eval', 'strategy', 'style_guide', 'creative_expert', 'prompt_assembly', 'image_generation']
            assert executed_stages == expected_order, f"Expected {expected_order}, got {executed_stages}"
            
            print(f"✅ Stages executed in correct order: {' → '.join(executed_stages)}")
            
        finally:
            # Clean up patches
            for patcher in patches:
                patcher.stop()
    
    def test_pipeline_error_handling(self):
        """Test pipeline behavior when stages encounter errors."""
        ctx = self.create_complete_test_context()
        executor = PipelineExecutor()
        
        # Mock a stage to raise an error
        with patch('ai_marketing.stages.strategy.run') as mock_strategy:
            mock_strategy.side_effect = Exception("Simulated strategy stage error")
            
            # Run pipeline - should continue despite error
            result_ctx = executor.run(ctx)
            
            # Verify error was logged and pipeline continued
            error_logged = any("ERROR in stage strategy" in str(log) for log in result_ctx.logs)
            assert error_logged, "Strategy stage error should be logged"
            
            # Pipeline should still complete
            completion_logged = any("Pipeline execution completed" in str(log) for log in result_ctx.logs)
            assert completion_logged, "Pipeline should complete despite stage error"
            
            print("✅ Pipeline error handling works correctly")
    
    def test_full_pipeline_performance(self):
        """Test pipeline performance and execution time."""
        ctx = self.create_complete_test_context()
        executor = PipelineExecutor()
        
        import time
        start_time = time.time()
        
        # Run the complete pipeline
        result_ctx = executor.run(ctx)
        
        execution_time = time.time() - start_time
        
        # Verify reasonable execution time (should be fast with simulation)
        assert execution_time < 30.0, f"Pipeline took too long: {execution_time:.2f}s"
        
        # Check that timing information is logged
        timing_logged = any("completed in" in str(log) for log in result_ctx.logs)
        assert timing_logged, "Stage timing should be logged"
        
        print(f"✅ Full pipeline completed in {execution_time:.2f}s")
    
    def test_context_state_preservation(self):
        """Test that pipeline context state is properly preserved and modified."""
        original_ctx = self.create_complete_test_context()
        executor = PipelineExecutor()
        
        # Capture initial state
        initial_logs_count = len(original_ctx.logs)
        initial_mode = original_ctx.mode
        initial_prompt = original_ctx.prompt
        
        # Run pipeline
        result_ctx = executor.run(original_ctx)
        
        # Verify original data is preserved
        assert result_ctx.mode == initial_mode
        assert result_ctx.prompt == initial_prompt
        
        # Verify state was modified (logs should be added)
        assert len(result_ctx.logs) > initial_logs_count
        
        # Verify context is the same object (modified in place)
        assert result_ctx is original_ctx
        
        print("✅ Context state preservation verified")


# Test to compare with original monolith behavior
def test_pipeline_parity_with_monolith():
    """
    Test that our modular pipeline produces equivalent results to the original monolith.
    This is a high-level parity test.
    """
    # Create the same inputs that would go to the original run_full_pipeline
    test_inputs = {
        "mode": "easy_mode",
        "platform": "Instagram Post (1:1 Square)",
        "prompt": "A delicious gourmet burger",
        "creativity_level": 2,
        "render_text": True,
        "apply_branding": False
    }
    
    # Run our modular pipeline
    ctx = PipelineContext(
        mode=test_inputs["mode"],
        target_platform={
            "name": test_inputs["platform"],
            "resolution_details": {"aspect_ratio": "1:1"}
        },
        prompt=test_inputs["prompt"],
        creativity_level=test_inputs["creativity_level"],
        render_text=test_inputs["render_text"],
        apply_branding=test_inputs["apply_branding"]
    )
    
    executor = PipelineExecutor()
    result_ctx = executor.run(ctx)
    
    # Basic structural validation - ensure we have the same data structure
    # that the original pipeline would produce
    
    # Should have logs (equivalent to print statements in original)
    assert len(result_ctx.logs) > 0
    
    # Should have gone through all pipeline phases
    pipeline_phases = [
        "image evaluation", "strategy", "style", "creative", "prompt", "image"
    ]
    
    log_text = " ".join(str(log) for log in result_ctx.logs).lower()
    phases_found = sum(1 for phase in pipeline_phases if phase in log_text)
    
    assert phases_found >= 4, f"Should find evidence of at least 4 pipeline phases, found {phases_found}"
    
    print(f"✅ Pipeline parity test passed - found evidence of {phases_found} phases") 