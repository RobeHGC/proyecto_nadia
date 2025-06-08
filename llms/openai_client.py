# llms/openai_client.py
"""Cliente wrapper para la API de OpenAI."""
import logging
from typing import Dict, List

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
