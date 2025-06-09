# tests/test_gdpr_api.py
"""Tests para el endpoint GDPR de borrado de datos."""
import pytest
from fastapi.testclient import TestClient

from api.server import app
from memory.user_memory import UserMemoryManager
from utils.config import Config


class TestGDPRAPI:
    """Tests para verificar el cumplimiento GDPR."""

    @pytest.fixture
    def client(self):
        """Cliente de test para la API."""
        return TestClient(app)

    @pytest.fixture
    async def memory_manager(self):
        """Gestor de memoria para tests."""
        config = Config.from_env()
        return UserMemoryManager(config.redis_url)

    @pytest.mark.asyncio
    async def test_delete_existing_user(self, client, memory_manager):
        """Verifica el borrado exitoso de un usuario existente."""
        user_id = "test_user_123"

        # Crear datos de usuario
        await memory_manager.update_user_context(
            user_id,
            {"name": "Test User", "age": 25}
        )

        # Verificar que el usuario existe
        context = await memory_manager.get_user_context(user_id)
        assert context["name"] == "Test User"

        # Llamar al endpoint de borrado
        response = client.delete(f"/users/{user_id}/memory")
        assert response.status_code == 204

        # Verificar que los datos fueron eliminados
        context = await memory_manager.get_user_context(user_id)
        assert context == {}

    def test_delete_nonexistent_user(self, client):
        """Verifica el manejo de usuarios no existentes."""
        response = client.delete("/users/nonexistent_user/memory")
        assert response.status_code == 404
        assert "no encontrado" in response.json()["detail"]

    def test_health_endpoint(self, client):
        """Verifica el endpoint de salud."""
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] in ["healthy", "unhealthy"]
        assert "services" in response.json()

    def test_root_endpoint(self, client):
        """Verifica el endpoint raíz."""
        response = client.get("/")
        assert response.status_code == 200
        assert "Nadia Bot API" in response.json()["message"]
        assert "endpoints" in response.json()

    @pytest.mark.asyncio
    async def test_get_user_memory(self, client, memory_manager):
        """Verifica la lectura de memoria de usuario."""
        user_id = "test_read_user"
        test_data = {"name": "Reader", "preferences": ["chat", "music"]}

        # Crear datos
        await memory_manager.update_user_context(user_id, test_data)

        # Leer mediante API
        response = client.get(f"/users/{user_id}/memory")
        assert response.status_code == 200

        data = response.json()
        assert data["user_id"] == user_id
        assert data["context"]["name"] == "Reader"
        assert "preferences" in data["context"]

    def test_get_nonexistent_user_memory(self, client):
        """Verifica el manejo de lectura de usuarios no existentes."""
        response = client.get("/users/ghost_user/memory")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_user_with_multiple_keys(self, client, memory_manager):
        """Verifica el borrado completo de usuarios con múltiples claves."""
        user_id = "complex_user"

        # Crear múltiples entradas para el usuario
        await memory_manager.update_user_context(
            user_id,
            {"name": "Complex", "data": "main"}
        )

        # Simular claves adicionales (para futuras extensiones)
        r = await memory_manager._get_redis()
        await r.set(f"user:{user_id}:preferences", '{"theme": "dark"}')
        await r.set(f"user:{user_id}:history", '[]')

        # Verificar que existen múltiples claves
        keys = []
        async for key in r.scan_iter(match=f"user:{user_id}*"):
            keys.append(key)
        assert len(keys) >= 1  # Al menos la clave principal

        # Borrar mediante API
        response = client.delete(f"/users/{user_id}/memory")
        assert response.status_code == 204

        # Verificar que todas las claves fueron eliminadas
        keys_after = []
        async for key in r.scan_iter(match=f"user:{user_id}*"):
            keys_after.append(key)
        assert len(keys_after) == 0
