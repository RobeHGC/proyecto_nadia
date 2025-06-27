# utils/protocol_manager.py
"""Protocol Manager for handling silence protocol with Redis caching."""
import asyncio
import json
import logging
from typing import Dict, List, Optional, Set

import redis.asyncio as redis

from database.models import DatabaseManager
from utils.redis_mixin import RedisConnectionMixin

logger = logging.getLogger(__name__)


class ProtocolManager(RedisConnectionMixin):
    """Manages silence protocol with Redis caching and database persistence."""
    
    CACHE_TTL = 300  # 5 minutes
    CACHE_PREFIX = "protocol_cache:"
    QUARANTINE_QUEUE = "nadia_quarantine_queue"
    QUARANTINE_ITEMS = "nadia_quarantine_items"
    
    def __init__(self, db_manager: DatabaseManager):
        """Initialize protocol manager."""
        super().__init__()
        self.db = db_manager
        self._active_protocols: Set[str] = set()
        self._cache_loaded = False
    
    async def initialize(self):
        """Initialize and warm cache with active protocols."""
        try:
            # Load all active protocols from database
            active_users = await self.db.get_active_protocol_users()
            
            # Warm Redis cache
            r = await self._get_redis()
            pipe = r.pipeline()
            
            for user_id in active_users:
                cache_key = f"{self.CACHE_PREFIX}{user_id}"
                pipe.setex(cache_key, self.CACHE_TTL, "ACTIVE")
                self._active_protocols.add(user_id)
            
            await pipe.execute()
            self._cache_loaded = True
            
            logger.info(f"Protocol cache warmed with {len(active_users)} active protocols")
            
        except Exception as e:
            logger.error(f"Failed to initialize protocol manager: {e}")
            raise
    
    async def is_protocol_active(self, user_id: str) -> bool:
        """Check if protocol is active for user (with caching)."""
        try:
            r = await self._get_redis()
            cache_key = f"{self.CACHE_PREFIX}{user_id}"
            
            # Check Redis cache first
            cached = await r.get(cache_key)
            if cached is not None:
                return cached.decode() == "ACTIVE"
            
            # Cache miss - check database
            status = await self.db.get_protocol_status(user_id)
            is_active = status.get('status') == 'ACTIVE'
            
            # Update cache
            await r.setex(cache_key, self.CACHE_TTL, "ACTIVE" if is_active else "INACTIVE")
            
            # Update local set
            if is_active:
                self._active_protocols.add(user_id)
            else:
                self._active_protocols.discard(user_id)
            
            return is_active
            
        except Exception as e:
            logger.error(f"Error checking protocol status: {e}")
            # Fallback to database on Redis error
            status = await self.db.get_protocol_status(user_id)
            return status.get('status') == 'ACTIVE'
    
    async def activate_protocol(self, user_id: str, activated_by: str, reason: Optional[str] = None) -> bool:
        """Activate protocol and update cache."""
        try:
            # Update database
            success = await self.db.activate_protocol(user_id, activated_by, reason)
            
            if success:
                # Update Redis cache
                r = await self._get_redis()
                cache_key = f"{self.CACHE_PREFIX}{user_id}"
                await r.setex(cache_key, self.CACHE_TTL, "ACTIVE")
                
                # Update local set
                self._active_protocols.add(user_id)
                
                # Publish event for real-time updates
                await r.publish("protocol_updates", json.dumps({
                    "action": "activated",
                    "user_id": user_id,
                    "by": activated_by
                }))
                
                logger.info(f"Protocol activated for {user_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to activate protocol: {e}")
            raise
    
    async def deactivate_protocol(self, user_id: str, deactivated_by: str, reason: Optional[str] = None) -> bool:
        """Deactivate protocol and update cache."""
        try:
            # Update database
            success = await self.db.deactivate_protocol(user_id, deactivated_by, reason)
            
            if success:
                # Update Redis cache
                r = await self._get_redis()
                cache_key = f"{self.CACHE_PREFIX}{user_id}"
                await r.setex(cache_key, self.CACHE_TTL, "INACTIVE")
                
                # Update local set
                self._active_protocols.discard(user_id)
                
                # Publish event
                await r.publish("protocol_updates", json.dumps({
                    "action": "deactivated",
                    "user_id": user_id,
                    "by": deactivated_by
                }))
                
                logger.info(f"Protocol deactivated for {user_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Failed to deactivate protocol: {e}")
            raise
    
    async def queue_for_quarantine(self, user_id: str, message_id: str, message_text: str,
                                 telegram_message_id: Optional[int] = None,
                                 context_preview: Optional[List[Dict]] = None) -> str:
        """Queue message for quarantine instead of processing."""
        try:
            # Save to database
            quarantine_id = await self.db.save_quarantine_message(
                user_id, message_id, message_text, telegram_message_id
            )
            
            # Add to Redis queue for real-time display
            r = await self._get_redis()
            
            quarantine_item = {
                "id": message_id,
                "quarantine_id": quarantine_id,
                "user_id": user_id,
                "message": message_text,
                "telegram_message_id": telegram_message_id,
                "timestamp": asyncio.get_event_loop().time(),
                "context_preview": context_preview or []
            }
            
            # Add to hash
            await r.hset(
                self.QUARANTINE_ITEMS,
                message_id,
                json.dumps(quarantine_item)
            )
            
            # Add to sorted set with timestamp as score
            await r.zadd(
                self.QUARANTINE_QUEUE,
                {message_id: quarantine_item["timestamp"]}
            )
            
            logger.info(f"Message {message_id} from {user_id} queued for quarantine")
            return quarantine_id
            
        except Exception as e:
            logger.error(f"Failed to queue message for quarantine: {e}")
            raise
    
    async def get_quarantine_queue(self, limit: int = 50) -> List[Dict]:
        """Get messages in quarantine queue from Redis."""
        try:
            r = await self._get_redis()
            
            # Get message IDs from sorted set (newest first)
            message_ids = await r.zrevrange(self.QUARANTINE_QUEUE, 0, limit - 1)
            
            if not message_ids:
                return []
            
            # Get message data from hash
            pipe = r.pipeline()
            for msg_id in message_ids:
                pipe.hget(self.QUARANTINE_ITEMS, msg_id)
            
            results = await pipe.execute()
            
            messages = []
            for msg_data in results:
                if msg_data:
                    messages.append(json.loads(msg_data))
            
            return messages
            
        except Exception as e:
            logger.error(f"Failed to get quarantine queue: {e}")
            # Fallback to database
            db_messages = await self.db.get_quarantine_messages(limit=limit)
            return db_messages
    
    async def process_quarantine_message(self, message_id: str, processed_by: str) -> Optional[Dict]:
        """Process a single quarantine message."""
        try:
            # Get message data
            r = await self._get_redis()
            msg_data = await r.hget(self.QUARANTINE_ITEMS, message_id)
            
            if not msg_data:
                # Try database if not in Redis
                return await self.db.process_quarantine_message(message_id, processed_by)
            
            msg_dict = json.loads(msg_data)
            
            # Mark as processed in database
            db_result = await self.db.process_quarantine_message(message_id, processed_by)
            
            if db_result:
                # Remove from Redis queue
                await r.hdel(self.QUARANTINE_ITEMS, message_id)
                await r.zrem(self.QUARANTINE_QUEUE, message_id)
                
                logger.info(f"Processed quarantine message {message_id}")
            
            return db_result
            
        except Exception as e:
            logger.error(f"Failed to process quarantine message: {e}")
            raise
    
    async def invalidate_cache(self, user_id: str):
        """Invalidate cache for a specific user."""
        try:
            r = await self._get_redis()
            cache_key = f"{self.CACHE_PREFIX}{user_id}"
            await r.delete(cache_key)
            logger.debug(f"Cache invalidated for user {user_id}")
        except Exception as e:
            logger.error(f"Failed to invalidate cache: {e}")
    
    async def get_stats(self) -> Dict:
        """Get protocol statistics."""
        stats = await self.db.get_protocol_stats()
        
        # Add Redis queue size
        try:
            r = await self._get_redis()
            queue_size = await r.zcard(self.QUARANTINE_QUEUE)
            stats['quarantine_queue_size'] = queue_size
        except:
            stats['quarantine_queue_size'] = 0
        
        stats['cached_protocols'] = len(self._active_protocols)
        
        return stats
    
    def is_cache_loaded(self) -> bool:
        """Check if cache has been loaded."""
        return self._cache_loaded