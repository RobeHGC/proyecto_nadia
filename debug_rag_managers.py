#!/usr/bin/env python3
"""
Debug the difference between RAG managers.
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


async def debug_rag_managers():
    """Debug both RAG manager implementations."""
    try:
        logger.info("🔍 Debugging RAG Managers...")
        
        # Test 1: Direct Local RAG Manager
        logger.info("\n=== Test 1: Direct Local RAG Manager ===")
        from knowledge.local_rag_manager import get_local_rag_manager as get_local_file_rag
        
        local_rag = await get_local_file_rag()
        logger.info(f"Local RAG Manager type: {type(local_rag)}")
        logger.info(f"Local RAG Manager stats: {local_rag.get_stats()}")
        
        # Test with a query
        test_message = "Tell me about your family"
        response1 = await local_rag.enhance_prompt_with_context(
            user_message=test_message,
            user_id="test_user",
            conversation_context={"user_id": "test_user"}
        )
        
        logger.info(f"Local RAG Response: success={response1.success}, confidence={response1.context_used.confidence_score:.2f}")
        
        # Test 2: Supervisor's RAG Manager 
        logger.info("\n=== Test 2: Supervisor's RAG Manager ===")
        from agents.supervisor_agent import SupervisorAgent
        from memory.user_memory import UserMemoryManager
        from llms.openai_client import OpenAIClient
        
        class TestConfig:
            def __init__(self):
                self.redis_url = "redis://localhost:6379"
                self.openai_api_key = "test-key"
                self.openai_model = "gpt-4o-mini"
                self.database_url = "test"
                self.llm1_provider = "gemini"
                self.llm1_model = "gemini-2.0-flash-exp"
                self.llm2_provider = "openai"
                self.llm2_model = "gpt-4o-mini"
                self.llm_profile = "cost_optimized"
                self.gemini_api_key = "test-key"
        
        config = TestConfig()
        memory = UserMemoryManager(config.redis_url)
        llm_client = OpenAIClient(config.openai_api_key, config.openai_model)
        supervisor = SupervisorAgent(llm_client, memory, config)
        
        # Initialize RAG
        await supervisor._initialize_rag()
        
        logger.info(f"Supervisor RAG Manager type: {type(supervisor.rag_manager)}")
        
        if hasattr(supervisor.rag_manager, 'get_stats'):
            logger.info(f"Supervisor RAG stats: {supervisor.rag_manager.get_stats()}")
        else:
            logger.info("Supervisor RAG manager has no get_stats method")
        
        # Test with same query
        response2 = await supervisor.rag_manager.enhance_prompt_with_context(
            user_message=test_message,
            user_id="test_user",
            conversation_context={"user_id": "test_user"}
        )
        
        logger.info(f"Supervisor RAG Response: success={response2.success}, confidence={response2.context_used.confidence_score:.2f}")
        
        # Compare results
        logger.info("\n=== Comparison ===")
        logger.info(f"Local RAG confidence: {response1.context_used.confidence_score:.2f}")
        logger.info(f"Supervisor RAG confidence: {response2.context_used.confidence_score:.2f}")
        logger.info(f"Local RAG docs: {len(response1.context_used.relevant_documents)}")
        logger.info(f"Supervisor RAG docs: {len(response2.context_used.relevant_documents)}")
        
        if response1.context_used.confidence_score != response2.context_used.confidence_score:
            logger.warning("⚠️  Different confidence scores! Different RAG managers being used.")
        else:
            logger.info("✅ Same confidence scores - RAG managers are equivalent")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Debug failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(debug_rag_managers())
    sys.exit(0 if success else 1)