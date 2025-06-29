#!/usr/bin/env python3
"""
Test script for local RAG system without MongoDB dependency.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_local_rag():
    """Test the local RAG system."""
    try:
        from knowledge.local_rag_manager import get_local_rag_manager
        
        logger.info("🚀 Testing Local RAG System")
        
        # Initialize local RAG manager
        rag_manager = await get_local_rag_manager()
        
        # Get stats
        stats = rag_manager.get_stats()
        logger.info(f"📊 RAG Stats: {stats}")
        
        # Test queries
        test_queries = [
            "Tell me about Nadia's family",
            "What does Nadia study?",
            "What are Nadia's hobbies?",
            "Where does Nadia live?",
            "What is Nadia's favorite music?"
        ]
        
        logger.info("🔍 Testing RAG queries...")
        
        for i, query in enumerate(test_queries, 1):
            logger.info(f"\n--- Test Query {i}: {query} ---")
            
            # Test RAG enhancement
            response = await rag_manager.enhance_prompt_with_context(
                user_message=query,
                user_id="test_user"
            )
            
            if response.success:
                logger.info(f"✅ Success: Confidence {response.context_used.confidence_score:.2f}")
                logger.info(f"📄 Documents found: {len(response.context_used.relevant_documents)}")
                
                if response.context_used.relevant_documents:
                    for doc in response.context_used.relevant_documents:
                        logger.info(f"   - {doc.title} (similarity: {doc.similarity_score:.2f})")
                
                # Show enhanced prompt preview
                if len(response.enhanced_prompt) > len(query):
                    logger.info(f"🔧 Enhanced prompt: {response.enhanced_prompt[:200]}...")
                else:
                    logger.info("🔧 No enhancement applied (low confidence)")
            else:
                logger.error(f"❌ Failed: {response.error_message}")
        
        logger.info("\n✅ Local RAG system test completed successfully!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_local_rag())
    sys.exit(0 if success else 1)