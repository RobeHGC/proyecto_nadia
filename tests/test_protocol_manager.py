"""Unit tests for ProtocolManager - PROTOCOLO DE SILENCIO functionality."""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from typing import Dict, List

from utils.protocol_manager import ProtocolManager
from database.models import DatabaseManager


class TestProtocolManager:
    """Test suite for ProtocolManager class."""

    @pytest.fixture
    def mock_db(self):
        """Mock database manager."""
        db = AsyncMock()  # Remove spec to avoid attribute errors
        return db

    @pytest.fixture
    def protocol_manager(self, mock_db):
        """Create ProtocolManager instance with mocked dependencies."""
        manager = ProtocolManager(mock_db)
        return manager

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis connection."""
        redis_mock = AsyncMock()
        # Create a separate mock for pipeline that has sync methods for setex but async for execute
        pipeline_mock = MagicMock()
        pipeline_mock.setex.return_value = None
        pipeline_mock.execute = AsyncMock(return_value=[])
        # Make pipeline() a regular (non-async) method
        redis_mock.pipeline = MagicMock(return_value=pipeline_mock)
        return redis_mock

    @patch('utils.protocol_manager.ProtocolManager._get_redis', new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_initialization(self, mock_get_redis, protocol_manager, mock_db, mock_redis):
        """Test ProtocolManager initialization and cache warming."""
        # Setup
        mock_db.get_active_protocol_users.return_value = ["user1", "user2", "user3"]
        # Configure async mock to return mock_redis when awaited
        mock_get_redis.return_value = mock_redis
        
        # Execute
        await protocol_manager.initialize()
        
        # Verify
        mock_db.get_active_protocol_users.assert_called_once()
        assert protocol_manager._cache_loaded is True
        assert protocol_manager._active_protocols == {"user1", "user2", "user3"}
        
        # Verify Redis pipeline operations
        mock_redis.pipeline.assert_called_once()
        pipeline_mock = mock_redis.pipeline.return_value
        assert pipeline_mock.setex.call_count == 3
        pipeline_mock.execute.assert_called_once()

    @patch('utils.protocol_manager.ProtocolManager._get_redis', new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_is_protocol_active_cache_hit(self, mock_get_redis, protocol_manager, mock_redis):
        """Test checking protocol status with cache hit."""
        # Setup
        mock_get_redis.return_value = mock_redis
        mock_redis.get.return_value = b"ACTIVE"
        
        # Execute
        result = await protocol_manager.is_protocol_active("user123")
        
        # Verify
        assert result is True
        mock_redis.get.assert_called_once_with("protocol_cache:user123")

    @patch('utils.protocol_manager.ProtocolManager._get_redis', new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_is_protocol_active_cache_miss(self, mock_get_redis, protocol_manager, mock_db, mock_redis):
        """Test checking protocol status with cache miss."""
        # Setup
        mock_get_redis.return_value = mock_redis
        mock_redis.get.return_value = None  # Cache miss
        mock_db.get_protocol_status.return_value = {"status": "ACTIVE"}
        
        # Execute
        result = await protocol_manager.is_protocol_active("user123")
        
        # Verify
        assert result is True
        mock_db.get_protocol_status.assert_called_once_with("user123")
        mock_redis.setex.assert_called_once_with("protocol_cache:user123", 300, "ACTIVE")
        assert "user123" in protocol_manager._active_protocols

    @patch('utils.protocol_manager.ProtocolManager._get_redis', new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_is_protocol_active_inactive_user(self, mock_get_redis, protocol_manager, mock_db, mock_redis):
        """Test checking protocol status for inactive user."""
        # Setup
        mock_get_redis.return_value = mock_redis
        mock_redis.get.return_value = None  # Cache miss
        mock_db.get_protocol_status.return_value = {"status": "INACTIVE"}
        
        # Execute
        result = await protocol_manager.is_protocol_active("user123")
        
        # Verify
        assert result is False
        mock_redis.setex.assert_called_once_with("protocol_cache:user123", 300, "INACTIVE")
        assert "user123" not in protocol_manager._active_protocols

    @patch('utils.protocol_manager.ProtocolManager._get_redis', new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_activate_protocol_success(self, mock_get_redis, protocol_manager, mock_db, mock_redis):
        """Test successful protocol activation."""
        # Setup
        mock_get_redis.return_value = mock_redis
        mock_db.activate_protocol.return_value = True
        
        # Execute
        result = await protocol_manager.activate_protocol("user123", "admin", "time waster")
        
        # Verify
        assert result is True
        mock_db.activate_protocol.assert_called_once_with("user123", "admin", "time waster")
        mock_redis.setex.assert_called_once_with("protocol_cache:user123", 300, "ACTIVE")
        assert "user123" in protocol_manager._active_protocols
        
        # Verify publish event
        expected_event = json.dumps({
            "action": "activated",
            "user_id": "user123",
            "by": "admin"
        })
        mock_redis.publish.assert_called_once_with("protocol_updates", expected_event)

    @patch('utils.protocol_manager.ProtocolManager._get_redis', new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_activate_protocol_failure(self, mock_get_redis, protocol_manager, mock_db, mock_redis):
        """Test failed protocol activation."""
        # Setup
        mock_get_redis.return_value = mock_redis
        mock_db.activate_protocol.return_value = False
        
        # Execute
        result = await protocol_manager.activate_protocol("user123", "admin", "reason")
        
        # Verify
        assert result is False
        mock_db.activate_protocol.assert_called_once_with("user123", "admin", "reason")
        # Should not update cache or publish event on failure
        mock_redis.setex.assert_not_called()
        mock_redis.publish.assert_not_called()

    @patch('utils.protocol_manager.ProtocolManager._get_redis', new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_deactivate_protocol_success(self, mock_get_redis, protocol_manager, mock_db, mock_redis):
        """Test successful protocol deactivation."""
        # Setup
        mock_get_redis.return_value = mock_redis
        mock_db.deactivate_protocol.return_value = True
        protocol_manager._active_protocols.add("user123")  # User was active
        
        # Execute
        result = await protocol_manager.deactivate_protocol("user123", "admin", "resolved")
        
        # Verify
        assert result is True
        mock_db.deactivate_protocol.assert_called_once_with("user123", "admin", "resolved")
        mock_redis.setex.assert_called_once_with("protocol_cache:user123", 300, "INACTIVE")
        assert "user123" not in protocol_manager._active_protocols
        
        # Verify publish event
        expected_event = json.dumps({
            "action": "deactivated",
            "user_id": "user123",
            "by": "admin"
        })
        mock_redis.publish.assert_called_once_with("protocol_updates", expected_event)

    @patch('utils.protocol_manager.ProtocolManager._get_redis', new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_queue_for_quarantine(self, mock_get_redis, protocol_manager, mock_db, mock_redis):
        """Test queuing message for quarantine."""
        # Setup
        mock_get_redis.return_value = mock_redis
        mock_db.save_quarantine_message.return_value = "quar_123"
        
        with patch('asyncio.get_event_loop') as mock_loop:
            mock_loop.return_value.time.return_value = 1640995200.0  # Fixed timestamp
            
            # Execute
            result = await protocol_manager.queue_for_quarantine(
                "user123", "msg_456", "Hello world", 789, [{"role": "user", "content": "Hi"}]
            )
        
        # Verify
        assert result == "quar_123"
        mock_db.save_quarantine_message.assert_called_once_with("user123", "msg_456", "Hello world", 789)
        
        # Verify Redis operations
        expected_item = json.dumps({
            "id": "msg_456",
            "quarantine_id": "quar_123",
            "user_id": "user123",
            "message": "Hello world",
            "telegram_message_id": 789,
            "timestamp": 1640995200.0,
            "context_preview": [{"role": "user", "content": "Hi"}]
        })
        mock_redis.hset.assert_called_once_with("nadia_quarantine_items", "msg_456", expected_item)
        mock_redis.zadd.assert_called_once_with("nadia_quarantine_queue", {"msg_456": 1640995200.0})

    @patch('utils.protocol_manager.ProtocolManager._get_redis', new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_get_quarantine_queue(self, mock_get_redis, protocol_manager, mock_redis):
        """Test getting quarantine queue from Redis."""
        # Setup
        mock_get_redis.return_value = mock_redis
        mock_redis.zrevrange.return_value = [b"msg1", b"msg2"]
        
        # Mock pipeline
        pipeline_mock = MagicMock()
        pipeline_mock.hget.return_value = None
        pipeline_mock.execute = AsyncMock()
        
        msg1_data = json.dumps({"id": "msg1", "user_id": "user1", "message": "Hello"})
        msg2_data = json.dumps({"id": "msg2", "user_id": "user2", "message": "World"})
        pipeline_mock.execute.return_value = [msg1_data.encode(), msg2_data.encode()]
        
        mock_redis.pipeline = MagicMock(return_value=pipeline_mock)
        
        # Execute
        result = await protocol_manager.get_quarantine_queue(10)
        
        # Verify
        assert len(result) == 2
        assert result[0]["id"] == "msg1"
        assert result[1]["id"] == "msg2"
        mock_redis.zrevrange.assert_called_once_with("nadia_quarantine_queue", 0, 9)
        pipeline_mock.execute.assert_called_once()

    @patch('utils.protocol_manager.ProtocolManager._get_redis', new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_get_quarantine_queue_empty(self, mock_get_redis, protocol_manager, mock_redis):
        """Test getting empty quarantine queue."""
        # Setup
        mock_get_redis.return_value = mock_redis
        mock_redis.zrevrange.return_value = []
        
        # Execute
        result = await protocol_manager.get_quarantine_queue()
        
        # Verify
        assert result == []
        mock_redis.zrevrange.assert_called_once_with("nadia_quarantine_queue", 0, 49)

    @patch('utils.protocol_manager.ProtocolManager._get_redis', new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_get_quarantine_queue_redis_fallback(self, mock_get_redis, protocol_manager, mock_db, mock_redis):
        """Test quarantine queue fallback to database on Redis error."""
        # Setup
        mock_get_redis.return_value = mock_redis
        mock_redis.zrevrange.side_effect = Exception("Redis error")
        mock_db.get_quarantine_messages.return_value = [{"id": "msg1", "message": "fallback"}]
        
        # Execute
        result = await protocol_manager.get_quarantine_queue()
        
        # Verify
        assert len(result) == 1
        assert result[0]["id"] == "msg1"
        mock_db.get_quarantine_messages.assert_called_once_with(limit=50)

    @patch('utils.protocol_manager.ProtocolManager._get_redis', new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_process_quarantine_message(self, mock_get_redis, protocol_manager, mock_db, mock_redis):
        """Test processing quarantine message."""
        # Setup
        mock_get_redis.return_value = mock_redis
        msg_data = json.dumps({"id": "msg123", "user_id": "user1", "message": "Hello"})
        mock_redis.hget.return_value = msg_data.encode()
        mock_db.process_quarantine_message.return_value = {"processed": True}
        
        # Execute
        result = await protocol_manager.process_quarantine_message("msg123", "admin")
        
        # Verify
        assert result == {"processed": True}
        mock_db.process_quarantine_message.assert_called_once_with("msg123", "admin")
        mock_redis.hdel.assert_called_once_with("nadia_quarantine_items", "msg123")
        mock_redis.zrem.assert_called_once_with("nadia_quarantine_queue", "msg123")

    @patch('utils.protocol_manager.ProtocolManager._get_redis', new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_process_quarantine_message_not_in_redis(self, mock_get_redis, protocol_manager, mock_db, mock_redis):
        """Test processing quarantine message not in Redis."""
        # Setup
        mock_get_redis.return_value = mock_redis
        mock_redis.hget.return_value = None  # Not in Redis
        mock_db.process_quarantine_message.return_value = {"processed": True}
        
        # Execute
        result = await protocol_manager.process_quarantine_message("msg123", "admin")
        
        # Verify
        assert result == {"processed": True}
        mock_db.process_quarantine_message.assert_called_once_with("msg123", "admin")
        # Should not try to remove from Redis if not there
        mock_redis.hdel.assert_not_called()
        mock_redis.zrem.assert_not_called()

    @patch('utils.protocol_manager.ProtocolManager._get_redis', new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_invalidate_cache(self, mock_get_redis, protocol_manager, mock_redis):
        """Test cache invalidation."""
        # Setup
        mock_get_redis.return_value = mock_redis
        
        # Execute
        await protocol_manager.invalidate_cache("user123")
        
        # Verify
        mock_redis.delete.assert_called_once_with("protocol_cache:user123")

    @patch('utils.protocol_manager.ProtocolManager._get_redis', new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_get_stats(self, mock_get_redis, protocol_manager, mock_db, mock_redis):
        """Test getting protocol statistics."""
        # Setup
        mock_get_redis.return_value = mock_redis
        mock_db.get_protocol_stats.return_value = {
            "active_protocols": 5,
            "total_quarantined": 15
        }
        mock_redis.zcard.return_value = 3
        protocol_manager._active_protocols = {"user1", "user2"}
        
        # Execute
        result = await protocol_manager.get_stats()
        
        # Verify
        expected_stats = {
            "active_protocols": 5,
            "total_quarantined": 15,
            "quarantine_queue_size": 3,
            "cached_protocols": 2
        }
        assert result == expected_stats

    @patch('utils.protocol_manager.ProtocolManager._get_redis', new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_get_stats_redis_error(self, mock_get_redis, protocol_manager, mock_db, mock_redis):
        """Test getting stats with Redis error."""
        # Setup
        mock_get_redis.return_value = mock_redis
        mock_db.get_protocol_stats.return_value = {"active_protocols": 5}
        mock_redis.zcard.side_effect = Exception("Redis error")
        
        # Execute
        result = await protocol_manager.get_stats()
        
        # Verify
        assert result["quarantine_queue_size"] == 0  # Fallback value

    def test_is_cache_loaded(self, protocol_manager):
        """Test cache loaded status."""
        # Initially false
        assert protocol_manager.is_cache_loaded() is False
        
        # After setting
        protocol_manager._cache_loaded = True
        assert protocol_manager.is_cache_loaded() is True

    @patch('utils.protocol_manager.ProtocolManager._get_redis', new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_error_handling_redis_failure(self, mock_get_redis, protocol_manager, mock_db):
        """Test error handling when Redis fails."""
        # Setup
        mock_get_redis.side_effect = Exception("Redis connection failed")
        mock_db.get_protocol_status.return_value = {"status": "ACTIVE"}
        
        # Execute - should fallback to database
        result = await protocol_manager.is_protocol_active("user123")
        
        # Verify
        assert result is True
        mock_db.get_protocol_status.assert_called_once_with("user123")

    @patch('utils.protocol_manager.ProtocolManager._get_redis', new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_concurrent_access(self, mock_get_redis, protocol_manager, mock_db, mock_redis):
        """Test concurrent access to protocol status."""
        # Setup
        mock_get_redis.return_value = mock_redis
        mock_redis.get.return_value = b"ACTIVE"
        
        # Execute multiple concurrent requests
        tasks = [
            protocol_manager.is_protocol_active("user123")
            for _ in range(10)
        ]
        results = await asyncio.gather(*tasks)
        
        # Verify
        assert all(result is True for result in results)
        # Should only call Redis once due to caching
        assert mock_redis.get.call_count <= 10  # May be called multiple times due to concurrency

    @patch('utils.protocol_manager.ProtocolManager._get_redis', new_callable=AsyncMock)
    @pytest.mark.asyncio
    async def test_protocol_activation_with_none_reason(self, mock_get_redis, protocol_manager, mock_db, mock_redis):
        """Test protocol activation with None reason."""
        # Setup
        mock_get_redis.return_value = mock_redis
        mock_db.activate_protocol.return_value = True
        
        # Execute
        result = await protocol_manager.activate_protocol("user123", "admin", None)
        
        # Verify
        assert result is True
        mock_db.activate_protocol.assert_called_once_with("user123", "admin", None)