# tests/conftest.py
"""Configuración de fixtures para pytest."""
from unittest.mock import AsyncMock

import pytest

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
