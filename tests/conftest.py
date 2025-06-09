# conftest.py
"""Configuración global de pytest para el proyecto."""
import asyncio
import sys
from pathlib import Path

import pytest
import redis.asyncio as redis

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent))

@pytest.fixture
async def redis_cleanup():
    """
    Fixture que garantiza la limpieza de conexiones Redis.

    Este fixture se ejecuta después de cada test que lo use,
    cerrando todas las conexiones Redis pendientes.
    """
    # Setup (antes del test)
    connections = []

    # Guardar referencia a la función original
    original_from_url = redis.from_url

    async def wrapped_from_url(*args, **kwargs):
        """Wrapper que rastrea conexiones creadas."""
        conn = await original_from_url(*args, **kwargs)
        connections.append(conn)
        return conn

    # Reemplazar temporalmente
    redis.from_url = wrapped_from_url

    yield

    # Teardown (después del test)
    # Restaurar función original
    redis.from_url = original_from_url

    # Cerrar todas las conexiones rastreadas
    for conn in connections:
        try:
            await conn.aclose()
        except Exception:
            pass  # Ignorar errores al cerrar
@pytest.fixture(scope="session")
def event_loop():
    """
    Crea un event loop para toda la sesión de tests.

    Esto ayuda a evitar problemas de "Event loop is closed"
    al reutilizar el mismo loop.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()

    yield loop

    # Dar tiempo para que se completen las tareas pendientes
    pending = asyncio.all_tasks(loop)
    if pending:
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

    # Cerrar el loop limpiamente
    loop.close()
# Marcar todos los tests como asyncio por defecto
def pytest_collection_modifyitems(items):
    """Marca automáticamente los tests async con pytest.mark.asyncio."""
    pytest_asyncio_mark = pytest.mark.asyncio
    for item in items:
        if asyncio.iscoroutinefunction(item.obj):
            item.add_marker(pytest_asyncio_mark)
