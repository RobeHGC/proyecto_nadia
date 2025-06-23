# memory/user_memory.py
"""Gestor de memoria para almacenar contexto de usuarios."""
import json
import logging
from typing import Any, Dict

import redis.asyncio as redis

logger = logging.getLogger(__name__)


class UserMemoryManager:
    """Gestiona la memoria y contexto de cada usuario."""

    def __init__(self, redis_url: str, max_history_length: int = 50, max_context_size_kb: int = 100):
        """Inicializa el gestor con conexión a Redis y límites de memoria."""
        self.redis_url = redis_url
        self._redis = None
        
        # Memory limits configuration
        self.max_history_length = max_history_length  # Máximo número de mensajes en historial
        self.max_context_size_kb = max_context_size_kb  # Máximo tamaño del contexto en KB

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
        """Actualiza el contexto de un usuario con límites de tamaño."""
        try:
            r = await self._get_redis()

            # Obtener contexto actual
            context = await self.get_user_context(user_id)

            # Actualizar con nuevos datos
            context.update(updates)
            
            # Aplicar límites de memoria
            context = await self._apply_context_limits(user_id, context)

            # Guardar
            await r.set(
                f"user:{user_id}",
                json.dumps(context),
                ex=86400 * 30  # Expirar en 30 días
            )

        except Exception as e:
            logger.error(f"Error actualizando contexto: {e}")
    
    async def _apply_context_limits(self, user_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Aplica límites de memoria al contexto del usuario."""
        try:
            # Calcular tamaño actual del contexto
            context_json = json.dumps(context)
            context_size_kb = len(context_json.encode('utf-8')) / 1024
            
            # Si el contexto excede el límite, aplicar compresión inteligente
            if context_size_kb > self.max_context_size_kb:
                logger.warning(f"Context size for user {user_id}: {context_size_kb:.1f}KB exceeds limit {self.max_context_size_kb}KB")
                context = await self._compress_context(user_id, context)
                
                # Recalcular tamaño después de compresión
                context_json = json.dumps(context)
                new_size_kb = len(context_json.encode('utf-8')) / 1024
                logger.info(f"Context compressed for user {user_id}: {context_size_kb:.1f}KB → {new_size_kb:.1f}KB")
            
            return context
            
        except Exception as e:
            logger.error(f"Error applying context limits for user {user_id}: {e}")
            return context
    
    async def _compress_context(self, user_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Comprime el contexto manteniendo la información más relevante."""
        try:
            compressed_context = context.copy()
            
            # 1. Mantener datos esenciales del perfil
            essential_keys = ['name', 'age', 'location', 'occupation', 'preferences']
            profile_data = {k: v for k, v in context.items() if k in essential_keys}
            
            # 2. Comprimir historial de conversación si existe
            if 'conversation_summary' in compressed_context:
                # Mantener solo resumen más reciente
                if isinstance(compressed_context['conversation_summary'], list):
                    compressed_context['conversation_summary'] = compressed_context['conversation_summary'][-3:]
            
            # 3. Comprimir metadata menos importante
            metadata_to_keep = ['last_interaction', 'first_interaction', 'total_messages']
            metadata = {k: v for k, v in context.items() if k in metadata_to_keep}
            
            # 4. Crear contexto comprimido
            compressed_context = {
                **profile_data,
                **metadata,
                'compression_applied': True,
                'compression_timestamp': json.dumps({"timestamp": "now"})  # Simple timestamp
            }
            
            # 5. Si aún es muy grande, mantener solo lo esencial
            compressed_json = json.dumps(compressed_context)
            if len(compressed_json.encode('utf-8')) / 1024 > self.max_context_size_kb:
                logger.warning(f"Applying aggressive compression for user {user_id}")
                compressed_context = {
                    'name': context.get('name', 'Unknown'),
                    'last_interaction': context.get('last_interaction'),
                    'aggressive_compression_applied': True
                }
            
            return compressed_context
            
        except Exception as e:
            logger.error(f"Error compressing context for user {user_id}: {e}")
            return context

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

    async def get_conversation_history(self, user_id: str) -> list[Dict[str, Any]]:
        """
        Obtiene el historial de conversación de un usuario.
        
        Args:
            user_id: ID del usuario
            
        Returns:
            Lista de mensajes del historial
        """
        try:
            r = await self._get_redis()
            
            # Obtener historial desde Redis
            history_key = f"user:{user_id}:history"
            history_data = await r.get(history_key)
            
            if history_data:
                return json.loads(history_data)
            
            return []
            
        except Exception as e:
            logger.error(f"Error obteniendo historial para {user_id}: {e}")
            return []

    async def add_to_conversation_history(self, user_id: str, message: Dict[str, Any]) -> None:
        """
        Agrega un mensaje al historial de conversación.
        
        Args:
            user_id: ID del usuario
            message: Mensaje a agregar (debe incluir 'role' y 'content')
        """
        try:
            r = await self._get_redis()
            
            # Obtener historial actual
            history = await self.get_conversation_history(user_id)
            
            # Agregar nuevo mensaje
            history.append(message)
            
            # Aplicar límite de historial configurable
            if len(history) > self.max_history_length:
                # Mantener solo los mensajes más recientes
                history = history[-self.max_history_length:]
                logger.debug(f"History trimmed for user {user_id} to {self.max_history_length} messages")
            
            # Guardar historial actualizado
            history_key = f"user:{user_id}:history"
            await r.set(
                history_key,
                json.dumps(history),
                ex=86400 * 7  # Expirar en 7 días
            )
            
        except Exception as e:
            logger.error(f"Error agregando al historial para {user_id}: {e}")

    async def get_memory_stats(self, user_id: str) -> Dict[str, Any]:
        """Obtiene estadísticas de memoria para un usuario."""
        try:
            context = await self.get_user_context(user_id)
            history = await self.get_conversation_history(user_id)
            
            # Calcular tamaños
            context_size_kb = len(json.dumps(context).encode('utf-8')) / 1024
            history_size_kb = len(json.dumps(history).encode('utf-8')) / 1024
            total_size_kb = context_size_kb + history_size_kb
            
            return {
                'user_id': user_id,
                'context_size_kb': round(context_size_kb, 2),
                'history_size_kb': round(history_size_kb, 2),
                'total_size_kb': round(total_size_kb, 2),
                'history_length': len(history),
                'max_history_length': self.max_history_length,
                'max_context_size_kb': self.max_context_size_kb,
                'context_limit_exceeded': context_size_kb > self.max_context_size_kb,
                'history_limit_exceeded': len(history) > self.max_history_length,
                'compression_applied': context.get('compression_applied', False)
            }
            
        except Exception as e:
            logger.error(f"Error getting memory stats for {user_id}: {e}")
            return {}
    
    async def cleanup_oversized_contexts(self) -> Dict[str, int]:
        """Limpia contextos que exceden los límites en todos los usuarios."""
        try:
            user_ids = await self.get_all_user_ids()
            cleaned_count = 0
            total_users = len(user_ids)
            total_size_before_kb = 0
            total_size_after_kb = 0
            
            for user_id in user_ids:
                try:
                    # Obtener estadísticas antes
                    stats_before = await self.get_memory_stats(user_id)
                    total_size_before_kb += stats_before.get('total_size_kb', 0)
                    
                    # Solo procesar si excede límites
                    if (stats_before.get('context_limit_exceeded', False) or 
                        stats_before.get('history_limit_exceeded', False)):
                        
                        # Aplicar límites
                        context = await self.get_user_context(user_id)
                        compressed_context = await self._apply_context_limits(user_id, context)
                        
                        # Guardar contexto comprimido
                        r = await self._get_redis()
                        await r.set(
                            f"user:{user_id}",
                            json.dumps(compressed_context),
                            ex=86400 * 30
                        )
                        
                        # Limpiar historial si es necesario
                        history = await self.get_conversation_history(user_id)
                        if len(history) > self.max_history_length:
                            history = history[-self.max_history_length:]
                            history_key = f"user:{user_id}:history"
                            await r.set(
                                history_key,
                                json.dumps(history),
                                ex=86400 * 7
                            )
                        
                        cleaned_count += 1
                    
                    # Obtener estadísticas después
                    stats_after = await self.get_memory_stats(user_id)
                    total_size_after_kb += stats_after.get('total_size_kb', 0)
                    
                except Exception as e:
                    logger.error(f"Error cleaning user {user_id}: {e}")
                    continue
            
            space_saved_kb = total_size_before_kb - total_size_after_kb
            
            logger.info(f"Memory cleanup completed: {cleaned_count}/{total_users} users processed, {space_saved_kb:.2f}KB saved")
            
            return {
                'total_users': total_users,
                'cleaned_users': cleaned_count,
                'space_saved_kb': round(space_saved_kb, 2),
                'total_size_before_kb': round(total_size_before_kb, 2),
                'total_size_after_kb': round(total_size_after_kb, 2)
            }
            
        except Exception as e:
            logger.error(f"Error during memory cleanup: {e}")
            return {}
