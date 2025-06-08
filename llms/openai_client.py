"""
Cliente wrapper para la API de OpenAI.
Maneja las llamadas al modelo de lenguaje.
"""
from typing import Dict, List


class OpenAIClient:
    """Wrapper para interactuar con la API de OpenAI."""

    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo"):
        """
        Inicializa el cliente de OpenAI.

        Args:
            api_key: Clave API de OpenAI
            model: Modelo a utilizar
        """
        pass

    async def generate_response(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.7
    ) -> str:
        """
        Genera una respuesta usando el modelo de OpenAI.

        Args:
            messages: Lista de mensajes en formato OpenAI
            temperature: Creatividad de la respuesta (0-1)

        Returns:
            Respuesta generada
        """
        pass
