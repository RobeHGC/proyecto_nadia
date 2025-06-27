"""
Entity Resolution System for NADIA HITL Bot

Garantiza que todas las entidades de Telegram estén resueltas antes de 
enviar mensajes con typing simulation, eliminando errores de PeerUser.
"""

import asyncio
import logging
import time
from typing import Dict, Optional, Any
from telethon import TelegramClient
from telethon.errors import PeerIdInvalidError, FloodWaitError
from telethon.tl.types import User, Chat, Channel

logger = logging.getLogger(__name__)

class EntityResolver:
    """
    Sistema proactivo de resolución de entidades para Telegram.
    
    Funcionalidades:
    - Cache inteligente de entidades resueltas
    - Warm-up automático al iniciar el bot
    - Pre-resolución asíncrona cuando llegan mensajes nuevos
    - Manejo robusto de errores con retry logic
    """
    
    def __init__(self, client: TelegramClient, cache_size: int = 1000):
        self.client = client
        self.entity_cache: Dict[int, Any] = {}
        self.resolution_attempts: Dict[int, int] = {}
        self.last_cleanup = time.time()
        self.cache_size = cache_size
        
        # Configuración
        self.max_retry_attempts = 3
        self.cleanup_interval = 3600  # 1 hora
        self.entity_ttl = 7200  # 2 horas
        
    async def ensure_entity_resolved(self, user_id: int) -> bool:
        """
        Garantiza que la entidad esté resuelta para typing simulation.
        
        Args:
            user_id: ID del usuario de Telegram
            
        Returns:
            bool: True si entidad está resuelta, False si falló
        """
        # Check cache primero
        if user_id in self.entity_cache:
            logger.debug(f"Entity {user_id} found in cache")
            return True
            
        # Intentar resolver usando get_input_entity para typing simulation
        return await self._resolve_entity_for_typing(user_id)
    
    async def preload_entity_for_message(self, user_id: int) -> None:
        """
        Pre-resuelve entidad en background para mensaje entrante.
        
        Se ejecuta de manera asíncrona sin bloquear el procesamiento
        del mensaje.
        """
        try:
            if user_id not in self.entity_cache:
                logger.debug(f"Pre-loading entity for user {user_id}")
                await self._resolve_entity(user_id)
        except Exception as e:
            logger.warning(f"Failed to preload entity {user_id}: {e}")
    
    async def warm_up_from_dialogs(self, limit: int = 100) -> int:
        """
        Calentar cache con entidades de diálogos existentes.
        
        Args:
            limit: Número máximo de diálogos a procesar
            
        Returns:
            int: Número de entidades resueltas exitosamente
        """
        logger.info(f"Starting entity warm-up with limit {limit}")
        resolved_count = 0
        
        try:
            async for dialog in self.client.iter_dialogs(limit=limit):
                if dialog.is_user:
                    user_id = dialog.entity.id
                    if user_id not in self.entity_cache:
                        self.entity_cache[user_id] = dialog.entity
                        resolved_count += 1
                        
            logger.info(f"Entity warm-up completed: {resolved_count} entities cached")
            return resolved_count
            
        except Exception as e:
            logger.error(f"Error during entity warm-up: {e}")
            return resolved_count
    
    async def _resolve_entity(self, user_id: int) -> bool:
        """
        Intenta resolver una entidad específica con retry logic.
        
        Args:
            user_id: ID del usuario a resolver
            
        Returns:
            bool: True si se resolvió exitosamente
        """
        attempts = self.resolution_attempts.get(user_id, 0)
        
        if attempts >= self.max_retry_attempts:
            logger.warning(f"Max retry attempts reached for user {user_id}")
            return False
            
        try:
            # Incrementar contador de intentos
            self.resolution_attempts[user_id] = attempts + 1
            
            # Intentar obtener entidad
            entity = await self.client.get_entity(user_id)
            
            # Guardar en cache
            self.entity_cache[user_id] = entity
            
            # Limpiar contador de intentos
            if user_id in self.resolution_attempts:
                del self.resolution_attempts[user_id]
                
            logger.debug(f"Successfully resolved entity for user {user_id}")
            
            # Cleanup periódico
            await self._periodic_cleanup()
            
            return True
            
        except PeerIdInvalidError:
            logger.warning(f"Invalid peer ID: {user_id}")
            return False
            
        except FloodWaitError as e:
            logger.warning(f"Flood wait error for user {user_id}: {e.seconds}s")
            # En caso de flood wait, no reintentar inmediatamente
            return False
            
        except Exception as e:
            logger.warning(f"Failed to resolve entity {user_id} (attempt {attempts + 1}): {e}")
            return False
    
    async def _resolve_entity_for_typing(self, user_id: int) -> bool:
        """
        Método específico para resolver entidades para typing simulation.
        
        Usa diferentes estrategias de Telethon para obtener la entidad.
        """
        attempts = self.resolution_attempts.get(user_id, 0)
        
        if attempts >= self.max_retry_attempts:
            logger.warning(f"Max retry attempts reached for user {user_id}")
            return False
            
        try:
            # Incrementar contador de intentos
            self.resolution_attempts[user_id] = attempts + 1
            
            # Estrategia 1: Usar get_input_entity (más confiable para typing)
            try:
                input_entity = await self.client.get_input_entity(user_id)
                self.entity_cache[user_id] = input_entity
                logger.debug(f"Successfully resolved input entity for user {user_id}")
                
                # Limpiar contador de intentos
                if user_id in self.resolution_attempts:
                    del self.resolution_attempts[user_id]
                    
                return True
                
            except Exception:
                # Estrategia 2: Fallback a get_entity normal
                entity = await self.client.get_entity(user_id)
                self.entity_cache[user_id] = entity
                logger.debug(f"Successfully resolved entity for user {user_id} (fallback)")
                
                # Limpiar contador de intentos
                if user_id in self.resolution_attempts:
                    del self.resolution_attempts[user_id]
                    
                return True
                
        except PeerIdInvalidError:
            logger.warning(f"Invalid peer ID: {user_id}")
            return False
            
        except FloodWaitError as e:
            logger.warning(f"Flood wait error for user {user_id}: {e.seconds}s")
            return False
            
        except Exception as e:
            logger.warning(f"Failed to resolve entity {user_id} for typing (attempt {attempts + 1}): {e}")
            return False
    
    async def _periodic_cleanup(self) -> None:
        """
        Limpieza periódica del cache para evitar memory leaks.
        """
        current_time = time.time()
        
        if current_time - self.last_cleanup < self.cleanup_interval:
            return
            
        logger.debug("Starting periodic cache cleanup")
        
        # Limpiar cache si está muy grande
        if len(self.entity_cache) > self.cache_size:
            # Remover entradas más antiguas (simplificado - FIFO)
            excess = len(self.entity_cache) - int(self.cache_size * 0.8)
            keys_to_remove = list(self.entity_cache.keys())[:excess]
            
            for key in keys_to_remove:
                del self.entity_cache[key]
                
            logger.info(f"Cleaned {excess} entries from entity cache")
        
        # Limpiar intentos fallidos antiguos
        failed_to_remove = []
        for user_id, attempts in self.resolution_attempts.items():
            if attempts >= self.max_retry_attempts:
                failed_to_remove.append(user_id)
                
        for user_id in failed_to_remove:
            del self.resolution_attempts[user_id]
            
        self.last_cleanup = current_time
        
        logger.debug(f"Cache cleanup completed. Current size: {len(self.entity_cache)}")
    
    def get_cache_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas del cache para monitoreo.
        
        Returns:
            Dict con métricas del cache
        """
        return {
            "cache_size": len(self.entity_cache),
            "max_cache_size": self.cache_size,
            "pending_resolutions": len(self.resolution_attempts),
            "last_cleanup": self.last_cleanup,
            "cache_utilization": len(self.entity_cache) / self.cache_size * 100
        }
    
    async def force_resolve_entity(self, user_id: int) -> bool:
        """
        Fuerza la resolución de una entidad, ignorando cache y retry limits.
        
        Útil para debugging o casos especiales.
        """
        logger.info(f"Force resolving entity {user_id}")
        
        # Limpiar contadores
        if user_id in self.resolution_attempts:
            del self.resolution_attempts[user_id]
            
        # Remover del cache para forzar resolución
        if user_id in self.entity_cache:
            del self.entity_cache[user_id]
            
        return await self._resolve_entity(user_id)