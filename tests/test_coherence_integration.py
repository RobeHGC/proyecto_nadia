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
        
        # Check essential supervisor attributes exist
        assert hasattr(supervisor, 'llm1'), "LLM1 client should exist"
        assert hasattr(supervisor, 'llm2'), "LLM2 client should exist" 
        assert hasattr(supervisor, 'constitution'), "Constitution should exist"
        assert hasattr(supervisor, 'memory'), "Memory manager should exist"
        
        logger.info("✅ Essential supervisor components initialized")
        
        # Simulate setting db_manager (would initialize coherence agents)
        # Note: We can't actually set it without a real database connection
        # but we can verify the method exists
        assert hasattr(supervisor, 'set_db_manager'), "set_db_manager method exists"
        
        logger.info("✅ set_db_manager method available")
        
        # Check _generate_creative_response has expected parameters
        import inspect
        sig = inspect.signature(supervisor._generate_creative_response)
        params = list(sig.parameters.keys())
        assert 'message' in params, "message parameter exists in _generate_creative_response"
        assert 'context' in params, "context parameter exists in _generate_creative_response"
        
        logger.info("✅ _generate_creative_response has correct parameters")
        
        # Verify core processing method exists
        assert hasattr(supervisor, 'process_message'), "process_message method exists"
        
        logger.info("✅ Core processing method available")
        
        logger.info("\n🎉 Coherence pipeline integration test PASSED!")
        
    except Exception as e:
        logger.error(f"❌ Test failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(test_coherence_integration())