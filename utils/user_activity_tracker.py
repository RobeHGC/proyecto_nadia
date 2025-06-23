"""
User Activity Tracker for Adaptive Message Pacing

This module implements an adaptive window system that:
1. Buffers incoming messages for a short window
2. Detects rapid message sequences 
3. Applies intelligent batching to reduce API costs
4. Maintains good UX for single messages
"""

import asyncio
import json
import logging
import time
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class UserActivityTracker:
    """Tracks user activity and manages message batching with adaptive windows."""
    
    def __init__(self, redis_url: str, config):
        self.redis_url = redis_url
        self.config = config
        self._redis: Optional[redis.Redis] = None
        
        # In-memory state for fast access
        self.message_buffers: Dict[str, List[Dict]] = {}  # user_id -> [messages]
        self.buffer_timers: Dict[str, asyncio.Task] = {}  # user_id -> timer_task
        self.typing_states: Dict[str, bool] = {}  # user_id -> is_typing
        
        # Redis keys
        self.buffer_key = "nadia_message_buffer"  # Hash: user_id -> message_list
        self.typing_key = "nadia_typing_state"    # Hash: user_id -> typing_state
    
    async def _get_redis(self) -> redis.Redis:
        """Get Redis connection."""
        if not self._redis:
            self._redis = await redis.from_url(self.redis_url)
        return self._redis
    
    async def close(self):
        """Close Redis connection and cleanup."""
        # Cancel all pending timers
        for timer in self.buffer_timers.values():
            timer.cancel()
        self.buffer_timers.clear()
        
        if self._redis:
            await self._redis.close()
    
    # ────────────────────────────────────────────────────────────────
    # Core Adaptive Window Logic
    # ────────────────────────────────────────────────────────────────
    
    async def handle_message(self, event, process_callback) -> bool:
        """
        Handle incoming message with adaptive window logic.
        
        Args:
            event: Telegram message event
            process_callback: Function to call for processing messages
            
        Returns:
            bool: True if message was handled, False if should use fallback
        """
        if not self.config.enable_typing_pacing:
            return False  # Use original processing
        
        user_id = str(event.sender_id)
        
        try:
            # Add message to buffer
            await self.add_to_buffer(user_id, event)
            
            # Cancel existing timer if any
            if user_id in self.buffer_timers:
                self.buffer_timers[user_id].cancel()
            
            # Start adaptive window timer
            self.buffer_timers[user_id] = asyncio.create_task(
                self._adaptive_window_timer(user_id, process_callback)
            )
            
            logger.info(f"PACING: Message buffered for user {user_id}, window started")
            return True
            
        except Exception as exc:
            logger.error(f"Error in adaptive window handling: {exc}")
            return False  # Fallback to original processing
    
    async def _adaptive_window_timer(self, user_id: str, process_callback):
        """
        Adaptive window timer that waits for additional messages.
        
        Phase 1: Initial window (1.5s) - detect rapid messages
        Phase 2: If rapid detected, wait for typing completion
        """
        try:
            # Phase 1: Initial detection window
            await asyncio.sleep(self.config.typing_window_delay)
            
            buffer_size = len(self.message_buffers.get(user_id, []))
            
            if buffer_size >= self.config.min_batch_size:
                # Rapid messages detected - enter batching mode
                logger.info(f"PACING: Rapid messages detected for user {user_id} ({buffer_size} messages), entering batching mode")
                
                # Phase 2: Wait for typing completion
                await self._wait_for_typing_completion(user_id)
                
            else:
                logger.info(f"PACING: Single message for user {user_id}, processing immediately")
            
            # Process all buffered messages
            await self._process_buffer(user_id, process_callback)
            
        except asyncio.CancelledError:
            logger.debug(f"PACING: Timer cancelled for user {user_id}")
        except Exception as exc:
            logger.error(f"PACING: Error in adaptive timer for user {user_id}: {exc}")
            # Process buffer anyway to avoid losing messages
            await self._process_buffer(user_id, process_callback)
    
    async def _wait_for_typing_completion(self, user_id: str):
        """
        Wait for user to stop typing (debounce period).
        """
        max_wait_time = self.config.max_batch_wait_time
        debounce_delay = self.config.typing_debounce_delay
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            # Check if user is typing (from Telegram events)
            is_typing = await self.is_user_typing(user_id)
            
            if not is_typing:
                # User stopped typing, wait debounce period
                logger.debug(f"PACING: User {user_id} stopped typing, waiting {debounce_delay}s")
                await asyncio.sleep(debounce_delay)
                
                # Check again after debounce
                is_typing_after_debounce = await self.is_user_typing(user_id)
                if not is_typing_after_debounce:
                    logger.info(f"PACING: Typing completed for user {user_id}")
                    return
                else:
                    logger.debug(f"PACING: User {user_id} resumed typing during debounce")
            
            # Check for new messages while waiting
            current_buffer_size = len(self.message_buffers.get(user_id, []))
            if current_buffer_size >= self.config.max_batch_size:
                logger.info(f"PACING: Max batch size reached for user {user_id} ({current_buffer_size} messages)")
                return
            
            # Short polling interval
            await asyncio.sleep(0.5)
        
        logger.warning(f"PACING: Max wait time reached for user {user_id}, processing anyway")
    
    # ────────────────────────────────────────────────────────────────
    # Message Buffer Management
    # ────────────────────────────────────────────────────────────────
    
    async def add_to_buffer(self, user_id: str, event):
        """Add message to user's buffer."""
        if user_id not in self.message_buffers:
            self.message_buffers[user_id] = []
        
        message_data = {
            "user_id": user_id,
            "message": event.text,
            "chat_id": event.chat_id,
            "message_id": event.message.id,
            "timestamp": datetime.now().isoformat(),
            "event": event  # Store full event for processing
        }
        
        self.message_buffers[user_id].append(message_data)
        
        # Persist to Redis for reliability
        r = await self._get_redis()
        await r.hset(
            self.buffer_key,
            user_id,
            json.dumps([{k: v for k, v in msg.items() if k != "event"} 
                       for msg in self.message_buffers[user_id]])
        )
        
        logger.debug(f"PACING: Added message to buffer for user {user_id}, buffer size: {len(self.message_buffers[user_id])}")
    
    async def _process_buffer(self, user_id: str, process_callback):
        """Process all messages in user's buffer."""
        if user_id not in self.message_buffers or not self.message_buffers[user_id]:
            return
        
        messages = self.message_buffers[user_id].copy()
        buffer_size = len(messages)
        
        # Clear buffer first
        self.message_buffers[user_id] = []
        if user_id in self.buffer_timers:
            del self.buffer_timers[user_id]
        
        # Clear Redis buffer
        r = await self._get_redis()
        await r.hdel(self.buffer_key, user_id)
        
        logger.info(f"PACING: Processing buffer for user {user_id} with {buffer_size} messages")
        
        # Process each message through original callback
        for message_data in messages:
            try:
                event = message_data.get("event")
                if event:
                    await process_callback(event)
                else:
                    logger.warning(f"PACING: No event data for buffered message from user {user_id}")
            except Exception as exc:
                logger.error(f"PACING: Error processing buffered message for user {user_id}: {exc}")
        
        # Log metrics
        if buffer_size > 1:
            estimated_savings = ((buffer_size - 1) / buffer_size) * 100
            logger.info(f"PACING_METRICS: user={user_id}, action=batch_processed, messages={buffer_size}, estimated_savings={estimated_savings:.1f}%")
        else:
            logger.info(f"PACING_METRICS: user={user_id}, action=single_processed, messages={buffer_size}, estimated_savings=0%")
    
    # ────────────────────────────────────────────────────────────────
    # Typing State Management
    # ────────────────────────────────────────────────────────────────
    
    async def handle_typing_event(self, event):
        """Handle typing events from Telegram."""
        user_id = str(event.user_id)
        
        # Determine if user is typing or stopped
        action_type = str(type(event.action)).lower()
        is_typing = "typing" in action_type
        
        await self.set_typing_state(user_id, is_typing)
        
        logger.debug(f"PACING: Typing event for user {user_id}: {is_typing}")
    
    async def set_typing_state(self, user_id: str, is_typing: bool):
        """Set user's typing state."""
        self.typing_states[user_id] = is_typing
        
        # Persist to Redis with expiration
        r = await self._get_redis()
        if is_typing:
            await r.hset(self.typing_key, user_id, "true")
            await r.expire(f"{self.typing_key}:{user_id}", 30)  # Auto-expire typing state
        else:
            await r.hset(self.typing_key, user_id, "false")
    
    async def is_user_typing(self, user_id: str) -> bool:
        """Check if user is currently typing."""
        # Check in-memory first
        if user_id in self.typing_states:
            return self.typing_states[user_id]
        
        # Fallback to Redis
        try:
            r = await self._get_redis()
            typing_state = await r.hget(self.typing_key, user_id)
            return typing_state == b"true" if typing_state else False
        except Exception:
            return False
    
    # ────────────────────────────────────────────────────────────────
    # Utilities and Metrics
    # ────────────────────────────────────────────────────────────────
    
    async def get_buffer_size(self, user_id: str) -> int:
        """Get current buffer size for user."""
        return len(self.message_buffers.get(user_id, []))
    
    async def get_metrics(self) -> Dict[str, Any]:
        """Get pacing system metrics."""
        active_buffers = len([uid for uid, buf in self.message_buffers.items() if buf])
        active_timers = len(self.buffer_timers)
        typing_users = len([uid for uid, typing in self.typing_states.items() if typing])
        
        return {
            "active_buffers": active_buffers,
            "active_timers": active_timers,
            "typing_users": typing_users,
            "total_users_tracked": len(self.message_buffers),
        }
    
    async def cleanup_old_data(self):
        """Cleanup old data to prevent memory leaks."""
        current_time = datetime.now()
        cutoff_time = current_time - timedelta(hours=1)
        
        # Cleanup old buffers (safety measure)
        users_to_remove = []
        for user_id, messages in self.message_buffers.items():
            if messages:
                last_message_time = datetime.fromisoformat(messages[-1]["timestamp"])
                if last_message_time < cutoff_time:
                    users_to_remove.append(user_id)
        
        for user_id in users_to_remove:
            del self.message_buffers[user_id]
            if user_id in self.buffer_timers:
                self.buffer_timers[user_id].cancel()
                del self.buffer_timers[user_id]
            if user_id in self.typing_states:
                del self.typing_states[user_id]
        
        if users_to_remove:
            logger.info(f"PACING: Cleaned up data for {len(users_to_remove)} inactive users")