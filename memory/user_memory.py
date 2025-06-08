# memory/user_memory.py
"""Gestor de memoria para almacenar contexto de usuarios."""
import json
import logging
from typing import Any, Dict

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class UserMemoryManager:
    """Gestiona la memoria y contexto de cada usuario."""

    def __init__(self, redis_url: str):
        """Inicializa el gestor con conexión a Redis."""
        self.redis_url = redis_url
        self._redis = None

    async def _get_redis(self):
        """Obtiene o crea la conexión a Redis."""
        if not self._redis:
            self._redis = await redis.from_url(self.redis_url)
        return self._redis

    async def get_user_context(self, user_id: str) -> Dict[str, Any]:
        """Obtiene el contexto almacenado de un usuario."""
        try:
            r = await self._get_redis()
            data = await r.get(f"user:{user_id}")

            if data:
                return json.loads(data)
            return {}

        except Exception as e:
            logger.error(f"Error obteniendo contexto: {e}")
            return {}

    async def update_user_context(
        self,
        user_id: str,
        updates: Dict[str, Any]
    ) -> None:
        """Actualiza el contexto de un usuario."""
        try:
            r = await self._get_redis()

            # Obtener contexto actual
            context = await self.get_user_context(user_id)

            # Actualizar con nuevos datos
            context.update(updates)

            # Guardar
            await r.set(
                f"user:{user_id}",
                json.dumps(context),
                ex=86400 * 30  # Expirar en 30 días
            )

        except Exception as e:
            logger.error(f"Error actualizando contexto: {e}")

    async def set_name(self, user_id: str, name: str) -> None:
        """Almacena el nombre del usuario."""
        await self.update_user_context(user_id, {"name": name})
        logger.info(f"Nombre guardado para usuario {user_id}: {name}")
