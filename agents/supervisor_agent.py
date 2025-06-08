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
