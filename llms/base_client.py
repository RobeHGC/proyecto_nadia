# llms/base_client.py
"""
Base abstract class for all LLM clients in the HITL system.
Provides a common interface for multi-LLM support.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any


class BaseLLMClient(ABC):
    """
    Abstract base class for LLM clients.
    All LLM implementations must inherit from this class.
    """
    
    def __init__(self, api_key: str, model: str):
        """Initialize the LLM client with API key and model."""
        self.api_key = api_key
        self.model = model
        self._last_cost = 0.0
        self._last_tokens_used = 0
    
    @abstractmethod
    async def generate_response(self, messages: List[Dict[str, Any]], temperature: float = 0.7) -> str:
        """
        Generate a response from the LLM.
        
        Args:
            messages: List of message dictionaries in OpenAI format
                     [{"role": "system/user/assistant", "content": "text"}]
            temperature: Sampling temperature (0.0 to 1.0)
            
        Returns:
            Generated response text
            
        Raises:
            Exception: If API call fails
        """
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """
        Get the model name being used.
        
        Returns:
            Model name string
        """
        pass
    
    def get_last_cost(self) -> float:
        """
        Get the cost of the last API call in USD.
        
        Returns:
            Cost in USD
        """
        return self._last_cost
    
    def get_last_tokens_used(self) -> int:
        """
        Get the number of tokens used in the last API call.
        
        Returns:
            Number of tokens used
        """
        return self._last_tokens_used
    
    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Calculate cost based on token usage.
        Must be implemented by subclasses with their specific pricing.
        
        Args:
            prompt_tokens: Number of input tokens
            completion_tokens: Number of output tokens
            
        Returns:
            Cost in USD
        """
        return 0.0  # Default implementation, override in subclasses