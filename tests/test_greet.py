# tests/test_greet.py
"""Tests básicos para el flujo de saludo."""
import pytest


@pytest.mark.asyncio
async def test_greeting_extracts_name(supervisor, mock_memory):
    """Verifica que se extraiga y almacene el nombre del saludo."""
    # Simular mensaje de saludo
    user_id = "123"
    message = "Hola, me llamo Ana"

    # Procesar mensaje
    response = await supervisor.process_message(user_id, message)

    # Verificar que se guardó el nombre
    mock_memory.set_name.assert_called_once_with(user_id, "Ana")
    assert "Ana" in response


@pytest.mark.asyncio
async def test_greeting_remembers_name(supervisor, mock_memory):
    """Verifica que se recuerde el nombre en conversaciones posteriores."""
    # Configurar contexto con nombre
    mock_memory.get_user_context.return_value = {"name": "Carlos"}

    # Procesar mensaje
    user_id = "456"
    message = "¿Cómo estás?"

    response = await supervisor.process_message(user_id, message)
    assert "Ana" in response
    # Verificar que se usó el contexto
    mock_memory.get_user_context.assert_called_once_with(user_id)
    # El LLM debería haber recibido el nombre en el prompt
    call_args = supervisor.llm.generate_response.call_args[0][0]
    assert any("Carlos" in msg["content"] for msg in call_args)
