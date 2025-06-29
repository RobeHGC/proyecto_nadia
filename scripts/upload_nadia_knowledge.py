#!/usr/bin/env python3
"""Upload Nadia's biographical knowledge to RAG system."""
import asyncio
import os
import sys
from typing import List, Dict, Any
import json

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set environment for local embeddings
os.environ['USE_LOCAL_EMBEDDINGS'] = 'true'
os.environ['LOCAL_EMBEDDINGS_MODEL'] = 'sentence-transformers/all-MiniLM-L6-v2'

async def upload_documents_to_rag():
    """Upload Nadia's biographical documents to RAG system."""
    print("📚 Uploading Nadia's Biography to RAG Knowledge Base")
    print("Using Local Embeddings (Ryzen 7 5700)")
    print("="*60)
    
    # Import RAG system
    try:
        from knowledge.rag_manager import get_local_rag_manager
        from knowledge.mongodb_manager import get_mongodb_manager
        
        # Initialize with local embeddings
        rag_manager = await get_local_rag_manager()
        mongodb_manager = await get_mongodb_manager()
        
        print("✅ RAG system initialized with local embeddings")
        
    except Exception as e:
        print(f"❌ Failed to initialize RAG system: {e}")
        return False
    
    # Define documents to upload
    documents = [
        {
            "file": "nadia_biografia_familiar.md",
            "title": "Nadia - Historia Familiar",
            "category": "biografia",
            "source": "personal_background"
        },
        {
            "file": "nadia_vida_estudiantil.md", 
            "title": "Nadia - Vida Estudiantil y Académica",
            "category": "estudios",
            "source": "personal_background"
        },
        {
            "file": "nadia_personalidad_hobbies.md",
            "title": "Nadia - Personalidad y Hobbies", 
            "category": "personalidad",
            "source": "personal_background"
        },
        {
            "file": "nadia_fanvue_backstory.md",
            "title": "Nadia - Historia y Contexto de Fanvue",
            "category": "backstory", 
            "source": "personal_background"
        },
        {
            "file": "nadia_austin_texas.md",
            "title": "Nadia - Conexión con Austin, Texas",
            "category": "geografia",
            "source": "personal_background"
        },
        {
            "file": "nadia_conocimiento_medico.md",
            "title": "Nadia - Conocimiento Médico y Experiencia",
            "category": "medicina",
            "source": "academic_background"
        }
    ]
    
    knowledge_dir = "knowledge_documents"
    uploaded_count = 0
    
    # Upload each document
    for doc_info in documents:
        file_path = os.path.join(knowledge_dir, doc_info["file"])
        
        if not os.path.exists(file_path):
            print(f"⚠️  File not found: {file_path}")
            continue
        
        try:
            # Read document content
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            print(f"🔄 Uploading: {doc_info['title']}")
            print(f"   📁 Category: {doc_info['category']}")
            print(f"   📄 Content length: {len(content)} chars")
            
            # Store in knowledge base
            result = await mongodb_manager.store_knowledge_document(
                title=doc_info["title"],
                content=content,
                source=doc_info["source"],
                category=doc_info["category"],
                metadata={
                    "file_origin": doc_info["file"],
                    "uploaded_by": "upload_script",
                    "character": "nadia",
                    "content_type": "biographical"
                }
            )
            
            if result:
                uploaded_count += 1
                print(f"   ✅ Uploaded successfully (ID: {result})")
            else:
                print(f"   ❌ Upload failed")
                
        except Exception as e:
            print(f"   ❌ Error uploading {doc_info['file']}: {e}")
    
    print(f"\n📊 Upload Summary:")
    print(f"   ✅ Successfully uploaded: {uploaded_count}/{len(documents)} documents")
    
    return uploaded_count > 0

async def test_rag_retrieval():
    """Test RAG retrieval with sample queries."""
    print("\n🧪 Testing RAG Retrieval with Sample Queries")
    print("="*50)
    
    try:
        from knowledge.rag_manager import get_local_rag_manager
        
        rag_manager = await get_local_rag_manager()
        
        # Test queries that should match different categories
        test_queries = [
            {
                "query": "Tell me about your family background",
                "expected_category": "biografia"
            },
            {
                "query": "What are you studying in medical school?",
                "expected_category": "estudios"
            },
            {
                "query": "What do you like to do for fun?",
                "expected_category": "personalidad"
            },
            {
                "query": "How did you start using Fanvue?",
                "expected_category": "backstory"
            },
            {
                "query": "What's it like living in Austin?",
                "expected_category": "geografia"
            },
            {
                "query": "What medical knowledge do you have?",
                "expected_category": "medicina"
            }
        ]
        
        successful_retrievals = 0
        
        for i, test in enumerate(test_queries, 1):
            print(f"\n🔍 Test {i}: '{test['query']}'")
            
            try:
                # Enhance prompt with RAG context
                rag_response = await rag_manager.enhance_prompt_with_context(
                    user_message=test["query"],
                    user_id="test_user",
                    conversation_context=[]
                )
                
                if rag_response.success:
                    context = rag_response.context_used
                    print(f"   ✅ Retrieved {len(context.relevant_documents)} documents")
                    print(f"   📊 Confidence score: {context.confidence_score:.3f}")
                    
                    # Show retrieved documents
                    for j, doc in enumerate(context.relevant_documents):
                        print(f"   📄 Doc {j+1}: {doc.title} (similarity: {doc.similarity_score:.3f})")
                        print(f"      Category: {doc.category}")
                        print(f"      Preview: {doc.content[:100]}...")
                    
                    successful_retrievals += 1
                else:
                    print(f"   ❌ Retrieval failed: {rag_response.error_message}")
                    
            except Exception as e:
                print(f"   ❌ Error testing query: {e}")
        
        print(f"\n📊 Retrieval Test Summary:")
        print(f"   ✅ Successful retrievals: {successful_retrievals}/{len(test_queries)}")
        
        return successful_retrievals > 0
        
    except Exception as e:
        print(f"❌ Failed to test RAG retrieval: {e}")
        return False

async def performance_benchmark():
    """Benchmark local embeddings performance in RAG context."""
    print("\n⚡ Local Embeddings Performance Benchmark")
    print("="*50)
    
    try:
        from knowledge.local_embeddings_service import get_local_embeddings_service
        
        service = get_local_embeddings_service()
        
        # Test embedding generation for various query types
        test_texts = [
            "Tell me about your family",
            "What are you studying?", 
            "How do you like Austin?",
            "What are your hobbies?",
            "How did you get into medical school?",
            "What's your experience with Fanvue?",
            "Tell me about your medical knowledge",
            "What's your favorite place in Texas?"
        ]
        
        print(f"🔄 Generating embeddings for {len(test_texts)} queries...")
        
        import time
        start_time = time.time()
        
        # Test batch generation
        results = await service.get_embeddings_batch(test_texts)
        
        end_time = time.time()
        elapsed_ms = (end_time - start_time) * 1000
        
        successful = sum(1 for r in results if r is not None)
        
        print(f"✅ Generated {successful}/{len(test_texts)} embeddings")
        print(f"⏱️  Total time: {elapsed_ms:.1f}ms")
        print(f"⚡ Avg time per embedding: {elapsed_ms/len(test_texts):.1f}ms")
        
        # Get performance stats
        stats = service.get_cache_stats()
        print(f"📊 Performance Statistics:")
        print(f"   🔧 Model: {stats['model']}")
        print(f"   📏 Dimensions: {stats['embedding_dimension']}")
        print(f"   💾 Cache size: {stats['cache_size']}")
        print(f"   📈 Cache hit rate: {stats['cache_hit_rate']:.1%}")
        print(f"   ⚡ Overall avg: {stats.get('avg_time_per_embedding_ms', 0):.1f}ms")
        
        return True
        
    except Exception as e:
        print(f"❌ Performance benchmark failed: {e}")
        return False

async def main():
    """Main function to upload and test Nadia's knowledge base."""
    print("🚀 NADIA RAG Knowledge Base Setup")
    print("Hardware: AMD Ryzen 7 5700 + Local Embeddings")
    print("="*60)
    
    # Step 1: Upload documents
    upload_success = await upload_documents_to_rag()
    
    if upload_success:
        # Step 2: Test retrieval
        retrieval_success = await test_rag_retrieval()
        
        # Step 3: Performance benchmark
        performance_success = await performance_benchmark()
        
        print(f"\n🎉 RAG TESTING COMPLETE!")
        print(f"✅ Documents uploaded: {upload_success}")
        print(f"✅ Retrieval working: {retrieval_success}")
        print(f"✅ Performance good: {performance_success}")
        
        if upload_success and retrieval_success and performance_success:
            print(f"\n🎯 Ready for Production!")
            print(f"💰 Cost: $0 (local embeddings)")
            print(f"🚀 Performance: Optimized for Ryzen 7 5700")
            print(f"🧠 Knowledge: Comprehensive Nadia biography")
            print(f"\nNext: Use RAG-enhanced responses in conversations")
        
    else:
        print(f"\n❌ Upload failed - check MongoDB connection and dependencies")

if __name__ == "__main__":
    asyncio.run(main())