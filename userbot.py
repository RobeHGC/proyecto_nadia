# userbot.py
"""Main entry point for the Telegram bot."""
import asyncio
import contextlib
import json
import logging
from datetime import datetime

import redis.asyncio as redis
from telethon import TelegramClient, events

from agents.supervisor_agent import SupervisorAgent
from cognition.cognitive_controller import CognitiveController
from cognition.constitution import Constitution  # NUEVO: Import Constitution
from llms.openai_client import OpenAIClient
from memory.user_memory import UserMemoryManager
from utils.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class UserBot:
    """Main Telegram client that handles message events."""

    def __init__(self, config: Config):
        self.config = config

        # Telegram
        self.client = TelegramClient("bot_session", config.api_id, config.api_hash)

        # Internal components
        self.memory = UserMemoryManager(config.redis_url)
        self.llm = OpenAIClient(config.openai_api_key, config.openai_model)
        self.supervisor = SupervisorAgent(self.llm, self.memory)
        self.cognitive_controller = CognitiveController()
        self.constitution = Constitution()  # NUEVO: Initialize Constitution

        # Redis / WAL
        self.redis_url = config.redis_url
        self._redis: redis.Redis | None = None
        self.message_queue_key = "nadia_message_queue"
        self.processing_key = "nadia_processing"

    # ────────────────────────────────
    # Redis Helpers
    # ────────────────────────────────
    async def _get_redis(self) -> redis.Redis:
        if not self._redis:
            self._redis = await redis.from_url(self.redis_url)
        return self._redis

    # ────────────────────────────────
    # Main Flow
    # ────────────────────────────────
    async def start(self):
        """Starts the bot and WAL worker."""
        await self.client.start(phone=self.config.phone_number)
        logger.info("Bot started successfully")

        wal_worker = asyncio.create_task(self._process_wal_queue())

        @self.client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
        async def _(event):  # noqa: D401,  WPS122
            await self._enqueue_message(event)

        try:
            await self.client.run_until_disconnected()
        finally:
            wal_worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await wal_worker
            await self.memory.close()

    # ────────────────────────────────
    # WAL Enqueue
    # ────────────────────────────────
    async def _enqueue_message(self, event):
        """Adds message to WAL before processing."""
        try:
            r = await self._get_redis()
            message_data = {
                "user_id": str(event.sender_id),
                "message": event.text,
                "chat_id": event.chat_id,
                "message_id": event.message.id,
                "timestamp": datetime.now().isoformat(),
            }
            await r.lpush(self.message_queue_key, json.dumps(message_data))
            logger.info("Message enqueued in WAL from user %s", message_data["user_id"])
        except Exception as exc:  # pragma: no cover
            logger.error("Error enqueuing message in WAL: %s", exc)
            await self._handle_message_direct(event)

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
    # Message Processing with Constitution
    # ────────────────────────────────
    async def _process_message(self, msg: dict):
        """Processes a message from the WAL."""
        try:
            route = self.cognitive_controller.route_message(msg["message"])

            if route == "fast_path":
                response = await self._handle_fast_path(msg["message"])
            else:
                # Slow path: get response from supervisor
                response = await self.supervisor.process_message(
                    msg["user_id"], msg["message"]
                )

                # NUEVO: Validate response with Constitution
                if not self.constitution.validate(response):
                    logger.warning(
                        "Constitution blocked response for user %s. Original: %.100s...",
                        msg["user_id"],
                        response
                    )
                    # Use safe response instead
                    response = self.constitution.get_safe_response()

                    # Log violation for metrics
                    await self._log_constitution_violation(
                        msg["user_id"],
                        msg["message"],
                        response
                    )

            await self.client.send_message(msg["chat_id"], response)
            logger.info("Response sent via %s: %.50s…", route, response)

        except Exception as exc:  # pragma: no cover
            logger.error("Error processing WAL message: %s", exc)
            await self.client.send_message(
                msg["chat_id"],
                "Sorry, I'm experiencing high volume right now. "
                "Give me just a moment to catch up! 😅",
            )

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
                "timestamp": datetime.now().isoformat()
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
    async def _handle_fast_path(self, message: str) -> str:
        """Handles simple commands."""
        m = message.lower().strip()
        fast = {
            "/help": (
                "🌟 Hello! I'm Nadia, your conversational assistant.\n\n"
                "You can talk to me naturally or use these commands:\n"
                "• /help - Show this message\n"
                "• /status - Check my current status\n"
                "• /version - See my version\n\n"
                "What can I help you with today? 💫"
            ),
            "/ayuda": "Same as /help 😊",
            "/status": "✨ Status: Working perfectly\n🧠 Memory: Active\n💬 Mode: Conversational",
            "/estado": "Same as /status 🎯",
            "/version": "🤖 Nadia v0.2.0 - Sprint 2\n🧠 Adaptive Consciousness Architecture",
            "/start": "Hello! 👋 I'm Nadia. How can I help you today?",
            "/stop": "Goodbye! 👋 It was a pleasure talking with you.",
            "/commands": "Use /help to see all available commands 📋",
        }
        return fast.get(m, "Command not recognized. Use /help to see available commands.")

    # ────────────────────────────────
    # Direct Fallback (without WAL)
    # ────────────────────────────────
    async def _handle_message_direct(self, event):
        try:
            user_id = str(event.sender_id)
            message = event.text

            logger.warning("Processing message without WAL from user %s", user_id)

            # Check if it's a fast path command first
            route = self.cognitive_controller.route_message(message)

            if route == "fast_path":
                response = await self._handle_fast_path(message)
            else:
                # Process with supervisor
                response = await self.supervisor.process_message(user_id, message)

                # NUEVO: Validate with Constitution even in direct path
                if not self.constitution.validate(response):
                    logger.warning(
                        "Constitution blocked direct response for user %s",
                        user_id
                    )
                    response = self.constitution.get_safe_response()

            await event.reply(response)
            logger.info("Direct response sent: %.50s...", response)

        except Exception as exc:  # pragma: no cover
            logger.error("Error processing direct message: %s", exc)
            await event.reply(
                "Sorry, I'm experiencing high volume right now. "
                "Give me just a moment to catch up! 😅"
            )


# ────────────────────────────────
# Bootstrap
# ────────────────────────────────
async def main():
    cfg = Config.from_env()
    await UserBot(cfg).start()


if __name__ == "__main__":  # pragma: no cover
    asyncio.run(main())
