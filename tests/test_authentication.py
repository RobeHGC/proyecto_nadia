"""Test suite for Epic 53 Session 1 authentication system."""
import pytest
import asyncio
import os
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timezone, timedelta

# Test imports
from auth.oauth_provider import GoogleOAuthProvider, GitHubOAuthProvider, OAuthManager
from auth.token_manager import TokenManager
from auth.rbac_manager import RBACManager, UserRole, Permission, rbac_manager
from auth.session_manager import SessionManager
from auth.token_blacklist import TokenBlacklist
from api.middleware.rate_limiting import AuthRateLimiter


class TestOAuthProviders:
    """Test OAuth provider implementations."""
    
    def test_google_oauth_init(self):
        """Test Google OAuth provider initialization."""
        with patch.dict(os.environ, {
            'GOOGLE_OAUTH_CLIENT_ID': 'test_client_id',
            'GOOGLE_OAUTH_CLIENT_SECRET': 'test_client_secret'
        }):
            provider = GoogleOAuthProvider()
            assert provider.client_id == 'test_client_id'
            assert provider.client_secret == 'test_client_secret'
            assert 'googleapis.com' in provider.token_url
    
    def test_github_oauth_init(self):
        """Test GitHub OAuth provider initialization."""
        with patch.dict(os.environ, {
            'GITHUB_OAUTH_CLIENT_ID': 'test_client_id',
            'GITHUB_OAUTH_CLIENT_SECRET': 'test_client_secret'
        }):
            provider = GitHubOAuthProvider()
            assert provider.client_id == 'test_client_id'
            assert provider.client_secret == 'test_client_secret'
            assert 'github.com' in provider.token_url
    
    def test_oauth_manager_get_provider(self):
        """Test OAuth manager provider retrieval."""
        manager = OAuthManager()
        
        with patch.dict(os.environ, {
            'GOOGLE_OAUTH_CLIENT_ID': 'test_id',
            'GOOGLE_OAUTH_CLIENT_SECRET': 'test_secret'
        }):
            google_provider = manager.get_provider('google')
            assert isinstance(google_provider, GoogleOAuthProvider)
        
        with pytest.raises(ValueError):
            manager.get_provider('invalid_provider')
    
    def test_state_token_generation(self):
        """Test OAuth state token generation."""
        manager = OAuthManager()
        state1 = manager.generate_state_token()
        state2 = manager.generate_state_token()
        
        assert len(state1) > 20  # Secure length
        assert state1 != state2  # Unique tokens
        assert state1.replace('-', '').replace('_', '').isalnum()  # URL safe


class TestTokenManager:
    """Test JWT token management."""
    
    def setup_method(self):
        """Setup test environment."""
        self.token_manager = TokenManager()
        self.test_user_id = "test_user_123"
        self.test_email = "test@example.com"
        self.test_role = "reviewer"
    
    def test_create_access_token(self):
        """Test access token creation."""
        token = self.token_manager.create_access_token(
            user_id=self.test_user_id,
            email=self.test_email,
            role=self.test_role
        )
        
        assert isinstance(token, str)
        assert len(token.split('.')) == 3  # JWT format
        
        # Decode and verify
        payload = self.token_manager.decode_token(token)
        assert payload['sub'] == self.test_user_id
        assert payload['email'] == self.test_email
        assert payload['role'] == self.test_role
        assert payload['type'] == 'access'
    
    def test_create_refresh_token(self):
        """Test refresh token creation."""
        token = self.token_manager.create_refresh_token(self.test_user_id)
        
        payload = self.token_manager.decode_token(token)
        assert payload['sub'] == self.test_user_id
        assert payload['type'] == 'refresh'
        
        # Refresh tokens should have longer expiration
        exp_time = datetime.fromtimestamp(payload['exp'], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        assert (exp_time - now).days > 1
    
    def test_token_verification(self):
        """Test token verification methods."""
        access_token = self.token_manager.create_access_token(
            user_id=self.test_user_id,
            email=self.test_email,
            role=self.test_role
        )
        refresh_token = self.token_manager.create_refresh_token(self.test_user_id)
        
        # Test access token verification
        access_payload = self.token_manager.verify_access_token(access_token)
        assert access_payload['type'] == 'access'
        
        # Test refresh token verification
        user_id = self.token_manager.verify_refresh_token(refresh_token)
        assert user_id == self.test_user_id
        
        # Test wrong token type
        with pytest.raises(ValueError):
            self.token_manager.verify_access_token(refresh_token)
    
    def test_token_hashing(self):
        """Test token hashing for storage."""
        token = self.token_manager.create_access_token(
            user_id=self.test_user_id,
            email=self.test_email,
            role=self.test_role
        )
        
        hash1 = self.token_manager.hash_token(token)
        hash2 = self.token_manager.hash_token(token)
        
        assert hash1 == hash2  # Consistent hashing
        assert len(hash1) == 64  # SHA256 hex length
        assert hash1 != token  # Different from original


class TestRBACManager:
    """Test Role-Based Access Control."""
    
    def setup_method(self):
        """Setup test environment."""
        self.rbac = RBACManager()
    
    def test_role_permissions(self):
        """Test role permission assignments."""
        # Admin should have all permissions
        assert self.rbac.has_permission('admin', Permission.MESSAGE_APPROVE)
        assert self.rbac.has_permission('admin', Permission.USER_MANAGE_ROLES)
        assert self.rbac.has_permission('admin', Permission.SYSTEM_CONFIG)
        
        # Reviewer should have message permissions but not user management
        assert self.rbac.has_permission('reviewer', Permission.MESSAGE_APPROVE)
        assert not self.rbac.has_permission('reviewer', Permission.USER_MANAGE_ROLES)
        
        # Viewer should only have read permissions
        assert self.rbac.has_permission('viewer', Permission.MESSAGE_READ)
        assert not self.rbac.has_permission('viewer', Permission.MESSAGE_APPROVE)
    
    def test_endpoint_permissions(self):
        """Test endpoint permission checking."""
        # Admin can access all endpoints
        assert self.rbac.check_endpoint_permission('admin', 'POST', '/messages/*/approve')
        assert self.rbac.check_endpoint_permission('admin', 'PUT', '/users/*')
        
        # Reviewer can approve messages but not manage users
        assert self.rbac.check_endpoint_permission('reviewer', 'POST', '/messages/*/approve')
        assert not self.rbac.check_endpoint_permission('reviewer', 'PUT', '/users/*')
        
        # Viewer cannot approve or manage
        assert not self.rbac.check_endpoint_permission('viewer', 'POST', '/messages/*/approve')
        assert self.rbac.check_endpoint_permission('viewer', 'GET', '/messages')
    
    def test_invalid_role(self):
        """Test handling of invalid roles."""
        with pytest.raises(ValueError):
            self.rbac.has_permission('invalid_role', Permission.MESSAGE_READ)


class TestRateLimiting:
    """Test authentication rate limiting."""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis for testing."""
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None  # No existing blocks
        mock_redis.incr.return_value = 1    # First request
        mock_redis.pipeline.return_value = mock_redis
        mock_redis.execute.return_value = [1, True]  # incr result, expire result
        return mock_redis
    
    @pytest.mark.asyncio
    async def test_rate_limit_creation(self):
        """Test rate limiter initialization."""
        limiter = AuthRateLimiter()
        assert '/auth/login' in limiter.limits
        assert '/auth/refresh' in limiter.limits
        assert limiter.limits['/auth/login']['requests'] == 5
    
    @pytest.mark.asyncio
    async def test_rate_limit_checking(self, mock_redis):
        """Test rate limit checking logic."""
        limiter = AuthRateLimiter()
        limiter._redis = mock_redis
        
        # Mock request
        mock_request = Mock()
        mock_request.client.host = '127.0.0.1'
        mock_request.headers = {}
        
        # Should pass on first request
        result = await limiter.check_rate_limit(mock_request, '/auth/login')
        assert result is True
        
        # Mock rate limit exceeded
        mock_redis.execute.return_value = [6, True]  # Over limit
        
        with pytest.raises(Exception):  # Should raise HTTPException
            await limiter.check_rate_limit(mock_request, '/auth/login')


class TestTokenBlacklist:
    """Test token blacklisting functionality."""
    
    @pytest.fixture
    def mock_redis(self):
        """Mock Redis for testing."""
        mock_redis = AsyncMock()
        mock_redis.hset.return_value = True
        mock_redis.expire.return_value = True
        mock_redis.sadd.return_value = True
        mock_redis.exists.return_value = False
        mock_redis.pipeline.return_value = mock_redis
        mock_redis.execute.return_value = [True, True, True, True]
        return mock_redis
    
    @pytest.mark.asyncio
    async def test_token_blacklisting(self, mock_redis):
        """Test token blacklisting process."""
        blacklist = TokenBlacklist()
        blacklist._redis = mock_redis
        
        # Create a test token
        token_manager = TokenManager()
        token = token_manager.create_access_token(
            user_id="test_user",
            email="test@example.com", 
            role="reviewer"
        )
        
        # Blacklist the token
        result = await blacklist.blacklist_token(token, reason="test_revocation")
        assert result is True
        
        # Verify Redis calls
        assert mock_redis.hset.called
        assert mock_redis.expire.called
    
    @pytest.mark.asyncio
    async def test_blacklist_checking(self, mock_redis):
        """Test checking if token is blacklisted."""
        blacklist = TokenBlacklist()
        blacklist._redis = mock_redis
        
        token_manager = TokenManager()
        token = token_manager.create_access_token(
            user_id="test_user",
            email="test@example.com",
            role="reviewer"
        )
        
        # Token not blacklisted
        mock_redis.exists.return_value = False
        is_blacklisted = await blacklist.is_token_blacklisted(token)
        assert is_blacklisted is False
        
        # Token is blacklisted
        mock_redis.exists.return_value = True
        mock_redis.hgetall.return_value = {b'reason': b'test_revocation'}
        is_blacklisted = await blacklist.is_token_blacklisted(token)
        assert is_blacklisted is True


class TestSessionManager:
    """Test session management."""
    
    @pytest.fixture
    def mock_db_pool(self):
        """Mock database pool."""
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = {
            'id': 'session_123',
            'created_at': datetime.now(timezone.utc)
        }
        mock_conn.execute.return_value = None
        
        mock_pool = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
        
        return mock_pool
    
    @pytest.mark.asyncio
    async def test_session_creation(self, mock_db_pool):
        """Test session creation process."""
        session_manager = SessionManager()
        session_manager._db = Mock()
        session_manager._db._pool = mock_db_pool
        
        session_data = await session_manager.create_session(
            user_id="test_user_123",
            user_email="test@example.com",
            user_role="reviewer",
            ip_address="127.0.0.1"
        )
        
        assert 'tokens' in session_data
        assert 'access_token' in session_data['tokens']
        assert 'refresh_token' in session_data['tokens']
        assert session_data['session_id'] == 'session_123'


# Integration tests
class TestAuthenticationIntegration:
    """Integration tests for complete authentication flow."""
    
    @pytest.mark.asyncio
    async def test_oauth_to_session_flow(self):
        """Test complete OAuth to session creation flow."""
        # This would test the full flow in integration environment
        # Skipped for unit testing
        pytest.skip("Integration test - requires full environment")
    
    @pytest.mark.asyncio 
    async def test_rbac_with_token_validation(self):
        """Test RBAC working with token validation."""
        # Create token
        token_manager = TokenManager()
        token = token_manager.create_access_token(
            user_id="test_user",
            email="test@example.com",
            role="reviewer"
        )
        
        # Verify token payload
        payload = token_manager.verify_access_token(token)
        
        # Check RBAC permissions
        rbac = RBACManager()
        assert rbac.has_permission(payload['role'], Permission.MESSAGE_APPROVE)
        assert not rbac.has_permission(payload['role'], Permission.USER_MANAGE_ROLES)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])