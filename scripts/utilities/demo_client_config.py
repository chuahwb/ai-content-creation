#!/usr/bin/env python3
"""
Demo Client Configuration Test

This script tests the client configuration system and verifies that
API clients are properly set up with the real credentials from .env file.
"""

import sys
import os

# Add the project root to Python path so we can import churns
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from churns.core.client_config import get_client_config, get_configured_clients
from churns.pipeline.executor import PipelineExecutor
from churns.pipeline.context import PipelineContext


def test_client_configuration():
    """Test the client configuration system."""
    print("🧪 Testing Client Configuration System")
    print("=" * 60)
    
    # Test 1: Basic client configuration loading
    print("\n1️⃣ Testing basic client configuration...")
    try:
        config = get_client_config()
        config.print_configuration_summary()
        print("✅ Client configuration loaded successfully")
    except Exception as e:
        print(f"❌ Error loading client configuration: {e}")
        return False
    
    # Test 2: Pipeline executor with client injection
    print("\n2️⃣ Testing pipeline executor with client injection...")
    try:
        executor = PipelineExecutor()
        client_summary = executor.get_client_summary()
        
        print("Pipeline Executor Client Summary:")
        for client_name, status in client_summary.items():
            print(f"  {client_name}: {status}")
        
        configured_count = sum(1 for status in client_summary.values() if "✅" in status)
        total_count = len(client_summary)
        print(f"✅ Pipeline executor configured {configured_count}/{total_count} clients")
    except Exception as e:
        print(f"❌ Error testing pipeline executor: {e}")
        return False
    
    # Test 3: Check .env file status
    print("\n3️⃣ Checking .env file status...")
    env_path = ".env"
    if os.path.exists(env_path):
        print(f"✅ Found .env file at: {env_path}")
        
        # Read and check for API keys (without revealing them)
        with open(env_path, 'r') as f:
            env_content = f.read()
        
        keys_to_check = ['OPENROUTER_API_KEY', 'GEMINI_API_KEY', 'OPENAI_API_KEY']
        for key in keys_to_check:
            if f"{key}=" in env_content and not f"{key}=your_" in env_content:
                print(f"  ✅ {key}: Appears to be configured")
            else:
                print(f"  ⚠️ {key}: Not configured or using placeholder")
    else:
        print(f"⚠️ No .env file found at: {env_path}")
        print("   💡 Copy sample.env to .env and add your API keys")
    
    # Test 4: Quick pipeline context test
    print("\n4️⃣ Testing pipeline context creation...")
    try:
        ctx = PipelineContext()
        ctx.prompt = "Test burger image"
        ctx.task_type = "1. Product Photography"
        ctx.target_platform = {
            "name": "Instagram Post (1:1 Square)",
            "resolution_details": {"aspect_ratio": "1:1"}
        }
        print("✅ Pipeline context created successfully")
        print(f"   Prompt: {ctx.prompt}")
        print(f"   Task Type: {ctx.task_type}")
        print(f"   Platform: {ctx.target_platform['name']}")
    except Exception as e:
        print(f"❌ Error creating pipeline context: {e}")
        return False
    
    print("\n🎉 Client configuration test completed!")
    return True


def test_stage_module_loading():
    """Test that stage modules can be loaded and have the required attributes."""
    print("\n🧪 Testing Stage Module Loading")
    print("=" * 60)
    
    stages_to_test = [
        ("churns.stages.image_eval", ["instructor_client_img_eval", "IMG_EVAL_MODEL_ID"]),
        ("churns.stages.strategy", ["instructor_client_strategy", "STRATEGY_MODEL_ID"]),
        ("churns.stages.style_guide", ["instructor_client_style_guide", "STYLE_GUIDER_MODEL_ID"]),
        ("churns.stages.creative_expert", ["instructor_client_creative_expert", "CREATIVE_EXPERT_MODEL_ID"]),
        ("churns.stages.prompt_assembly", []),  # No client variables needed
        ("churns.stages.image_generation", ["image_gen_client", "IMAGE_GENERATION_MODEL_ID"])
    ]
    
    for stage_module_name, expected_attrs in stages_to_test:
        print(f"\n📦 Testing {stage_module_name}...")
        try:
            import importlib
            stage_module = importlib.import_module(stage_module_name)
            
            for attr_name in expected_attrs:
                if hasattr(stage_module, attr_name):
                    print(f"  ✅ {attr_name}: Available")
                else:
                    print(f"  ❌ {attr_name}: Missing")
            
            if hasattr(stage_module, 'run'):
                print(f"  ✅ run function: Available")
            else:
                print(f"  ❌ run function: Missing")
                
        except Exception as e:
            print(f"  ❌ Error loading {stage_module_name}: {e}")


def main():
    """Main demo function."""
    print("🚀 Churns - Client Configuration Demo")
    print("=" * 60)
    
    print("This demo tests the client configuration system that enables")
    print("the migrated codebase to work with real API calls.")
    print()
    
    # Test client configuration
    success = test_client_configuration()
    
    # Test stage module loading
    test_stage_module_loading()
    
    print("\n" + "=" * 60)
    if success:
        print("🎯 Configuration Status: READY")
        print()
        print("✅ The migrated codebase is properly configured for API calls!")
        print("📝 Next steps:")
        print("   1. Make sure your .env file has valid API keys")
        print("   2. Run the full pipeline demo: python demo_full_pipeline.py")
        print("   3. Check that real API calls are working")
    else:
        print("⚠️ Configuration Status: NEEDS ATTENTION")
        print()
        print("🔧 Please check the errors above and:")
        print("   1. Ensure .env file exists with valid API keys")
        print("   2. Install required dependencies: pip install -r requirements.txt")
        print("   3. Check for any import errors")


if __name__ == "__main__":
    main() 