#!/usr/bin/env python3
"""Quick test for local embeddings without heavy dependencies."""
import os
import sys
import asyncio

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_local_embeddings():
    """Test local embeddings setup."""
    print("🧪 Testing Local Embeddings Setup")
    print("="*40)
    
    # Check environment
    use_local = os.getenv('USE_LOCAL_EMBEDDINGS', 'false').lower() == 'true'
    local_model = os.getenv('LOCAL_EMBEDDINGS_MODEL', 'sentence-transformers/all-MiniLM-L6-v2')
    
    print(f"✅ Environment configured for local embeddings: {use_local}")
    print(f"✅ Model configured: {local_model}")
    
    # Try to import service
    try:
        from knowledge.local_embeddings_service import LocalEmbeddingsService
        print("✅ LocalEmbeddingsService imported successfully")
    except ImportError as e:
        print(f"❌ Import failed: {e}")
        print("💡 Run: pip install sentence-transformers")
        return False
    
    # Try to create service (this will download model if needed)
    try:
        print("🔄 Initializing service (downloading model if needed)...")
        service = LocalEmbeddingsService(local_model)
        print(f"✅ Service created: {service.model_name}")
        
        # Get model info
        info = service.get_model_info()
        print(f"📊 Model info: {info}")
        
        return True
        
    except Exception as e:
        print(f"❌ Service initialization failed: {e}")
        return False

async def test_embedding_generation():
    """Test actual embedding generation."""
    print("\n🎯 Testing Embedding Generation")
    print("="*40)
    
    try:
        from knowledge.local_embeddings_service import get_local_embeddings_service
        
        service = get_local_embeddings_service()
        
        # Test single embedding
        test_text = "hello this is a test message for embeddings"
        print(f"🔄 Generating embedding for: '{test_text}'")
        
        result = await service.get_embedding(test_text)
        
        if result:
            print(f"✅ Embedding generated!")
            print(f"   📏 Dimensions: {len(result.embedding)}")
            print(f"   🔤 Tokens: {result.token_count}")
            print(f"   🏷️  Model: {result.model}")
            
            # Test batch
            test_texts = [
                "hello world",
                "how are you today",
                "this is a test message"
            ]
            
            print(f"\n🔄 Testing batch generation with {len(test_texts)} texts...")
            batch_results = await service.get_embeddings_batch(test_texts)
            
            successful = sum(1 for r in batch_results if r is not None)
            print(f"✅ Batch completed: {successful}/{len(test_texts)} successful")
            
            # Get performance stats
            stats = service.get_cache_stats()
            print(f"\n📊 Performance Stats:")
            print(f"   ⚡ Avg time: {stats.get('avg_time_per_embedding_ms', 0):.1f}ms")
            print(f"   💾 Cache hits: {stats.get('cache_hits', 0)}")
            print(f"   📈 Generated: {stats.get('embeddings_generated', 0)}")
            
            return True
        else:
            print("❌ Failed to generate embedding")
            return False
            
    except Exception as e:
        print(f"❌ Embedding test failed: {e}")
        return False

async def main():
    """Main test function."""
    print("🚀 NADIA Local Embeddings Test")
    print("Hardware: AMD Ryzen 7 5700 + 16GB RAM")
    print("="*50)
    
    # Test 1: Setup
    setup_ok = await test_local_embeddings()
    
    if setup_ok:
        # Test 2: Generation
        generation_ok = await test_embedding_generation()
        
        if generation_ok:
            print("\n🎉 All tests passed!")
            print("✅ Local embeddings are working perfectly")
            print("💰 Cost: $0 (no OpenAI API calls for embeddings)")
            print("🚀 Ready to use in RAG system")
        else:
            print("\n⚠️  Setup OK but generation failed")
    else:
        print("\n❌ Setup failed - check dependencies")
        print("💡 Try: pip install sentence-transformers torch transformers")

if __name__ == "__main__":
    asyncio.run(main())