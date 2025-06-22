# llms/llm_factory.py
"""
Factory pattern for creating LLM clients.
Supports multiple LLM providers for the HITL system.
"""
import logging
from typing import Optional

from .base_client import BaseLLMClient
from .openai_client import OpenAIClient
from .gemini_client import GeminiClient

logger = logging.getLogger(__name__)


class LLMFactory:
    """Factory for creating LLM client instances."""
    
    SUPPORTED_PROVIDERS = {
        "openai": OpenAIClient,
        "gemini": GeminiClient,
    }
    
    @classmethod
    def create_llm_client(
        cls, 
        provider: str, 
        api_key: str,
        model: str,
        **kwargs
    ) -> BaseLLMClient:
        """
        Create an LLM client instance.
        
        Args:
            provider: LLM provider name ("openai", "gemini")
            api_key: API key for the provider
            model: Model name to use
            **kwargs: Additional provider-specific arguments
            
        Returns:
            LLM client instance
            
        Raises:
            ValueError: If provider is not supported
            Exception: If client creation fails
        """
        provider = provider.lower().strip()
        
        if provider not in cls.SUPPORTED_PROVIDERS:
            raise ValueError(
                f"Unsupported LLM provider: {provider}. "
                f"Supported providers: {list(cls.SUPPORTED_PROVIDERS.keys())}"
            )
        
        client_class = cls.SUPPORTED_PROVIDERS[provider]
        
        try:
            client = client_class(api_key=api_key, model=model, **kwargs)
            logger.info(f"Created {provider} client with model: {model}")
            return client
            
        except Exception as e:
            logger.error(f"Failed to create {provider} client: {str(e)}")
            raise Exception(f"LLM client creation failed for {provider}: {str(e)}")
    
    @classmethod
    def get_supported_providers(cls) -> list:
        """
        Get list of supported LLM providers.
        
        Returns:
            List of supported provider names
        """
        return list(cls.SUPPORTED_PROVIDERS.keys())
    
    @classmethod
    def validate_provider_config(cls, provider: str, model: str) -> bool:
        """
        Validate provider and model combination.
        
        Args:
            provider: Provider name
            model: Model name
            
        Returns:
            True if configuration is valid
        """
        if provider not in cls.SUPPORTED_PROVIDERS:
            return False
        
        # Provider-specific model validation
        if provider == "openai":
            return cls._validate_openai_model(model)
        elif provider == "gemini":
            return cls._validate_gemini_model(model)
        
        return True
    
    @classmethod
    def _validate_openai_model(cls, model: str) -> bool:
        """Validate OpenAI model names."""
        valid_models = [
            "gpt-3.5-turbo",
            "gpt-4",
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
        ]
        return model in valid_models
    
    @classmethod
    def _validate_gemini_model(cls, model: str) -> bool:
        """Validate Gemini model names."""
        valid_models = [
            "gemini-2.0-flash-exp",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
            "gemini-pro",
        ]
        return model in valid_models


def create_llm_client(provider: str, model: str, api_key: str, **kwargs) -> BaseLLMClient:
    """
    Convenience function to create LLM client.
    
    Args:
        provider: LLM provider name
        model: Model name
        api_key: API key
        **kwargs: Additional arguments
        
    Returns:
        LLM client instance
    """
    return LLMFactory.create_llm_client(provider, api_key, model, **kwargs)