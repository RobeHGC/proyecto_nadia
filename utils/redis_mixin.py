# utils/redis_mixin.py
"""Redis connection mixin for eliminating connection duplication."""
import redis.asyncio as redis
from typing import Optional
from utils.config import Config


class RedisConnectionMixin:
    """Mixin to provide Redis connection management."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._redis: Optional[redis.Redis] = None
        self._config = getattr(self, 'config', None) or Config.from_env()
    
    async def _get_redis(self) -> redis.Redis:
        """Get or create Redis connection."""
        if not self._redis:
            self._redis = await redis.from_url(self._config.redis_url)
        return self._redis
    
    async def _close_redis(self):
        """Close Redis connection."""
        if self._redis:
            await self._redis.aclose()
            self._redis = None