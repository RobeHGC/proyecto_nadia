# api/server.py
"""Servidor API para gestión del bot y cumplimiento GDPR."""
import json
import logging
import os
from datetime import datetime
from typing import List, Optional

import redis.asyncio as redis
from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from database.models import DatabaseManager
from memory.user_memory import UserMemoryManager
from utils.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Security setup
limiter = Limiter(key_func=get_remote_address)
security = HTTPBearer()

# Pydantic models for API with validation
class ReviewApprovalRequest(BaseModel):
    final_bubbles: List[str] = Field(..., min_items=1, max_items=10)
    edit_tags: List[str] = Field(..., max_items=20)
    quality_score: int = Field(..., ge=1, le=5)
    reviewer_notes: Optional[str] = Field(None, max_length=1000)

    @field_validator('final_bubbles')
    @classmethod
    def validate_bubbles(cls, v):
        for bubble in v:
            if len(bubble.strip()) == 0:
                raise ValueError('Empty bubbles not allowed')
            if len(bubble) > 500:
                raise ValueError('Bubble too long (max 500 chars)')
        return v

    @field_validator('edit_tags')
    @classmethod
    def validate_tags(cls, v):
        allowed_tags = {
            'CTA_SOFT', 'CTA_MEDIUM', 'CTA_DIRECT',
            'REDUCED_CRINGE', 'INCREASED_FLIRT', 'MORE_CASUAL',
            'ENGLISH_SLANG', 'TEXT_SPEAK', 'STRUCT_SHORTEN',
            'STRUCT_BUBBLE', 'CONTENT_EMOJI_ADD', 'CONTENT_QUESTION',
            'CONTENT_REWRITE'
        }
        for tag in v:
            if tag not in allowed_tags:
                raise ValueError(f'Invalid tag: {tag}')
        return v

    @field_validator('reviewer_notes')
    @classmethod
    def validate_reviewer_notes(cls, v):
        if v:
            import html
            if len(v) > 1000:
                raise ValueError('Reviewer notes too long (max 1000 chars)')
            return html.escape(v.strip())
        return v


class ReviewRejectionRequest(BaseModel):
    reviewer_notes: Optional[str] = Field(None, max_length=1000)

    @field_validator('reviewer_notes')
    @classmethod
    def validate_reviewer_notes(cls, v):
        if v:
            import html
            if len(v) > 1000:
                raise ValueError('Reviewer notes too long (max 1000 chars)')
            return html.escape(v.strip())
        return v


class ReviewResponse(BaseModel):
    id: str
    user_id: str
    user_message: str
    llm1_raw_response: str
    llm2_bubbles: List[str]
    constitution_risk_score: float
    constitution_flags: List[str]
    constitution_recommendation: str
    priority_score: float
    created_at: datetime


# Crear app FastAPI
app = FastAPI(
    title="Nadia Bot API",
    description="API para gestión del bot Nadia y cumplimiento GDPR + HITL Review",
    version="0.3.0"
)

# Rate limiting setup
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Configurar CORS - SECURE
allowed_origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "https://localhost:3000"
]

# Add production origins from environment if available

if production_origins := os.getenv("ALLOWED_ORIGINS"):
    allowed_origins.extend(production_origins.split(","))

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

# Configuración global
config = Config.from_env()
memory_manager = UserMemoryManager(config.redis_url)
db_manager = DatabaseManager(config.database_url)

# Redis fallback for pending reviews
async def get_reviews_from_redis(limit: int = 20) -> List[ReviewResponse]:
    """Get pending reviews from Redis as fallback."""
    try:
        r = await redis.from_url(config.redis_url)
        
        # Get review IDs from sorted set (highest priority first)
        review_ids = await r.zrevrange("nadia_review_queue", 0, limit - 1)
        
        reviews = []
        for review_id in review_ids:
            # Get review data from hash
            review_data_json = await r.hget("nadia_review_items", review_id)
            if review_data_json:
                review_data = json.loads(review_data_json)
                reviews.append(ReviewResponse(
                    id=review_data["id"],
                    user_id=review_data["user_id"],
                    user_message=review_data["user_message"],
                    llm1_raw_response=review_data["ai_suggestion"]["llm1_raw"],
                    llm2_bubbles=review_data["ai_suggestion"]["llm2_bubbles"],
                    constitution_risk_score=review_data["ai_suggestion"]["constitution_analysis"]["risk_score"],
                    constitution_flags=review_data["ai_suggestion"]["constitution_analysis"]["flags"],
                    constitution_recommendation=review_data["ai_suggestion"]["constitution_analysis"]["recommendation"],
                    priority_score=review_data["priority"],
                    created_at=datetime.fromisoformat(review_data["timestamp"])
                ))
        
        await r.aclose()
        return reviews
        
    except Exception as e:
        logger.error(f"Error reading from Redis: {e}")
        return []

# Simple API key authentication
API_KEY = os.getenv("DASHBOARD_API_KEY", "dev-key-change-in-production")

async def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify API key for dashboard access."""
    if credentials.credentials != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return credentials.credentials


@app.on_event("startup")
async def startup_event():
    """Inicialización al arrancar el servidor."""
    logger.info("API Server iniciando...")

    # Skip database initialization in development mode
    database_mode = os.getenv("DATABASE_MODE", "normal")
    if database_mode == "skip":
        logger.info("Skipping database initialization (DATABASE_MODE=skip)")
    else:
        try:
            await db_manager.initialize()
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            logger.info("Running in no-database mode")


@app.on_event("shutdown")
async def shutdown_event():
    """Limpieza al cerrar el servidor."""
    logger.info("API Server cerrando...")
    await memory_manager.close()
    await db_manager.close()


@app.get("/")
async def root():
    """Endpoint raíz de bienvenida."""
    return {
        "message": "Nadia Bot API - HITL Review System",
        "version": "0.3.0",
        "endpoints": {
            "health": "/health",
            "delete_user": "DELETE /users/{user_id}/memory",
            "pending_reviews": "GET /reviews/pending",
            "approve_review": "POST /reviews/{review_id}/approve",
            "reject_review": "POST /reviews/{review_id}/reject",
            "dashboard_metrics": "GET /metrics/dashboard",
            "edit_taxonomy": "GET /edit-taxonomy"
        }
    }


@app.get("/health")
async def health_check():
    """Verifica el estado de salud del servicio."""
    services = {"api": "ok", "redis": "unknown", "database": "unknown"}
    status = "healthy"

    try:
        # Verificar conexión a Redis
        r = await redis.from_url(config.redis_url)
        await r.ping()
        await r.aclose()
        services["redis"] = "ok"
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        services["redis"] = "error"
        status = "unhealthy"

    try:
        # Verificar conexión a PostgreSQL
        async with db_manager._pool.acquire() as conn:
            await conn.fetchval("SELECT 1")
        services["database"] = "ok"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        services["database"] = "error"
        status = "unhealthy"

    return {
        "status": status,
        "services": services
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


# ════════════════════════════════════════════════════════════════
# HITL Review Management Endpoints
# ════════════════════════════════════════════════════════════════

@app.get("/reviews/pending", response_model=List[ReviewResponse])
@limiter.limit("30/minute")
async def get_pending_reviews(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    min_priority: float = Query(0.0, ge=0.0, le=1.0),
    api_key: str = Depends(verify_api_key)
):
    """Get pending reviews ordered by priority."""
    try:
        # Return data from Redis if no database
        database_mode = os.getenv("DATABASE_MODE", "normal")
        if database_mode == "skip":
            return await get_reviews_from_redis(limit=limit)

        try:
            reviews = await db_manager.get_pending_reviews(limit=limit, min_priority=min_priority)
            return [
                ReviewResponse(
                    id=str(review["id"]),
                    user_id=review["user_id"],
                    user_message=review["user_message"],
                    llm1_raw_response=review["llm1_raw_response"],
                    llm2_bubbles=review["llm2_bubbles"],
                    constitution_risk_score=review["constitution_risk_score"],
                    constitution_flags=review["constitution_flags"],
                    constitution_recommendation=review["constitution_recommendation"],
                    priority_score=review["priority_score"],
                    created_at=review["created_at"]
                )
                for review in reviews
            ]
        except Exception as e:
            logger.error(f"Database read failed: {e}")
            # Fallback to Redis
            return await get_reviews_from_redis(limit=limit)
    except Exception as e:
        logger.error(f"Error getting pending reviews: {e}")
        return []  # Return empty list instead of error


@app.get("/reviews/{review_id}")
async def get_review(review_id: str):
    """Get a specific review by ID."""
    try:
        review = await db_manager.get_interaction(review_id)
        if not review:
            raise HTTPException(status_code=404, detail="Review not found")

        return review
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting review {review_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/reviews/{review_id}/approve")
async def approve_review(review_id: str, request: ReviewApprovalRequest):
    """Approve a review and send the message."""
    try:
        # Start the review (mark as reviewing)
        started = await db_manager.start_review(review_id, "api_user")  # TODO: Add proper user auth
        if not started:
            raise HTTPException(status_code=404, detail="Review not found or already being reviewed")

        # NUEVO: Check if CTA was inserted and create CTA data
        cta_data = None
        cta_tags = [tag for tag in request.edit_tags if tag.startswith('CTA_')]

        if cta_tags:
            # Extract CTA type from tag (e.g., "CTA_SOFT" -> "SOFT")
            cta_type = cta_tags[0].replace('CTA_', '').lower()

            # TODO: In a real implementation, get conversation_depth from context
            cta_data = {
                "inserted": True,
                "type": cta_type,
                "conversation_depth": 1,  # Placeholder - should come from conversation history
                "timestamp": datetime.now().isoformat(),
                "tags": cta_tags
            }

            logger.info(f"CTA {cta_type} inserted in review {review_id}")

        # Approve the review (now with CTA data)
        approved = await db_manager.approve_review(
            review_id,
            request.final_bubbles,
            request.edit_tags,
            request.quality_score,
            request.reviewer_notes,
            cta_data
        )

        if not approved:
            raise HTTPException(status_code=400, detail="Failed to approve review")

        # Send the approved message via Redis notification
        # The bot will pick it up and send to user
        try:
            r = await redis.from_url(config.redis_url)
            await r.lpush("nadia_approved_messages", json.dumps({
                "review_id": review_id,
                "bubbles": request.final_bubbles
            }))
            await r.aclose()
        except Exception as e:
            logger.error(f"Error notifying bot: {e}")

        response_data = {"status": "approved", "review_id": review_id}
        if cta_data:
            response_data["cta_inserted"] = True
            response_data["cta_type"] = cta_data["type"]

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving review {review_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/reviews/{review_id}/reject")
async def reject_review(review_id: str, request: ReviewRejectionRequest):
    """Reject a review."""
    try:
        # Start the review (mark as reviewing)
        started = await db_manager.start_review(review_id, "api_user")  # TODO: Add proper user auth
        if not started:
            raise HTTPException(status_code=404, detail="Review not found or already being reviewed")

        # Reject the review
        rejected = await db_manager.reject_review(review_id, request.reviewer_notes)

        if not rejected:
            raise HTTPException(status_code=400, detail="Failed to reject review")

        return {"status": "rejected", "review_id": review_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting review {review_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/metrics/dashboard")
@limiter.limit("60/minute")
async def get_dashboard_metrics(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """Get metrics for the dashboard."""
    try:
        # Return mock data if no database
        database_mode = os.getenv("DATABASE_MODE", "normal")
        if database_mode == "skip":
            return {
                "pending_reviews": 0,
                "reviewed_today": 0,
                "avg_review_time_seconds": 0,
                "popular_edit_tags": []
            }

        metrics = await db_manager.get_dashboard_metrics()
        return metrics
    except Exception as e:
        logger.error(f"Error getting dashboard metrics: {e}")
        return {
            "pending_reviews": 0,
            "reviewed_today": 0,
            "avg_review_time_seconds": 0,
            "popular_edit_tags": []
        }


@app.get("/edit-taxonomy")
@limiter.limit("60/minute")
async def get_edit_taxonomy(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """Get available edit tags."""
    try:
        # Return mock data if no database
        database_mode = os.getenv("DATABASE_MODE", "normal")
        if database_mode == "skip":
            return [
                {"code": "CTA_SOFT", "category": "CTA", "description": "Soft call to action"},
                {"code": "CTA_MEDIUM", "category": "CTA", "description": "Medium call to action"},
                {"code": "CTA_DIRECT", "category": "CTA", "description": "Direct call to action"},
                {"code": "REDUCED_CRINGE", "category": "STYLE", "description": "Reduce cringe factor"},
                {"code": "INCREASED_FLIRT", "category": "STYLE", "description": "Increase flirtiness"},
                {"code": "MORE_CASUAL", "category": "STYLE", "description": "Make more casual"},
                {"code": "ENGLISH_SLANG", "category": "LANGUAGE", "description": "Add English slang"},
                {"code": "TEXT_SPEAK", "category": "LANGUAGE", "description": "Add text speak"},
                {"code": "STRUCT_SHORTEN", "category": "STRUCTURE", "description": "Shorten message"},
                {"code": "STRUCT_BUBBLE", "category": "STRUCTURE", "description": "Split into bubbles"},
                {"code": "CONTENT_EMOJI_ADD", "category": "CONTENT", "description": "Add emojis"},
                {"code": "CONTENT_QUESTION", "category": "CONTENT", "description": "Add question"},
                {"code": "CONTENT_REWRITE", "category": "CONTENT", "description": "Complete rewrite"}
            ]

        taxonomy = await db_manager.get_edit_taxonomy()
        return taxonomy
    except Exception as e:
        logger.error(f"Error getting edit taxonomy: {e}")
        # Return mock data on error
        return [
            {"code": "CTA_SOFT", "category": "CTA", "description": "Soft call to action"},
            {"code": "CTA_MEDIUM", "category": "CTA", "description": "Medium call to action"},
            {"code": "CTA_DIRECT", "category": "CTA", "description": "Direct call to action"}
        ]


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
