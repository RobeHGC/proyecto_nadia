"""Unit tests for ProtocolManager - simplified mocking approach."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from utils.protocol_manager import ProtocolManager
from database.models import DatabaseManager


class TestProtocolManagerUnit:
    """Unit tests for ProtocolManager using simpler mocking."""

    @pytest.fixture
    def mock_db(self):
        """Mock database manager."""
        return AsyncMock(spec=DatabaseManager)

    @pytest.fixture
    def protocol_manager(self, mock_db):
        """Create ProtocolManager instance."""
        return ProtocolManager(mock_db)

    @patch('utils.protocol_manager.ProtocolManager._get_redis')
    async def test_is_protocol_active_cache_hit_simple(self, mock_get_redis, protocol_manager):
        """Test protocol check with cache hit."""
        # Setup
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=b"ACTIVE")
        mock_get_redis.return_value = mock_redis
        
        # Execute
        result = await protocol_manager.is_protocol_active("user123")
        
        # Verify
        assert result is True
        mock_redis.get.assert_called_once_with("protocol_cache:user123")

    @patch('utils.protocol_manager.ProtocolManager._get_redis')
    async def test_is_protocol_active_cache_miss(self, mock_get_redis, protocol_manager, mock_db):
        """Test protocol check with cache miss."""
        # Setup
        mock_redis = AsyncMock()
        mock_redis.get = AsyncMock(return_value=None)  # Cache miss
        mock_redis.setex = AsyncMock()
        mock_get_redis.return_value = mock_redis
        mock_db.get_protocol_status.return_value = {"status": "ACTIVE"}
        
        # Execute
        result = await protocol_manager.is_protocol_active("user123")
        
        # Verify
        assert result is True
        mock_db.get_protocol_status.assert_called_once_with("user123")
        mock_redis.setex.assert_called_once_with("protocol_cache:user123", 300, "ACTIVE")

    @patch('utils.protocol_manager.ProtocolManager._get_redis')
    async def test_activate_protocol_success(self, mock_get_redis, protocol_manager, mock_db):
        """Test successful protocol activation."""
        # Setup
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock()
        mock_redis.publish = AsyncMock()
        mock_get_redis.return_value = mock_redis
        mock_db.activate_protocol.return_value = True
        
        # Execute
        result = await protocol_manager.activate_protocol("user123", "admin", "spam")
        
        # Verify
        assert result is True
        mock_db.activate_protocol.assert_called_once_with("user123", "admin", "spam")
        mock_redis.setex.assert_called_once_with("protocol_cache:user123", 300, "ACTIVE")
        assert "user123" in protocol_manager._active_protocols

    @patch('utils.protocol_manager.ProtocolManager._get_redis')
    async def test_deactivate_protocol_success(self, mock_get_redis, protocol_manager, mock_db):
        """Test successful protocol deactivation."""
        # Setup
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock()
        mock_redis.publish = AsyncMock()
        mock_get_redis.return_value = mock_redis
        mock_db.deactivate_protocol.return_value = True
        protocol_manager._active_protocols.add("user123")
        
        # Execute
        result = await protocol_manager.deactivate_protocol("user123", "admin", "resolved")
        
        # Verify
        assert result is True
        mock_db.deactivate_protocol.assert_called_once_with("user123", "admin", "resolved")
        assert "user123" not in protocol_manager._active_protocols

    @patch('utils.protocol_manager.ProtocolManager._get_redis')
    async def test_invalidate_cache(self, mock_get_redis, protocol_manager):
        """Test cache invalidation."""
        # Setup
        mock_redis = AsyncMock()
        mock_redis.delete = AsyncMock()
        mock_get_redis.return_value = mock_redis
        
        # Execute
        await protocol_manager.invalidate_cache("user123")
        
        # Verify
        mock_redis.delete.assert_called_once_with("protocol_cache:user123")

    @patch('utils.protocol_manager.ProtocolManager._get_redis')
    async def test_get_stats_success(self, mock_get_redis, protocol_manager, mock_db):
        """Test getting protocol statistics."""
        # Setup
        mock_redis = AsyncMock()
        mock_redis.zcard = AsyncMock(return_value=3)
        mock_get_redis.return_value = mock_redis
        mock_db.get_protocol_stats.return_value = {
            "active_protocols": 5,
            "total_quarantined": 15
        }
        protocol_manager._active_protocols = {"user1", "user2"}
        
        # Execute
        result = await protocol_manager.get_stats()
        
        # Verify
        expected = {
            "active_protocols": 5,
            "total_quarantined": 15,
            "quarantine_queue_size": 3,
            "cached_protocols": 2
        }
        assert result == expected

    def test_is_cache_loaded_flag(self, protocol_manager):
        """Test cache loaded flag management."""
        # Initially false
        assert protocol_manager.is_cache_loaded() is False
        
        # After setting
        protocol_manager._cache_loaded = True
        assert protocol_manager.is_cache_loaded() is True

    async def test_redis_connection_error_handling(self, protocol_manager, mock_db):
        """Test error handling when Redis is completely unavailable."""
        # Setup
        with patch('utils.protocol_manager.ProtocolManager._get_redis', side_effect=Exception("Redis down")):
            mock_db.get_protocol_status.return_value = {"status": "ACTIVE"}
            
            # Execute
            result = await protocol_manager.is_protocol_active("user123")
            
            # Verify - should fallback to database
            assert result is True
            mock_db.get_protocol_status.assert_called_once_with("user123")

    @patch('utils.protocol_manager.ProtocolManager._get_redis')
    async def test_protocol_local_cache_management(self, mock_get_redis, protocol_manager, mock_db):
        """Test local cache (_active_protocols set) is managed correctly."""
        # Setup
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock()
        mock_redis.publish = AsyncMock()
        mock_get_redis.return_value = mock_redis
        mock_db.activate_protocol.return_value = True
        mock_db.deactivate_protocol.return_value = True
        
        # Test activation updates local cache
        await protocol_manager.activate_protocol("user123", "admin", "reason")
        assert "user123" in protocol_manager._active_protocols
        
        # Test deactivation updates local cache
        await protocol_manager.deactivate_protocol("user123", "admin", "reason")
        assert "user123" not in protocol_manager._active_protocols

    @patch('utils.protocol_manager.ProtocolManager._get_redis')
    async def test_protocol_failure_scenarios(self, mock_get_redis, protocol_manager, mock_db):
        """Test handling of database failures during protocol operations."""
        # Setup
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis
        mock_db.activate_protocol.return_value = False  # Database operation failed
        
        # Execute
        result = await protocol_manager.activate_protocol("user123", "admin", "reason")
        
        # Verify
        assert result is False
        # Should not update Redis or local cache on database failure
        mock_redis.setex.assert_not_called()
        mock_redis.publish.assert_not_called()
        assert "user123" not in protocol_manager._active_protocols

    @patch('utils.protocol_manager.ProtocolManager._get_redis')
    async def test_get_stats_redis_error_fallback(self, mock_get_redis, protocol_manager, mock_db):
        """Test stats collection with Redis error fallback."""
        # Setup
        mock_redis = AsyncMock()
        mock_redis.zcard = AsyncMock(side_effect=Exception("Redis error"))
        mock_get_redis.return_value = mock_redis
        mock_db.get_protocol_stats.return_value = {"active_protocols": 5}
        
        # Execute
        result = await protocol_manager.get_stats()
        
        # Verify fallback to 0 for Redis-dependent stats
        assert result["quarantine_queue_size"] == 0
        assert result["active_protocols"] == 5

    @patch('utils.protocol_manager.ProtocolManager._get_redis')
    async def test_protocol_event_publishing(self, mock_get_redis, protocol_manager, mock_db):
        """Test that protocol changes publish events for real-time updates."""
        # Setup
        mock_redis = AsyncMock()
        mock_redis.setex = AsyncMock()
        mock_redis.publish = AsyncMock()
        mock_get_redis.return_value = mock_redis
        mock_db.activate_protocol.return_value = True
        
        # Execute
        await protocol_manager.activate_protocol("user123", "admin", "spam")
        
        # Verify event was published
        mock_redis.publish.assert_called_once()
        call_args = mock_redis.publish.call_args[0]
        assert call_args[0] == "protocol_updates"
        # Check event contains required fields
        import json
        event_data = json.loads(call_args[1])
        assert event_data["action"] == "activated"
        assert event_data["user_id"] == "user123"
        assert event_data["by"] == "admin"