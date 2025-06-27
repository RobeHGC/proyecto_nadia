#!/usr/bin/env python3
"""Test script to verify coherence pipeline integration."""
import asyncio
import logging
import pytest
from datetime import datetime

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_coherence_integration():
    """Test the coherence pipeline is properly integrated."""
    try:
        # Import required modules
        from agents.supervisor_agent import SupervisorAgent
        from memory.user_memory import UserMemoryManager
        from utils.config import Config
        from database.models import DatabaseManager
        
        logger.info("✅ All imports successful")
        
        # Create test config
        config = Config(
            api_id=12345678,
            api_hash="test-hash",
            phone_number="+1234567890",
            redis_url="redis://localhost:6379",
            openai_api_key="test-key",
            gemini_api_key="test-key",
            llm1_provider="gemini",
            llm1_model="gemini-2.0-flash-exp",
            llm2_provider="openai",
            llm2_model="gpt-4o-mini",
            database_url="postgresql://localhost/nadia_hitl"
        )
        
        # Initialize components
        memory = UserMemoryManager(config.redis_url)
        supervisor = SupervisorAgent(None, memory, config)
        
        logger.info("✅ Supervisor initialized")
        
        # Check coherence agents are None before db_manager
        assert supervisor.intermediary_agent is None, "Intermediary agent should be None initially"
        assert supervisor.post_llm2_agent is None, "Post-LLM2 agent should be None initially"
        
        logger.info("✅ Coherence agents correctly uninitialized")
        
        # Simulate setting db_manager (would initialize coherence agents)
        # Note: We can't actually set it without a real database connection
        # but we can verify the method exists
        assert hasattr(supervisor, 'set_db_manager'), "set_db_manager method exists"
        
        logger.info("✅ set_db_manager method available")
        
        # Check _generate_creative_response accepts interaction_id
        import inspect
        sig = inspect.signature(supervisor._generate_creative_response)
        params = list(sig.parameters.keys())
        assert 'interaction_id' in params, "interaction_id parameter added to _generate_creative_response"
        
        logger.info("✅ _generate_creative_response accepts interaction_id parameter")
        
        # Verify time context method exists
        time_context = supervisor._get_monterrey_time_context()
        assert 'current_time' in time_context
        assert 'current_date' in time_context
        assert 'period' in time_context
        
        logger.info(f"✅ Time context working: {time_context['current_time']} ({time_context['period']})")
        
        logger.info("\n🎉 Coherence pipeline integration test PASSED!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(test_coherence_integration())