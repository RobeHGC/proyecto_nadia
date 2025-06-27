# agents/recovery_agent.py
"""Recovery Agent: 'Sin Dejar a Nadie Atrás' - Zero message loss system."""
import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from agents.supervisor_agent import SupervisorAgent
from database.models import DatabaseManager
from utils.recovery_config import RecoveryConfig
from utils.redis_mixin import RedisConnectionMixin
from utils.telegram_history import TelegramHistoryManager

logger = logging.getLogger(__name__)


class MessagePriority(Enum):
    """Message processing priority tiers based on age."""

    TIER_1 = "TIER_1"  # <2h - high priority, immediate
    TIER_2 = "TIER_2"  # 2-6h - medium priority, batch
    TIER_3 = "TIER_3"  # 6-12h - low priority, controlled
    SKIP = "SKIP"  # >12h - auto-skip, log only


@dataclass
class RecoveredMessage:
    """Container for a recovered Telegram message."""

    telegram_message_id: int
    telegram_date: datetime
    user_id: str
    message_text: str
    priority: MessagePriority
    age_hours: float


@dataclass
class RecoveryBatch:
    """Batch of messages for processing."""

    priority: MessagePriority
    messages: List[RecoveredMessage]
    batch_delay: float  # seconds between messages in batch
    user_id: str


class RecoveryAgent(RedisConnectionMixin):
    """Manages message recovery operations during system downtime."""

    def __init__(
        self,
        database_manager: DatabaseManager,
        telegram_history: TelegramHistoryManager,
        supervisor_agent: SupervisorAgent,
        config: Optional[RecoveryConfig] = None,
    ):
        """Initialize Recovery Agent."""
        self.db = database_manager
        self.telegram_history = telegram_history
        self.supervisor = supervisor_agent
        self.config = config or RecoveryConfig()

        # Rate limiting and processing control
        self.processing_semaphore = asyncio.Semaphore(self.config.max_concurrent_users)
        self.last_telegram_request = 0.0
        self.telegram_rate_limiter = asyncio.Semaphore(self.config.telegram_rate_limit)

        logger.info(f"Recovery Agent initialized with config: {self.config}")

    async def startup_recovery_check(self) -> Dict[str, Any]:
        """
        Perform comprehensive recovery check on startup using the new strategy:
        1. Scan all Telegram dialogs to get user IDs
        2. For each user: SQL lookup for last message
        3. Gap detection: Telegram messages > SQL last message
        4. Batch recovery with rate limiting
        """
        logger.info(
            "🔄 Starting comprehensive recovery check with Telegram dialog scan..."
        )

        # Start recovery operation in database
        operation_id = await self.db.start_recovery_operation(
            operation_type="startup_comprehensive",
            metadata={
                "startup_time": datetime.now().isoformat(),
                "strategy": "telegram_scan",
            },
        )

        stats = {
            "operation_id": operation_id,
            "users_scanned": 0,
            "users_with_history": 0,
            "users_checked": 0,
            "messages_recovered": 0,
            "messages_skipped": 0,
            "errors": 0,
            "start_time": datetime.now(),
        }

        try:
            # STEP 1: Scan all Telegram dialogs to get comprehensive user list
            logger.info("📱 Step 1: Scanning all Telegram dialogs...")
            telegram_user_ids = await self.telegram_history.scan_all_dialogs()
            stats["users_scanned"] = len(telegram_user_ids)

            if not telegram_user_ids:
                logger.warning(
                    "⚠️  No Telegram dialogs found. Check Telegram client connection."
                )
                await self.db.update_recovery_operation(
                    operation_id, status="completed", **stats
                )
                return stats

            logger.info(f"✅ Found {len(telegram_user_ids)} users in Telegram dialogs")

            # STEP 2: SQL lookup for last message per user
            logger.info("🗄️  Step 2: Looking up last processed messages in SQL...")
            sql_last_messages = await self.db.get_last_message_per_user(
                telegram_user_ids
            )
            stats["users_with_history"] = len(sql_last_messages)

            logger.info(
                f"📊 SQL lookup complete: {len(sql_last_messages)} users have message history"
            )

            # STEP 3 & 4: Gap detection and batch recovery per user
            logger.info("🔍 Step 3-4: Gap detection and batch recovery...")
            recovery_batches = {}

            # Process users in batches to avoid overwhelming the system
            batch_size = 10  # Process 10 users at a time
            for i in range(0, len(telegram_user_ids), batch_size):
                user_batch = telegram_user_ids[i : i + batch_size]

                # Process this batch of users concurrently
                tasks = []
                for user_id in user_batch:
                    if (
                        stats["users_checked"]
                        >= self.config.max_users_per_startup_check
                    ):
                        logger.info(
                            f"Reached max users limit ({self.config.max_users_per_startup_check})"
                        )
                        break

                    task = self._process_user_comprehensive_recovery(
                        user_id, sql_last_messages.get(user_id), stats
                    )
                    tasks.append(task)

                # Wait for this batch to complete
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)

                # Collect recovery batches from results
                for result in batch_results:
                    if (
                        isinstance(result, dict)
                        and "user_id" in result
                        and result.get("messages")
                    ):
                        recovery_batches[result["user_id"]] = result["messages"]

                # Small delay between user batches
                await asyncio.sleep(0.5)

            # STEP 5: Process all recovery batches
            if recovery_batches:
                logger.info(
                    f"🔄 Processing {len(recovery_batches)} users with recovery messages..."
                )
                await self._process_recovery_batches(recovery_batches, stats)
            else:
                logger.info("✅ No messages to recover - all users are up to date!")

            # Update operation status
            await self.db.update_recovery_operation(
                operation_id,
                status="completed",
                users_checked=stats["users_checked"],
                messages_recovered=stats["messages_recovered"],
                messages_skipped=stats["messages_skipped"],
                errors_encountered=stats["errors"],
            )

            duration = (datetime.now() - stats["start_time"]).total_seconds()
            logger.info(
                f"✅ Startup recovery completed in {duration:.1f}s: "
                f"{stats['messages_recovered']} recovered, "
                f"{stats['messages_skipped']} skipped, "
                f"{stats['errors']} errors"
            )

            return stats

        except Exception as e:
            logger.error(f"❌ Startup recovery failed: {e}")
            await self.db.update_recovery_operation(
                operation_id=operation_id,
                status="failed",
                error_details={"error": str(e), "type": type(e).__name__},
            )
            raise

    async def _recover_user_messages(
        self, cursor: Dict[str, Any], global_stats: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Recover messages for a single user."""
        user_id = cursor["user_id"]
        last_processed_id = cursor["last_processed_telegram_id"]
        last_processed_date = cursor["last_processed_telegram_date"]

        stats = {"recovered": 0, "skipped": 0, "errors": 0}

        async with self.processing_semaphore:
            try:
                global_stats["users_checked"] += 1
                logger.info(
                    f"🔍 Checking user {user_id} since message {last_processed_id}"
                )

                # Check PROTOCOLO DE SILENCIO integration
                if self.config.integrate_with_protocol_silence:
                    protocol_status = await self._check_protocol_silence_status(user_id)
                    if protocol_status.get("is_quarantined", False):
                        logger.info(
                            f"⚠️  User {user_id} is quarantined, skipping recovery"
                        )
                        stats["skipped"] += 1
                        return stats

                # Get missed messages from Telegram
                missed_messages = await self.telegram_history.get_missed_messages(
                    user_id=user_id,
                    since_message_id=last_processed_id,
                    since_date=last_processed_date,
                    limit=self.config.max_messages_per_user,
                )

                if not missed_messages:
                    logger.debug(f"No missed messages for user {user_id}")
                    return stats

                logger.info(
                    f"Found {len(missed_messages)} missed messages for user {user_id}"
                )

                # Convert to RecoveredMessage objects with priority classification
                recovered_messages = []
                for msg in missed_messages:
                    age_hours = (datetime.now() - msg["date"]).total_seconds() / 3600
                    priority = self._classify_message_priority(age_hours)

                    if priority == MessagePriority.SKIP:
                        stats["skipped"] += 1
                        logger.info(
                            f"Skipping message {msg['id']} (age: {age_hours:.1f}h)"
                        )
                        continue

                    recovered_msg = RecoveredMessage(
                        telegram_message_id=msg["id"],
                        telegram_date=msg["date"],
                        user_id=user_id,
                        message_text=msg["text"],
                        priority=priority,
                        age_hours=age_hours,
                    )
                    recovered_messages.append(recovered_msg)

                if recovered_messages:
                    # Process messages in priority-based batches
                    batches = self._create_priority_batches(recovered_messages, user_id)

                    for batch in batches:
                        processed = (
                            await self._process_recovery_batch_with_enhanced_controls(
                                batch
                            )
                        )
                        stats["recovered"] += processed

                        # Update cursor after each batch
                        latest_msg = max(
                            batch.messages, key=lambda m: m.telegram_message_id
                        )
                        await self.db.update_user_cursor(
                            user_id=user_id,
                            telegram_message_id=latest_msg.telegram_message_id,
                            telegram_date=latest_msg.telegram_date,
                            messages_recovered=processed,
                        )

                return stats

            except Exception as e:
                logger.error(f"❌ Error recovering messages for user {user_id}: {e}")
                stats["errors"] += 1
                return stats

    def _classify_message_priority(self, age_hours: float) -> MessagePriority:
        """Classify message priority based on age."""
        if age_hours > self.config.max_message_age_hours:
            return MessagePriority.SKIP
        elif age_hours <= 2:
            return MessagePriority.TIER_1
        elif age_hours <= 12:
            return MessagePriority.TIER_2
        else:
            return MessagePriority.TIER_3

    def _create_priority_batches(
        self, messages: List[RecoveredMessage], user_id: str
    ) -> List[RecoveryBatch]:
        """Group messages into priority-based processing batches."""
        # Group by priority
        priority_groups = {}
        for msg in messages:
            if msg.priority not in priority_groups:
                priority_groups[msg.priority] = []
            priority_groups[msg.priority].append(msg)

        batches = []

        # Create batches with appropriate delays
        for priority, msgs in priority_groups.items():
            if priority == MessagePriority.TIER_1:
                batch_delay = 0.5  # Fast processing
            elif priority == MessagePriority.TIER_2:
                batch_delay = 2.0  # Medium delay
            else:  # TIER_3
                batch_delay = 5.0  # Slow processing

            # Sort messages by telegram_message_id to maintain order
            msgs.sort(key=lambda m: m.telegram_message_id)

            batch = RecoveryBatch(
                priority=priority,
                messages=msgs,
                batch_delay=batch_delay,
                user_id=user_id,
            )
            batches.append(batch)

        # Sort batches by priority (TIER_1 first)
        priority_order = {
            MessagePriority.TIER_1: 1,
            MessagePriority.TIER_2: 2,
            MessagePriority.TIER_3: 3,
        }
        batches.sort(key=lambda b: priority_order[b.priority])

        return batches

    async def _process_user_comprehensive_recovery(
        self,
        user_id: str,
        sql_last_message: Optional[Dict[str, Any]],
        stats: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Process gap detection and recovery for a single user.
        Core method of the comprehensive recovery strategy.
        """
        stats["users_checked"] += 1

        try:
            # Determine the starting point for gap detection
            if sql_last_message:
                # User has SQL history - check for gaps
                since_message_id = sql_last_message["telegram_message_id"]
                since_date = sql_last_message["telegram_date"]
                logger.debug(
                    f"🔍 User {user_id}: Checking for gaps since message ID {since_message_id}"
                )
            else:
                # New user - get all recent messages (within time limit)
                since_message_id = 0
                since_date = datetime.now() - timedelta(
                    hours=self.config.max_message_age_hours
                )
                logger.debug(
                    f"🆕 User {user_id}: New user, checking last {self.config.max_message_age_hours}h"
                )

            # Get missed messages from Telegram
            missed_telegram_messages = await self.telegram_history.get_missed_messages(
                user_id=user_id,
                since_message_id=since_message_id,
                since_date=since_date,
                limit=self.config.max_messages_per_user_per_session,
            )

            if not missed_telegram_messages:
                logger.debug(f"✅ User {user_id}: No gaps detected")
                return {"user_id": user_id, "messages": []}

            # Convert to RecoveredMessage objects with priority
            recovered_messages = []
            for msg_data in missed_telegram_messages:
                # Calculate message age
                msg_date = (
                    datetime.fromisoformat(msg_data["date"])
                    if isinstance(msg_data["date"], str)
                    else msg_data["date"]
                )
                age_hours = (
                    datetime.now() - msg_date.replace(tzinfo=None)
                ).total_seconds() / 3600

                # Assign priority based on age (max 12 hours)
                if age_hours < 2:
                    priority = MessagePriority.TIER_1
                elif age_hours < 6:
                    priority = MessagePriority.TIER_2
                elif age_hours < 12:
                    priority = MessagePriority.TIER_3
                else:
                    priority = MessagePriority.SKIP
                    stats["messages_skipped"] += 1
                    logger.debug(
                        f"⏰ Skipping old message (age: {age_hours:.1f}h > 12h limit)"
                    )
                    continue  # Skip messages older than 12 hours

                recovered_msg = RecoveredMessage(
                    telegram_message_id=msg_data["id"],
                    telegram_date=msg_date,
                    user_id=user_id,
                    message_text=msg_data["text"],
                    priority=priority,
                    age_hours=age_hours,
                )
                recovered_messages.append(recovered_msg)

            if recovered_messages:
                logger.info(
                    f"📨 User {user_id}: Found {len(recovered_messages)} messages to recover"
                )
                return {"user_id": user_id, "messages": recovered_messages}
            else:
                logger.debug(f"⏭️  User {user_id}: All messages too old, skipped")
                return {"user_id": user_id, "messages": []}

        except Exception as e:
            logger.error(f"❌ Error processing user {user_id}: {e}")
            stats["errors"] += 1
            return {"user_id": user_id, "messages": [], "error": str(e)}

    async def _process_recovery_batches(
        self, recovery_batches: Dict[str, List[RecoveredMessage]], stats: Dict[str, Any]
    ) -> None:
        """
        Process all recovery batches with proper rate limiting and prioritization.
        """
        total_messages = sum(len(messages) for messages in recovery_batches.values())
        logger.info(
            f"🔄 Processing {total_messages} total messages from {len(recovery_batches)} users"
        )

        # Create priority batches for all users
        all_batches = []
        for user_id, messages in recovery_batches.items():
            user_batches = self._create_priority_batches(messages, user_id)
            all_batches.extend(user_batches)

        # Sort all batches by priority across all users (TIER_1 from all users first)
        priority_order = {
            MessagePriority.TIER_1: 1,
            MessagePriority.TIER_2: 2,
            MessagePriority.TIER_3: 3,
        }
        all_batches.sort(key=lambda b: priority_order[b.priority])

        # Process batches sequentially with proper delays
        for batch in all_batches:
            try:
                processed = await self._process_recovery_batch(batch)
                stats["messages_recovered"] += processed

                # Rate limiting delay between batches
                await asyncio.sleep(batch.batch_delay)

            except Exception as e:
                logger.error(f"❌ Error processing batch for user {batch.user_id}: {e}")
                stats["errors"] += 1

    async def _process_recovery_batch(self, batch: RecoveryBatch) -> int:
        """Process a batch of recovered messages through the AI pipeline."""
        logger.info(
            f"🔄 Processing {batch.priority.value} batch: {len(batch.messages)} messages for user {batch.user_id}"
        )

        processed_count = 0

        for message in batch.messages:
            try:
                # Rate limiting for Telegram API compliance
                async with self.telegram_rate_limiter:
                    # Add temporal context prefix for recovered messages
                    temporal_context = self._generate_temporal_context(message)
                    enhanced_message = f"{temporal_context}\n\n{message.message_text}"

                    # Process through supervisor agent (LLM pipeline)
                    review_item = await self.supervisor.process_message(
                        user_id=message.user_id,
                        message=enhanced_message,
                        context_override={
                            "is_recovered_message": True,
                            "original_date": message.telegram_date,
                        },
                    )

                    # Save to database with recovery tracking
                    interaction_id = await self.db.save_interaction_with_recovery_data(
                        review_item=review_item,
                        telegram_message_id=message.telegram_message_id,
                        telegram_date=message.telegram_date,
                        is_recovered=True,
                    )

                    processed_count += 1
                    logger.debug(
                        f"✅ Processed recovered message {message.telegram_message_id} -> {interaction_id}"
                    )

                    # Batch delay to avoid overwhelming the system
                    if batch.batch_delay > 0:
                        await asyncio.sleep(batch.batch_delay)

            except Exception as e:
                logger.error(
                    f"❌ Failed to process recovered message {message.telegram_message_id}: {e}"
                )
                continue

        logger.info(
            f"✅ Batch completed: {processed_count}/{len(batch.messages)} messages processed"
        )
        return processed_count

    def _generate_temporal_context(self, message: RecoveredMessage) -> str:
        """Generate temporal context prefix for recovered messages."""
        age_hours = message.age_hours

        if age_hours < 1:
            time_desc = f"{int(age_hours * 60)} minutes ago"
        elif age_hours < 24:
            time_desc = f"{int(age_hours)} hours ago"
        else:
            time_desc = f"{int(age_hours / 24)} days ago"

        return (
            f"[RECOVERED MESSAGE from {time_desc}] "
            f"This message was sent during system downtime and is being processed now. "
            f"Respond naturally as if you just received it, acknowledging the time gap if relevant."
        )

    async def manual_recovery_trigger(
        self, user_id: Optional[str] = None, max_messages: Optional[int] = None
    ) -> Dict[str, Any]:
        """Manually trigger recovery for specific user or all users."""
        logger.info(f"🔄 Manual recovery triggered for user: {user_id or 'ALL'}")

        operation_id = await self.db.start_recovery_operation(
            operation_type="manual",
            metadata={
                "user_id": user_id,
                "max_messages": max_messages,
                "triggered_at": datetime.now().isoformat(),
            },
        )

        try:
            if user_id:
                # Single user recovery
                cursor = await self.db.get_user_cursor(user_id)
                if not cursor:
                    raise ValueError(f"No cursor found for user {user_id}")

                stats = {
                    "users_checked": 0,
                    "messages_recovered": 0,
                    "messages_skipped": 0,
                    "errors": 0,
                }
                result = await self._recover_user_messages(cursor, stats)

                await self.db.update_recovery_operation(
                    operation_id=operation_id,
                    status="completed",
                    users_checked=1,
                    messages_recovered=result["recovered"],
                    messages_skipped=result["skipped"],
                    errors_encountered=result["errors"],
                )

                return {"operation_id": operation_id, "result": result}
            else:
                # Full recovery (similar to startup but manual)
                return await self.startup_recovery_check()

        except Exception as e:
            logger.error(f"❌ Manual recovery failed: {e}")
            await self.db.update_recovery_operation(
                operation_id=operation_id,
                status="failed",
                error_details={"error": str(e)},
            )
            raise

    async def get_recovery_status(self) -> Dict[str, Any]:
        """Get current recovery system status."""
        try:
            # Get basic recovery stats
            stats = await self.db.get_recovery_stats()

            # Get recent operations
            recent_ops = await self.db.get_recovery_operations(limit=10)

            # Get user cursor summary
            cursors = await self.db.get_all_user_cursors()
            cursor_summary = {
                "total_users": len(cursors),
                "users_with_recent_recovery": sum(
                    1
                    for c in cursors
                    if (datetime.now() - c["last_recovery_check"]).days < 1
                ),
                "oldest_recovery_check": min(c["last_recovery_check"] for c in cursors)
                if cursors
                else None,
            }

            return {
                "enabled": self.config.enabled,
                "config": self.config.to_dict(),
                "stats": stats,
                "recent_operations": recent_ops,
                "cursor_summary": cursor_summary,
                "status": "healthy",
            }

        except Exception as e:
            logger.error(f"❌ Error getting recovery status: {e}")
            return {"enabled": self.config.enabled, "status": "error", "error": str(e)}

    async def _check_protocol_silence_status(self, user_id: str) -> Dict[str, Any]:
        """Check if user is under PROTOCOLO DE SILENCIO (quarantined)."""
        try:
            # Get user protocol status from database
            protocol_status = await self.db.get_protocol_status(user_id)

            if not protocol_status:
                return {"is_quarantined": False, "status": "no_protocol"}

            is_active = protocol_status.get("is_active", False)
            return {
                "is_quarantined": is_active,
                "status": "active" if is_active else "inactive",
                "reason": protocol_status.get("reason"),
                "activated_at": protocol_status.get("activated_at"),
                "messages_quarantined": protocol_status.get("messages_quarantined", 0),
            }

        except Exception as e:
            logger.error(f"❌ Error checking protocol status for user {user_id}: {e}")
            # Default to allow recovery if we can't check protocol status
            return {"is_quarantined": False, "status": "error", "error": str(e)}

    async def _apply_enhanced_rate_limiting(self):
        """Enhanced rate limiting with circuit breaker pattern."""
        current_time = asyncio.get_event_loop().time()

        # Basic rate limiting (existing)
        time_since_last = current_time - self.last_telegram_request
        if time_since_last < self.min_request_interval:
            sleep_time = self.min_request_interval - time_since_last
            await asyncio.sleep(sleep_time)

        # Update last request time
        self.last_telegram_request = asyncio.get_event_loop().time()

        # Circuit breaker logic could be added here for error rates

    async def _process_recovery_batch_with_enhanced_controls(
        self, batch: RecoveryBatch
    ) -> int:
        """Enhanced batch processing with better controls and error handling."""
        logger.info(
            f"🔄 Processing {batch.priority.value} batch: {len(batch.messages)} messages for user {batch.user_id}"
        )

        processed_count = 0
        consecutive_errors = 0
        max_consecutive_errors = 3

        for i, message in enumerate(batch.messages):
            try:
                # Enhanced rate limiting
                await self._apply_enhanced_rate_limiting()

                # Check if we should continue processing this batch
                if consecutive_errors >= max_consecutive_errors:
                    logger.warning(
                        f"❌ Too many consecutive errors ({consecutive_errors}) for batch {batch.priority.value}, stopping"
                    )
                    break

                # Add temporal context prefix for recovered messages
                temporal_context = self._generate_temporal_context(message)
                enhanced_message = f"{temporal_context}\n\n{message.message_text}"

                # Process through supervisor agent (LLM pipeline)
                review_item = await self.supervisor.process_message(
                    user_id=message.user_id,
                    message=enhanced_message,
                    context_override={
                        "is_recovered_message": True,
                        "original_date": message.telegram_date,
                        "recovery_priority": message.priority.value,
                    },
                )

                # Save to database with recovery tracking
                interaction_id = await self.db.save_interaction_with_recovery_data(
                    review_item=review_item,
                    telegram_message_id=message.telegram_message_id,
                    telegram_date=message.telegram_date,
                    is_recovered=True,
                )

                processed_count += 1
                consecutive_errors = 0  # Reset error counter on success
                logger.debug(
                    f"✅ Processed recovered message {message.telegram_message_id} -> {interaction_id}"
                )

                # Dynamic batch delay based on priority and position in batch
                delay = self._calculate_dynamic_delay(batch, i, len(batch.messages))
                if delay > 0:
                    await asyncio.sleep(delay)

            except Exception as e:
                consecutive_errors += 1
                logger.error(
                    f"❌ Failed to process recovered message {message.telegram_message_id}: {e}"
                )

                # Exponential backoff for errors
                if consecutive_errors <= max_consecutive_errors:
                    backoff_delay = min(2**consecutive_errors, 10)  # Max 10 seconds
                    await asyncio.sleep(backoff_delay)

                continue

        logger.info(
            f"✅ Batch completed: {processed_count}/{len(batch.messages)} messages processed"
        )
        return processed_count

    def _calculate_dynamic_delay(
        self, batch: RecoveryBatch, current_index: int, total_messages: int
    ) -> float:
        """Calculate dynamic delay based on batch priority and processing progress."""
        base_delay = batch.batch_delay

        # Reduce delay as we progress through the batch (front-loaded processing)
        progress_factor = (
            1.0 - (current_index / total_messages) * 0.3
        )  # Up to 30% reduction

        # Add small random jitter to avoid thundering herd
        import random

        jitter = random.uniform(0.8, 1.2)

        return base_delay * progress_factor * jitter
