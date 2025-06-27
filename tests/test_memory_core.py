"""Unit tests for UserMemoryManager core functionality."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json

from memory.user_memory import UserMemoryManager
from utils.constants import MAX_HISTORY_LENGTH, RECENT_MESSAGES_COUNT


class TestUserMemoryManager:
    """Test suite for UserMemoryManager."""

    @pytest.fixture
    def memory_manager(self):
        """Create UserMemoryManager instance."""
        return UserMemoryManager()

    @pytest.fixture
    def sample_messages(self):
        """Sample conversation messages."""
        return [
            {"role": "user", "content": "Hello", "timestamp": "2024-01-01T10:00:00"},
            {"role": "assistant", "content": "Hi there!", "timestamp": "2024-01-01T10:01:00"},
            {"role": "user", "content": "How are you?", "timestamp": "2024-01-01T10:02:00"},
            {"role": "assistant", "content": "I'm doing well!", "timestamp": "2024-01-01T10:03:00"}
        ]

    @patch('memory.user_memory.UserMemoryManager._get_redis')
    async def test_save_user_message(self, mock_get_redis, memory_manager):
        """Test saving user message to Redis."""
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis
        mock_redis.llen.return_value = 5  # Current length
        
        result = await memory_manager.save_user_message("user123", "Hello world")
        
        assert result is True
        mock_redis.lpush.assert_called_once()
        mock_redis.expire.assert_called_once()

    @patch('memory.user_memory.UserMemoryManager._get_redis')
    async def test_save_bot_response(self, mock_get_redis, memory_manager):
        """Test saving bot response to Redis."""
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis
        mock_redis.llen.return_value = 5
        
        result = await memory_manager.save_bot_response("user123", "Hi there!")
        
        assert result is True
        mock_redis.lpush.assert_called_once()
        mock_redis.expire.assert_called_once()

    @patch('memory.user_memory.UserMemoryManager._get_redis')
    async def test_get_conversation_history(self, mock_get_redis, memory_manager, sample_messages):
        """Test retrieving conversation history."""
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis
        
        # Mock Redis returning JSON strings
        redis_data = [json.dumps(msg).encode() for msg in sample_messages]
        mock_redis.lrange.return_value = redis_data
        
        result = await memory_manager.get_conversation_history("user123", limit=10)
        
        assert len(result) == 4
        assert result[0]["role"] == "user"
        assert result[0]["content"] == "Hello"
        mock_redis.lrange.assert_called_once_with("user:user123:history", 0, 9)

    @patch('memory.user_memory.UserMemoryManager._get_redis')
    async def test_get_conversation_history_empty(self, mock_get_redis, memory_manager):
        """Test retrieving empty conversation history."""
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis
        mock_redis.lrange.return_value = []
        
        result = await memory_manager.get_conversation_history("user123")
        
        assert result == []

    @patch('memory.user_memory.UserMemoryManager._get_redis')
    async def test_history_length_management(self, mock_get_redis, memory_manager):
        """Test history length is managed correctly."""
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis
        mock_redis.llen.return_value = MAX_HISTORY_LENGTH + 5  # Over limit
        
        await memory_manager.save_user_message("user123", "Test message")
        
        # Should trim when over limit
        mock_redis.ltrim.assert_called_once_with("user:user123:history", 0, MAX_HISTORY_LENGTH - 1)

    @patch('memory.user_memory.UserMemoryManager._get_redis')
    async def test_redis_key_format(self, mock_get_redis, memory_manager):
        """Test Redis key format is consistent."""
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis
        mock_redis.llen.return_value = 1
        
        await memory_manager.save_user_message("user123", "Test")
        
        # Check key format used in lpush call
        call_args = mock_redis.lpush.call_args[0]
        assert call_args[0] == "user:user123:history"

    @patch('memory.user_memory.UserMemoryManager._get_redis')
    async def test_message_json_serialization(self, mock_get_redis, memory_manager):
        """Test messages are properly JSON serialized."""
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis
        mock_redis.llen.return_value = 1
        
        await memory_manager.save_user_message("user123", "Test message")
        
        # Check JSON serialization in lpush call
        call_args = mock_redis.lpush.call_args[0]
        message_json = call_args[1]
        message_data = json.loads(message_json)
        
        assert message_data["role"] == "user"
        assert message_data["content"] == "Test message"
        assert "timestamp" in message_data

    @patch('memory.user_memory.UserMemoryManager._get_redis')
    async def test_redis_expiration_set(self, mock_get_redis, memory_manager):
        """Test Redis expiration is set correctly."""
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis
        mock_redis.llen.return_value = 1
        
        await memory_manager.save_user_message("user123", "Test")
        
        # Check expire call
        mock_redis.expire.assert_called_once()
        expire_args = mock_redis.expire.call_args[0]
        assert expire_args[0] == "user:user123:history"
        assert expire_args[1] > 0  # Should have positive expiration

    @patch('memory.user_memory.UserMemoryManager._get_redis')
    async def test_error_handling_redis_failure(self, mock_get_redis, memory_manager):
        """Test error handling when Redis fails."""
        mock_get_redis.side_effect = Exception("Redis connection failed")
        
        result = await memory_manager.save_user_message("user123", "Test")
        
        assert result is False

    @patch('memory.user_memory.UserMemoryManager._get_redis')
    async def test_conversation_isolation(self, mock_get_redis, memory_manager):
        """Test conversations are isolated per user."""
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis
        mock_redis.llen.return_value = 1
        
        await memory_manager.save_user_message("user123", "Message from user 123")
        await memory_manager.save_user_message("user456", "Message from user 456")
        
        # Check different keys were used
        call_args_list = mock_redis.lpush.call_args_list
        assert len(call_args_list) == 2
        assert call_args_list[0][0][0] == "user:user123:history"
        assert call_args_list[1][0][0] == "user:user456:history"

    def test_constants_usage(self):
        """Test that memory manager uses defined constants."""
        # Verify constants are imported and used
        assert MAX_HISTORY_LENGTH == 50
        assert RECENT_MESSAGES_COUNT == 10
        assert MAX_HISTORY_LENGTH > RECENT_MESSAGES_COUNT

    @patch('memory.user_memory.UserMemoryManager._get_redis')
    async def test_message_structure_consistency(self, mock_get_redis, memory_manager):
        """Test message structure is consistent between user and bot messages."""
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis
        mock_redis.llen.return_value = 1
        
        await memory_manager.save_user_message("user123", "User message")
        await memory_manager.save_bot_response("user123", "Bot response")
        
        # Check both messages have consistent structure
        call_args_list = mock_redis.lpush.call_args_list
        user_msg = json.loads(call_args_list[0][0][1])
        bot_msg = json.loads(call_args_list[1][0][1])
        
        # Both should have same keys
        assert set(user_msg.keys()) == set(bot_msg.keys())
        assert user_msg["role"] == "user"
        assert bot_msg["role"] == "assistant"
        assert "content" in user_msg
        assert "timestamp" in user_msg

    @patch('memory.user_memory.UserMemoryManager._get_redis')
    async def test_limit_parameter_respected(self, mock_get_redis, memory_manager, sample_messages):
        """Test limit parameter is respected in get_conversation_history."""
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis
        
        redis_data = [json.dumps(msg).encode() for msg in sample_messages]
        mock_redis.lrange.return_value = redis_data
        
        # Request only 2 messages
        result = await memory_manager.get_conversation_history("user123", limit=2)
        
        # Should call lrange with correct limit
        mock_redis.lrange.assert_called_once_with("user:user123:history", 0, 1)

    @patch('memory.user_memory.UserMemoryManager._get_redis')
    async def test_invalid_json_handling(self, mock_get_redis, memory_manager):
        """Test handling of invalid JSON in Redis data."""
        mock_redis = AsyncMock()
        mock_get_redis.return_value = mock_redis
        
        # Mock Redis returning invalid JSON
        mock_redis.lrange.return_value = [b"invalid json", b'{"valid": "json"}']
        
        result = await memory_manager.get_conversation_history("user123")
        
        # Should skip invalid JSON and return valid ones
        assert len(result) == 1
        assert result[0]["valid"] == "json"