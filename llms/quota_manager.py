# llms/quota_manager.py
"""
Quota manager for tracking Gemini API usage limits.
Uses Redis to track daily and per-minute request counts.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class GeminiQuotaManager:
    """
    Manages Gemini API quota tracking using Redis.
    
    Tracks:
    - Daily requests: 32,000/day limit
    - Per-minute requests: 1,500/minute limit
    """
    
    # Gemini free tier limits
    DAILY_LIMIT = 32000
    MINUTE_LIMIT = 1500
    
    def __init__(self, redis_url: str):
        """Initialize quota manager with Redis connection."""
        self.redis_url = redis_url
        self._redis = None
    
    async def _get_redis(self):
        """Get or create Redis connection."""
        if not self._redis:
            self._redis = await redis.from_url(self.redis_url)
        return self._redis
    
    async def close(self):
        """Close Redis connection cleanly."""
        if self._redis:
            await self._redis.aclose()
            self._redis = None
    
    async def can_use_free_tier(self) -> bool:
        """
        Check if we can make a request within free tier limits.
        
        Returns:
            True if request can be made within limits
        """
        try:
            # Check both daily and minute limits
            daily_available = await self._check_daily_limit()
            minute_available = await self._check_minute_limit()
            
            return daily_available and minute_available
            
        except Exception as e:
            logger.error(f"Error checking quota limits: {e}")
            # Default to allowing requests if Redis fails
            return True
    
    async def increment_usage(self) -> None:
        """
        Increment usage counters for both daily and per-minute tracking.
        Call this after successful API request.
        """
        try:
            r = await self._get_redis()
            now = datetime.utcnow()
            
            # Increment daily counter
            daily_key = f"gemini:daily_count:{now.strftime('%Y-%m-%d')}"
            await r.incr(daily_key)
            await r.expire(daily_key, 86400)  # Expire in 24 hours
            
            # Increment minute counter
            minute_key = f"gemini:minute_count:{now.strftime('%Y-%m-%d:%H:%M')}"
            await r.incr(minute_key)
            await r.expire(minute_key, 60)  # Expire in 60 seconds
            
            logger.debug(f"Incremented Gemini usage counters for {now}")
            
        except Exception as e:
            logger.error(f"Error incrementing usage: {e}")
    
    async def get_daily_usage(self) -> int:
        """
        Get current daily usage count.
        
        Returns:
            Number of requests made today
        """
        try:
            r = await self._get_redis()
            today = datetime.utcnow().strftime('%Y-%m-%d')
            daily_key = f"gemini:daily_count:{today}"
            
            count = await r.get(daily_key)
            return int(count) if count else 0
            
        except Exception as e:
            logger.error(f"Error getting daily usage: {e}")
            return 0
    
    async def get_minute_usage(self) -> int:
        """
        Get current minute usage count.
        
        Returns:
            Number of requests made in current minute
        """
        try:
            r = await self._get_redis()
            now = datetime.utcnow().strftime('%Y-%m-%d:%H:%M')
            minute_key = f"gemini:minute_count:{now}"
            
            count = await r.get(minute_key)
            return int(count) if count else 0
            
        except Exception as e:
            logger.error(f"Error getting minute usage: {e}")
            return 0
    
    async def reset_daily(self) -> None:
        """
        Reset daily quota counter.
        Useful for testing or manual resets.
        """
        try:
            r = await self._get_redis()
            today = datetime.utcnow().strftime('%Y-%m-%d')
            daily_key = f"gemini:daily_count:{today}"
            
            await r.delete(daily_key)
            logger.info("Reset daily Gemini quota counter")
            
        except Exception as e:
            logger.error(f"Error resetting daily quota: {e}")
    
    
    async def _check_daily_limit(self) -> bool:
        """Check if daily limit allows more requests."""
        daily_usage = await self.get_daily_usage()
        return daily_usage < self.DAILY_LIMIT
    
    async def _check_minute_limit(self) -> bool:
        """Check if per-minute limit allows more requests."""
        minute_usage = await self.get_minute_usage()
        return minute_usage < self.MINUTE_LIMIT
    
    async def record_usage(self, tokens: int) -> None:
        """
        Record token usage for quota tracking.
        
        Args:
            tokens: Number of tokens consumed
        """
        try:
            r = await self._get_redis()
            now = datetime.utcnow()
            
            # Update daily counter
            today = now.strftime('%Y-%m-%d')
            daily_key = f"gemini:daily_count:{today}"
            await r.incr(daily_key, tokens)
            await r.expire(daily_key, 86400)  # Expire after 24 hours
            
            # Update minute counter
            current_minute = now.strftime('%Y-%m-%d:%H:%M')
            minute_key = f"gemini:minute_count:{current_minute}"
            await r.incr(minute_key, tokens)
            await r.expire(minute_key, 120)  # Expire after 2 minutes
            
            logger.debug(f"Recorded {tokens} tokens for Gemini quota tracking")
            
        except Exception as e:
            logger.error(f"Error recording quota usage: {e}")
    
    async def get_quota_status(self) -> dict:
        """
        Get comprehensive quota status including can_use_free_tier.
        
        Returns:
            Dictionary with quota information
        """
        daily_usage = await self.get_daily_usage()
        minute_usage = await self.get_minute_usage()
        can_use = await self.can_use_free_tier()
        
        return {
            "daily_usage": daily_usage,
            "daily_limit": self.DAILY_LIMIT,
            "daily_remaining": max(0, self.DAILY_LIMIT - daily_usage),
            "minute_usage": minute_usage,
            "minute_limit": self.MINUTE_LIMIT,
            "minute_remaining": max(0, self.MINUTE_LIMIT - minute_usage),
            "can_make_request": can_use,
            "can_use_free_tier": can_use
        }