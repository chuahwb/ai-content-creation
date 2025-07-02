#!/usr/bin/env python3
"""
Simplified Refinement Testing

Direct validation of refinement stages with temporary client injection.
This test confirms the stages work correctly before Phase 2.
"""

import os
import sys
import tempfile
import json
from unittest.mock import Mock
from PIL import Image

# Add the churns package to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from churns.pipeline.context import PipelineContext
from churns.stages import subject_repair, text_repair, prompt_refine
from churns.stages import image_generation  # Direct import for client injection


def create_test_image(path, size=(200, 200), color="blue"):
    """Create a test image file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img = Image.new('RGB', size, color)
    img.save(path, 'PNG')
    return path


def create_mock_client():
    """Create a mock OpenAI client."""
    mock_client = Mock()
    # Simple 1x1 PNG base64 data
    fake_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
    mock_response = Mock()
    mock_response.data = [Mock(b64_json=fake_b64)]
    mock_client.images.edit.return_value = mock_response
    return mock_client


def test_subject_repair():
    """Test subject repair stage."""
    print("🔧 Testing Subject Repair...")
    
    # Create test context
    ctx = PipelineContext()
    ctx.run_id = "test_subject_123"
    ctx.parent_run_id = "parent_123"
    ctx.parent_image_id = "image_0"
    ctx.parent_image_type = "original"
    ctx.generation_index = 0
    ctx.refinement_type = "subject"
    ctx.instructions = "Replace subject with modern version"
    ctx.cost_summary = {"stage_costs": []}
    
    # Create test images
    test_dir = tempfile.mkdtemp()
    ctx.base_image_path = create_test_image(os.path.join(test_dir, "base.png"))
    ctx.reference_image_path = create_test_image(os.path.join(test_dir, "ref.png"))
    
    # Inject mock client
    original_client = image_generation.image_gen_client
    image_generation.image_gen_client = create_mock_client()
    
    try:
        # Run the stage
        subject_repair.run(ctx)
        
        # Validate results
        assert ctx.refinement_result is not None
        assert ctx.refinement_result["type"] == "subject_repair"
        assert ctx.refinement_result["status"] == "completed"
        assert ctx.refinement_cost > 0
        
        print("   ✅ Subject repair completed successfully")
        return True
        
    except Exception as e:
        print(f"   ❌ Subject repair failed: {e}")
        return False
    finally:
        # Restore original client
        image_generation.image_gen_client = original_client


def test_text_repair():
    """Test text repair stage."""
    print("🔧 Testing Text Repair...")
    
    # Create test context
    ctx = PipelineContext()
    ctx.run_id = "test_text_123"
    ctx.parent_run_id = "parent_123"
    ctx.parent_image_id = "image_0"
    ctx.parent_image_type = "original"
    ctx.generation_index = 0
    ctx.refinement_type = "text"
    ctx.instructions = "Fix spelling and improve clarity"
    ctx.cost_summary = {"stage_costs": []}
    
    # Add original pipeline data for context enhancement
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
    
    # Create test image
    test_dir = tempfile.mkdtemp()
    ctx.base_image_path = create_test_image(os.path.join(test_dir, "base.png"))
    
    # Inject mock client
    original_client = image_generation.image_gen_client
    image_generation.image_gen_client = create_mock_client()
    
    try:
        # Run the stage
        text_repair.run(ctx)
        
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
    finally:
        # Restore original client
        image_generation.image_gen_client = original_client


def test_utilities():
    """Test utility functions."""
    print("🔧 Testing Shared Utilities...")
    
    from churns.stages.refinement_utils import (
        calculate_refinement_cost,
        create_mask_from_coordinates,
    )
    
    try:
        # Test cost calculation
        ctx = PipelineContext()
        cost = calculate_refinement_cost(ctx, "test prompt")
        assert cost > 0
        
        # Test mask creation
        ctx.mask_coordinates = json.dumps({
            "type": "rectangle",
            "x1": 0.25, "y1": 0.25,
            "x2": 0.75, "y2": 0.75
        })
        mask = create_mask_from_coordinates(ctx, (200, 200))
        assert mask is not None
        
        
        print("   ✅ All utilities working correctly")
        return True
        
    except Exception as e:
        print(f"   ❌ Utilities test failed: {e}")
        return False


def main():
    """Run all tests."""
    print("🧪 Running Simplified Refinement Tests")
    print("=" * 50)
    
    tests = [
        test_subject_repair,
        test_text_repair, 
        test_utilities
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            if test():
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
    exit(main()) 