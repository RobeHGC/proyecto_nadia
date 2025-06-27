"""Redis connection startup tests - prevents Redis-related startup failures.

EPIC 1: CRITICAL FOUNDATION TESTS
Issue: https://github.com/RobeHGC/proyecto_nadia/issues/22

This test ensures Redis connections can be established and the RedisConnectionMixin
works properly, preventing production startup failures.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import redis.asyncio as redis
from utils.redis_mixin import RedisConnectionMixin
from utils.config import Config


class TestRedisStartup:
    """Test Redis connection and startup functionality."""
    
    VALID_REDIS_URLS = [
        "redis://localhost:6379/0",
        "redis://localhost:6379/1", 
        "redis://127.0.0.1:6379/0",
        "redis://:password@localhost:6379/0",
        "redis://user:password@localhost:6379/0"
    ]
    
    INVALID_REDIS_URLS = [
        "",
        "invalid_url",
        "redis://",
        "redis://nonexistent_host:6379/0",
        "redis://localhost:99999/0",  # Invalid port
        "not_a_redis_url_at_all",
        "http://localhost:6379/0",  # Wrong protocol
    ]
    
    class TestClassWithRedisMixin(RedisConnectionMixin):
        """Test class that uses RedisConnectionMixin."""
        
        def __init__(self, config=None):
            self.config = config
            super().__init__()
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock config with valid Redis URL."""
        config = MagicMock()
        config.redis_url = "redis://localhost:6379/0"
        return config
    
    @pytest.fixture
    def redis_test_class(self, mock_config):
        """Create test class instance with Redis mixin."""
        return self.TestClassWithRedisMixin(mock_config)
    
    @pytest.mark.asyncio
    async def test_redis_connection_mixin_initialization(self, redis_test_class):
        """Test RedisConnectionMixin initialization."""
        assert redis_test_class._redis is None
        assert redis_test_class._config is not None
    
    @pytest.mark.asyncio
    async def test_redis_connection_creation_success(self, redis_test_class):
        """Test successful Redis connection creation."""
        mock_redis = AsyncMock()
        
        with patch('redis.asyncio.from_url', return_value=mock_redis) as mock_from_url:
            redis_conn = await redis_test_class._get_redis()
            
            mock_from_url.assert_called_once_with(redis_test_class._config.redis_url)
            assert redis_conn == mock_redis
            assert redis_test_class._redis == mock_redis
    
    @pytest.mark.asyncio
    async def test_redis_connection_reuse(self, redis_test_class):
        """Test that Redis connection is reused after first creation."""
        mock_redis = AsyncMock()
        
        with patch('redis.asyncio.from_url', return_value=mock_redis) as mock_from_url:
            # First call should create connection
            redis_conn1 = await redis_test_class._get_redis()
            # Second call should reuse existing connection
            redis_conn2 = await redis_test_class._get_redis()
            
            mock_from_url.assert_called_once()  # Only called once
            assert redis_conn1 == redis_conn2
            assert redis_conn1 == mock_redis
    
    @pytest.mark.asyncio
    async def test_redis_connection_failure(self, redis_test_class):
        """Test Redis connection failure handling."""
        connection_error = redis.exceptions.ConnectionError("Redis connection failed")
        
        with patch('redis.asyncio.from_url', side_effect=connection_error):
            with pytest.raises(redis.exceptions.ConnectionError):
                await redis_test_class._get_redis()
            
            assert redis_test_class._redis is None
    
    @pytest.mark.asyncio
    async def test_redis_connection_close(self, redis_test_class):
        """Test Redis connection closing."""
        mock_redis = AsyncMock()
        
        with patch('redis.asyncio.from_url', return_value=mock_redis):
            # Create connection
            await redis_test_class._get_redis()
            assert redis_test_class._redis == mock_redis
            
            # Close connection
            await redis_test_class._close_redis()
            mock_redis.aclose.assert_called_once()
            assert redis_test_class._redis is None
    
    @pytest.mark.asyncio
    async def test_redis_connection_close_when_not_connected(self, redis_test_class):
        """Test closing Redis connection when not connected."""
        # Should not raise an exception
        await redis_test_class._close_redis()
        assert redis_test_class._redis is None
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("redis_url", VALID_REDIS_URLS)
    async def test_redis_connection_with_various_valid_urls(self, redis_url):
        """Test Redis connection with various valid URL formats."""
        mock_redis = AsyncMock()
        
        config = MagicMock()
        config.redis_url = redis_url
        test_instance = self.TestClassWithRedisMixin(config)
        
        with patch('redis.asyncio.from_url', return_value=mock_redis) as mock_from_url:
            redis_conn = await test_instance._get_redis()
            
            mock_from_url.assert_called_once_with(redis_url)
            assert redis_conn == mock_redis
    
    @pytest.mark.asyncio
    @pytest.mark.parametrize("redis_url", INVALID_REDIS_URLS)
    async def test_redis_connection_with_invalid_urls(self, redis_url):
        """Test Redis connection with invalid URLs."""
        config = MagicMock()
        config.redis_url = redis_url
        test_instance = self.TestClassWithRedisMixin(config)
        
        # Mock redis.from_url to raise appropriate errors for invalid URLs
        with patch('redis.asyncio.from_url', side_effect=redis.exceptions.ConnectionError("Invalid URL")):
            with pytest.raises(redis.exceptions.ConnectionError):
                await test_instance._get_redis()
    
    @pytest.mark.asyncio
    async def test_redis_mixin_with_config_from_env(self):
        """Test RedisConnectionMixin using Config.from_env()."""
        mock_redis = AsyncMock()
        
        # Mock Config.from_env to return a config with Redis URL
        with patch.object(Config, 'from_env') as mock_from_env:
            mock_config = MagicMock()
            mock_config.redis_url = "redis://localhost:6379/0"
            mock_from_env.return_value = mock_config
            
            # Create instance without passing config (should use Config.from_env)
            test_instance = self.TestClassWithRedisMixin()
            
            with patch('redis.asyncio.from_url', return_value=mock_redis):
                redis_conn = await test_instance._get_redis()
                
                assert redis_conn == mock_redis
                mock_from_env.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_redis_basic_operations(self):
        """Test basic Redis operations to ensure connection works."""
        mock_redis = AsyncMock()
        mock_redis.set.return_value = True
        mock_redis.get.return_value = b"test_value"
        mock_redis.delete.return_value = 1
        
        config = MagicMock()
        config.redis_url = "redis://localhost:6379/0"
        test_instance = self.TestClassWithRedisMixin(config)
        
        with patch('redis.asyncio.from_url', return_value=mock_redis):
            redis_conn = await test_instance._get_redis()
            
            # Test basic operations
            await redis_conn.set("test_key", "test_value")
            value = await redis_conn.get("test_key")
            deleted_count = await redis_conn.delete("test_key")
            
            mock_redis.set.assert_called_once_with("test_key", "test_value")
            mock_redis.get.assert_called_once_with("test_key")
            mock_redis.delete.assert_called_once_with("test_key")
            
            assert value == b"test_value"
            assert deleted_count == 1
    
    @pytest.mark.asyncio
    async def test_redis_connection_timeout_handling(self, redis_test_class):
        """Test Redis connection timeout handling."""
        timeout_error = redis.exceptions.TimeoutError("Redis timeout")
        
        with patch('redis.asyncio.from_url', side_effect=timeout_error):
            with pytest.raises(redis.exceptions.TimeoutError):
                await redis_test_class._get_redis()
    
    @pytest.mark.asyncio
    async def test_redis_connection_auth_failure(self, redis_test_class):
        """Test Redis authentication failure handling."""
        auth_error = redis.exceptions.AuthenticationError("Authentication failed")
        
        with patch('redis.asyncio.from_url', side_effect=auth_error):
            with pytest.raises(redis.exceptions.AuthenticationError):
                await redis_test_class._get_redis()
    
    @pytest.mark.asyncio
    async def test_redis_startup_sequence(self):
        """Test complete Redis startup sequence."""
        mock_redis = AsyncMock()
        config = MagicMock()
        config.redis_url = "redis://localhost:6379/0"
        
        with patch('redis.asyncio.from_url', return_value=mock_redis):
            # Step 1: Create instance
            test_instance = self.TestClassWithRedisMixin(config)
            assert test_instance._redis is None
            
            # Step 2: Get Redis connection (initializes)
            redis_conn = await test_instance._get_redis()
            assert redis_conn == mock_redis
            assert test_instance._redis == mock_redis
            
            # Step 3: Use Redis connection
            await redis_conn.ping()
            mock_redis.ping.assert_called_once()
            
            # Step 4: Clean shutdown
            await test_instance._close_redis()
            mock_redis.aclose.assert_called_once()
            assert test_instance._redis is None
    
    @pytest.mark.asyncio
    async def test_redis_multiple_connection_attempts(self, redis_test_class):
        """Test multiple Redis connection attempts after failure."""
        # First attempt fails, second succeeds
        connection_error = redis.exceptions.ConnectionError("Connection failed")
        mock_redis = AsyncMock()
        
        with patch('redis.asyncio.from_url', side_effect=[connection_error, mock_redis]):
            # First attempt should fail
            with pytest.raises(redis.exceptions.ConnectionError):
                await redis_test_class._get_redis()
            assert redis_test_class._redis is None
            
            # Reset the connection state manually (simulating retry logic)
            redis_test_class._redis = None
            
            # Second attempt should succeed
            redis_conn = await redis_test_class._get_redis()
            assert redis_conn == mock_redis
            assert redis_test_class._redis == mock_redis
    
    def test_redis_url_format_validation(self):
        """Test Redis URL format validation."""
        # This tests the config handling, not Redis itself
        valid_formats = [
            "redis://localhost:6379",
            "redis://localhost:6379/0",
            "redis://localhost:6379/1",
            "redis://:password@localhost:6379",
            "redis://user:password@localhost:6379/0"
        ]
        
        for url in valid_formats:
            config = MagicMock()
            config.redis_url = url
            test_instance = self.TestClassWithRedisMixin(config)
            assert test_instance._config.redis_url == url