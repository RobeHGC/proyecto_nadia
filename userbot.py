# userbot.py
"""Punto de entrada principal del bot de Telegram."""
import asyncio
import logging

from telethon import TelegramClient, events

from agents.supervisor_agent import SupervisorAgent
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

    async def start(self):
        """Inicia la conexión con Telegram y configura handlers."""
        await self.client.start(phone=self.config.phone_number)
        logger.info("Bot iniciado correctamente")

        # Registrar handler para mensajes privados
        @self.client.on(events.NewMessage(incoming=True, func=lambda e: e.is_private))
        async def handle_message(event):
            await self._handle_message(event)

        # Mantener el bot corriendo
        await self.client.run_until_disconnected()

    async def _handle_message(self, event):
        """Procesa mensajes entrantes."""
        try:
            user_id = str(event.sender_id)
            message = event.text

            logger.info(f"Mensaje recibido de {user_id}: {message}")

            # Procesar mensaje con el supervisor
            response = await self.supervisor.process_message(user_id, message)

            # Enviar respuesta
            await event.reply(response)
            logger.info(f"Respuesta enviada: {response}")

        except Exception as e:
            logger.error(f"Error procesando mensaje: {e}")
            await event.reply("Lo siento, ocurrió un error. ¿Podrías repetir?")
async def main():
    """Función principal."""
    config = Config.from_env()
    bot = UserBot(config)
    await bot.start()
if __name__ == "__main__":
    asyncio.run(main())
