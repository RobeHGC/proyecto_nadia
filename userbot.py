# userbot.py
"""Main entry point for the Telegram bot."""
import asyncio
import contextlib
import json
from datetime import datetime

from telethon import TelegramClient, events

from agents.supervisor_agent import ReviewItem, SupervisorAgent
from cognition.cognitive_controller import CognitiveController
from cognition.constitution import Constitution
from database.models import DatabaseManager
from llms.openai_client import OpenAIClient
from memory.user_memory import UserMemoryManager
from utils.config import Config
from utils.constants import TYPING_DEBOUNCE_DELAY
from utils.datetime_helpers import now_iso
from utils.entity_resolver import EntityResolver
from utils.error_handling import handle_errors
from utils.logging_config import get_logger
from utils.redis_mixin import RedisConnectionMixin
from utils.typing_simulator import TypingSimulator
from utils.user_activity_tracker import UserActivityTracker

logger = get_logger(__name__)


class UserBot(RedisConnectionMixin):
    """Main Telegram client that handles message events."""

    def __init__(self, config: Config):
        super().__init__()
        self.config = config

        # Telegram
        self.client = TelegramClient("bot_session", config.api_id, config.api_hash)

        # Internal components
        self.memory = UserMemoryManager(config.redis_url)
        self.llm = OpenAIClient(config.openai_api_key, config.openai_model)
        self.supervisor = SupervisorAgent(self.llm, self.memory, config)
        self.cognitive_controller = CognitiveController()
        self.constitution = Constitution()
        self.db_manager = DatabaseManager(config.database_url)
        
        # Configure db_manager in supervisor for nickname access
        self.supervisor.set_db_manager(self.db_manager)
        self.message_queue_key = "nadia_message_queue"
        self.processing_key = "nadia_processing"

        # HITL Review Queue
        self.review_queue_key = "nadia_review_queue"  # Sorted set for priority
        self.review_items_key = "nadia_review_items"  # Hash for ReviewItem data
        self.approved_messages_key = "nadia_approved_messages"  # List for approved messages to send
        
        # Typing simulation
        self.typing_simulator = None  # Will be initialized after client start
        
        # Entity resolution
        self.entity_resolver = None  # Will be initialized after client start
        
        # Adaptive Window Message Pacing
        self.activity_tracker = None  # Will be initialized after client start

    # ────────────────────────────────
    # Redis Helpers
    # ────────────────────────────────

    # ────────────────────────────────
    # Main Flow
    # ────────────────────────────────
    async def start(self):
        """Starts the bot and WAL worker."""
        await self.client.start(phone=self.config.phone_number)
        await self.db_manager.initialize()  # NUEVO: Initialize database
        
        # Initialize entity resolver and warm up cache
        self.entity_resolver = EntityResolver(self.client, cache_size=self.config.entity_cache_size)
        resolved_count = await self.entity_resolver.warm_up_from_dialogs(limit=self.config.entity_warm_up_dialogs)
        logger.info(f"Entity resolver initialized with {resolved_count} cached entities")
        
        self.typing_simulator = TypingSimulator(self.client)  # Initialize typing simulator
        self.typing_simulator.set_entity_resolver(self.entity_resolver)  # Connect entity resolver
        self.activity_tracker = UserActivityTracker(self.config.redis_url, self.config)  # Initialize activity tracker
        logger.info("Bot started successfully")
        
        if self.config.enable_typing_pacing:
            logger.info("Adaptive Window Message Pacing enabled")
        else:
            logger.info("Adaptive Window Message Pacing disabled - using original processing")

        self.wal_task = asyncio.create_task(self._process_wal_queue())
        self.approved_task = asyncio.create_task(self._process_approved_messages())

        @self.client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
        async def _(event):  # noqa: D401,  WPS122
            await self._handle_incoming_message(event)
        
        # Add typing event handler for adaptive window pacing
        @self.client.on(events.ChatAction(func=lambda e: e.is_private))
        async def handle_typing(event):  # noqa: D401,  WPS122
            if self.activity_tracker:
                await self.activity_tracker.handle_typing_event(event)

        try:
            await self.client.run_until_disconnected()
        finally:
            self.wal_task.cancel()
            self.approved_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.wal_task
                await self.approved_task
            await self.memory.close()
            await self.db_manager.close()  # NUEVO: Close database
            if self.activity_tracker:
                await self.activity_tracker.close()  # Close activity tracker

    # ────────────────────────────────
    # Message Handling with Adaptive Window
    # ────────────────────────────────
    async def _handle_incoming_message(self, event):
        """Handle incoming message with adaptive window logic or fallback to original."""
        # Cache entity from event immediately (when it's available)
        if self.entity_resolver and hasattr(event, 'sender'):
            try:
                # Cache the entity directly from the event
                self.entity_resolver.entity_cache[event.sender_id] = event.sender
                logger.debug(f"Cached entity for user {event.sender_id} from event")
            except Exception as e:
                logger.warning(f"Failed to cache entity from event for {event.sender_id}: {e}")
                # Fallback to background preloading
                asyncio.create_task(
                    self.entity_resolver.preload_entity_for_message(event.sender_id)
                )
        
        if self.config.enable_typing_pacing and self.activity_tracker:
            # Try adaptive window processing
            handled = await self.activity_tracker.handle_message(event, self._enqueue_message)
            if handled:
                return  # Successfully handled by adaptive window
        
        # Fallback to original processing
        await self._enqueue_message(event)
    
    # ────────────────────────────────
    # WAL Enqueue (Original)
    # ────────────────────────────────
    async def _enqueue_message(self, event_or_data, is_batch=False):
        """Adds message to WAL before processing."""
        try:
            r = await self._get_redis()
            
            if is_batch:
                # Handle batch data directly
                message_data = event_or_data
                logger.info("Batch message enqueued in WAL from user %s (batch size: %d)", 
                           message_data["user_id"], message_data.get("batch_size", 1))
            else:
                # Handle regular event
                event = event_or_data
                message_data = {
                    "user_id": str(event.sender_id),
                    "message": event.text,
                    "chat_id": event.chat_id,
                    "message_id": event.message.id,
                    "timestamp": now_iso(),
                }
                logger.info("Message enqueued in WAL from user %s", message_data["user_id"])
            
            await r.lpush(self.message_queue_key, json.dumps(message_data))
            
        except Exception as exc:  # pragma: no cover
            logger.error("Error enqueuing message in WAL: %s", exc)
            if not is_batch:
                await self._handle_message_direct(event_or_data)

    # ────────────────────────────────
    # WAL Worker
    # ────────────────────────────────
    async def _process_wal_queue(self):
        """Continuously consumes the WAL queue."""
        logger.info("Starting WAL queue processor")
        r = await self._get_redis()

        try:
            while True:
                _, raw = await r.brpop(self.message_queue_key, timeout=1) or (None, None)
                if not raw:
                    await asyncio.sleep(0.1)
                    continue

                data = json.loads(raw)
                await r.set(
                    f"{self.processing_key}:{data['user_id']}",
                    raw,
                    ex=300,
                )

                await self._process_message(data)
                await r.delete(f"{self.processing_key}:{data['user_id']}")
        except asyncio.CancelledError:
            logger.info("WAL worker stopped")
            raise
        finally:
            await self.memory.close()

    # ────────────────────────────────
    # Approved Messages Worker
    # ────────────────────────────────
    async def _process_approved_messages(self):
        """Continuously processes approved messages from dashboard for sending."""
        logger.info("Starting approved messages processor")
        r = await self._get_redis()

        try:
            while True:
                # Check for approved messages to send
                _, raw = await r.brpop(self.approved_messages_key, timeout=1) or (None, None)
                if not raw:
                    await asyncio.sleep(0.1)
                    continue

                try:
                    data = json.loads(raw)
                    review_id = data["review_id"]
                    bubbles = data["bubbles"]
                    
                    # Get user info from review data
                    # First try to get from current review items
                    review_data_json = await r.hget(self.review_items_key, review_id)
                    if review_data_json:
                        review_data = json.loads(review_data_json)
                        user_id = review_data["user_id"]
                        
                        # Send with realistic typing cadence
                        if self.typing_simulator:
                            # Get previous user message for reading time simulation
                            previous_message = review_data.get("user_message", "")
                            await self.typing_simulator.simulate_human_cadence(
                                int(user_id), bubbles, previous_message
                            )
                        else:
                            # Fallback: Send each bubble as a separate message
                            for bubble in bubbles:
                                await self.client.send_message(int(user_id), bubble)
                                await asyncio.sleep(0.5)  # Small delay between bubbles
                        
                        logger.info("Approved message sent to user %s: %d bubbles", user_id, len(bubbles))
                        
                        # 🆕 CRITICAL FIX: Guardar respuesta del bot en historial
                        # Combine bubbles into single response for history
                        combined_response = " ".join(bubbles)
                        await self.memory.add_to_conversation_history(user_id, {
                            "role": "assistant",
                            "content": combined_response,
                            "timestamp": now_iso(),
                            "bubbles": bubbles  # Keep original bubbles for reference
                        })
                        logger.info(f"Bot response saved to conversation history for user {user_id}")
                    else:
                        # Try to get user info from database if not in Redis
                        database_mode = getattr(self.config, 'database_mode', 'normal')
                        if database_mode != "skip":
                            try:
                                review = await self.db_manager.get_interaction(review_id)
                                if review:
                                    user_id = review["user_id"]
                                    # Send with realistic typing cadence
                                    if self.typing_simulator:
                                        previous_message = review.get("user_message", "")
                                        await self.typing_simulator.simulate_human_cadence(
                                            int(user_id), bubbles, previous_message
                                        )
                                    else:
                                        # Fallback: Send each bubble as a separate message
                                        for bubble in bubbles:
                                            await self.client.send_message(int(user_id), bubble)
                                            await asyncio.sleep(0.5)  # Small delay between bubbles
                                    
                                    logger.info("Approved message sent to user %s: %d bubbles", user_id, len(bubbles))
                                    
                                    # 🆕 CRITICAL FIX: Guardar respuesta del bot en historial
                                    await self.memory.add_to_conversation_history(user_id, {
                                        "role": "assistant",
                                        "content": " ".join(bubbles),
                                        "timestamp": now_iso()
                                    })
                                else:
                                    logger.error("Review %s not found in database", review_id)
                            except Exception as e:
                                logger.error("Error getting review from database: %s", e)
                        else:
                            logger.error("Review %s not found and database mode is skip", review_id)
                
                except Exception as e:
                    logger.error("Error processing approved message: %s", e)
                    logger.error("Message data: %s", raw)

        except asyncio.CancelledError:
            logger.info("Approved messages worker stopped")
            raise
        except Exception as e:
            logger.error("Error in approved messages worker: %s", e)

    # ────────────────────────────────
    # Message Processing - HITL Mode
    # ────────────────────────────────
    async def _process_message(self, msg: dict):
        """Processes a message from the WAL - HITL version."""
        try:
            route = self.cognitive_controller.route_message(msg["message"])

            if route == "fast_path":
                # Fast path commands with minimal typing simulation
                response = await self._handle_fast_path(msg["message"], msg["user_id"])
                
                # Add minimal typing delay to maintain naturalness
                if self.typing_simulator:
                    await self.typing_simulator.simulate_human_cadence(
                        msg["chat_id"], [response], msg["message"]
                    )
                else:
                    # Fallback: small delay
                    await asyncio.sleep(1.0)
                    await self.client.send_message(msg["chat_id"], response)
                
                logger.info("Fast path response sent: %.50s…", response)
            else:
                # Slow path: Queue for human review instead of sending
                review_item = await self.supervisor.process_message(
                    msg["user_id"], msg["message"]
                )

                # Add chat_id to the review item for sending later
                review_item.conversation_context["chat_id"] = msg["chat_id"]

                # Queue the review item
                await self._queue_for_review(review_item)
                logger.info("Message queued for review: %s (priority: %.2f)",
                           review_item.id, review_item.priority)

        except Exception as exc:  # pragma: no cover
            logger.error("Error processing WAL message: %s", exc)
            # No enviar mensajes enlatados - prohibido para mantener naturalidad

    # ────────────────────────────────
    # HITL Review Queue Management
    # ────────────────────────────────
    async def _queue_for_review(self, review_item: ReviewItem):
        """Queue a ReviewItem for human review."""
        try:
            r = await self._get_redis()

            # Serialize ReviewItem to JSON
            review_data = {
                "id": review_item.id,
                "user_id": review_item.user_id,
                "user_message": review_item.user_message,
                "ai_suggestion": {
                    "llm1_raw": review_item.ai_suggestion.llm1_raw,
                    "llm2_bubbles": review_item.ai_suggestion.llm2_bubbles,
                    "constitution_analysis": {
                        "flags": review_item.ai_suggestion.constitution_analysis.flags,
                        "risk_score": review_item.ai_suggestion.constitution_analysis.risk_score,
                        "recommendation": review_item.ai_suggestion.constitution_analysis.recommendation.value,
                        "violations": review_item.ai_suggestion.constitution_analysis.violations
                    },
                    "tokens_used": review_item.ai_suggestion.tokens_used,
                    "generation_time": review_item.ai_suggestion.generation_time,
                    # Multi-LLM tracking fields
                    "llm1_model": review_item.ai_suggestion.llm1_model,
                    "llm2_model": review_item.ai_suggestion.llm2_model,
                    "llm1_cost": review_item.ai_suggestion.llm1_cost,
                    "llm2_cost": review_item.ai_suggestion.llm2_cost
                },
                "priority": review_item.priority,
                "timestamp": review_item.timestamp.isoformat(),
                "conversation_context": review_item.conversation_context
            }

            # Store in hash (for retrieval)
            await r.hset(self.review_items_key, review_item.id, json.dumps(review_data))

            # Add to chronological queue (sorted set by timestamp - newest first)
            timestamp_score = review_item.timestamp.timestamp()
            await r.zadd(self.review_queue_key, {review_item.id: timestamp_score})

            # NUEVO: Also save to PostgreSQL for dashboard
            try:
                db_id = await self.db_manager.save_interaction(review_item)
                logger.info("ReviewItem %s saved to database with ID %s", review_item.id, db_id)
            except Exception as db_exc:
                logger.error("Error saving to database: %s", db_exc)
                # Continue with Redis-only operation

            logger.info("ReviewItem %s queued chronologically at %s", review_item.id, review_item.timestamp.isoformat())

        except Exception as exc:
            logger.error("Error queueing review item: %s", exc)

    async def send_approved_message(self, review_id: str, approved_bubbles: list):
        """Send approved message bubbles to user."""
        try:
            r = await self._get_redis()

            # Get review item data
            review_data_json = await r.hget(self.review_items_key, review_id)
            if not review_data_json:
                logger.error("Review item %s not found", review_id)
                return False

            review_data = json.loads(review_data_json)
            chat_id = review_data["conversation_context"]["chat_id"]

            # Send with realistic typing cadence
            non_empty_bubbles = [bubble.strip() for bubble in approved_bubbles if bubble.strip()]
            if self.typing_simulator:
                # Get user message for reading time simulation
                user_message = review_data.get("user_message", "")
                await self.typing_simulator.simulate_human_cadence(
                    chat_id, non_empty_bubbles, user_message
                )
            else:
                # Fallback: Send each bubble as separate message
                for bubble in non_empty_bubbles:
                    await self.client.send_message(chat_id, bubble)
                    await asyncio.sleep(0.5)  # Small delay between bubbles

            # Clean up from queue
            await r.zrem(self.review_queue_key, review_id)
            await r.hdel(self.review_items_key, review_id)

            logger.info("Approved message sent for review %s", review_id)
            return True

        except Exception as exc:
            logger.error("Error sending approved message: %s", exc)
            return False

    # ────────────────────────────────
    # Constitution Violation Logging
    # ────────────────────────────────
    async def _log_constitution_violation(self, user_id: str, user_message: str, blocked_response: str):
        """Logs Constitution violations for analysis and metrics."""
        try:
            r = await self._get_redis()
            violation_data = {
                "user_id": user_id,
                "user_message": user_message[:200],  # Truncate for privacy
                "blocked_response": blocked_response[:200],
                "timestamp": now_iso()
            }

            # Store in Redis with expiration for privacy
            violation_key = f"constitution_violation:{user_id}:{datetime.now().timestamp()}"
            await r.set(
                violation_key,
                json.dumps(violation_data),
                ex=86400 * 7  # Keep for 7 days for analysis
            )

            # Increment violation counter for metrics
            await r.incr(f"constitution_violations:count:{user_id}")
            await r.incr("constitution_violations:total")

        except Exception as exc:
            logger.error("Error logging constitution violation: %s", exc)

    # ────────────────────────────────
    # Fast-path (English)
    # ────────────────────────────────
    async def _handle_fast_path(self, message: str, user_id: str = None) -> str:
        """Handles simple commands."""
        m = message.lower().strip()
        
        # Restrict quick commands to specific admin user ID
        admin_user_id = "7833076816"
        if user_id and user_id != admin_user_id and m in ["/status", "/commands"]:
            # Return natural response for non-admin users on restricted commands
            return "hey! what's up? 😊"
        
        fast = {
            "/help": (
                "🌟 Hey! I'm Nadia, your chat buddy here.\n\n"
                "Just talk to me naturally or use:\n"
                "• /help - This message\n"
                "• /status - Check my status\n\n"
                "What's on your mind? 💭"
            ),
            "/start": "Hey there! 👋 I'm Nadia. What's up?",
            "/stop": "Bye for now! 👋 Hit me up anytime!",
            "/status": "✨ All good here!\n🧠 Memory: Active\n💬 Mode: Chatty",
            "/commands": "Check /help for what I can do 📋",
        }
        return fast.get(m, "Command not recognized. Use /help to see available commands.")

    # ────────────────────────────────
    # Direct Fallback (without WAL) - HITL Mode
    # ────────────────────────────────
    async def _handle_message_direct(self, event):
        try:
            user_id = str(event.sender_id)
            message = event.text

            logger.warning("Processing message without WAL from user %s", user_id)

            # Check if it's a fast path command first
            route = self.cognitive_controller.route_message(message)

            if route == "fast_path":
                response = await self._handle_fast_path(message, user_id)
                
                # Add minimal typing delay to maintain naturalness
                if self.typing_simulator:
                    await self.typing_simulator.simulate_human_cadence(
                        event.chat_id, [response], message
                    )
                else:
                    # Fallback: small delay
                    await asyncio.sleep(1.0)
                    await event.reply(response)
                
                logger.info("Direct fast path response sent: %.50s...", response)
            else:
                # Process with supervisor to get ReviewItem
                review_item = await self.supervisor.process_message(user_id, message)

                # Add chat_id for direct messages
                review_item.conversation_context["chat_id"] = event.chat_id

                # Queue for review (same as WAL path)
                await self._queue_for_review(review_item)
                logger.info("Direct message queued for review: %s", review_item.id)

        except Exception as exc:  # pragma: no cover
            logger.error("Error processing direct message: %s", exc)
            # No enviar mensajes enlatados - prohibido para mantener naturalidad


# ────────────────────────────────
# Bootstrap
# ────────────────────────────────
async def main():
    cfg = Config.from_env()
    await UserBot(cfg).start()


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
