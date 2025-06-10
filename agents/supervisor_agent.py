# agents/supervisor_agent.py
"""Agente supervisor que orquesta la lógica de conversación."""
import logging
import re
from typing import Any, Dict

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
        """Builds the prompt for the LLM."""
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a friendly and empathetic conversational assistant. "
                    "Your goal is to maintain natural and pleasant conversations. "
                    "Remember the details that users share with you."
                )
            }
        ]

        # Añadir contexto si existe
        if context.get("name"):
            messages.append({
                "role": "system",
                "content": f"The user's name is {context['name']}."
            })

        # Añadir mensaje del usuario
        messages.append({
            "role": "user",
            "content": message
        })

        return messages
    #patrones de extracción de nombre:
    async def _extract_and_store_info(self, user_id: str, message: str, response: str):
        """Extrae información del mensaje y la almacena."""
        # Buscar patrones de presentación
        name_patterns = [
            r"my name is (\w+)",
            r"i'm (\w+)",
            r"i am (\w+)",
            r"call me (\w+)",
            r"this is (\w+)",
            r"(\w+) here",  # "John here"
            r"it's (\w+)",  # "It's John"
        ]

        for pattern in name_patterns:
            match = re.search(pattern, message.lower())
            if match:
                name = match.group(1).capitalize()
                await self.memory.set_name(user_id, name)
                logger.info(f"Name extracted and stored: {name}")
                break
