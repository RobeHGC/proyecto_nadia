# utils/telegram_history.py
"""Telegram History Manager for Recovery Agent."""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from telethon import TelegramClient
from telethon.tl.types import User, Chat, Channel
from telethon.errors import FloodWaitError, UserPrivacyRestrictedError, ChatAdminRequiredError

logger = logging.getLogger(__name__)


@dataclass
class TelegramMessage:
    """Represents a message from Telegram history."""
    id: int
    date: datetime
    text: str
    user_id: str
    chat_id: Optional[int] = None
    is_outgoing: bool = False
    reply_to_msg_id: Optional[int] = None


class TelegramHistoryManager:
    """Manages Telegram message history retrieval for recovery operations."""
    
    def __init__(self, telegram_client: TelegramClient):
        """Initialize with existing Telegram client."""
        self.client = telegram_client
        
        # Rate limiting to respect Telegram API limits
        self.last_request_time = 0.0
        self.min_request_interval = 1.0 / 30  # 30 requests per second max
        self.flood_wait_backoff = 1.0
        
    async def _rate_limit(self):
        """Ensure we don't exceed Telegram API rate limits."""
        now = asyncio.get_event_loop().time()
        time_since_last = now - self.last_request_time
        
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            await asyncio.sleep(sleep_time)
        
        self.last_request_time = asyncio.get_event_loop().time()

    async def get_missed_messages(self, user_id: str, since_message_id: int,
                                since_date: datetime, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get messages that were missed during downtime for a specific user.
        
        Args:
            user_id: Telegram user ID (as string)
            since_message_id: Last processed message ID
            since_date: Last processed message date
            limit: Maximum messages to retrieve
            
        Returns:
            List of message dictionaries with id, date, text, user_id
        """
        try:
            await self._rate_limit()
            
            logger.info(f"🔍 Fetching missed messages for user {user_id} since ID {since_message_id}")
            
            # Convert user_id to integer for Telegram API
            try:
                telegram_user_id = int(user_id)
            except ValueError:
                logger.error(f"Invalid user_id format: {user_id}")
                return []
            
            # Get the user entity
            try:
                user_entity = await self.client.get_entity(telegram_user_id)
            except Exception as e:
                logger.error(f"Could not get entity for user {user_id}: {e}")
                return []
            
            # Get message history from the private chat
            missed_messages = []
            
            try:
                # Get messages newer than our last processed message
                # We'll iterate through messages and stop when we reach our cursor
                async for message in self.client.iter_messages(
                    user_entity, 
                    limit=limit,
                    reverse=False  # Start from newest
                ):
                    # Skip messages older than or equal to our cursor
                    if message.id <= since_message_id:
                        break
                    
                    # Skip outgoing messages (our responses)
                    if message.out:
                        continue
                    
                    # Skip messages without text content
                    if not message.text:
                        logger.debug(f"Skipping message {message.id} - no text content")
                        continue
                    
                    # Only include messages from the user (not from us)
                    if message.from_id and hasattr(message.from_id, 'user_id'):
                        if str(message.from_id.user_id) != user_id:
                            continue
                    
                    # Convert to our format
                    msg_dict = {
                        "id": message.id,
                        "date": message.date,
                        "text": message.text,
                        "user_id": user_id,
                        "chat_id": message.chat_id if hasattr(message, 'chat_id') else None,
                        "is_outgoing": message.out,
                        "reply_to_msg_id": message.reply_to_msg_id if message.reply_to else None
                    }
                    
                    missed_messages.append(msg_dict)
                    logger.debug(f"Found missed message {message.id}: {message.text[:50]}...")
                
                # Sort by message ID to process in chronological order
                missed_messages.sort(key=lambda m: m["id"])
                
                logger.info(f"✅ Found {len(missed_messages)} missed messages for user {user_id}")
                return missed_messages
                
            except FloodWaitError as e:
                logger.warning(f"Flood wait error: waiting {e.seconds} seconds")
                await asyncio.sleep(e.seconds)
                return []  # Return empty list and let retry logic handle it
                
            except UserPrivacyRestrictedError:
                logger.warning(f"User {user_id} privacy settings prevent message history access")
                return []
                
            except ChatAdminRequiredError:
                logger.warning(f"Admin rights required to access chat history for user {user_id}")
                return []
                
        except Exception as e:
            logger.error(f"❌ Error fetching missed messages for user {user_id}: {e}")
            return []

    async def get_last_message_info(self, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the most recent message info for a user to initialize cursor.
        
        Args:
            user_id: Telegram user ID (as string)
            
        Returns:
            Dictionary with id, date of last message, or None if no messages
        """
        try:
            await self._rate_limit()
            
            telegram_user_id = int(user_id)
            user_entity = await self.client.get_entity(telegram_user_id)
            
            # Get the most recent message from this user
            async for message in self.client.iter_messages(user_entity, limit=1):
                if not message.out and message.text:  # Only incoming messages with text
                    return {
                        "id": message.id,
                        "date": message.date,
                        "text": message.text[:100] + "..." if len(message.text) > 100 else message.text
                    }
            
            logger.info(f"No recent messages found for user {user_id}")
            return None
            
        except Exception as e:
            logger.error(f"❌ Error getting last message info for user {user_id}: {e}")
            return None

    async def scan_all_dialogs(self) -> List[str]:
        """
        Scan all Telegram dialogs to get complete list of user IDs.
        This is the foundation of the comprehensive recovery strategy.
        
        Returns:
            List of user IDs (as strings) from all private conversations
        """
        try:
            await self._rate_limit()
            logger.info("🔍 Scanning all Telegram dialogs for comprehensive recovery...")
            
            user_ids = []
            dialog_count = 0
            
            # Iterate through all dialogs (conversations)
            async for dialog in self.client.iter_dialogs():
                dialog_count += 1
                
                # Only process private conversations (not groups/channels)
                if hasattr(dialog.entity, 'id') and hasattr(dialog.entity, 'username'):
                    # This is a User entity (private conversation)
                    if isinstance(dialog.entity, User):
                        user_id = str(dialog.entity.id)
                        user_ids.append(user_id)
                        logger.debug(f"📱 Found user dialog: {user_id} (@{dialog.entity.username or 'no_username'})")
                
                # Rate limiting for dialog scanning
                if dialog_count % 50 == 0:  # Every 50 dialogs, small pause
                    await asyncio.sleep(0.1)
            
            logger.info(f"✅ Dialog scan complete: {len(user_ids)} private conversations found from {dialog_count} total dialogs")
            return user_ids
            
        except FloodWaitError as e:
            logger.warning(f"⏳ Telegram flood wait during dialog scan: {e.seconds}s")
            await asyncio.sleep(e.seconds)
            return []
        except Exception as e:
            logger.error(f"❌ Error scanning Telegram dialogs: {e}")
            return []

    async def verify_message_continuity(self, user_id: str, 
                                      expected_last_id: int) -> Dict[str, Any]:
        """
        Verify if there's a gap in message continuity for a user.
        
        Args:
            user_id: Telegram user ID
            expected_last_id: The message ID we think was last processed
            
        Returns:
            Dictionary with gap_detected, missing_count, latest_message_id
        """
        try:
            await self._rate_limit()
            
            telegram_user_id = int(user_id)
            user_entity = await self.client.get_entity(telegram_user_id)
            
            # Get the latest message ID
            latest_message = None
            async for message in self.client.iter_messages(user_entity, limit=1):
                if not message.out and message.text:
                    latest_message = message
                    break
            
            if not latest_message:
                return {
                    "gap_detected": False,
                    "missing_count": 0,
                    "latest_message_id": expected_last_id,
                    "latest_message_date": None
                }
            
            gap_detected = latest_message.id > expected_last_id
            missing_count = max(0, latest_message.id - expected_last_id)
            
            return {
                "gap_detected": gap_detected,
                "missing_count": missing_count,
                "latest_message_id": latest_message.id,
                "latest_message_date": latest_message.date,
                "gap_hours": (latest_message.date - datetime.now()).total_seconds() / 3600 if gap_detected else 0
            }
            
        except Exception as e:
            logger.error(f"❌ Error verifying message continuity for user {user_id}: {e}")
            return {
                "gap_detected": False,
                "missing_count": 0,
                "latest_message_id": expected_last_id,
                "error": str(e)
            }

    async def get_user_chat_history_summary(self, user_id: str, 
                                          days_back: int = 7) -> Dict[str, Any]:
        """
        Get a summary of chat history with a user for context building.
        
        Args:
            user_id: Telegram user ID
            days_back: How many days of history to analyze
            
        Returns:
            Dictionary with message counts, date ranges, activity patterns
        """
        try:
            await self._rate_limit()
            
            telegram_user_id = int(user_id)
            user_entity = await self.client.get_entity(telegram_user_id)
            
            # Calculate date cutoff
            cutoff_date = datetime.now() - timedelta(days=days_back)
            
            summary = {
                "user_id": user_id,
                "analysis_period_days": days_back,
                "total_messages": 0,
                "user_messages": 0,
                "bot_messages": 0,
                "first_message_date": None,
                "last_message_date": None,
                "daily_activity": {},
                "message_lengths": [],
                "has_recent_activity": False
            }
            
            # Analyze messages within the time period
            async for message in self.client.iter_messages(
                user_entity, 
                offset_date=cutoff_date,
                limit=500  # Reasonable limit for analysis
            ):
                summary["total_messages"] += 1
                
                if message.out:
                    summary["bot_messages"] += 1
                else:
                    summary["user_messages"] += 1
                    if message.text:
                        summary["message_lengths"].append(len(message.text))
                
                # Track date range
                if not summary["first_message_date"] or message.date < summary["first_message_date"]:
                    summary["first_message_date"] = message.date
                if not summary["last_message_date"] or message.date > summary["last_message_date"]:
                    summary["last_message_date"] = message.date
                
                # Daily activity tracking
                day_key = message.date.strftime("%Y-%m-%d")
                if day_key not in summary["daily_activity"]:
                    summary["daily_activity"][day_key] = {"user": 0, "bot": 0}
                
                if message.out:
                    summary["daily_activity"][day_key]["bot"] += 1
                else:
                    summary["daily_activity"][day_key]["user"] += 1
            
            # Calculate additional metrics
            if summary["message_lengths"]:
                summary["avg_message_length"] = sum(summary["message_lengths"]) / len(summary["message_lengths"])
                summary["median_message_length"] = sorted(summary["message_lengths"])[len(summary["message_lengths"]) // 2]
            
            summary["has_recent_activity"] = summary["last_message_date"] and \
                                           (datetime.now() - summary["last_message_date"]).days < 1
            
            logger.info(f"✅ Generated chat history summary for user {user_id}: "
                       f"{summary['total_messages']} messages over {days_back} days")
            
            return summary
            
        except Exception as e:
            logger.error(f"❌ Error generating chat history summary for user {user_id}: {e}")
            return {
                "user_id": user_id,
                "error": str(e),
                "total_messages": 0
            }

    async def health_check(self) -> Dict[str, Any]:
        """
        Perform a health check of the Telegram connection.
        
        Returns:
            Dictionary with connection status and capabilities
        """
        try:
            # Test basic connection
            me = await self.client.get_me()
            
            # Test message history access (try to get one message from ourselves)
            test_successful = False
            try:
                async for message in self.client.iter_messages("me", limit=1):
                    test_successful = True
                    break
            except Exception as e:
                logger.warning(f"Message history test failed: {e}")
            
            return {
                "status": "healthy",
                "connected": True,
                "bot_id": me.id,
                "bot_username": me.username,
                "message_history_access": test_successful,
                "rate_limiting_active": True,
                "min_request_interval": self.min_request_interval,
                "last_request_time": self.last_request_time
            }
            
        except Exception as e:
            logger.error(f"❌ Telegram history manager health check failed: {e}")
            return {
                "status": "unhealthy",
                "connected": False,
                "error": str(e)
            }