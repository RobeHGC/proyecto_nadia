"""Enhanced rate limiting middleware with role-based limits, progressive backoff, and monitoring."""
import os
import time
import json
import asyncio
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from fastapi import HTTPException, Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import redis.asyncio as redis

try:
    from auth.rbac_manager import UserRole, rbac_manager
except ImportError:
    # Fallback enum for testing/development
    from enum import Enum
    class UserRole(Enum):
        ADMIN = "admin"
        REVIEWER = "reviewer"
        VIEWER = "viewer"
    rbac_manager = None
try:
    from api.middleware.auth import get_current_user
except ImportError:
    get_current_user = None

try:
    from utils.logging_config import get_logger
except ImportError:
    import logging
    def get_logger(name):
        return logging.getLogger(name)

try:
    from utils.redis_mixin import RedisConnectionMixin
except ImportError:
    # Fallback Redis mixin
    class RedisConnectionMixin:
        def __init__(self, redis_url=None):
            self.redis_url = redis_url or 'redis://localhost:6379'
            self._redis = None
        
        async def _get_redis(self):
            if not self._redis:
                self._redis = redis.from_url(self.redis_url)
            return self._redis

logger = get_logger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_minute: int
    burst_allowance: int = 0  # Extra requests allowed in burst
    progressive_backoff: bool = True
    violation_penalty_minutes: int = 15
    max_penalty_minutes: int = 240  # 4 hours max
    monitoring_enabled: bool = True


@dataclass  
class RateLimitViolation:
    """Rate limit violation record."""
    user_id: Optional[str]
    ip_address: str
    endpoint: str
    timestamp: datetime
    violation_count: int
    penalty_minutes: int
    user_agent: Optional[str] = None


class EnhancedRateLimiter(RedisConnectionMixin):
    """Enhanced rate limiter with role-based limits and progressive backoff."""
    
    def __init__(self, redis_url: Optional[str] = None, config_file: Optional[str] = None):
        # Initialize the mixin properly
        self._redis = None
        self.redis_url = redis_url or 'redis://localhost:6379'
        self.config_file = config_file or 'config/rate_limits.json'
        self._config_last_modified = 0
        
        # Initialize configurations
        self._load_configuration()
    
    def _load_configuration(self):
        """Load configuration from file with hot-reload support."""
        try:
            import os
            if os.path.exists(self.config_file):
                stat = os.stat(self.config_file)
                if stat.st_mtime > self._config_last_modified:
                    with open(self.config_file, 'r') as f:
                        config_data = json.load(f)
                    
                    # Load role limits from config
                    role_config = config_data.get('role_limits', {})
                    self.role_limits = {}
                    
                    for role_name, limits in role_config.items():
                        try:
                            if role_name == 'unauthenticated':
                                continue  # Handle separately
                            role = UserRole(role_name)
                            self.role_limits[role] = RateLimitConfig(**limits)
                        except (ValueError, TypeError) as e:
                            logger.warning(f"Invalid role config for {role_name}: {e}")
                    
                    # Load endpoint modifiers
                    self.endpoint_modifiers = config_data.get('endpoint_modifiers', {})
                    
                    # Load default limit for unauthenticated
                    unauth_config = role_config.get('unauthenticated', {})
                    self.default_limit = RateLimitConfig(**unauth_config) if unauth_config else self._get_default_config()
                    
                    self._config_last_modified = stat.st_mtime
                    logger.info(f"Rate limit configuration loaded from {self.config_file}")
                    return
            
        except Exception as e:
            logger.warning(f"Failed to load config from {self.config_file}: {e}, using defaults")
        
        # Fallback to hardcoded configuration
        self._load_default_configuration()
    
    def _get_default_config(self) -> RateLimitConfig:
        """Get default configuration for unauthenticated users."""
        return RateLimitConfig(
            requests_per_minute=20,
            burst_allowance=5,
            violation_penalty_minutes=30,
            max_penalty_minutes=480
        )
    
    def _load_default_configuration(self):
        """Load hardcoded default configuration."""
        
        # Role-based rate limit configurations
        self.role_limits: Dict[UserRole, RateLimitConfig] = {
            UserRole.ADMIN: RateLimitConfig(
                requests_per_minute=120,  # High limit for admins
                burst_allowance=20,
                violation_penalty_minutes=5,  # Short penalty
                max_penalty_minutes=60
            ),
            UserRole.REVIEWER: RateLimitConfig(
                requests_per_minute=60,   # Medium limit for reviewers  
                burst_allowance=15,
                violation_penalty_minutes=10,
                max_penalty_minutes=120
            ),
            UserRole.VIEWER: RateLimitConfig(
                requests_per_minute=30,   # Lower limit for viewers
                burst_allowance=10,
                violation_penalty_minutes=15,
                max_penalty_minutes=240
            )
        }
        
        # Default limit for unauthenticated users
        self.default_limit = RateLimitConfig(
            requests_per_minute=20,    # Very restrictive for unauthenticated
            burst_allowance=5,
            violation_penalty_minutes=30,
            max_penalty_minutes=480   # 8 hours max
        )
        
        # Endpoint-specific modifiers
        self.endpoint_modifiers: Dict[str, float] = {
            # Authentication endpoints - more restrictive
            '/auth/login': 0.1,        # 10% of normal limit
            '/auth/refresh': 0.2,      # 20% of normal limit
            '/auth/callback': 0.3,     # 30% of normal limit
            
            # Review endpoints - higher limits
            '/reviews/pending': 2.0,    # 200% of normal limit
            '/reviews/*/approve': 0.5,  # 50% of normal limit
            '/reviews/*/reject': 0.5,   # 50% of normal limit
            
            # Analytics endpoints - moderate limits
            '/api/analytics/*': 1.5,    # 150% of normal limit
            '/api/dashboard/*': 1.5,    # 150% of normal limit
            
            # Health endpoints - very high limits
            '/health': 5.0,            # 500% of normal limit
            '/mcp/health': 3.0,        # 300% of normal limit
            
            # Admin endpoints - restricted
            '/api/models/reload': 0.1,  # 10% of normal limit
            '/quarantine/batch-process': 0.2,  # 20% of normal limit
        }
    
    async def _get_redis(self) -> redis.Redis:
        """Get Redis connection (override mixin method)."""
        if not self._redis:
            self._redis = redis.from_url(self.redis_url)
        return self._redis
    
    def _get_client_identifier(self, request: Request, user_id: Optional[str] = None) -> str:
        """Get unique client identifier for rate limiting."""
        # Use user ID if authenticated, otherwise IP
        if user_id:
            return f"rate_limit:user:{user_id}"
        
        # Get real IP from headers (if behind proxy)
        real_ip = request.headers.get('X-Forwarded-For')
        if real_ip:
            real_ip = real_ip.split(',')[0].strip()
        else:
            real_ip = request.client.host if request.client else 'unknown'
        
        return f"rate_limit:ip:{real_ip}"
    
    def _get_rate_limit_config(self, user_role: Optional[UserRole], endpoint: str) -> RateLimitConfig:
        """Get rate limit configuration for user role and endpoint."""
        # Get base config
        if user_role and user_role in self.role_limits:
            base_config = self.role_limits[user_role]
        else:
            base_config = self.default_limit
        
        # Apply endpoint modifier
        modifier = self._get_endpoint_modifier(endpoint)
        
        # Create modified config
        modified_config = RateLimitConfig(
            requests_per_minute=max(1, int(base_config.requests_per_minute * modifier)),
            burst_allowance=max(0, int(base_config.burst_allowance * modifier)),
            progressive_backoff=base_config.progressive_backoff,
            violation_penalty_minutes=base_config.violation_penalty_minutes,
            max_penalty_minutes=base_config.max_penalty_minutes,
            monitoring_enabled=base_config.monitoring_enabled
        )
        
        return modified_config
    
    def _get_endpoint_modifier(self, endpoint: str) -> float:
        """Get rate limit modifier for specific endpoint."""
        # Check for exact match first
        if endpoint in self.endpoint_modifiers:
            return self.endpoint_modifiers[endpoint]
        
        # Check for pattern matches (with wildcards)
        for pattern, modifier in self.endpoint_modifiers.items():
            if '*' in pattern:
                # Simple wildcard matching
                pattern_prefix = pattern.split('*')[0]
                if endpoint.startswith(pattern_prefix):
                    return modifier
        
        return 1.0  # Default modifier
    
    async def _get_violation_count(self, client_id: str) -> int:
        """Get number of recent violations for progressive backoff."""
        r = await self._get_redis()
        violation_key = f"{client_id}:violations"
        
        # Get violations from last 24 hours
        cutoff_time = time.time() - 86400  # 24 hours ago
        violations = await r.zrangebyscore(violation_key, cutoff_time, '+inf')
        
        return len(violations)
    
    async def _record_violation(self, client_id: str, endpoint: str, request: Request, penalty_minutes: int) -> None:
        """Record a rate limit violation for monitoring."""
        r = await self._get_redis()
        violation_key = f"{client_id}:violations"
        
        # Record violation with timestamp
        violation_time = time.time()
        violation_data = {
            'endpoint': endpoint,
            'timestamp': violation_time,
            'penalty_minutes': penalty_minutes,
            'user_agent': request.headers.get('User-Agent', 'Unknown'),
            'ip': request.client.host if request.client else 'Unknown'
        }
        
        # Add to sorted set with timestamp as score
        await r.zadd(violation_key, {json.dumps(violation_data): violation_time})
        
        # Keep only violations from last 7 days
        cutoff_time = violation_time - (7 * 86400)
        await r.zremrangebyscore(violation_key, '-inf', cutoff_time)
        
        # Set expiration on violation key
        await r.expire(violation_key, 7 * 86400)  # 7 days
        
        # Record in monitoring metrics
        await self._record_monitoring_metric(
            'rate_limit_violation',
            {
                'endpoint': endpoint,
                'penalty_minutes': penalty_minutes,
                'client_type': 'user' if ':user:' in client_id else 'ip'
            }
        )
    
    async def _record_monitoring_metric(self, metric_type: str, data: Dict) -> None:
        """Record metrics for monitoring dashboard."""
        r = await self._get_redis()
        metric_key = f"rate_limit_metrics:{metric_type}"
        
        metric_entry = {
            'timestamp': time.time(),
            'data': data
        }
        
        # Add to list (keep last 1000 entries)
        await r.lpush(metric_key, json.dumps(metric_entry))
        await r.ltrim(metric_key, 0, 999)
        await r.expire(metric_key, 86400)  # 24 hours
    
    async def check_rate_limit(
        self, 
        request: Request, 
        endpoint: str, 
        user_id: Optional[str] = None,
        user_role: Optional[UserRole] = None
    ) -> Tuple[bool, Dict]:
        """
        Check if request is within rate limits.
        
        Returns:
            (allowed: bool, info: Dict)
        """
        config = self._get_rate_limit_config(user_role, endpoint)
        client_id = self._get_client_identifier(request, user_id)
        
        r = await self._get_redis()
        current_time = int(time.time())
        
        # Check if client is currently blocked
        block_key = f"{client_id}:blocked"
        block_until = await r.get(block_key)
        if block_until:
            block_until_time = int(block_until.decode())
            if current_time < block_until_time:
                retry_after = block_until_time - current_time
                
                # Record monitoring metric
                await self._record_monitoring_metric(
                    'rate_limit_blocked_attempt',
                    {
                        'endpoint': endpoint,
                        'retry_after': retry_after,
                        'client_type': 'user' if ':user:' in client_id else 'ip'
                    }
                )
                
                return False, {
                    'error': 'Rate limit exceeded',
                    'retry_after': retry_after,
                    'message': 'Too many requests. Please try again later.',
                    'blocked_until': datetime.fromtimestamp(block_until_time).isoformat()
                }
            else:
                # Block expired, clean up
                await r.delete(block_key)
        
        # Check current request count in this minute
        minute_window = current_time // 60
        window_key = f"{client_id}:window:{minute_window}"
        
        # Get current count and increment
        pipe = r.pipeline()
        pipe.incr(window_key)
        pipe.expire(window_key, 120)  # Keep for 2 minutes
        results = await pipe.execute()
        
        current_count = results[0]
        effective_limit = config.requests_per_minute + config.burst_allowance
        
        if current_count > effective_limit:
            # Rate limit exceeded - calculate penalty
            if config.progressive_backoff:
                violation_count = await self._get_violation_count(client_id)
                penalty_minutes = min(
                    config.violation_penalty_minutes * (2 ** violation_count),
                    config.max_penalty_minutes
                )
            else:
                penalty_minutes = config.violation_penalty_minutes
            
            # Block the client
            block_until_time = current_time + (penalty_minutes * 60)
            await r.setex(block_key, penalty_minutes * 60, block_until_time)
            
            # Record violation
            await self._record_violation(client_id, endpoint, request, penalty_minutes)
            
            # Log security event
            logger.warning(
                f"Rate limit exceeded for {client_id} on {endpoint}. "
                f"Count: {current_count}/{effective_limit}, "
                f"penalty: {penalty_minutes} minutes"
            )
            
            return False, {
                'error': 'Rate limit exceeded',
                'retry_after': penalty_minutes * 60,
                'message': f'Rate limit exceeded. Blocked for {penalty_minutes} minutes.',
                'requests_made': current_count,
                'requests_limit': effective_limit,
                'penalty_minutes': penalty_minutes
            }
        
        # Success - return status info
        remaining = max(0, effective_limit - current_count)
        
        # Log warning if approaching limit
        if current_count > effective_limit * 0.8:
            logger.info(
                f"Client {client_id} approaching rate limit: "
                f"{current_count}/{effective_limit} on {endpoint}"
            )
        
        return True, {
            'requests_made': current_count,
            'requests_limit': effective_limit,
            'remaining': remaining,
            'window_reset_seconds': 60 - (current_time % 60),
            'user_role': user_role.value if user_role else 'unauthenticated'
        }
    
    async def get_rate_limit_stats(self, client_id: str) -> Dict:
        """Get comprehensive rate limit statistics for a client."""
        r = await self._get_redis()
        current_time = int(time.time())
        
        # Check if blocked
        block_key = f"{client_id}:blocked"
        block_until = await r.get(block_key)
        
        # Get recent violations
        violation_key = f"{client_id}:violations"
        recent_violations = await r.zrangebyscore(
            violation_key, 
            current_time - 86400,  # Last 24 hours
            '+inf'
        )
        
        # Get current window usage
        minute_window = current_time // 60
        window_key = f"{client_id}:window:{minute_window}"
        current_usage = await r.get(window_key)
        current_usage = int(current_usage) if current_usage else 0
        
        return {
            'blocked': bool(block_until),
            'block_until': int(block_until.decode()) if block_until else None,
            'recent_violations_24h': len(recent_violations),
            'current_minute_usage': current_usage,
            'violations_history': [
                json.loads(v.decode()) for v in recent_violations
            ]
        }


class EnhancedRateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware to apply enhanced rate limiting to all API endpoints."""
    
    def __init__(self, app, redis_url: Optional[str] = None):
        super().__init__(app)
        self.rate_limiter = EnhancedRateLimiter(redis_url)
        
        # Endpoints to exclude from rate limiting
        self.excluded_endpoints = {
            '/docs',
            '/openapi.json',
            '/redoc',
            '/favicon.ico'
        }
    
    def _should_apply_rate_limiting(self, path: str) -> bool:
        """Check if rate limiting should be applied to this path."""
        # Skip excluded endpoints
        if path in self.excluded_endpoints:
            return False
        
        # Skip static assets
        if path.startswith('/static/') or path.endswith(('.css', '.js', '.png', '.jpg')):
            return False
        
        return True
    
    async def _get_user_info(self, request: Request) -> Tuple[Optional[str], Optional[UserRole]]:
        """Get user ID and role from request."""
        try:
            # Try to get user from Authorization header
            auth_header = request.headers.get('Authorization')
            if not auth_header:
                return None, None
            
            # This is a simplified version - in real implementation,
            # you would validate the token and extract user info
            # For now, we'll use a placeholder
            user_id = "user_from_token"  # Extract from JWT token
            user_role = UserRole.VIEWER   # Extract from JWT token or database
            
            return user_id, user_role
        except Exception as e:
            logger.debug(f"Could not extract user info: {e}")
            return None, None
    
    async def dispatch(self, request: Request, call_next):
        """Apply rate limiting if endpoint should be protected."""
        path = request.url.path
        
        # Skip rate limiting for excluded endpoints
        if not self._should_apply_rate_limiting(path):
            return await call_next(request)
        
        # Get user information
        user_id, user_role = await self._get_user_info(request)
        
        # Check rate limit
        try:
            allowed, info = await self.rate_limiter.check_rate_limit(
                request, path, user_id, user_role
            )
            
            if not allowed:
                # Return rate limit error response
                return JSONResponse(
                    status_code=429,
                    content=info,
                    headers={
                        'X-RateLimit-Retry-After': str(info.get('retry_after', 60)),
                        'X-RateLimit-Limit': str(info.get('requests_limit', 0)),
                        'X-RateLimit-Remaining': '0'
                    }
                )
            
            # Process request
            response = await call_next(request)
            
            # Add rate limit headers
            response.headers['X-RateLimit-Limit'] = str(info.get('requests_limit', 0))
            response.headers['X-RateLimit-Remaining'] = str(info.get('remaining', 0))
            response.headers['X-RateLimit-Reset'] = str(info.get('window_reset_seconds', 60))
            
            if user_role:
                response.headers['X-RateLimit-Role'] = user_role.value
            
            return response
            
        except Exception as e:
            logger.error(f"Error in rate limiting middleware: {e}")
            # If rate limiting fails, allow the request to proceed
            return await call_next(request)


# Rate limiting decorator for individual endpoints
def rate_limit(
    requests_per_minute: Optional[int] = None,
    endpoint_modifier: Optional[float] = None
):
    """Decorator to apply custom rate limits to specific endpoints."""
    def decorator(func):
        # Store rate limiting metadata on the function
        if not hasattr(func, '_rate_limit_config'):
            func._rate_limit_config = {}
        
        if requests_per_minute is not None:
            func._rate_limit_config['requests_per_minute'] = requests_per_minute
        if endpoint_modifier is not None:
            func._rate_limit_config['endpoint_modifier'] = endpoint_modifier
        
        return func
    return decorator