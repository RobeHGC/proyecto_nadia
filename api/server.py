# api/server.py
"""Servidor API para gestión del bot y cumplimiento GDPR."""
import logging

import redis.asyncio as redis
from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware

from memory.user_memory import UserMemoryManager
from utils.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Crear app FastAPI
app = FastAPI(
    title="Nadia Bot API",
    description="API para gestión del bot Nadia y cumplimiento GDPR",
    version="0.2.0"
)

# Configurar CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # En producción, especificar dominios permitidos
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuración global
config = Config.from_env()
memory_manager = UserMemoryManager(config.redis_url)


@app.on_event("startup")
async def startup_event():
    """Inicialización al arrancar el servidor."""
    logger.info("API Server iniciando...")


@app.on_event("shutdown")
async def shutdown_event():
    """Limpieza al cerrar el servidor."""
    logger.info("API Server cerrando...")
    await memory_manager.close()


@app.get("/")
async def root():
    """Endpoint raíz de bienvenida."""
    return {
        "message": "Nadia Bot API",
        "version": "0.2.0",
        "endpoints": {
            "health": "/health",
            "delete_user": "DELETE /users/{user_id}/memory"
        }
    }


@app.get("/health")
async def health_check():
    """Verifica el estado de salud del servicio."""
    try:
        # Verificar conexión a Redis
        r = await redis.from_url(config.redis_url)
        await r.ping()
        await r.aclose()

        return {
            "status": "healthy",
            "services": {
                "api": "ok",
                "redis": "ok"
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "services": {
                "api": "ok",
                "redis": "error"
            },
            "error": str(e)
        }


@app.delete("/users/{user_id}/memory", status_code=204)
async def delete_user_data(user_id: str):
    """
    Elimina todos los datos de un usuario (GDPR - Derecho al olvido).

    Args:
        user_id: ID del usuario de Telegram

    Returns:
        204 No Content si se eliminó correctamente
        404 Not Found si el usuario no existe
        500 Internal Server Error si hay un error
    """
    try:
        logger.info(f"Solicitud de borrado GDPR para usuario {user_id}")

        # Verificar si el usuario existe
        context = await memory_manager.get_user_context(user_id)
        if not context:
            raise HTTPException(
                status_code=404,
                detail=f"Usuario {user_id} no encontrado"
            )

        # Eliminar todos los datos del usuario
        deleted = await memory_manager.delete_all_data_for_user(user_id)

        if deleted:
            logger.info(f"Datos del usuario {user_id} eliminados exitosamente")
            return Response(status_code=204)
        else:
            raise HTTPException(
                status_code=500,
                detail="Error al eliminar los datos del usuario"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error eliminando datos del usuario {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )


@app.get("/users/{user_id}/memory")
async def get_user_memory(user_id: str):
    """
    Obtiene el contexto/memoria de un usuario (para verificación).

    Args:
        user_id: ID del usuario de Telegram

    Returns:
        El contexto almacenado del usuario
    """
    try:
        context = await memory_manager.get_user_context(user_id)
        if not context:
            raise HTTPException(
                status_code=404,
                detail=f"Usuario {user_id} no encontrado"
            )

        return {
            "user_id": user_id,
            "context": context
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo memoria del usuario {user_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error interno del servidor"
        )


if __name__ == "__main__":
    import uvicorn

    # Configurar puerto desde variables de entorno o usar 8000
    port = int(config.api_port) if hasattr(config, 'api_port') else 8000

    uvicorn.run(
        "api.server:app",
        host="0.0.0.0",
        port=port,
        reload=config.debug,
        log_level=config.log_level.lower()
    )
