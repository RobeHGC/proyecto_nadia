# llms/openai_client.py
"""Cliente wrapper para la API de OpenAI."""
import logging
from typing import Dict, List, Any

import tiktoken
from openai import AsyncOpenAI

from .base_client import BaseLLMClient

logger = logging.getLogger(__name__)


class OpenAIClient(BaseLLMClient):
    """Wrapper para interactuar con la API de OpenAI."""
    
    # OpenAI pricing (per 1K tokens as of latest rates)
    PRICING = {
        "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
        "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},  # GPT-4o-mini pricing
        "gpt-4.1-nano": {"input": 0.0001, "output": 0.0004, "cached_input": 0.000025},  # GPT-4.1-nano pricing
        "gpt-4o": {"input": 0.005, "output": 0.015},
        "gpt-4": {"input": 0.03, "output": 0.06},
    }

    def __init__(self, api_key: str, model: str = "gpt-3.5-turbo"):
        """Inicializa el cliente de OpenAI."""
        super().__init__(api_key, model)
        self.client = AsyncOpenAI(api_key=api_key)
        try:
            self.encoding = tiktoken.encoding_for_model(self.model)
        except KeyError:
            # Fallback para modelos no reconocidos (como gpt-4.1-nano)
            self.encoding = tiktoken.get_encoding("cl100k_base")

    async def generate_response(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        seed: int = None
    ) -> str:
        """Genera una respuesta usando el modelo de OpenAI."""
        try:
            # Calcular tokens reales (no estimación)
            prompt_text = " ".join(m["content"] for m in messages)
            actual_tokens = len(self.encoding.encode(prompt_text))
            
            logger.info(f"Prompt size: {actual_tokens} tokens")
            
            # Determine max_tokens based on model and use case
            max_tokens = self._get_max_tokens_for_model()
            
            kwargs = {
                'model': self.model,
                'messages': messages,
                'temperature': temperature,
                'max_tokens': max_tokens
            }
            
            # Agregar seed si se proporciona
            if seed is not None:
                kwargs['seed'] = seed
                
            response = await self.client.chat.completions.create(**kwargs)

            # Update usage metrics
            if hasattr(response, 'usage') and response.usage:
                prompt_tokens = response.usage.prompt_tokens
                completion_tokens = response.usage.completion_tokens
                self._last_tokens_used = response.usage.total_tokens
                self._last_cost = self._calculate_cost(prompt_tokens, completion_tokens)
            
            content = response.choices[0].message.content
            if content is None:
                logger.warning("OpenAI returned None content")
                return "Lo siento, no pude generar una respuesta."
            
            logger.info(f"OpenAI response generated. Model: {self.model}, Tokens: {self._last_tokens_used}, Cost: ${self._last_cost:.6f}")
            
            return content.strip()

        except Exception as e:
            logger.error(f"Error llamando a OpenAI: {e}")
            raise Exception(f"OpenAI generation failed: {str(e)}")
    
    def get_model_name(self) -> str:
        """Get the OpenAI model name."""
        return self.model
    
    def _get_max_tokens_for_model(self) -> int:
        """
        Get appropriate max_tokens based on model and use case.
        
        Returns:
            Maximum tokens for response
        """
        # Higher token limits for newer models and refinement tasks
        if "gpt-4o" in self.model:
            return 2048
        elif "gpt-4" in self.model:
            return 1024
        else:
            return 512  # Conservative for older models
    
    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Calculate cost for OpenAI API usage.
        
        Args:
            prompt_tokens: Input tokens
            completion_tokens: Output tokens
            
        Returns:
            Cost in USD
        """
        if self.model not in self.PRICING:
            logger.warning(f"Unknown model pricing for {self.model}, using gpt-3.5-turbo rates")
            pricing = self.PRICING["gpt-3.5-turbo"]
        else:
            pricing = self.PRICING[self.model]
        
        input_cost = (prompt_tokens / 1000) * pricing["input"]
        output_cost = (completion_tokens / 1000) * pricing["output"]
        
        return input_cost + output_cost
