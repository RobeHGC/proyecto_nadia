"""Tests for enhanced rate limiting middleware."""
import pytest
import asyncio
import time
import json
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from fastapi.responses import JSONResponse

from api.middleware.enhanced_rate_limiting import (
    EnhancedRateLimiter, 
    EnhancedRateLimitMiddleware, 
    RateLimitConfig
)
from auth.rbac_manager import UserRole


@pytest.fixture
def mock_redis():
    """Mock Redis connection for testing."""
    mock_redis = AsyncMock()
    
    # Mock Redis operations
    mock_redis.get.return_value = None
    mock_redis.incr.return_value = 1
    mock_redis.expire.return_value = True
    mock_redis.setex.return_value = True
    mock_redis.delete.return_value = True
    mock_redis.pipeline.return_value = mock_redis
    mock_redis.execute.return_value = [1, True]
    mock_redis.zadd.return_value = True
    mock_redis.zrangebyscore.return_value = []
    mock_redis.zremrangebyscore.return_value = True
    mock_redis.lpush.return_value = True
    mock_redis.ltrim.return_value = True
    
    return mock_redis


@pytest.fixture
def rate_limiter(mock_redis):
    """Create EnhancedRateLimiter instance with mocked Redis."""
    limiter = EnhancedRateLimiter()
    
    # Mock the Redis connection
    async def mock_get_redis():
        return mock_redis
    
    limiter._get_redis = mock_get_redis
    return limiter


@pytest.fixture
def mock_request():
    """Create mock request object."""
    request = MagicMock()
    request.client.host = "127.0.0.1"
    request.headers = {"User-Agent": "Test Client"}
    request.url.path = "/test"
    return request


class TestRateLimitConfig:
    """Test rate limit configuration."""
    
    def test_config_creation(self):
        """Test creating rate limit configuration."""
        config = RateLimitConfig(
            requests_per_minute=60,
            burst_allowance=10,
            progressive_backoff=True,
            violation_penalty_minutes=15,
            max_penalty_minutes=240
        )
        
        assert config.requests_per_minute == 60
        assert config.burst_allowance == 10
        assert config.progressive_backoff is True
        assert config.violation_penalty_minutes == 15
        assert config.max_penalty_minutes == 240
        assert config.monitoring_enabled is True  # Default value


class TestEnhancedRateLimiter:
    """Test enhanced rate limiter functionality."""
    
    def test_client_identifier_with_user(self, rate_limiter, mock_request):
        """Test client identifier generation with user ID."""
        client_id = rate_limiter._get_client_identifier(mock_request, "user123")
        assert client_id == "rate_limit:user:user123"
    
    def test_client_identifier_without_user(self, rate_limiter, mock_request):
        """Test client identifier generation without user ID."""
        client_id = rate_limiter._get_client_identifier(mock_request)
        assert client_id == "rate_limit:ip:127.0.0.1"
    
    def test_client_identifier_with_forwarded_ip(self, rate_limiter, mock_request):
        """Test client identifier with X-Forwarded-For header."""
        mock_request.headers = {"X-Forwarded-For": "192.168.1.1, 10.0.0.1"}
        client_id = rate_limiter._get_client_identifier(mock_request)
        assert client_id == "rate_limit:ip:192.168.1.1"
    
    def test_rate_limit_config_for_admin(self, rate_limiter):
        """Test rate limit configuration for admin role."""
        config = rate_limiter._get_rate_limit_config(UserRole.ADMIN, "/test")
        assert config.requests_per_minute == 120
        assert config.burst_allowance == 20
        assert config.violation_penalty_minutes == 5
    
    def test_rate_limit_config_for_viewer(self, rate_limiter):
        """Test rate limit configuration for viewer role."""
        config = rate_limiter._get_rate_limit_config(UserRole.VIEWER, "/test")
        assert config.requests_per_minute == 30
        assert config.burst_allowance == 10
        assert config.violation_penalty_minutes == 15
    
    def test_rate_limit_config_unauthenticated(self, rate_limiter):
        """Test rate limit configuration for unauthenticated users."""
        config = rate_limiter._get_rate_limit_config(None, "/test")
        assert config.requests_per_minute == 20
        assert config.burst_allowance == 5
        assert config.violation_penalty_minutes == 30
    
    def test_endpoint_modifier_exact_match(self, rate_limiter):
        """Test endpoint modifier for exact match."""
        modifier = rate_limiter._get_endpoint_modifier("/auth/login")
        assert modifier == 0.1
    
    def test_endpoint_modifier_wildcard_match(self, rate_limiter):
        """Test endpoint modifier for wildcard match."""
        modifier = rate_limiter._get_endpoint_modifier("/api/analytics/data")
        assert modifier == 1.5
    
    def test_endpoint_modifier_no_match(self, rate_limiter):
        """Test endpoint modifier when no pattern matches."""
        modifier = rate_limiter._get_endpoint_modifier("/unknown/endpoint")
        assert modifier == 1.0
    
    def test_rate_limit_config_with_modifier(self, rate_limiter):
        """Test rate limit configuration with endpoint modifier."""
        # Auth endpoint has 0.1 modifier
        config = rate_limiter._get_rate_limit_config(UserRole.ADMIN, "/auth/login")
        assert config.requests_per_minute == 12  # 120 * 0.1
        assert config.burst_allowance == 2      # 20 * 0.1
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed(self, rate_limiter, mock_request, mock_redis):
        """Test rate limit check when request is allowed."""
        # Mock Redis to return low usage
        mock_redis.execute.return_value = [5, True]  # 5 requests in current window
        
        allowed, info = await rate_limiter.check_rate_limit(
            mock_request, "/test", "user123", UserRole.ADMIN
        )
        
        assert allowed is True
        assert info['requests_made'] == 5
        assert info['requests_limit'] == 140  # 120 + 20 burst
        assert info['remaining'] == 135
        assert info['user_role'] == 'admin'
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_exceeded(self, rate_limiter, mock_request, mock_redis):
        """Test rate limit check when limit is exceeded."""
        # Mock Redis to return high usage
        mock_redis.execute.return_value = [150, True]  # 150 requests, exceeds limit
        
        allowed, info = await rate_limiter.check_rate_limit(
            mock_request, "/test", "user123", UserRole.ADMIN
        )
        
        assert allowed is False
        assert info['error'] == 'Rate limit exceeded'
        assert 'retry_after' in info
        assert 'penalty_minutes' in info
    
    @pytest.mark.asyncio
    async def test_check_rate_limit_blocked_client(self, rate_limiter, mock_request, mock_redis):
        """Test rate limit check for blocked client."""
        # Mock Redis to return block timestamp
        future_time = int(time.time()) + 1800  # 30 minutes from now
        mock_redis.get.return_value = str(future_time).encode()
        
        allowed, info = await rate_limiter.check_rate_limit(
            mock_request, "/test", "user123", UserRole.ADMIN
        )
        
        assert allowed is False
        assert info['error'] == 'Rate limit exceeded'
        assert info['retry_after'] <= 1800
        assert 'blocked_until' in info
    
    @pytest.mark.asyncio
    async def test_progressive_backoff(self, rate_limiter, mock_request, mock_redis):
        """Test progressive backoff calculation."""
        # Mock Redis to return violations
        mock_redis.zrangebyscore.return_value = [b'violation1', b'violation2']  # 2 violations
        mock_redis.execute.return_value = [150, True]  # Exceed limit
        
        allowed, info = await rate_limiter.check_rate_limit(
            mock_request, "/test", "user123", UserRole.ADMIN
        )
        
        assert allowed is False
        # Penalty should be base * (2 ^ violations) = 5 * (2 ^ 2) = 20 minutes
        assert info['penalty_minutes'] == 20


class TestEnhancedRateLimitMiddleware:
    """Test enhanced rate limit middleware."""
    
    @pytest.fixture
    def app_with_middleware(self, mock_redis):
        """Create FastAPI app with rate limiting middleware."""
        app = FastAPI()
        
        # Add test endpoint
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        # Add the middleware
        middleware = EnhancedRateLimitMiddleware(app)
        
        # Mock Redis connection
        async def mock_get_redis():
            return mock_redis
        
        middleware.rate_limiter._get_redis = mock_get_redis
        
        return app, middleware
    
    def test_should_apply_rate_limiting_normal_endpoint(self):
        """Test that rate limiting applies to normal endpoints."""
        middleware = EnhancedRateLimitMiddleware(MagicMock())
        assert middleware._should_apply_rate_limiting("/api/test") is True
    
    def test_should_apply_rate_limiting_excluded_endpoint(self):
        """Test that rate limiting doesn't apply to excluded endpoints."""
        middleware = EnhancedRateLimitMiddleware(MagicMock())
        assert middleware._should_apply_rate_limiting("/docs") is False
        assert middleware._should_apply_rate_limiting("/openapi.json") is False
        assert middleware._should_apply_rate_limiting("/static/style.css") is False
    
    @pytest.mark.asyncio
    async def test_get_user_info_no_auth(self):
        """Test getting user info when no authentication header."""
        middleware = EnhancedRateLimitMiddleware(MagicMock())
        request = MagicMock()
        request.headers = {}
        
        user_id, user_role = await middleware._get_user_info(request)
        assert user_id is None
        assert user_role is None
    
    @pytest.mark.asyncio
    async def test_get_user_info_with_auth(self):
        """Test getting user info with authentication header."""
        middleware = EnhancedRateLimitMiddleware(MagicMock())
        request = MagicMock()
        request.headers = {"Authorization": "Bearer token123"}
        
        user_id, user_role = await middleware._get_user_info(request)
        # Note: This is a placeholder implementation
        assert user_id == "user_from_token"
        assert user_role == UserRole.VIEWER


class TestRateLimitingIntegration:
    """Integration tests for rate limiting system."""
    
    @pytest.mark.asyncio
    async def test_rate_limiting_integration(self, mock_redis):
        """Test full rate limiting integration."""
        # Create a simple FastAPI app
        app = FastAPI()
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        # Add middleware
        limiter = EnhancedRateLimiter()
        
        # Mock Redis connection
        async def mock_get_redis():
            return mock_redis
        
        limiter._get_redis = mock_get_redis
        
        # Create mock request
        request = MagicMock()
        request.client.host = "127.0.0.1"
        request.headers = {"User-Agent": "Test Client"}
        request.url.path = "/test"
        
        # Test allowed request
        mock_redis.execute.return_value = [5, True]  # Low usage
        allowed, info = await limiter.check_rate_limit(request, "/test")
        
        assert allowed is True
        assert info['requests_made'] == 5
    
    @pytest.mark.asyncio
    async def test_concurrent_rate_limiting(self, mock_redis):
        """Test rate limiting under concurrent load."""
        limiter = EnhancedRateLimiter()
        
        # Mock Redis connection
        async def mock_get_redis():
            return mock_redis
        
        limiter._get_redis = mock_get_redis
        
        # Simulate concurrent requests
        requests = []
        for i in range(10):
            request = MagicMock()
            request.client.host = f"192.168.1.{i}"
            request.headers = {"User-Agent": "Test Client"}
            request.url.path = "/test"
            requests.append(request)
        
        # Mock Redis to allow all requests
        mock_redis.execute.return_value = [1, True]
        
        # Execute concurrent rate limit checks
        tasks = [
            limiter.check_rate_limit(req, "/test", f"user{i}", UserRole.VIEWER)
            for i, req in enumerate(requests)
        ]
        
        results = await asyncio.gather(*tasks)
        
        # All should be allowed with low usage
        for allowed, info in results:
            assert allowed is True


class TestRateLimitingPerformance:
    """Performance tests for rate limiting."""
    
    @pytest.mark.asyncio
    async def test_rate_limiting_performance(self, mock_redis):
        """Test rate limiting performance under load."""
        limiter = EnhancedRateLimiter()
        
        # Mock Redis connection
        async def mock_get_redis():
            return mock_redis
        
        limiter._get_redis = mock_get_redis
        
        # Mock Redis to be fast
        mock_redis.execute.return_value = [1, True]
        
        # Create test request
        request = MagicMock()
        request.client.host = "127.0.0.1"
        request.headers = {"User-Agent": "Test Client"}
        request.url.path = "/test"
        
        # Measure performance
        start_time = time.time()
        
        # Execute many rate limit checks
        tasks = [
            limiter.check_rate_limit(request, "/test", "user123", UserRole.ADMIN)
            for _ in range(100)
        ]
        
        results = await asyncio.gather(*tasks)
        
        end_time = time.time()
        duration = end_time - start_time
        
        # Should complete quickly (less than 1 second for 100 checks)
        assert duration < 1.0
        
        # All should be successful
        for allowed, info in results:
            assert allowed is True
    
    @pytest.mark.asyncio
    async def test_redis_error_handling(self, mock_redis):
        """Test error handling when Redis is unavailable."""
        limiter = EnhancedRateLimiter()
        
        # Mock Redis to raise exceptions
        async def failing_get_redis():
            raise ConnectionError("Redis unavailable")
        
        limiter._get_redis = failing_get_redis
        
        request = MagicMock()
        request.client.host = "127.0.0.1"
        request.headers = {"User-Agent": "Test Client"}
        request.url.path = "/test"
        
        # Should handle Redis errors gracefully
        with pytest.raises(ConnectionError):
            await limiter.check_rate_limit(request, "/test", "user123", UserRole.ADMIN)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])