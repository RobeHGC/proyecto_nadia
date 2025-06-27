"""Simplified unit tests for ProtocolManager - focusing on core functionality."""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from utils.protocol_manager import ProtocolManager
from database.models import DatabaseManager


class TestProtocolManagerSimple:
    """Simplified test suite for ProtocolManager."""

    @pytest.fixture
    def mock_db(self):
        """Mock database manager."""
        return AsyncMock(spec=DatabaseManager)

    @pytest.fixture
    def protocol_manager(self, mock_db):
        """Create ProtocolManager instance."""
        return ProtocolManager(mock_db)

    @pytest.fixture
    def mock_redis(self):
        """Mock Redis connection."""
        redis_mock = AsyncMock()
        pipeline_mock = AsyncMock()
        redis_mock.pipeline.return_value = pipeline_mock
        pipeline_mock.execute.return_value = []
        pipeline_mock.setex = AsyncMock()
        redis_mock.setex = AsyncMock()
        redis_mock.get = AsyncMock()
        redis_mock.publish = AsyncMock()
        redis_mock.hset = AsyncMock()
        redis_mock.zadd = AsyncMock()
        redis_mock.zrevrange = AsyncMock()
        redis_mock.hdel = AsyncMock()
        redis_mock.zrem = AsyncMock()
        redis_mock.delete = AsyncMock()
        redis_mock.zcard = AsyncMock()
        return redis_mock

    @patch('utils.protocol_manager.ProtocolManager._get_redis')
    async def test_initialization_success(self, mock_get_redis, protocol_manager, mock_db, mock_redis):
        """Test successful initialization."""
        mock_db.get_active_protocol_users.return_value = ["user1", "user2"]
        mock_get_redis.return_value = mock_redis
        
        # Create a proper pipeline mock
        pipeline_mock = AsyncMock()
        pipeline_mock.setex = AsyncMock()
        pipeline_mock.execute = AsyncMock(return_value=[])
        mock_redis.pipeline.return_value = pipeline_mock
        
        await protocol_manager.initialize()
        
        assert protocol_manager._cache_loaded is True
        assert len(protocol_manager._active_protocols) == 2
        mock_db.get_active_protocol_users.assert_called_once()
        pipeline_mock.execute.assert_called_once()

    @patch('utils.protocol_manager.ProtocolManager._get_redis')
    async def test_is_protocol_active_cache_hit(self, mock_get_redis, protocol_manager, mock_redis):
        """Test checking protocol with cache hit."""
        mock_get_redis.return_value = mock_redis
        mock_redis.get.return_value = b"ACTIVE"
        
        result = await protocol_manager.is_protocol_active("user123")
        
        assert result is True
        mock_redis.get.assert_called_once_with("protocol_cache:user123")

    @patch('utils.protocol_manager.ProtocolManager._get_redis')
    async def test_is_protocol_active_cache_miss_active(self, mock_get_redis, protocol_manager, mock_db, mock_redis):
        """Test checking protocol with cache miss - user is active."""
        mock_get_redis.return_value = mock_redis
        mock_redis.get.return_value = None  # Cache miss
        mock_db.get_protocol_status.return_value = {"status": "ACTIVE"}
        
        result = await protocol_manager.is_protocol_active("user123")
        
        assert result is True
        mock_db.get_protocol_status.assert_called_once_with("user123")
        mock_redis.setex.assert_called_once_with("protocol_cache:user123", 300, "ACTIVE")

    @patch('utils.protocol_manager.ProtocolManager._get_redis')
    async def test_is_protocol_active_cache_miss_inactive(self, mock_get_redis, protocol_manager, mock_db, mock_redis):
        """Test checking protocol with cache miss - user is inactive."""
        mock_get_redis.return_value = mock_redis
        mock_redis.get.return_value = None  # Cache miss
        mock_db.get_protocol_status.return_value = {"status": "INACTIVE"}
        
        result = await protocol_manager.is_protocol_active("user123")
        
        assert result is False
        mock_redis.setex.assert_called_once_with("protocol_cache:user123", 300, "INACTIVE")

    @patch('utils.protocol_manager.ProtocolManager._get_redis')
    async def test_activate_protocol_success(self, mock_get_redis, protocol_manager, mock_db, mock_redis):
        """Test successful protocol activation."""
        mock_get_redis.return_value = mock_redis
        mock_db.activate_protocol.return_value = True
        
        result = await protocol_manager.activate_protocol("user123", "admin", "spam")
        
        assert result is True
        mock_db.activate_protocol.assert_called_once_with("user123", "admin", "spam")
        mock_redis.setex.assert_called_once_with("protocol_cache:user123", 300, "ACTIVE")
        assert "user123" in protocol_manager._active_protocols

    @patch('utils.protocol_manager.ProtocolManager._get_redis')
    async def test_activate_protocol_failure(self, mock_get_redis, protocol_manager, mock_db, mock_redis):
        """Test failed protocol activation."""
        mock_get_redis.return_value = mock_redis
        mock_db.activate_protocol.return_value = False
        
        result = await protocol_manager.activate_protocol("user123", "admin", "reason")
        
        assert result is False
        mock_redis.setex.assert_not_called()
        mock_redis.publish.assert_not_called()

    @patch('utils.protocol_manager.ProtocolManager._get_redis')
    async def test_deactivate_protocol_success(self, mock_get_redis, protocol_manager, mock_db, mock_redis):
        """Test successful protocol deactivation."""
        mock_get_redis.return_value = mock_redis
        mock_db.deactivate_protocol.return_value = True
        protocol_manager._active_protocols.add("user123")
        
        result = await protocol_manager.deactivate_protocol("user123", "admin", "resolved")
        
        assert result is True
        mock_db.deactivate_protocol.assert_called_once_with("user123", "admin", "resolved")
        mock_redis.setex.assert_called_once_with("protocol_cache:user123", 300, "INACTIVE")
        assert "user123" not in protocol_manager._active_protocols

    @patch('utils.protocol_manager.ProtocolManager._get_redis')
    async def test_queue_for_quarantine(self, mock_get_redis, protocol_manager, mock_db, mock_redis):
        """Test queuing message for quarantine."""
        mock_get_redis.return_value = mock_redis
        mock_db.save_quarantine_message.return_value = "quar_123"
        
        # Mock asyncio.get_event_loop().time() with a fixed timestamp
        with patch('asyncio.get_event_loop') as mock_event_loop:
            mock_loop = MagicMock()
            mock_loop.time.return_value = 1640995200.0
            mock_event_loop.return_value = mock_loop
            
            result = await protocol_manager.queue_for_quarantine(
                "user123", "msg_456", "Hello", 789, [{"role": "user", "content": "Hi"}]
            )
        
        assert result == "quar_123"
        mock_db.save_quarantine_message.assert_called_once_with("user123", "msg_456", "Hello", 789)
        mock_redis.hset.assert_called_once()
        mock_redis.zadd.assert_called_once()

    @patch('utils.protocol_manager.ProtocolManager._get_redis')
    async def test_get_quarantine_queue_success(self, mock_get_redis, protocol_manager, mock_redis):
        """Test getting quarantine queue."""
        mock_get_redis.return_value = mock_redis
        mock_redis.zrevrange.return_value = [b"msg1", b"msg2"]
        
        msg1_data = json.dumps({"id": "msg1", "message": "Hello"})
        msg2_data = json.dumps({"id": "msg2", "message": "World"})
        
        # Create pipeline mock with proper execute return
        pipeline_mock = AsyncMock()
        pipeline_mock.execute.return_value = [msg1_data.encode(), msg2_data.encode()]
        mock_redis.pipeline.return_value = pipeline_mock
        
        result = await protocol_manager.get_quarantine_queue(10)
        
        assert len(result) == 2
        assert result[0]["id"] == "msg1"
        assert result[1]["id"] == "msg2"

    @patch('utils.protocol_manager.ProtocolManager._get_redis')
    async def test_get_quarantine_queue_empty(self, mock_get_redis, protocol_manager, mock_redis):
        """Test getting empty quarantine queue."""
        mock_get_redis.return_value = mock_redis
        mock_redis.zrevrange.return_value = []
        
        result = await protocol_manager.get_quarantine_queue()
        
        assert result == []

    @patch('utils.protocol_manager.ProtocolManager._get_redis')
    async def test_process_quarantine_message_success(self, mock_get_redis, protocol_manager, mock_db, mock_redis):
        """Test processing quarantine message."""
        mock_get_redis.return_value = mock_redis
        msg_data = json.dumps({"id": "msg123", "message": "Hello"})
        mock_redis.hget.return_value = msg_data.encode()
        mock_db.process_quarantine_message.return_value = {"processed": True}
        
        result = await protocol_manager.process_quarantine_message("msg123", "admin")
        
        assert result == {"processed": True}
        mock_db.process_quarantine_message.assert_called_once_with("msg123", "admin")
        mock_redis.hdel.assert_called_once_with("nadia_quarantine_items", "msg123")
        mock_redis.zrem.assert_called_once_with("nadia_quarantine_queue", "msg123")

    @patch('utils.protocol_manager.ProtocolManager._get_redis')
    async def test_invalidate_cache_success(self, mock_get_redis, protocol_manager, mock_redis):
        """Test cache invalidation."""
        mock_get_redis.return_value = mock_redis
        
        await protocol_manager.invalidate_cache("user123")
        
        mock_redis.delete.assert_called_once_with("protocol_cache:user123")

    @patch('utils.protocol_manager.ProtocolManager._get_redis')
    async def test_get_stats_success(self, mock_get_redis, protocol_manager, mock_db, mock_redis):
        """Test getting protocol statistics."""
        mock_get_redis.return_value = mock_redis
        mock_db.get_protocol_stats.return_value = {
            "active_protocols": 5,
            "total_quarantined": 15
        }
        mock_redis.zcard.return_value = 3
        protocol_manager._active_protocols = {"user1", "user2"}
        
        result = await protocol_manager.get_stats()
        
        expected = {
            "active_protocols": 5,
            "total_quarantined": 15,
            "quarantine_queue_size": 3,
            "cached_protocols": 2
        }
        assert result == expected

    @patch('utils.protocol_manager.ProtocolManager._get_redis')
    async def test_get_stats_redis_error(self, mock_get_redis, protocol_manager, mock_db, mock_redis):
        """Test getting stats when Redis fails."""
        mock_get_redis.return_value = mock_redis
        mock_db.get_protocol_stats.return_value = {"active_protocols": 5}
        mock_redis.zcard.side_effect = Exception("Redis error")
        
        result = await protocol_manager.get_stats()
        
        assert result["quarantine_queue_size"] == 0

    def test_is_cache_loaded(self, protocol_manager):
        """Test cache loaded status."""
        assert protocol_manager.is_cache_loaded() is False
        
        protocol_manager._cache_loaded = True
        assert protocol_manager.is_cache_loaded() is True

    async def test_error_handling_redis_failure(self, protocol_manager, mock_db):
        """Test error handling when Redis fails completely."""
        with patch('utils.protocol_manager.ProtocolManager._get_redis', side_effect=Exception("Redis down")):
            mock_db.get_protocol_status.return_value = {"status": "ACTIVE"}
            
            result = await protocol_manager.is_protocol_active("user123")
            
            assert result is True
            mock_db.get_protocol_status.assert_called_once_with("user123")

    @patch('utils.protocol_manager.ProtocolManager._get_redis')
    async def test_protocol_event_publishing(self, mock_get_redis, protocol_manager, mock_db, mock_redis):
        """Test that protocol changes publish events."""
        mock_get_redis.return_value = mock_redis
        mock_db.activate_protocol.return_value = True
        
        await protocol_manager.activate_protocol("user123", "admin", "spam")
        
        expected_event = json.dumps({
            "action": "activated",
            "user_id": "user123",
            "by": "admin"
        })
        mock_redis.publish.assert_called_once_with("protocol_updates", expected_event)

    @patch('utils.protocol_manager.ProtocolManager._get_redis')
    async def test_local_cache_management(self, mock_get_redis, protocol_manager, mock_db, mock_redis):
        """Test that local cache (_active_protocols) is managed correctly."""
        mock_get_redis.return_value = mock_redis
        mock_db.activate_protocol.return_value = True
        mock_db.deactivate_protocol.return_value = True
        
        # Activate
        await protocol_manager.activate_protocol("user123", "admin", "reason")
        assert "user123" in protocol_manager._active_protocols
        
        # Deactivate
        await protocol_manager.deactivate_protocol("user123", "admin", "reason")
        assert "user123" not in protocol_manager._active_protocols