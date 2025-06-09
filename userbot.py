# userbot.py
"""Punto de entrada principal del bot de Telegram."""
import asyncio
import json
import logging
from datetime import datetime

import redis.asyncio as redis
from telethon import TelegramClient, events

from agents.supervisor_agent import SupervisorAgent
from cognition.cognitive_controller import CognitiveController
from llms.openai_client import OpenAIClient
from memory.user_memory import UserMemoryManager
from utils.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class UserBot:
    """Cliente principal de Telegram que maneja eventos de mensajes."""

    def __init__(self, config: Config):
        """Inicializa el bot con la configuración dada."""
        self.config = config
        self.client = TelegramClient(
            'bot_session',
            config.api_id,
            config.api_hash
        )

        # Inicializar componentes
        self.memory = UserMemoryManager(config.redis_url)
        self.llm = OpenAIClient(config.openai_api_key, config.openai_model)
        self.supervisor = SupervisorAgent(self.llm, self.memory)
        self.cognitive_controller = CognitiveController()

        # Redis para WAL
        self.redis_url = config.redis_url
        self._redis = None

        # Cola de mensajes WAL
        self.message_queue_key = "nadia_message_queue"
        self.processing_key = "nadia_processing"

    async def _get_redis(self):
        """Obtiene o crea la conexión a Redis."""
        if not self._redis:
            self._redis = await redis.from_url(self.redis_url)
        return self._redis

    async def start(self):
        """Inicia la conexión con Telegram y configura handlers."""
        await self.client.start(phone=self.config.phone_number)
        logger.info("Bot iniciado correctamente")

        # Iniciar procesador de cola WAL
        asyncio.create_task(self._process_wal_queue())

        # Registrar handler para mensajes privados
        @self.client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
        async def handle_message(event):
            await self._enqueue_message(event)

        # Mantener el bot corriendo
        await self.client.run_until_disconnected()

    async def cleanup(self):
        """Limpia recursos antes de cerrar."""
        try:
            # Cerrar conexión Redis
            if self._redis:
                await self._redis.aclose()

            # Cerrar memoria
            await self.memory.close()

            logger.info("Recursos liberados correctamente")
        except Exception as e:
            logger.error(f"Error durante limpieza: {e}")

    async def _enqueue_message(self, event):
        """Encola un mensaje en el WAL para procesamiento robusto."""
        try:
            r = await self._get_redis()

            # Preparar datos del mensaje
            message_data = {
                'user_id': str(event.sender_id),
                'message': event.text,
                'chat_id': event.chat_id,
                'message_id': event.message.id,
                'timestamp': datetime.now().isoformat()
            }

            # Añadir a la cola WAL
            await r.lpush(self.message_queue_key, json.dumps(message_data))
            logger.info(f"Mensaje encolado en WAL de usuario {message_data['user_id']}")

        except Exception as e:
            logger.error(f"Error encolando mensaje en WAL: {e}")
            # En caso de fallo crítico, procesar directamente
            await self._handle_message_direct(event)

    async def _process_wal_queue(self):
        """Procesa mensajes de la cola WAL de forma continua."""
        logger.info("Iniciando procesador de cola WAL")
        r = await self._get_redis()

        while True:
            try:
                # Bloquear esperando mensajes (timeout de 1 segundo)
                result = await r.brpop(self.message_queue_key, timeout=1)

                if result:
                    _, message_json = result
                    message_data = json.loads(message_json)

                    # Marcar como en procesamiento
                    await r.set(
                        f"{self.processing_key}:{message_data['user_id']}",
                        message_json,
                        ex=300  # Expira en 5 minutos
                    )

                    # Procesar mensaje
                    await self._process_message(message_data)

                    # Limpiar marca de procesamiento
                    await r.delete(f"{self.processing_key}:{message_data['user_id']}")

            except Exception as e:
                logger.error(f"Error en procesador WAL: {e}")
                await asyncio.sleep(1)

    async def _process_message(self, message_data: dict):
        """Procesa un mensaje desde el WAL."""
        try:
            user_id = message_data['user_id']
            message = message_data['message']
            chat_id = message_data['chat_id']

            logger.info(f"Procesando mensaje WAL de {user_id}: {message}")

            # Decidir ruta con el Controlador Cognitivo
            route = self.cognitive_controller.route_message(message)

            if route == 'fast_path':
                # Procesar comando rápido
                response = await self._handle_fast_path(message)
            else:
                # Procesar con el supervisor (vía lenta)
                response = await self.supervisor.process_message(user_id, message)

            # Enviar respuesta
            await self.client.send_message(chat_id, response)
            logger.info(f"Respuesta enviada por ruta {route}: {response[:50]}...")

        except Exception as e:
            logger.error(f"Error procesando mensaje del WAL: {e}")
            # Enviar mensaje de contingencia mejorado
            try:
                await self.client.send_message(
                    message_data['chat_id'],
                    "Uf, perdona si tardo un poco... de repente siento que todo el mundo "
                    "me está hablando a la vez y mi cabeza va a mil. Dame un segundito "
                    "para poner mis ideas en orden. 😅"
                )
            except Exception as send_error:
                logger.error(f"No se pudo enviar mensaje de contingencia: {send_error}")

    async def _handle_fast_path(self, message: str) -> str:
        """Maneja comandos de vía rápida."""
        message_lower = message.lower().strip()

        # Respuestas predefinidas para comandos
        fast_responses = {
            '/ayuda': (
                "🌟 ¡Hola! Soy Nadia, tu asistente conversacional.\n\n"
                "Puedes hablarme de forma natural o usar estos comandos:\n"
                "• /ayuda - Ver este mensaje\n"
                "• /estado - Ver mi estado actual\n"
                "• /version - Ver mi versión\n\n"
                "¡Cuéntame en qué puedo ayudarte! 💫"
            ),
            '/help': "Same as /ayuda 😊",
            '/estado': "✨ Estado: Funcionando perfectamente\n🧠 Memoria: Activa\n💬 Modo: Conversacional",
            '/status': "Same as /estado 🎯",
            '/version': "🤖 Nadia v0.2.0 - Sprint 2\n🧠 Arquitectura de Conciencia Adaptativa",
            '/start': "¡Hola! 👋 Soy Nadia. ¿En qué puedo ayudarte hoy?",
            '/stop': "¡Hasta pronto! 👋 Fue un placer conversar contigo.",
            '/comandos': "Usa /ayuda para ver todos los comandos disponibles 📋"
        }

        return fast_responses.get(message_lower, "Comando no reconocido. Usa /ayuda para ver los comandos disponibles.")

    async def _handle_message_direct(self, event):
        """Manejo directo de mensajes (fallback sin WAL)."""
        try:
            user_id = str(event.sender_id)
            message = event.text

            logger.warning(f"Procesando mensaje sin WAL de {user_id}: {message}")

            # Procesar mensaje con el supervisor
            response = await self.supervisor.process_message(user_id, message)

            # Enviar respuesta
            await event.reply(response)
            logger.info(f"Respuesta directa enviada: {response}")

        except Exception as e:
            logger.error(f"Error procesando mensaje directo: {e}")
            await event.reply(
                "Uf, perdona si tardo un poco... de repente siento que todo el mundo "
                "me está hablando a la vez y mi cabeza va a mil. Dame un segundito "
                "para poner mis ideas en orden. 😅"
            )


async def main():
    """Función principal."""
    config = Config.from_env()
    bot = UserBot(config)

    try:
        await bot.start()
    finally:
        await bot.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
