#!/usr/bin/env python3
"""
Quick Refinement Testing Script

This script provides temporary fallbacks and simplified testing for the
refinement stages before Phase 2 implementation. It validates:
- Stage execution flow
- Shared utilities integration  
- Cost calculation and tracking
- File management and organization
- Error handling patterns

Can be run directly to validate refinement functionality.
"""

import os
import sys
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch
from PIL import Image

# Add the churns package to the path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from churns.pipeline.context import PipelineContext
from churns.stages import subject_repair, text_repair, prompt_refine
from churns.stages.refinement_utils import (
    calculate_refinement_cost,
    create_mask_from_coordinates,
    enhance_prompt_with_creativity_guidance
)


class RefinementTestRunner:
    """Quick test runner for refinement stages with fallbacks."""
    
    def __init__(self):
        self.test_dir = tempfile.mkdtemp(prefix="refinement_test_")
        self.results = {"passed": 0, "failed": 0, "details": []}
        print(f"🧪 Refinement Test Runner initialized")
        print(f"📁 Test directory: {self.test_dir}")
    
    def create_test_context(self, refinement_type="subject", has_mask=False):
        """Create a complete test context for refinement testing."""
        ctx = PipelineContext()
        
        # Basic refinement properties
        ctx.run_id = f"test_refinement_{refinement_type}_001"
        ctx.parent_run_id = "test_parent_run_123"
        ctx.parent_image_id = "image_0"
        ctx.parent_image_type = "original"
        ctx.generation_index = 0
        ctx.refinement_type = refinement_type
        ctx.creativity_level = 2
        
        # Create test images
        ctx.base_image_path = os.path.join(self.test_dir, f"base_{refinement_type}.png")
        self._create_test_image(ctx.base_image_path, (200, 200), "blue")
        
        # Set up base image metadata for cost calculation
        ctx.base_image_metadata = {"width": 200, "height": 200}
        
        # Type-specific setup
        if refinement_type == "subject":
            ctx.instructions = "Replace the main subject with a modern, professional version"
            ctx.reference_image_path = os.path.join(self.test_dir, "reference.png")
            self._create_test_image(ctx.reference_image_path, (150, 150), "green")
        
        elif refinement_type == "text":
            ctx.instructions = "Fix spelling errors and improve text readability"
        
        elif refinement_type == "prompt":
            ctx.prompt = "Add warm sunset lighting and enhance colors"
            if has_mask:
                ctx.mask_coordinates = json.dumps({
                    "type": "rectangle",
                    "x1": 0.1, "y1": 0.1,
                    "x2": 0.9, "y2": 0.9
                })
        
        # Add original pipeline context for enhanced prompts
        ctx.original_pipeline_data = {
            "processing_context": {
                "style_guidance_sets": [
                    {"style_keywords": ["professional", "modern", "clean"]}
                ],
                "suggested_marketing_strategies": [
                    {"target_audience": "food enthusiasts", "platform": "Instagram"}
                ]
            }
        }
        
        # Initialize cost tracking
        ctx.cost_summary = {"stage_costs": []}
        
        return ctx
    
    def _create_test_image(self, path, size=(100, 100), color="red"):
        """Create a test image file."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        img = Image.new('RGB', size, color)
        img.save(path, 'PNG')
        return path
    
    def create_mock_client(self):
        """Create a mock OpenAI client with successful response."""
        mock_client = Mock()
        
        # Create a simple base64 encoded 1x1 PNG image
        fake_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        
        mock_response = Mock()
        mock_response.data = [Mock(b64_json=fake_b64)]
        
        mock_client.images.edit.return_value = mock_response
        return mock_client
    
    def test_stage(self, stage_name, stage_func, context):
        """Test a single refinement stage."""
        test_name = f"{stage_name}_execution"
        
        try:
            print(f"  🔧 Testing {stage_name}...")
            
            # Create mock client for the test
            mock_client = self.create_mock_client()
            
            # Patch the image_generation module to provide our mock client
            with patch('churns.stages.image_generation') as mock_image_gen:
                mock_image_gen.image_gen_client = mock_client
                
                # Run the stage
                stage_func(context)
            
            # Validate results
            assert context.refinement_result is not None, "No refinement result produced"
            assert context.refinement_result["status"] == "completed", "Stage did not complete successfully"
            assert context.refinement_result["output_path"] is not None, "No output path generated"
            assert context.refinement_cost is not None, "No cost calculated"
            assert context.refinement_cost > 0, "Cost should be greater than 0"
            
            # Verify API was called
            mock_client.images.edit.assert_called_once()
            
            self._record_success(test_name, f"✅ {stage_name} executed successfully")
            return True
            
        except Exception as e:
            self._record_failure(test_name, f"❌ {stage_name} failed: {e}")
            return False
    
    def test_subject_repair(self):
        """Test subject repair stage."""
        print("\n📋 Testing Subject Repair Stage...")
        ctx = self.create_test_context("subject")
        return self.test_stage("subject_repair", subject_repair.run, ctx)
    
    def test_text_repair(self):
        """Test text repair stage."""
        print("\n📋 Testing Text Repair Stage...")
        ctx = self.create_test_context("text")
        return self.test_stage("text_repair", text_repair.run, ctx)
    
    def test_prompt_refine_global(self):
        """Test global prompt refinement (no mask)."""
        print("\n📋 Testing Prompt Refinement (Global)...")
        ctx = self.create_test_context("prompt", has_mask=False)
        return self.test_stage("prompt_refine_global", prompt_refine.run, ctx)
    
    def test_prompt_refine_regional(self):
        """Test regional prompt refinement (with mask)."""
        print("\n📋 Testing Prompt Refinement (Regional)...")
        ctx = self.create_test_context("prompt", has_mask=True)
        return self.test_stage("prompt_refine_regional", prompt_refine.run, ctx)
    
    def test_shared_utilities(self):
        """Test shared utility functions."""
        print("\n📋 Testing Shared Utilities...")
        
        tests = [
            self._test_cost_calculation,
            self._test_mask_creation,
            self._test_prompt_enhancement
        ]
        
        all_passed = True
        for test in tests:
            if not test():
                all_passed = False
        
        return all_passed
    
    def _test_cost_calculation(self):
        """Test cost calculation utility."""
        try:
            ctx = self.create_test_context("text")
            
            # Test basic cost calculation
            cost = calculate_refinement_cost(ctx, "test prompt")
            assert cost > 0, "Cost should be positive"
            
            # Test with different creativity levels
            ctx.creativity_level = 1
            cost_low = calculate_refinement_cost(ctx, "test prompt")
            ctx.creativity_level = 3  
            cost_high = calculate_refinement_cost(ctx, "test prompt")
            assert cost_high > cost_low, "Higher creativity should cost more"
            
            # Test with mask
            cost_mask = calculate_refinement_cost(ctx, "test prompt", has_mask=True)
            cost_no_mask = calculate_refinement_cost(ctx, "test prompt", has_mask=False)
            assert cost_mask > cost_no_mask, "Masked editing should cost slightly more"
            
            self._record_success("cost_calculation", "✅ Cost calculation working correctly")
            return True
            
        except Exception as e:
            self._record_failure("cost_calculation", f"❌ Cost calculation failed: {e}")
            return False
    
    def _test_mask_creation(self):
        """Test mask creation from coordinates."""
        try:
            ctx = PipelineContext()
            image_size = (200, 200)
            
            # Test rectangle mask
            ctx.mask_coordinates = json.dumps({
                "type": "rectangle",
                "x1": 0.25, "y1": 0.25,
                "x2": 0.75, "y2": 0.75
            })
            
            mask = create_mask_from_coordinates(ctx, image_size)
            assert mask is not None, "Rectangle mask should be created"
            assert mask.size == image_size, "Mask size should match image size"
            
            # Test circle mask
            ctx.mask_coordinates = json.dumps({
                "type": "circle",
                "cx": 0.5, "cy": 0.5,
                "radius": 0.25
            })
            
            mask = create_mask_from_coordinates(ctx, image_size)
            assert mask is not None, "Circle mask should be created"
            
            # Test no mask
            ctx.mask_coordinates = None
            mask = create_mask_from_coordinates(ctx, image_size)
            assert mask is None, "No mask should be created when coordinates are None"
            
            self._record_success("mask_creation", "✅ Mask creation working correctly")
            return True
            
        except Exception as e:
            self._record_failure("mask_creation", f"❌ Mask creation failed: {e}")
            return False
    
    def _test_prompt_enhancement(self):
        """Test prompt enhancement utility."""
        try:
            base_prompt = "Improve this image"
            
            # Test different creativity levels
            enhanced_1 = enhance_prompt_with_creativity_guidance(base_prompt, 1, "subject")
            enhanced_2 = enhance_prompt_with_creativity_guidance(base_prompt, 2, "subject")
            enhanced_3 = enhance_prompt_with_creativity_guidance(base_prompt, 3, "subject")
            
            assert "subtle" in enhanced_1.lower(), "Level 1 should include 'subtle'"
            assert "moderate" in enhanced_2.lower(), "Level 2 should include 'moderate'"
            assert "creative" in enhanced_3.lower() or "bold" in enhanced_3.lower(), "Level 3 should include creative language"
            
            # Test different refinement types
            subject_enhanced = enhance_prompt_with_creativity_guidance(base_prompt, 2, "subject")
            text_enhanced = enhance_prompt_with_creativity_guidance(base_prompt, 2, "text")
            prompt_enhanced = enhance_prompt_with_creativity_guidance(base_prompt, 2, "prompt")
            
            assert len(subject_enhanced) > len(base_prompt), "Enhancement should add content"
            assert len(text_enhanced) > len(base_prompt), "Enhancement should add content"
            assert len(prompt_enhanced) > len(base_prompt), "Enhancement should add content"
            
            self._record_success("prompt_enhancement", "✅ Prompt enhancement working correctly")
            return True
            
        except Exception as e:
            self._record_failure("prompt_enhancement", f"❌ Prompt enhancement failed: {e}")
            return False
    
    def _record_success(self, test_name, message):
        """Record a successful test."""
        self.results["passed"] += 1
        self.results["details"].append({"test": test_name, "status": "PASS", "message": message})
        print(f"    {message}")
    
    def _record_failure(self, test_name, message):
        """Record a failed test."""
        self.results["failed"] += 1
        self.results["details"].append({"test": test_name, "status": "FAIL", "message": message})
        print(f"    {message}")
    
    def run_all_tests(self):
        """Run all refinement tests."""
        print("🚀 Starting Comprehensive Refinement Testing...")
        print("=" * 60)
        
        # Run stage tests
        self.test_subject_repair()
        self.test_text_repair()
        self.test_prompt_refine_global()
        self.test_prompt_refine_regional()
        
        # Run utility tests
        self.test_shared_utilities()
        
        # Print summary
        self.print_summary()
        
        return self.results["failed"] == 0
    
    def print_summary(self):
        """Print test results summary."""
        print("\n" + "=" * 60)
        print("📊 TEST RESULTS SUMMARY")
        print("=" * 60)
        
        total_tests = self.results["passed"] + self.results["failed"]
        success_rate = (self.results["passed"] / total_tests * 100) if total_tests > 0 else 0
        
        print(f"✅ Passed: {self.results['passed']}")
        print(f"❌ Failed: {self.results['failed']}")
        print(f"📈 Success Rate: {success_rate:.1f}%")
        
        if self.results["failed"] == 0:
            print("\n🎉 ALL TESTS PASSED! Refinement stages are ready for Phase 2.")
        else:
            print(f"\n⚠️  {self.results['failed']} tests failed. Review details above.")
        
        print(f"\n🗂️  Test artifacts saved in: {self.test_dir}")
        print("=" * 60)
    
    def cleanup(self):
        """Clean up test artifacts."""
        try:
            import shutil
            shutil.rmtree(self.test_dir, ignore_errors=True)
            print(f"🧹 Cleaned up test directory: {self.test_dir}")
        except Exception as e:
            print(f"⚠️  Could not clean up test directory: {e}")


def main():
    """Main test execution function."""
    runner = RefinementTestRunner()
    
    try:
        success = runner.run_all_tests()
        return 0 if success else 1
    except KeyboardInterrupt:
        print("\n⚠️  Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"\n💥 Unexpected error during testing: {e}")
        return 1
    finally:
        # Optionally clean up (comment out to keep test artifacts for inspection)
        # runner.cleanup()
        pass


if __name__ == "__main__":
    exit(main()) 