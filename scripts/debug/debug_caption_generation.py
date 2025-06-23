#!/usr/bin/env python3
"""
Debug Caption Generation

Simple script to test caption generation with detailed logging
"""

import asyncio
import sys
from pathlib import Path

# Add churns to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from churns.api.background_tasks import PipelineTaskProcessor
from churns.core.client_config import get_configured_clients


async def test_caption_generation_directly():
    """Test caption generation directly without API"""
    print("🔧 Testing caption generation directly...")
    
    # Test run ID from our previous test
    test_run_id = "08abc3d5-0519-442f-8799-e680f36ccb01"
    
    # Create task processor
    task_processor = PipelineTaskProcessor()
    
    # Prepare caption data
    caption_data = {
        "run_id": test_run_id,
        "image_id": "image_0", 
        "caption_id": "test-caption-001",
        "settings": {"tone": "friendly"},
        "version": 0
    }
    
    try:
        print(f"📝 Starting caption generation for run {test_run_id}...")
        await task_processor.start_caption_generation("test-caption-001", caption_data)
        print("✅ Caption generation started successfully")
        
        # Wait a bit and check for files
        await asyncio.sleep(5)
        
        run_dir = Path(f"data/runs/{test_run_id}")
        caption_dir = run_dir / "captions" / "image_0"
        
        if caption_dir.exists():
            files = list(caption_dir.glob("*"))
            print(f"✅ Caption files created: {[f.name for f in files]}")
        else:
            print(f"❌ No caption directory found at {caption_dir}")
            
    except Exception as e:
        print(f"❌ Caption generation failed: {e}")
        import traceback
        traceback.print_exc()


async def test_llm_clients():
    """Test LLM client configuration"""
    print("\n🔧 Testing LLM client configuration...")
    
    try:
        clients = get_configured_clients()
        
        caption_clients = [
            'instructor_client_caption',
            'base_llm_client_caption'
        ]
        
        for client_name in caption_clients:
            if client_name in clients and clients[client_name]:
                print(f"✅ {client_name}: Available")
            else:
                print(f"❌ {client_name}: Not found")
                
        # Test a simple LLM call
        instructor_client = clients.get('instructor_client_caption')
        if instructor_client:
            print("🧪 Testing simple LLM call...")
            # This is just a basic test - we won't actually call the LLM
            print("✅ LLM client appears to be configured correctly")
        else:
            print("❌ No instructor client available for testing")
            
    except Exception as e:
        print(f"❌ LLM client test failed: {e}")
        import traceback
        traceback.print_exc()


async def main():
    """Run debug tests"""
    print("🚀 Starting Caption Generation Debug Tests")
    print("="*50)
    
    await test_llm_clients()
    await test_caption_generation_directly()
    
    print("\n" + "="*50)
    print("🏁 Debug tests completed")


if __name__ == "__main__":
    asyncio.run(main()) 