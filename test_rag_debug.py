#!/usr/bin/env python3
"""
Debug RAG similarity calculations.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def debug_rag_similarity():
    """Debug RAG similarity calculations in detail."""
    try:
        logger.info("🔍 Debugging RAG Similarity Calculations...")
        
        from knowledge.local_rag_manager import LocalRAGManager
        
        # Create RAG manager
        rag_manager = LocalRAGManager()
        await rag_manager.initialize()
        
        # Check documents loaded
        logger.info(f"Documents in cache: {len(rag_manager._knowledge_cache)}")
        for doc_id, doc in rag_manager._knowledge_cache.items():
            logger.info(f"  - {doc_id}: {doc.title} (embedding: {len(doc.embedding)} dims)")
        
        # Test query
        test_message = "Tell me about your family"
        logger.info(f"Testing query: '{test_message}'")
        
        # Generate embedding for query
        embedding_result = await rag_manager.embeddings_service.get_embedding(test_message)
        if not embedding_result:
            logger.error("Failed to generate embedding for query")
            return False
        
        query_embedding = embedding_result.embedding
        logger.info(f"Query embedding: {len(query_embedding)} dimensions")
        
        # Manually test similarity with each document
        logger.info("\nManual similarity calculations:")
        for doc_id, doc in rag_manager._knowledge_cache.items():
            similarity = rag_manager._cosine_similarity(query_embedding, doc.embedding)
            logger.info(f"  {doc.title}: similarity = {similarity:.4f}")
            
            # Check if this would pass the threshold
            threshold = rag_manager.config["min_similarity_threshold"]
            if similarity >= threshold:
                logger.info(f"    ✅ Above threshold ({threshold})")
            else:
                logger.info(f"    ❌ Below threshold ({threshold})")
        
        # Test the find_similar_documents method
        logger.info("\nTesting find_similar_documents method:")
        similar_docs = await rag_manager._find_similar_documents(query_embedding)
        logger.info(f"Found {len(similar_docs)} similar documents:")
        for doc, similarity in similar_docs:
            logger.info(f"  - {doc.title}: {similarity:.4f}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Debug failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(debug_rag_similarity())
    sys.exit(0 if success else 1)