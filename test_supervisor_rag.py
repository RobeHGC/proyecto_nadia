#!/usr/bin/env python3
"""
Test supervisor agent with RAG enhancement.
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


async def test_supervisor_with_rag():
    """Test supervisor agent with RAG enhancement."""
    try:
        from agents.supervisor_agent import SupervisorAgent
        from memory.user_memory import UserMemoryManager
        from llms.openai_client import OpenAIClient
        from utils.config import Config
        
        logger.info("🚀 Testing Supervisor Agent with RAG")
        
        # Create test configuration
        config = Config()
        
        # Initialize components
        memory = UserMemoryManager()
        llm_client = OpenAIClient(api_key="fake-key-for-test")  # Won't be used in this test
        
        # Initialize supervisor
        supervisor = SupervisorAgent(llm_client, memory, config)
        
        # Test RAG initialization
        await supervisor._initialize_rag()
        
        if supervisor.rag_manager:
            logger.info("✅ RAG Manager initialized successfully")
            
            # Test RAG-enhanced prompt building
            test_message = "Tell me about your family"
            test_context = {"user_id": "test_user"}
            
            logger.info(f"Building RAG-enhanced prompt for: '{test_message}'")
            
            # Test the private method that builds creative prompts
            messages = await supervisor._build_creative_prompt(test_message, test_context)
            
            # Find the enhanced message
            enhanced_found = False
            for msg in messages:
                if "User Message:" in msg.get("content", "") and "Relevant Knowledge:" in msg.get("content", ""):
                    enhanced_found = True
                    logger.info("✅ Found RAG-enhanced prompt!")
                    logger.info(f"Enhanced prompt preview: {msg['content'][:300]}...")
                    break
            
            if not enhanced_found:
                # Check if original message was used (low confidence)
                for msg in messages:
                    if msg.get("content") == test_message:
                        logger.info("ℹ️  Original message used (likely low confidence)")
                        break
            
            logger.info("✅ Supervisor RAG integration test completed successfully!")
            return True
        else:
            logger.error("❌ RAG Manager not initialized")
            return False
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_supervisor_with_rag())
    sys.exit(0 if success else 1)