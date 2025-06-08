"""
Agente supervisor que orquesta la lógica de conversación.
Decide qué acciones tomar basándose en el contexto.
"""
from typing import Any, Dict

from llms.openai_client import OpenAIClient
from memory.user_memory import UserMemoryManager


class SupervisorAgent:
    """Orquestador principal de la lógica conversacional."""

    def __init__(self, llm_client: OpenAIClient, memory: UserMemoryManager):
        """
        Inicializa el supervisor con sus dependencias.

        Args:
            llm_client: Cliente para interactuar con el LLM
            memory: Gestor de memoria de usuarios
        """
        pass

    async def process_message(self, user_id: str, message: str) -> str:
        """
        Procesa un mensaje y genera una respuesta.

        Args:
            user_id: Identificador único del usuario
            message: Mensaje recibido

        Returns:
            Respuesta generada
        """
        pass

    def _build_prompt(self, message: str, context: Dict[str, Any]) -> str:
        """
        Construye el prompt para el LLM.

        Args:
            message: Mensaje del usuario
            context: Contexto de la conversación

        Returns:
            Prompt formateado
        """
        pass
