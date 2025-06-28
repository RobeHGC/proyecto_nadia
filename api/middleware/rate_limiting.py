"""Rate limiting middleware for authentication endpoints."""
import os
import time
from typing import Dict, Optional
from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as redis

from utils.logging_config import get_logger

logger = get_logger(__name__)


class AuthRateLimiter:
    """Rate limiter specifically for authentication endpoints."""
    
    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.getenv('REDIS_URL', 'redis://localhost:6379')
        self._redis = None
        
        # Rate limiting configuration
        self.limits = {
            '/auth/login': {
                'requests': 5,
                'window': 300,  # 5 requests per 5 minutes
                'block_duration': 900  # 15 minute block on violation
            },
            '/auth/refresh': {
                'requests': 10,
                'window': 300,  # 10 requests per 5 minutes
                'block_duration': 600  # 10 minute block on violation
            },
            '/auth/callback': {
                'requests': 20,
                'window': 300,  # 20 requests per 5 minutes (OAuth flow)
                'block_duration': 300  # 5 minute block on violation
            }
        }
    
    async def _get_redis(self) -> redis.Redis:
        """Get Redis connection."""
        if not self._redis:
            self._redis = redis.from_url(self.redis_url)
        return self._redis
    
    def _get_client_identifier(self, request: Request) -> str:
        """Get client identifier for rate limiting."""
        # Try to get real IP from headers (if behind proxy)
        real_ip = request.headers.get('X-Forwarded-For')
        if real_ip:
            # Take first IP if comma-separated
            real_ip = real_ip.split(',')[0].strip()
        else:
            real_ip = request.client.host if request.client else 'unknown'
        
        return f"auth_rate_limit:{real_ip}"
    
    async def check_rate_limit(self, request: Request, endpoint: str) -> bool:
        """Check if request is within rate limits."""
        if endpoint not in self.limits:
            return True  # No limit configured
        
        limit_config = self.limits[endpoint]
        client_id = self._get_client_identifier(request)
        
        r = await self._get_redis()
        current_time = int(time.time())
        
        # Check if client is currently blocked
        block_key = f"{client_id}:blocked"
        is_blocked = await r.get(block_key)
        if is_blocked:
            logger.warning(f"Blocked client {client_id} attempted {endpoint}")
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "retry_after": int(is_blocked.decode()) - current_time,
                    "message": "Too many authentication attempts. Please try again later."
                }
            )
        
        # Check current request count
        window_key = f"{client_id}:{endpoint}:{current_time // limit_config['window']}"
        
        # Increment counter
        pipe = r.pipeline()
        pipe.incr(window_key)
        pipe.expire(window_key, limit_config['window'])
        results = await pipe.execute()
        
        current_count = results[0]
        
        if current_count > limit_config['requests']:
            # Block the client
            block_until = current_time + limit_config['block_duration']
            await r.setex(block_key, limit_config['block_duration'], block_until)
            
            # Log security event
            logger.warning(
                f"Rate limit exceeded for {client_id} on {endpoint}. "
                f"Count: {current_count}, blocked until: {block_until}"
            )
            
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Rate limit exceeded",
                    "retry_after": limit_config['block_duration'],
                    "message": "Too many authentication attempts. Account temporarily blocked."
                }
            )
        
        # Log if approaching limit
        if current_count > limit_config['requests'] * 0.8:
            logger.info(f"Client {client_id} approaching rate limit: {current_count}/{limit_config['requests']}")
        
        return True
    
    async def get_rate_limit_status(self, request: Request, endpoint: str) -> Dict:
        """Get current rate limit status for client."""
        if endpoint not in self.limits:
            return {"limited": False}
        
        limit_config = self.limits[endpoint]
        client_id = self._get_client_identifier(request)
        
        r = await self._get_redis()
        current_time = int(time.time())
        
        # Check if blocked
        block_key = f"{client_id}:blocked"
        block_until = await r.get(block_key)
        if block_until:
            return {
                "limited": True,
                "blocked": True,
                "retry_after": int(block_until.decode()) - current_time
            }
        
        # Check current usage
        window_key = f"{client_id}:{endpoint}:{current_time // limit_config['window']}"
        current_count = await r.get(window_key)
        current_count = int(current_count) if current_count else 0
        
        return {
            "limited": True,
            "blocked": False,
            "requests_made": current_count,
            "requests_limit": limit_config['requests'],
            "window_seconds": limit_config['window'],
            "remaining": max(0, limit_config['requests'] - current_count)
        }


class AuthRateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to apply rate limiting to authentication endpoints."""
    
    def __init__(self, app, redis_url: Optional[str] = None):
        super().__init__(app)
        self.rate_limiter = AuthRateLimiter(redis_url)
        self.protected_endpoints = {
            '/auth/login',
            '/auth/refresh', 
            '/auth/callback'
        }
    
    async def dispatch(self, request: Request, call_next):
        """Apply rate limiting if endpoint is protected."""
        path = request.url.path
        
        # Check if this endpoint should be rate limited
        if path in self.protected_endpoints:
            try:
                await self.rate_limiter.check_rate_limit(request, path)
            except HTTPException as e:
                # Return rate limit error response
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=e.status_code,
                    content=e.detail
                )
        
        response = await call_next(request)
        
        # Add rate limit headers if applicable
        if path in self.protected_endpoints:
            try:
                status = await self.rate_limiter.get_rate_limit_status(request, path)
                if status.get("limited"):
                    response.headers["X-RateLimit-Limit"] = str(status.get("requests_limit", 0))
                    response.headers["X-RateLimit-Remaining"] = str(status.get("remaining", 0))
                    response.headers["X-RateLimit-Reset"] = str(status.get("window_seconds", 0))
                    
                    if status.get("blocked"):
                        response.headers["X-RateLimit-Retry-After"] = str(status.get("retry_after", 0))
            except Exception as e:
                logger.error(f"Error adding rate limit headers: {e}")
        
        return response