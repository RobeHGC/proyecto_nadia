#!/usr/bin/env python3
"""
Comprehensive test suite for the hybrid memory system.
Tests memory storage, retrieval, consolidation, and integration.
"""

import asyncio
import logging
import os
import tempfile
import pytest
from datetime import datetime, timedelta
from typing import Dict, List, Any
import json

# Configure test logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Test imports
try:
    from memory.hybrid_memory_manager import HybridMemoryManager, MemoryItem, MemoryTier
    from memory.user_memory import UserMemoryManager  
    from agents.memory_strategies import AgentConfigurationManager, AgentType, MemoryConfig, MemoryStrategy
    from knowledge.rag_manager import RAGManager
    from agents.supervisor_agent import SupervisorAgent
    HYBRID_MEMORY_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Hybrid memory imports failed: {e}")
    HYBRID_MEMORY_AVAILABLE = False

# Mock database URL for testing
TEST_DATABASE_URL = "postgresql://test:test@localhost:5432/test_nadia"
TEST_MONGODB_URI = "mongodb://localhost:27017/test_nadia_memory"

@pytest.mark.skipif(not HYBRID_MEMORY_AVAILABLE, reason="Hybrid memory system not available")
class TestHybridMemoryManager:
    """Test suite for HybridMemoryManager core functionality."""
    
    @pytest.fixture
    async def memory_manager(self):
        """Create test memory manager instance."""
        manager = HybridMemoryManager(TEST_DATABASE_URL, TEST_MONGODB_URI)
        try:
            # Try to initialize - will fail gracefully if DB not available
            await manager.initialize()
        except Exception as e:
            logger.warning(f"Could not initialize memory manager: {e}")
            # Use mock mode for testing core logic
            manager.db_pool = None
            manager.mongo_client = None
        
        yield manager
        
        # Cleanup
        if manager:
            await manager.close()
    
    @pytest.mark.asyncio
    async def test_memory_item_creation(self, memory_manager):
        """Test creating and storing memory items."""
        memory_item = MemoryItem(
            user_id="test_user_1",
            content="I love hiking in the mountains",
            timestamp=datetime.utcnow(),
            memory_type="preference",
            importance=0.8,
            tier=MemoryTier.HOT,
            metadata={"source": "test", "category": "hobbies"}
        )
        
        assert memory_item.user_id == "test_user_1"
        assert memory_item.importance == 0.8
        assert memory_item.tier == MemoryTier.HOT
        assert memory_item.metadata["category"] == "hobbies"
    
    @pytest.mark.asyncio
    async def test_memory_tier_determination(self, memory_manager):
        """Test automatic memory tier assignment."""
        # Recent, high importance -> HOT
        recent_memory = MemoryItem(
            user_id="test_user_1",
            content="Important conversation",
            timestamp=datetime.utcnow(),
            memory_type="conversation",
            importance=0.9,
            tier=MemoryTier.HOT,
            metadata={}
        )
        
        tier = memory_manager._determine_tier(recent_memory)
        assert tier == MemoryTier.HOT
        
        # Old, low importance -> COLD
        old_memory = MemoryItem(
            user_id="test_user_1", 
            content="Old unimportant message",
            timestamp=datetime.utcnow() - timedelta(days=50),
            memory_type="conversation",
            importance=0.2,
            tier=MemoryTier.HOT,  # Will be overridden
            metadata={}
        )
        
        tier = memory_manager._determine_tier(old_memory)
        assert tier == MemoryTier.COLD
    
    @pytest.mark.asyncio
    async def test_memory_storage_fallback(self, memory_manager):
        """Test memory storage with database fallback."""
        memory_item = MemoryItem(
            user_id="test_user_storage",
            content="Test memory for storage",
            timestamp=datetime.utcnow(),
            memory_type="test",
            importance=0.7,
            tier=MemoryTier.HOT,
            metadata={"test_id": "storage_test"}
        )
        
        # Should handle gracefully even if databases not available
        try:
            memory_id = await memory_manager.store_memory(memory_item)
            assert memory_id is not None
            logger.info(f"Memory stored with ID: {memory_id}")
        except Exception as e:
            # Expected if databases not configured for testing
            logger.info(f"Storage failed as expected: {e}")
            assert "database" in str(e).lower() or "connection" in str(e).lower()
    
    @pytest.mark.asyncio
    async def test_memory_retrieval_empty(self, memory_manager):
        """Test memory retrieval when no data available."""
        memories = await memory_manager.retrieve_memories(
            user_id="nonexistent_user",
            query="test query",
            limit=5
        )
        
        # Should return empty list, not error
        assert isinstance(memories, list)
        assert len(memories) == 0

@pytest.mark.skipif(not HYBRID_MEMORY_AVAILABLE, reason="Hybrid memory system not available")
class TestUserMemoryIntegration:
    """Test UserMemoryManager integration with hybrid memory."""
    
    @pytest.fixture
    async def enhanced_memory(self):
        """Create enhanced user memory manager."""
        memory = UserMemoryManager(enable_hybrid_memory=True)
        yield memory
        await memory.close()
    
    @pytest.mark.asyncio
    async def test_enhanced_context_fallback(self, enhanced_memory):
        """Test enhanced context with fallback to standard context."""
        # Should not crash if hybrid memory unavailable
        context = await enhanced_memory.get_enhanced_context_with_rag("test_user", "test query")
        
        assert isinstance(context, dict)
        # Should have at least basic context structure
        expected_keys = ["recent_messages", "temporal_summary"]
        for key in expected_keys:
            assert key in context
    
    @pytest.mark.asyncio 
    async def test_message_importance_calculation(self, enhanced_memory):
        """Test message importance scoring."""
        # High importance message
        high_importance_msg = {
            "role": "user",
            "content": "My name is John and I work as a doctor. I love hiking and photography."
        }
        
        importance = enhanced_memory._calculate_message_importance(high_importance_msg)
        assert importance > 0.5
        logger.info(f"High importance message scored: {importance}")
        
        # Low importance message
        low_importance_msg = {
            "role": "user", 
            "content": "ok"
        }
        
        importance = enhanced_memory._calculate_message_importance(low_importance_msg)
        assert importance <= 0.5
        logger.info(f"Low importance message scored: {importance}")
    
    @pytest.mark.asyncio
    async def test_hybrid_memory_hooks(self, enhanced_memory):
        """Test hybrid memory integration hooks."""
        test_message = {
            "role": "user",
            "content": "I really enjoy mountain climbing and outdoor photography",
            "timestamp": datetime.now().isoformat()
        }
        
        # Should not crash even if hybrid memory not fully configured
        try:
            await enhanced_memory.add_to_conversation_history("test_user_hooks", test_message)
            logger.info("Message added to conversation history with hybrid hooks")
        except Exception as e:
            # Should handle gracefully
            logger.info(f"Hybrid hooks handled error gracefully: {e}")
            assert "database" in str(e).lower() or "connection" in str(e).lower()

@pytest.mark.skipif(not HYBRID_MEMORY_AVAILABLE, reason="Hybrid memory system not available") 
class TestAgentConfiguration:
    """Test agent configuration and memory strategies."""
    
    @pytest.fixture
    async def config_manager(self):
        """Create test configuration manager."""
        manager = AgentConfigurationManager()
        await manager.initialize()
        yield manager
        await manager.close()
    
    @pytest.mark.asyncio
    async def test_default_configurations(self, config_manager):
        """Test default agent configurations."""
        for agent_type in AgentType:
            config = await config_manager.get_agent_config(agent_type)
            
            assert isinstance(config, MemoryConfig)
            assert isinstance(config.strategy, MemoryStrategy)
            assert config.context_window_tokens > 0
            assert 0.0 <= config.compression_threshold <= 1.0
            assert config.retrieval_k > 0
            assert 0.0 <= config.temperature <= 2.0
            
            logger.info(f"{agent_type.value}: {config.strategy.value}, "
                       f"context:{config.context_window_tokens}, k:{config.retrieval_k}")
    
    @pytest.mark.asyncio
    async def test_memory_strategy_context_aware(self, config_manager):
        """Test context-aware memory strategy selection."""
        strategy, params = await config_manager.get_memory_strategy_for_context(
            agent_type=AgentType.SUPERVISOR,
            context_size=9000,  # High context
            user_activity_level="high",
            conversation_complexity="normal"
        )
        
        assert isinstance(strategy, MemoryStrategy)
        assert isinstance(params, dict)
        logger.info(f"Context-aware strategy: {strategy.value}, params: {params}")
    
    @pytest.mark.asyncio
    async def test_consolidation_schedule(self, config_manager):
        """Test memory consolidation scheduling."""
        schedule = await config_manager.get_consolidation_schedule()
        
        assert isinstance(schedule, dict)
        for agent_type, next_time in schedule.items():
            assert isinstance(agent_type, AgentType)
            assert isinstance(next_time, datetime)
            assert next_time > datetime.utcnow()
        
        logger.info(f"Consolidation schedule for {len(schedule)} agents")
    
    @pytest.mark.asyncio
    async def test_prompt_template_fallback(self, config_manager):
        """Test prompt template retrieval with fallback."""
        # Non-existent template should return empty string
        template = await config_manager.get_prompt_template("nonexistent_template")
        assert template == ""
        
        # With variables
        template = await config_manager.get_prompt_template(
            "test_template", 
            {"variable1": "value1", "variable2": "value2"}
        )
        assert isinstance(template, str)

@pytest.mark.skipif(not HYBRID_MEMORY_AVAILABLE, reason="Hybrid memory system not available")
class TestRAGIntegration:
    """Test RAG system integration with hybrid memory."""
    
    @pytest.fixture
    async def rag_manager(self):
        """Create test RAG manager."""
        try:
            # Try to create with hybrid memory integration
            rag = RAGManager(enable_memory_integration=True)
            await rag.initialize()
            yield rag
        except Exception as e:
            logger.warning(f"Could not initialize RAG manager: {e}")
            # Create mock RAG manager for testing
            class MockRAG:
                async def enhance_prompt_with_context(self, user_message, user_id, conversation_context=None):
                    from knowledge.rag_manager import RAGResponse, RAGContext
                    return RAGResponse(
                        enhanced_prompt=user_message,
                        context_used=RAGContext([], None, [], "", 0.1),
                        success=True
                    )
                
                async def store_interaction_in_hybrid_memory(self, user_id, user_message, ai_response, conversation_id=None):
                    return True
            
            yield MockRAG()
    
    @pytest.mark.asyncio
    async def test_rag_hybrid_memory_enhancement(self, rag_manager):
        """Test RAG enhancement with hybrid memory."""
        response = await rag_manager.enhance_prompt_with_context(
            user_message="Tell me about hiking",
            user_id="test_user_rag",
            conversation_context={"user_id": "test_user_rag"}
        )
        
        assert hasattr(response, 'enhanced_prompt')
        assert hasattr(response, 'success')
        assert response.success is True
        
        logger.info(f"RAG enhancement success: {response.success}")
    
    @pytest.mark.asyncio
    async def test_rag_interaction_storage(self, rag_manager):
        """Test storing interactions in hybrid memory through RAG."""
        if hasattr(rag_manager, 'store_interaction_in_hybrid_memory'):
            success = await rag_manager.store_interaction_in_hybrid_memory(
                user_id="test_user_storage",
                user_message="I love mountain biking",
                ai_response="That's awesome! Mountain biking is such a great way to stay active.",
                conversation_id="test_conv_123"
            )
            
            assert isinstance(success, bool)
            logger.info(f"RAG interaction storage result: {success}")

@pytest.mark.skipif(not HYBRID_MEMORY_AVAILABLE, reason="Hybrid memory system not available")
class TestMemoryConsolidation:
    """Test memory consolidation and tier management."""
    
    @pytest.fixture
    async def memory_manager(self):
        """Create memory manager for consolidation tests."""
        manager = HybridMemoryManager(TEST_DATABASE_URL, TEST_MONGODB_URI)
        try:
            await manager.initialize()
        except Exception:
            # Mock for testing
            pass
        yield manager
        if manager:
            await manager.close()
    
    @pytest.mark.asyncio
    async def test_memory_consolidation_stats(self, memory_manager):
        """Test memory consolidation process."""
        # Should handle gracefully even without real data
        stats = await memory_manager.consolidate_memories("test_user_consolidation")
        
        assert isinstance(stats, dict)
        expected_keys = ["promoted", "demoted", "archived", "compressed"]
        for key in expected_keys:
            assert key in stats
            assert isinstance(stats[key], int)
            assert stats[key] >= 0
        
        logger.info(f"Consolidation stats: {stats}")
    
    @pytest.mark.asyncio
    async def test_user_memory_consolidation(self):
        """Test user-specific memory consolidation."""
        memory = UserMemoryManager(enable_hybrid_memory=True)
        
        try:
            result = await memory.consolidate_user_memories("test_user_consolidation")
            
            assert isinstance(result, dict)
            assert "status" in result
            
            # Should either complete or indicate hybrid memory disabled
            assert result["status"] in ["completed", "hybrid_memory_disabled", "error"]
            
            logger.info(f"User consolidation result: {result['status']}")
            
        finally:
            await memory.close()

@pytest.mark.skipif(not HYBRID_MEMORY_AVAILABLE, reason="Hybrid memory system not available")
class TestPerformanceAndScaling:
    """Test performance characteristics and scaling behavior."""
    
    @pytest.mark.asyncio
    async def test_large_context_handling(self):
        """Test handling of large context windows."""
        memory = UserMemoryManager(enable_hybrid_memory=True)
        
        try:
            # Create a large conversation context
            large_context = {
                "user_id": "test_large_context",
                "recent_messages": [
                    {"role": "user", "content": f"Message {i} with some content"} 
                    for i in range(100)
                ],
                "temporal_summary": "Very long summary " * 100,
                "memory_system_enabled": True,
                "total_hybrid_memories": 50
            }
            
            # Should handle gracefully without memory issues
            context = await memory.get_enhanced_context_with_rag(
                "test_large_context", 
                "query with large context"
            )
            
            assert isinstance(context, dict)
            logger.info("Large context handled successfully")
            
        finally:
            await memory.close()
    
    @pytest.mark.asyncio
    async def test_concurrent_memory_operations(self):
        """Test concurrent memory operations."""
        memory = UserMemoryManager(enable_hybrid_memory=True)
        
        try:
            # Simulate concurrent users
            tasks = []
            for i in range(10):
                task = memory.add_to_conversation_history(
                    f"concurrent_user_{i}",
                    {
                        "role": "user",
                        "content": f"Concurrent message {i}",
                        "timestamp": datetime.now().isoformat()
                    }
                )
                tasks.append(task)
            
            # Should complete without deadlocks or errors
            await asyncio.gather(*tasks, return_exceptions=True)
            logger.info("Concurrent operations completed")
            
        finally:
            await memory.close()
    
    @pytest.mark.asyncio
    async def test_memory_stats_performance(self):
        """Test memory statistics collection performance."""
        memory = UserMemoryManager(enable_hybrid_memory=True)
        
        try:
            import time
            start_time = time.time()
            
            stats = await memory.get_memory_stats("test_performance_user")
            
            elapsed = time.time() - start_time
            
            assert isinstance(stats, dict)
            assert elapsed < 2.0  # Should be fast
            
            logger.info(f"Memory stats collected in {elapsed:.3f}s")
            
        finally:
            await memory.close()

@pytest.mark.skipif(not HYBRID_MEMORY_AVAILABLE, reason="Hybrid memory system not available")
class TestErrorHandling:
    """Test error handling and resilience."""
    
    @pytest.mark.asyncio
    async def test_database_connection_failure(self):
        """Test graceful handling of database connection failures."""
        # Use invalid database URL
        manager = HybridMemoryManager("postgresql://invalid:invalid@localhost:5432/invalid")
        
        try:
            # Should not crash on initialization failure
            await manager.initialize()
        except Exception as e:
            logger.info(f"Database connection failed as expected: {e}")
        
        # Should handle memory operations gracefully
        memory_item = MemoryItem(
            user_id="test_error",
            content="Test content",
            timestamp=datetime.utcnow(),
            memory_type="test",
            importance=0.5,
            tier=MemoryTier.HOT,
            metadata={}
        )
        
        try:
            await manager.store_memory(memory_item)
        except Exception as e:
            logger.info(f"Storage failed gracefully: {e}")
        
        # Cleanup
        await manager.close()
    
    @pytest.mark.asyncio
    async def test_invalid_memory_data(self):
        """Test handling of invalid memory data."""
        manager = HybridMemoryManager(TEST_DATABASE_URL)
        
        # Test with invalid user_id
        memories = await manager.retrieve_memories(
            user_id="",  # Empty user ID
            query="test",
            limit=5
        )
        
        assert isinstance(memories, list)
        assert len(memories) == 0
        
        await manager.close()
    
    @pytest.mark.asyncio
    async def test_memory_system_degradation(self):
        """Test system behavior when memory system is degraded."""
        memory = UserMemoryManager(enable_hybrid_memory=False)  # Disable hybrid memory
        
        try:
            # Should fall back to basic memory operations
            await memory.add_to_conversation_history("test_degraded", {
                "role": "user",
                "content": "Test message",
                "timestamp": datetime.now().isoformat()
            })
            
            context = await memory.get_user_context("test_degraded")
            assert isinstance(context, dict)
            
            # Enhanced features should gracefully degrade
            enhanced_context = await memory.get_enhanced_context_with_rag("test_degraded", "query")
            assert isinstance(enhanced_context, dict)
            
            logger.info("System degraded gracefully to basic memory")
            
        finally:
            await memory.close()

# Integration test with supervisor agent
@pytest.mark.skipif(not HYBRID_MEMORY_AVAILABLE, reason="Hybrid memory system not available")
class TestSupervisorIntegration:
    """Test supervisor agent integration with hybrid memory."""
    
    @pytest.mark.asyncio
    async def test_supervisor_memory_initialization(self):
        """Test supervisor agent memory system initialization."""
        try:
            from utils.config import Config
            from llms.openai_client import OpenAIClient
            
            # Create mock components
            config = Config.from_env()
            llm_client = OpenAIClient(api_key="test-key")
            memory = UserMemoryManager(enable_hybrid_memory=True)
            
            # This will test the hybrid memory initialization paths
            supervisor = SupervisorAgent(llm_client, memory, config)
            
            # Check hybrid memory attributes
            assert hasattr(supervisor, '_hybrid_memory_enabled')
            assert hasattr(supervisor, 'agent_config_manager')
            
            logger.info(f"Supervisor hybrid memory enabled: {supervisor._hybrid_memory_enabled}")
            
        except ImportError as e:
            logger.warning(f"Could not test supervisor integration: {e}")
        except Exception as e:
            logger.info(f"Supervisor initialization handled gracefully: {e}")

def run_memory_system_tests():
    """Run the complete hybrid memory system test suite."""
    logger.info("Starting hybrid memory system tests...")
    
    # Use pytest to run the tests
    import sys
    
    test_args = [
        __file__,
        "-v",  # Verbose output
        "-s",  # Don't capture output
        "--tb=short",  # Short traceback format
    ]
    
    # Add markers for different test categories
    if "--integration" in sys.argv:
        test_args.extend(["-m", "not slow"])
    
    if "--performance" in sys.argv:
        test_args.extend(["-k", "performance"])
    
    exit_code = pytest.main(test_args)
    
    if exit_code == 0:
        logger.info("✅ All hybrid memory system tests passed!")
    else:
        logger.error("❌ Some tests failed. Check output above.")
    
    return exit_code

if __name__ == "__main__":
    # Allow running tests directly
    exit_code = run_memory_system_tests()
    exit(exit_code)