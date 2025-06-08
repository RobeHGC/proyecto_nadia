# utils/config.py
"""Configuración centralizada del proyecto."""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    """Configuración de la aplicación."""
    # Telegram
    api_id: int
    api_hash: str
    phone_number: str
    
    # OpenAI
    openai_api_key: str
    openai_model: str = "gpt-3.5-turbo"
    
    # Redis
    redis_url: str
    
    # App
    debug: bool = False
    log_level: str = "INFO"
    
    @classmethod
    def from_env(cls) -> "Config":
        """Crea configuración desde variables de entorno."""
        return cls(
            api_id=int(os.getenv("API_ID", "0")),
            api_hash=os.getenv("API_HASH", ""),
            phone_number=os.getenv("PHONE_NUMBER", ""),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            debug=os.getenv("DEBUG", "False").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO")
        )


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


# agents/supervisor_agent.py
"""Agente supervisor que orquesta la lógica de conversación."""
import re
import logging
from typing import Optional, Dict, Any
from llms.openai_client import OpenAIClient
from memory.user_memory import UserMemoryManager

logger = logging.getLogger(__name__)


class SupervisorAgent:
    """Orquestador principal de la lógica conversacional."""
    
    def __init__(self, llm_client: OpenAIClient, memory: UserMemoryManager):
        """Inicializa el supervisor con sus dependencias."""
        self.llm = llm_client
        self.memory = memory
        
    async def process_message(self, user_id: str, message: str) -> str:
        """Procesa un mensaje y genera una respuesta."""
        # Obtener contexto del usuario
        context = await self.memory.get_user_context(user_id)
        
        # Construir prompt
        prompt = self._build_prompt(message, context)
        
        # Generar respuesta
        response = await self.llm.generate_response(prompt)
        
        # Extraer información relevante (ej: nombre)
        await self._extract_and_store_info(user_id, message, response)
        
        return response
    
    def _build_prompt(self, message: str, context: Dict[str, Any]) -> list:
        """Construye el prompt para el LLM."""
        messages = [
            {
                "role": "system",
                "content": (
                    "Eres una asistente conversacional amigable y empática. "
                    "Tu objetivo es mantener conversaciones naturales y agradables. "
                    "Recuerda los detalles que los usuarios compartan contigo."
                )
            }
        ]
        
        # Añadir contexto si existe
        if context.get("name"):
            messages.append({
                "role": "system",
                "content": f"El usuario se llama {context['name']}."
            })
        
        # Añadir mensaje del usuario
        messages.append({
            "role": "user",
            "content": message
        })
        
        return messages
    
    async def _extract_and_store_info(self, user_id: str, message: str, response: str):
        """Extrae información del mensaje y la almacena."""
        # Buscar patrones de presentación
        name_patterns = [
            r"me llamo (\w+)",
            r"mi nombre es (\w+)",
            r"soy (\w+)",
            r"puedes llamarme (\w+)"
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, message.lower())
            if match:
                name = match.group(1).capitalize()
                await self.memory.set_name(user_id, name)
                logger.info(f"Nombre extraído y almacenado: {name}")
                break


# llms/openai_client.py
"""Cliente wrapper para la API de OpenAI."""
import logging
from typing import List, Dict
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class OpenAIClient:
    """Wrapper para interactuar con la API de OpenAI."""
    
    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo"):
        """Inicializa el cliente de OpenAI."""
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        
    async def generate_response(
        self, 
        messages: List[Dict[str, str]], 
        temperature: float = 0.7
    ) -> str:
        """Genera una respuesta usando el modelo de OpenAI."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=150
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error llamando a OpenAI: {e}")
            return "Lo siento, no pude procesar tu mensaje en este momento."


# memory/user_memory.py
"""Gestor de memoria para almacenar contexto de usuarios."""
import json
import logging
from typing import Optional, Dict, Any
import redis.asyncio as redis

logger = logging.getLogger(__name__)


class UserMemoryManager:
    """Gestiona la memoria y contexto de cada usuario."""
    
    def __init__(self, redis_url: str):
        """Inicializa el gestor con conexión a Redis."""
        self.redis_url = redis_url
        self._redis = None
        
    async def _get_redis(self):
        """Obtiene o crea la conexión a Redis."""
        if not self._redis:
            self._redis = await redis.from_url(self.redis_url)
        return self._redis
        
    async def get_user_context(self, user_id: str) -> Dict[str, Any]:
        """Obtiene el contexto almacenado de un usuario."""
        try:
            r = await self._get_redis()
            data = await r.get(f"user:{user_id}")
            
            if data:
                return json.loads(data)
            return {}
            
        except Exception as e:
            logger.error(f"Error obteniendo contexto: {e}")
            return {}
    
    async def update_user_context(
        self, 
        user_id: str, 
        updates: Dict[str, Any]
    ) -> None:
        """Actualiza el contexto de un usuario."""
        try:
            r = await self._get_redis()
            
            # Obtener contexto actual
            context = await self.get_user_context(user_id)
            
            # Actualizar con nuevos datos
            context.update(updates)
            
            # Guardar
            await r.set(
                f"user:{user_id}", 
                json.dumps(context),
                ex=86400 * 30  # Expirar en 30 días
            )
            
        except Exception as e:
            logger.error(f"Error actualizando contexto: {e}")
    
    async def set_name(self, user_id: str, name: str) -> None:
        """Almacena el nombre del usuario."""
        await self.update_user_context(user_id, {"name": name})
        logger.info(f"Nombre guardado para usuario {user_id}: {name}")


# tests/conftest.py
"""Configuración de fixtures para pytest."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from agents.supervisor_agent import SupervisorAgent
from llms.openai_client import OpenAIClient
from memory.user_memory import UserMemoryManager


@pytest.fixture
def mock_llm():
    """Mock del cliente LLM."""
    llm = AsyncMock(spec=OpenAIClient)
    llm.generate_response = AsyncMock(return_value="¡Hola Ana! Mucho gusto.")
    return llm


@pytest.fixture
def mock_memory():
    """Mock del gestor de memoria."""
    memory = AsyncMock(spec=UserMemoryManager)
    memory.get_user_context = AsyncMock(return_value={})
    memory.set_name = AsyncMock()
    memory.update_user_context = AsyncMock()
    return memory


@pytest.fixture
def supervisor(mock_llm, mock_memory):
    """Fixture del supervisor con mocks."""
    return SupervisorAgent(mock_llm, mock_memory)


# tests/test_greet.py
"""Tests básicos para el flujo de saludo."""
import pytest
from agents.supervisor_agent import SupervisorAgent


@pytest.mark.asyncio
async def test_greeting_extracts_name(supervisor, mock_memory):
    """Verifica que se extraiga y almacene el nombre del saludo."""
    # Simular mensaje de saludo
    user_id = "123"
    message = "Hola, me llamo Ana"
    
    # Procesar mensaje
    response = await supervisor.process_message(user_id, message)
    
    # Verificar que se guardó el nombre
    mock_memory.set_name.assert_called_once_with(user_id, "Ana")
    assert "Ana" in response


@pytest.mark.asyncio
async def test_greeting_remembers_name(supervisor, mock_memory):
    """Verifica que se recuerde el nombre en conversaciones posteriores."""
    # Configurar contexto con nombre
    mock_memory.get_user_context.return_value = {"name": "Carlos"}
    
    # Procesar mensaje
    user_id = "456"
    message = "¿Cómo estás?"
    
    response = await supervisor.process_message(user_id, message)
    
    # Verificar que se usó el contexto
    mock_memory.get_user_context.assert_called_once_with(user_id)
    # El LLM debería haber recibido el nombre en el prompt
    call_args = supervisor.llm.generate_response.call_args[0][0]
    assert any("Carlos" in msg["content"] for msg in call_args)