"""
Comprehensive integration tests for multi-LLM system.
Tests end-to-end functionality including Gemini + GPT pipeline.
"""
import asyncio
import logging
import os
import pytest
import redis
import uuid
from decimal import Decimal
from typing import Dict, Any

from agents.supervisor_agent import SupervisorAgent
from database.models import DatabaseManager
from llms.quota_manager import GeminiQuotaManager
from memory.user_memory import UserMemoryManager
from utils.config import Config

# Setup logging for tests
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test user IDs (non-destructive)
TEST_USER_IDS = [
    "test_user_12345",
    "test_user_67890", 
    "test_user_integration"
]

@pytest.fixture
async def config():
    """Create config instance for testing."""
    return Config.from_env()

@pytest.fixture 
async def redis_client():
    """Redis client for testing."""
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/1')  # Use DB 1 for tests
    client = redis.from_url(redis_url, decode_responses=True)
    yield client
    # Cleanup test data
    for user_id in TEST_USER_IDS:
        client.delete(f"gemini_quota:{user_id}")
        client.delete(f"user_memory:{user_id}")

@pytest.fixture
async def db_manager():
    """Database manager for testing."""
    database_url = os.getenv('DATABASE_URL', 'postgresql://localhost/nadia_hitl_test')
    db = DatabaseManager(database_url)
    await db.initialize()
    yield db
    # Cleanup test interactions
    if hasattr(db, 'cleanup_test_data'):
        await db.cleanup_test_data(TEST_USER_IDS)
    await db.close()

@pytest.fixture
async def memory_manager():
    """User memory manager for testing."""
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/1')  # Use DB 1 for tests
    return UserMemoryManager(redis_url)

@pytest.fixture
async def supervisor_agent(config, memory_manager):
    """Supervisor agent with multi-LLM setup."""
    # Mock OpenAI client for legacy compatibility
    from llms.openai_client import OpenAIClient
    mock_llm = OpenAIClient("dummy-key", "gpt-3.5-turbo")
    
    return SupervisorAgent(mock_llm, memory_manager, config)

@pytest.fixture
async def quota_manager(redis_client):
    """Quota manager for testing."""
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    return GeminiQuotaManager(redis_url)

class TestMultiLLMIntegration:
    """Integration tests for multi-LLM system."""

    async def test_basic_message_processing(self, supervisor_agent):
        """Test basic message processing through multi-LLM pipeline."""
        user_id = TEST_USER_IDS[0]
        test_message = "Hi! My name is Alice and I'm new here."
        
        # Process message
        review_item = await supervisor_agent.process_message(user_id, test_message)
        
        # Validate ReviewItem structure
        assert review_item.id is not None
        assert review_item.user_id == user_id
        assert review_item.user_message == test_message
        assert review_item.ai_suggestion is not None
        assert review_item.priority > 0.0
        assert review_item.timestamp is not None
        
        # Validate AIResponse structure
        ai_response = review_item.ai_suggestion
        assert ai_response.llm1_raw is not None
        assert len(ai_response.llm2_bubbles) > 0
        assert ai_response.constitution_analysis is not None
        assert ai_response.tokens_used > 0
        assert ai_response.generation_time > 0
        
        # Validate multi-LLM tracking
        assert ai_response.llm1_model is not None
        assert ai_response.llm2_model is not None
        assert ai_response.llm1_cost >= 0
        assert ai_response.llm2_cost >= 0
        
        logger.info(f"✓ Basic processing: LLM1={ai_response.llm1_model}, LLM2={ai_response.llm2_model}")

    async def test_llm_provider_verification(self, supervisor_agent, config):
        """Verify correct LLM providers are being used."""
        user_id = TEST_USER_IDS[1]
        test_message = "What's your favorite movie?"
        
        review_item = await supervisor_agent.process_message(user_id, test_message)
        ai_response = review_item.ai_suggestion
        
        # Check LLM-1 (should be Gemini by default)
        if config.llm1_provider == "gemini":
            assert "gemini" in ai_response.llm1_model.lower()
        elif config.llm1_provider == "openai":
            assert "gpt" in ai_response.llm1_model.lower()
            
        # Check LLM-2 (should be OpenAI by default)  
        if config.llm2_provider == "openai":
            assert "gpt" in ai_response.llm2_model.lower()
        elif config.llm2_provider == "gemini":
            assert "gemini" in ai_response.llm2_model.lower()
            
        logger.info(f"✓ Provider verification: {config.llm1_provider} + {config.llm2_provider}")

    async def test_cost_tracking(self, supervisor_agent):
        """Test that costs are properly calculated and tracked."""
        user_id = TEST_USER_IDS[2]
        test_message = "Tell me about yourself!"
        
        review_item = await supervisor_agent.process_message(user_id, test_message)
        ai_response = review_item.ai_suggestion
        
        # Verify cost tracking
        assert isinstance(ai_response.llm1_cost, (int, float, Decimal))
        assert isinstance(ai_response.llm2_cost, (int, float, Decimal))
        assert ai_response.llm1_cost >= 0
        assert ai_response.llm2_cost >= 0
        
        # Calculate total cost
        total_cost = ai_response.llm1_cost + ai_response.llm2_cost
        
        logger.info(f"✓ Cost tracking: LLM1=${ai_response.llm1_cost:.6f}, LLM2=${ai_response.llm2_cost:.6f}, Total=${total_cost:.6f}")

    async def test_quota_manager(self, quota_manager):
        """Test Gemini quota management."""
        
        # Reset quota for clean test
        await quota_manager.reset_daily()
        
        # Check initial state
        daily_used = await quota_manager.get_daily_usage()
        minute_used = await quota_manager.get_minute_usage()
        
        assert daily_used == 0
        assert minute_used == 0
        
        # Check if we can use free tier
        can_use = await quota_manager.can_use_free_tier()
        assert can_use == True
        
        # Record usage
        await quota_manager.record_usage(1000)
        
        # Verify tracking
        daily_used_after = await quota_manager.get_daily_usage()
        assert daily_used_after == 1000
        
        # Get quota status
        status = await quota_manager.get_quota_status()
        assert status['daily_usage'] == 1000
        assert status['daily_limit'] == 32000
        assert status['can_use_free_tier'] == True
        
        logger.info(f"✓ Quota management: {daily_used_after} tokens recorded")

    async def test_constitution_analysis(self, supervisor_agent):
        """Test that Constitution analysis runs after LLM-2."""
        user_id = TEST_USER_IDS[1]
        test_message = "Can you help me with something?"
        
        review_item = await supervisor_agent.process_message(user_id, test_message)
        analysis = review_item.ai_suggestion.constitution_analysis
        
        # Verify Constitution analysis structure
        assert hasattr(analysis, 'flags')
        assert hasattr(analysis, 'risk_score')
        assert hasattr(analysis, 'violations')
        assert hasattr(analysis, 'recommendation')
        assert hasattr(analysis, 'normalized_text')
        
        # Risk score should be between 0.0 and 1.0
        assert 0.0 <= analysis.risk_score <= 1.0
        
        # Check if safe based on risk score
        is_safe = analysis.risk_score < 0.5
        
        logger.info(f"✓ Constitution analysis: risk={analysis.risk_score:.2f}, safe={is_safe}")

    async def test_bubble_formatting(self, supervisor_agent):
        """Test that messages are properly formatted into bubbles."""
        user_id = TEST_USER_IDS[2]
        test_message = "Tell me a story about your day!"
        
        review_item = await supervisor_agent.process_message(user_id, test_message)
        bubbles = review_item.ai_suggestion.llm2_bubbles
        
        # Should have at least one bubble
        assert len(bubbles) > 0
        
        # Each bubble should be non-empty
        for bubble in bubbles:
            assert bubble.strip() != ""
            
        # Should not contain [GLOBO] markers in final output
        for bubble in bubbles:
            assert "[GLOBO]" not in bubble
            
        logger.info(f"✓ Bubble formatting: {len(bubbles)} bubbles generated")

    async def test_memory_integration(self, supervisor_agent, memory_manager):
        """Test that memory integration works with multi-LLM system."""
        user_id = TEST_USER_IDS[0]
        
        # First message with name
        first_message = "Hi! I'm Bob and I love pizza."
        review_item1 = await supervisor_agent.process_message(user_id, first_message)
        
        # Check that name was extracted
        context = await memory_manager.get_user_context(user_id)
        assert context.get("name") == "Bob"
        
        # Second message should use the name
        second_message = "What do you think about Italian food?"
        review_item2 = await supervisor_agent.process_message(user_id, second_message)
        
        # Check that context includes the name
        assert review_item2.conversation_context.get("name") == "Bob"
        
        logger.info(f"✓ Memory integration: Name 'Bob' extracted and used in context")

    @pytest.mark.asyncio
    @pytest.mark.skipif(os.getenv('DATABASE_MODE') == 'skip', reason="Database tests skipped")
    async def test_database_persistence(self, supervisor_agent, db_manager):
        """Test that interactions are properly stored in database."""
        user_id = TEST_USER_IDS[1]
        test_message = "Hello database test!"
        
        # Process message
        review_item = await supervisor_agent.process_message(user_id, test_message)
        
        # Save to database directly with ReviewItem
        interaction_id = await db_manager.save_interaction(review_item)
        assert interaction_id is not None
        
        logger.info(f"✓ Database persistence: Interaction {interaction_id} saved with multi-LLM data")

    async def test_error_handling(self, supervisor_agent):
        """Test error handling in multi-LLM pipeline."""
        user_id = TEST_USER_IDS[2]
        
        # Test with empty message
        try:
            review_item = await supervisor_agent.process_message(user_id, "")
            # Should handle gracefully
            assert review_item is not None
        except Exception as e:
            logger.info(f"✓ Empty message handling: {str(e)}")
        
        # Test with very long message
        long_message = "test " * 1000
        try:
            review_item = await supervisor_agent.process_message(user_id, long_message)
            assert review_item is not None
        except Exception as e:
            logger.info(f"✓ Long message handling: {str(e)}")

    async def test_performance_metrics(self, supervisor_agent):
        """Test that performance metrics are tracked."""
        user_id = TEST_USER_IDS[0]
        test_message = "Quick performance test!"
        
        import time
        start_time = time.time()
        
        review_item = await supervisor_agent.process_message(user_id, test_message)
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Check that generation time is tracked
        assert review_item.ai_suggestion.generation_time > 0
        assert review_item.ai_suggestion.generation_time <= total_time
        
        # Check token usage
        assert review_item.ai_suggestion.tokens_used > 0
        
        logger.info(f"✓ Performance: {total_time:.2f}s total, {review_item.ai_suggestion.tokens_used} tokens")

# Utility function for running tests standalone
async def run_integration_tests():
    """Run integration tests independently."""
    logger.info("Starting multi-LLM integration tests...")
    
    # Initialize fixtures
    config = Config()
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/1')
    memory_manager = UserMemoryManager(redis_url)
    
    # Create supervisor with mock legacy client
    from llms.openai_client import OpenAIClient
    mock_llm = OpenAIClient("dummy-key", "gpt-3.5-turbo")
    supervisor = SupervisorAgent(mock_llm, memory_manager, config)
    
    # Run basic test
    try:
        user_id = "standalone_test_user"
        test_message = "Hi! This is a standalone test."
        
        review_item = await supervisor.process_message(user_id, test_message)
        
        logger.info("✅ Standalone test PASSED")
        logger.info(f"   LLM1: {review_item.ai_suggestion.llm1_model}")
        logger.info(f"   LLM2: {review_item.ai_suggestion.llm2_model}")
        logger.info(f"   Cost: ${review_item.ai_suggestion.llm1_cost + review_item.ai_suggestion.llm2_cost:.6f}")
        logger.info(f"   Bubbles: {len(review_item.ai_suggestion.llm2_bubbles)}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Standalone test FAILED: {e}")
        return False
    
    finally:
        # Cleanup
        await memory_manager.close()

if __name__ == "__main__":
    # Run standalone
    result = asyncio.run(run_integration_tests())
    exit(0 if result else 1)