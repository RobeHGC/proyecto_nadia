"""Authentication middleware for API endpoints."""
import os
from typing import Optional, Tuple
from fastapi import HTTPException, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware

from auth.session_manager import SessionManager
from auth.token_manager import TokenManager
from utils.logging_config import get_logger

logger = get_logger(__name__)

# Security scheme
security = HTTPBearer()

# Initialize managers
session_manager = SessionManager()
token_manager = TokenManager()

# Legacy API key for backward compatibility
LEGACY_API_KEY = os.getenv('DASHBOARD_API_KEY')


class AuthenticationMiddleware(BaseHTTPMiddleware):
    """Middleware for handling authentication across all requests."""
    
    def __init__(self, app, allow_legacy_api_key: bool = True):
        super().__init__(app)
        self.allow_legacy_api_key = allow_legacy_api_key
    
    async def dispatch(self, request: Request, call_next):
        """Process authentication for each request."""
        # Skip authentication for certain paths
        if self._is_public_path(request.url.path):
            return await call_next(request)
        
        # Try to authenticate the request
        auth_result = await self._authenticate_request(request)
        
        if auth_result:
            # Store auth info in request state
            request.state.user_id = auth_result.get('user_id')
            request.state.user_email = auth_result.get('email')
            request.state.user_role = auth_result.get('role')
            request.state.auth_type = auth_result.get('auth_type')
            request.state.session_id = auth_result.get('session_id')
        
        response = await call_next(request)
        return response
    
    def _is_public_path(self, path: str) -> bool:
        """Check if path should skip authentication."""
        public_paths = [
            '/health',
            '/docs',
            '/openapi.json',
            '/auth/login',
            '/auth/callback',
            '/auth/refresh'
        ]
        
        return any(path.startswith(p) for p in public_paths)
    
    async def _authenticate_request(self, request: Request) -> Optional[dict]:
        """Authenticate request using JWT or legacy API key."""
        auth_header = request.headers.get('Authorization')
        
        if not auth_header:
            return None
        
        # Try JWT authentication first
        if auth_header.startswith('Bearer '):
            token = auth_header[7:]
            
            # Check if it's a JWT token (has dots)
            if '.' in token:
                user_info = await session_manager.validate_session(token)
                if user_info:
                    user_info['auth_type'] = 'jwt'
                    return user_info
            
            # Try legacy API key if allowed
            elif self.allow_legacy_api_key and token == LEGACY_API_KEY:
                logger.warning("Legacy API key used - consider migrating to OAuth")
                return {
                    'user_id': 'legacy-api-user',
                    'email': 'api@nadia-hitl.com',
                    'role': 'admin',  # Legacy API key gets admin access
                    'auth_type': 'api_key'
                }
        
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    request: Request = None
) -> dict:
    """Dependency to get current authenticated user."""
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    
    # Check if it's a JWT token
    if '.' in token:
        user_info = await session_manager.validate_session(token)
        if not user_info:
            raise HTTPException(
                status_code=401,
                detail="Invalid or expired token",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user_info
    
    # Check legacy API key
    elif token == LEGACY_API_KEY:
        logger.warning("Legacy API key used in get_current_user")
        return {
            'user_id': 'legacy-api-user',
            'email': 'api@nadia-hitl.com',
            'role': 'admin',
            'name': 'Legacy API User'
        }
    
    # Invalid credentials
    raise HTTPException(
        status_code=401,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def require_user(
    credentials: HTTPAuthorizationCredentials = Security(security)
) -> dict:
    """Require authenticated user (no legacy API key)."""
    if not credentials:
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    token = credentials.credentials
    
    # Only accept JWT tokens
    if not '.' in token:
        raise HTTPException(
            status_code=401,
            detail="Legacy API key not accepted here. Please use OAuth login.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_info = await session_manager.validate_session(token)
    if not user_info:
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user_info


async def get_optional_user(
    authorization: Optional[str] = None
) -> Optional[dict]:
    """Get user if authenticated, otherwise return None."""
    if not authorization or not authorization.startswith('Bearer '):
        return None
    
    token = authorization[7:]
    
    if '.' in token:
        return await session_manager.validate_session(token, update_activity=False)
    elif token == LEGACY_API_KEY:
        return {
            'user_id': 'legacy-api-user',
            'email': 'api@nadia-hitl.com',
            'role': 'admin',
            'name': 'Legacy API User'
        }
    
    return None