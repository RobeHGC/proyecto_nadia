# llms/__init__.py
"""
Multi-LLM support module for NADIA HITL system.

This module provides a unified interface for working with multiple
LLM providers (OpenAI, Gemini) through a common base class.
"""

from .base_client import BaseLLMClient
from .openai_client import OpenAIClient
from .gemini_client import GeminiClient
from .llm_factory import LLMFactory, create_llm_client

__all__ = [
    "BaseLLMClient",
    "OpenAIClient", 
    "GeminiClient",
    "LLMFactory",
    "create_llm_client"
]