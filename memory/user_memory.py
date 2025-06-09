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

    async def close(self):
        """Cierra la conexión a Redis limpiamente."""
        if self._redis:
            await self._redis.aclose()
            self._redis = None

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

    async def delete_all_data_for_user(self, user_id: str) -> bool:
        """
        Elimina todos los datos de un usuario (GDPR - Derecho al olvido).

        Args:
            user_id: ID del usuario de Telegram

        Returns:
            True si se eliminó correctamente, False en caso de error
        """
        try:
            r = await self._get_redis()

            # Claves a eliminar para este usuario
            keys_to_delete = [
                f"user:{user_id}",  # Contexto principal
                f"user:{user_id}:*"  # Cualquier clave adicional futura
            ]

            # Buscar todas las claves relacionadas con el usuario
            deleted_count = 0
            for pattern in keys_to_delete:
                if '*' in pattern:
                    # Buscar claves con patrón
                    async for key in r.scan_iter(match=pattern):
                        await r.delete(key)
                        deleted_count += 1
                else:
                    # Eliminar clave directa
                    result = await r.delete(pattern)
                    deleted_count += result

            # También eliminar de cualquier cola de procesamiento
            # Eliminar mensajes pendientes del usuario en el WAL
            processing_key = f"nadia_processing:{user_id}"

            # Eliminar clave de procesamiento si existe
            await r.delete(processing_key)

            logger.info(f"Eliminadas {deleted_count} claves para usuario {user_id}")

            return True

        except Exception as e:
            logger.error(f"Error eliminando datos del usuario {user_id}: {e}")
            return False

    async def get_all_user_ids(self) -> list[str]:
        """
        Obtiene una lista de todos los IDs de usuarios almacenados.

        Returns:
            Lista de IDs de usuarios
        """
        try:
            r = await self._get_redis()
            user_ids = []

            # Buscar todas las claves de usuarios
            async for key in r.scan_iter(match="user:*"):
                # Extraer el user_id del formato "user:{user_id}"
                key_str = key.decode() if isinstance(key, bytes) else key
                if ':' in key_str and not key_str.count(':') > 1:
                    user_id = key_str.split(':')[1]
                    user_ids.append(user_id)

            return user_ids

        except Exception as e:
            logger.error(f"Error obteniendo lista de usuarios: {e}")
            return []
