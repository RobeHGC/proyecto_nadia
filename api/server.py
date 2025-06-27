# api/server.py
"""Servidor API para gestión del bot y cumplimiento GDPR."""
import json
import logging
import os
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

import redis.asyncio as redis
from fastapi import Depends, FastAPI, HTTPException, Header, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from database.models import DatabaseManager
from memory.user_memory import UserMemoryManager
from llms.quota_manager import GeminiQuotaManager
from llms.model_registry import get_model_registry
from llms.dynamic_router import get_dynamic_router
from utils.config import Config
from .data_analytics import analytics_manager, AnalyticsDataRequest, BackupRequest, CleanDataRequest

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
            'REDUCED_CRINGE', 'INCREASED_FLIRT',
            'ENGLISH_SLANG', 'TEXT_SPEAK', 'STRUCT_SHORTEN',
            'STRUCT_BUBBLE', 'CONTENT_EMOJI_ADD', 'CONTENT_EMOJI_CUT', 'CONTENT_QUESTION',
            'CONTENT_REWRITE', 'TONE_LESS_IA', 'CONTENT_QUESTION_CUT', 
            'CONTENT_SENTENCE_ADD', 'TONE_ROMANTIC_UP',
            # Missing tags from DATABASE_SCHEMA.sql
            'TONE_CASUAL', 'TONE_FLIRT_UP', 'TONE_CRINGE_DOWN', 'TONE_ENERGY_UP'
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


class RecoveryTriggerRequest(BaseModel):
    user_id: Optional[str] = Field(None, description="Specific user ID to recover, or None for all users")
    max_messages: Optional[int] = Field(None, ge=1, le=500, description="Maximum messages to recover per user")


class CursorUpdateRequest(BaseModel):
    telegram_message_id: int = Field(..., ge=1, description="Last processed Telegram message ID")
    telegram_date: str = Field(..., description="Last processed message date (ISO format)")
    messages_recovered: int = Field(0, ge=0, description="Number of messages recovered in this update")


# New model management request models
class ProfileSwitchRequest(BaseModel):
    profile_name: str = Field(..., min_length=1, max_length=50)
    
    @field_validator('profile_name')
    @classmethod
    def validate_profile_name(cls, v):
        # Only allow alphanumeric and underscores
        import re
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Profile name must contain only alphanumeric characters, hyphens, and underscores')
        return v

class CustomerStatusUpdateRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    customer_status: str = Field(..., pattern='^(PROSPECT|LEAD_QUALIFIED|CUSTOMER|CHURNED|LEAD_EXHAUSTED)$')
    reason: str = Field("Manual update from dashboard", max_length=200)
    ltv_amount: float = Field(0.0, ge=0.0, le=10000.0)  # Max $10k LTV

class NicknameUpdateRequest(BaseModel):
    nickname: str = Field(..., max_length=50, min_length=1)
    reason: str = Field("Manual update from dashboard", max_length=200)


class ReviewerNotesUpdateRequest(BaseModel):
    reviewer_notes: str = Field(..., max_length=1000)
    
    @field_validator('reviewer_notes')
    @classmethod
    def validate_reviewer_notes(cls, v):
        import html
        return html.escape(v.strip()) if v else ""


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
    # Multi-LLM tracking fields
    llm1_model: Optional[str] = None
    llm2_model: Optional[str] = None
    llm1_cost_usd: Optional[float] = None
    llm2_cost_usd: Optional[float] = None
    # Customer status tracking
    customer_status: Optional[str] = "PROSPECT"


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
quota_manager = GeminiQuotaManager(config.redis_url)

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
                    created_at=datetime.fromisoformat(review_data["timestamp"]),
                    # Multi-LLM tracking fields
                    llm1_model=review_data["ai_suggestion"].get("llm1_model"),
                    llm2_model=review_data["ai_suggestion"].get("llm2_model"),
                    llm1_cost_usd=review_data["ai_suggestion"].get("llm1_cost"),
                    llm2_cost_usd=review_data["ai_suggestion"].get("llm2_cost"),
                    customer_status=review_data.get("customer_status", "PROSPECT")
                ))
        
        await r.aclose()
        return reviews
        
    except Exception as e:
        logger.error(f"Error reading from Redis: {e}")
        return []

# Simple API key authentication
API_KEY = os.getenv("DASHBOARD_API_KEY")
if not API_KEY:
    logger.error("DASHBOARD_API_KEY environment variable is required!")
    raise ValueError("DASHBOARD_API_KEY must be set in environment variables")

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
            "edit_taxonomy": "GET /edit-taxonomy",
            "recovery_status": "GET /recovery/status",
            "recovery_trigger": "POST /recovery/trigger",
            "recovery_history": "GET /recovery/history",
            "recovery_cursor": "GET/POST /recovery/cursor/{user_id}"
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
                    created_at=review["created_at"],
                    # Multi-LLM tracking fields
                    llm1_model=review.get("llm1_model"),
                    llm2_model=review.get("llm2_model"),
                    llm1_cost_usd=review.get("llm1_cost_usd"),
                    llm2_cost_usd=review.get("llm2_cost_usd"),
                    # Customer status
                    customer_status=review.get("current_customer_status", "PROSPECT")
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
        # Check if database mode is skip
        database_mode = os.getenv("DATABASE_MODE", "normal")
        if database_mode == "skip":
            # Get from Redis
            r = await redis.from_url(config.redis_url)
            review_data_json = await r.hget("nadia_review_items", review_id)
            await r.aclose()
            
            if not review_data_json:
                raise HTTPException(status_code=404, detail="Review not found")
                
            review_data = json.loads(review_data_json)
            return ReviewResponse(
                id=review_data["id"],
                user_id=review_data["user_id"],
                user_message=review_data["user_message"],
                llm1_raw_response=review_data["ai_suggestion"]["llm1_raw"],
                llm2_bubbles=review_data["ai_suggestion"]["llm2_bubbles"],
                constitution_risk_score=review_data["ai_suggestion"]["constitution_analysis"]["risk_score"],
                constitution_flags=review_data["ai_suggestion"]["constitution_analysis"]["flags"],
                constitution_recommendation=review_data["ai_suggestion"]["constitution_analysis"]["recommendation"],
                priority_score=review_data["priority"],
                created_at=datetime.fromisoformat(review_data["timestamp"]),
                llm1_model=review_data["ai_suggestion"].get("llm1_model"),
                llm2_model=review_data["ai_suggestion"].get("llm2_model"),
                llm1_cost_usd=review_data["ai_suggestion"].get("llm1_cost"),
                llm2_cost_usd=review_data["ai_suggestion"].get("llm2_cost"),
                customer_status=review_data.get("customer_status", "PROSPECT")
            )
        
        # Try database first
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
        # Check if database mode is skip
        database_mode = os.getenv("DATABASE_MODE", "normal")
        
        if database_mode != "skip":
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
        if database_mode != "skip":
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

        # Send the approved message via Redis notification and cleanup
        # The bot will pick it up and send to user
        try:
            r = await redis.from_url(config.redis_url)
            
            # Send approval notification
            await r.lpush("nadia_approved_messages", json.dumps({
                "review_id": review_id,
                "bubbles": request.final_bubbles
            }))
            
            # Remove from review queue
            await r.zrem("nadia_review_queue", review_id)
            await r.hdel("nadia_review_items", review_id)
            
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
        # Check if database mode is skip
        database_mode = os.getenv("DATABASE_MODE", "normal")
        
        if database_mode != "skip":
            # Start the review (mark as reviewing)
            started = await db_manager.start_review(review_id, "api_user")  # TODO: Add proper user auth
            if not started:
                raise HTTPException(status_code=404, detail="Review not found or already being reviewed")

            # Reject the review
            rejected = await db_manager.reject_review(review_id, request.reviewer_notes)

            if not rejected:
                raise HTTPException(status_code=400, detail="Failed to reject review")

        # Remove from Redis queue regardless of database mode
        try:
            r = await redis.from_url(config.redis_url)
            
            # Remove from review queue
            await r.zrem("nadia_review_queue", review_id)
            await r.hdel("nadia_review_items", review_id)
            
            await r.aclose()
        except Exception as e:
            logger.error(f"Error cleaning up Redis: {e}")

        return {"status": "rejected", "review_id": review_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting review {review_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/reviews/{review_id}/cancel")
async def cancel_review(review_id: str, request: ReviewRejectionRequest):
    """Cancel a review without saving any edits to database.
    
    This endpoint properly handles review cancellation by:
    1. Returning the review to pending state in database
    2. Clearing reviewer assignment
    3. NOT saving any edited content
    4. Keeping the review in Redis queue for other reviewers
    
    This prevents data contamination from cancelled reviews.
    """
    try:
        # Check if database mode is skip
        database_mode = os.getenv("DATABASE_MODE", "normal")
        
        if database_mode != "skip":
            # Cancel the review in database (returns to pending state)
            cancelled = await db_manager.cancel_review(review_id, request.reviewer_notes)
            
            if not cancelled:
                raise HTTPException(status_code=404, detail="Review not found or not in reviewing state")
        
        # Important: Do NOT remove from Redis queue - leave it for other reviewers
        # This is the key difference from approve/reject which remove the item
        
        return {
            "status": "cancelled", 
            "review_id": review_id,
            "message": "Review cancelled successfully. Returned to pending state for other reviewers."
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting review {review_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


async def get_model_distribution() -> dict:
    """Get model usage distribution for today."""
    try:
        async with db_manager._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT 
                    llm1_model,
                    llm2_model,
                    COUNT(*) as count
                FROM interactions 
                WHERE DATE(created_at) = CURRENT_DATE
                GROUP BY llm1_model, llm2_model
                """
            )
            
            distribution = {"gemini": 0, "gpt": 0, "other": 0}
            
            for row in rows:
                count = row["count"]
                llm1_model = row.get("llm1_model", "")
                llm2_model = row.get("llm2_model", "")
                
                # Count LLM-1 usage
                if "gemini" in llm1_model.lower():
                    distribution["gemini"] += count
                elif "gpt" in llm1_model.lower():
                    distribution["gpt"] += count
                else:
                    distribution["other"] += count
                
                # Count LLM-2 usage (separate)
                if "gemini" in llm2_model.lower():
                    distribution["gemini"] += count
                elif "gpt" in llm2_model.lower():
                    distribution["gpt"] += count
                else:
                    distribution["other"] += count
            
            return distribution
            
    except Exception as e:
        logger.error(f"Error getting model distribution: {e}")
        return {"gemini": 0, "gpt": 0, "other": 0}


async def calculate_daily_savings(model_stats: dict) -> float:
    """Calculate estimated savings from using Gemini vs OpenAI for today."""
    try:
        # Estimated savings calculation
        # Assuming average tokens per interaction and cost differences
        
        gemini_interactions = model_stats.get("gemini", 0)
        
        # Rough estimates based on typical usage:
        # - Average tokens per creative response: ~500 tokens
        # - Gemini 2.0 Flash: $0.001/1K tokens input, $0.002/1K output
        # - GPT-4o-mini: $0.00015/1K tokens input, $0.0006/1K output
        
        avg_tokens_per_interaction = 500
        
        # Cost if all were OpenAI GPT-4o-mini
        openai_cost_per_interaction = (avg_tokens_per_interaction / 1000) * (0.00015 + 0.0006)
        
        # Cost for Gemini (free tier)
        gemini_cost_per_interaction = 0.0  # Free tier
        
        # Calculate savings
        savings = gemini_interactions * (openai_cost_per_interaction - gemini_cost_per_interaction)
        
        return round(savings, 4)
        
    except Exception as e:
        logger.error(f"Error calculating savings: {e}")
        return 0.0


@app.get("/metrics/dashboard")
@limiter.limit("60/minute")
async def get_dashboard_metrics(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """Get metrics for the dashboard."""
    try:
        # Return data from Redis if no database
        database_mode = os.getenv("DATABASE_MODE", "normal")
        if database_mode == "skip":
            # Count pending reviews from Redis
            r = await redis.from_url(config.redis_url)
            pending_count = await r.zcard("nadia_review_queue")
            quota_status = await quota_manager.get_quota_status()
            await r.aclose()
            
            return {
                "pending_reviews": pending_count,
                "reviewed_today": 0,
                "avg_review_time_seconds": 0,
                "popular_edit_tags": [],
                # Multi-LLM metrics from quota manager
                "gemini_quota_used_today": quota_status["daily_usage"],
                "gemini_quota_total": quota_status["daily_limit"],
                "savings_today_usd": 0.0,
                "model_distribution": {"gemini": 0, "gpt": 0}
            }

        # Get base metrics from database
        metrics = await db_manager.get_dashboard_metrics()
        
        # Add multi-LLM metrics
        quota_status = await quota_manager.get_quota_status()
        
        # Get model distribution from database
        model_stats = await get_model_distribution()
        
        # Calculate savings (estimate based on model usage)
        savings = await calculate_daily_savings(model_stats)
        
        # Extend metrics with multi-LLM data
        metrics.update({
            "gemini_quota_used_today": quota_status["daily_usage"],
            "gemini_quota_total": quota_status["daily_limit"],
            "savings_today_usd": savings,
            "model_distribution": model_stats
        })
        
        return metrics
    except Exception as e:
        logger.error(f"Error getting dashboard metrics: {e}")
        return {
            "pending_reviews": 0,
            "reviewed_today": 0,
            "avg_review_time_seconds": 0,
            "popular_edit_tags": [],
            # Multi-LLM metrics (error fallback)
            "gemini_quota_used_today": 0,
            "gemini_quota_total": 32000,
            "savings_today_usd": 0.0,
            "model_distribution": {"gemini": 0, "gpt": 0}
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
                {"code": "ENGLISH_SLANG", "category": "LANGUAGE", "description": "Add English slang"},
                {"code": "TEXT_SPEAK", "category": "LANGUAGE", "description": "Add text speak"},
                {"code": "STRUCT_SHORTEN", "category": "STRUCTURE", "description": "Shorten message"},
                {"code": "STRUCT_BUBBLE", "category": "STRUCTURE", "description": "Split into bubbles"},
                {"code": "CONTENT_EMOJI_ADD", "category": "CONTENT", "description": "Add emojis"},
                {"code": "CONTENT_EMOJI_CUT", "category": "CONTENT", "description": "Remove excessive emojis"},
                {"code": "CONTENT_QUESTION", "category": "CONTENT", "description": "Add question"},
                {"code": "CONTENT_QUESTION_CUT", "category": "CONTENT", "description": "Remove questions"},
                {"code": "CONTENT_SENTENCE_ADD", "category": "CONTENT", "description": "Add sentences"},
                {"code": "CONTENT_REWRITE", "category": "CONTENT", "description": "Complete rewrite"},
                {"code": "TONE_LESS_IA", "category": "TONE", "description": "Make less AI-like"},
                {"code": "TONE_ROMANTIC_UP", "category": "TONE", "description": "Increase romantic tone"}
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


# ===== NEW MODEL MANAGEMENT ENDPOINTS =====

@app.get("/api/models")
@limiter.limit("30/minute")
async def get_available_models(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """Get all available models by provider."""
    try:
        registry = get_model_registry()
        models = registry.list_available_models()
        
        # Get detailed model information
        detailed_models = {}
        for provider, model_list in models.items():
            detailed_models[provider] = {}
            for model_name in model_list:
                model_config = registry.get_model_config(provider, model_name)
                if model_config:
                    detailed_models[provider][model_name] = {
                        'model_id': model_config.model_id,
                        'description': model_config.description,
                        'capabilities': model_config.capabilities,
                        'context_window': model_config.context_window,
                        'cost_per_million_input': model_config.cost_per_million_input,
                        'cost_per_million_output': model_config.cost_per_million_output,
                        'free_quota': model_config.free_quota,
                        'rpm_limit': model_config.rpm_limit
                    }
        
        return {
            'models': detailed_models,
            'total_providers': len(models),
            'total_models': sum(len(model_list) for model_list in models.values())
        }
    except Exception as e:
        logger.error(f"Error getting available models: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve models")


@app.get("/api/models/profiles")
@limiter.limit("30/minute")
async def get_available_profiles(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """Get all available model profiles."""
    try:
        registry = get_model_registry()
        profiles = registry.get_profile_details()
        
        return {
            'profiles': profiles,
            'total_profiles': len(profiles),
            'default_profile': registry.get_default_profile()
        }
    except Exception as e:
        logger.error(f"Error getting available profiles: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve profiles")


@app.post("/api/models/profile")
@limiter.limit("10/minute")
async def switch_profile(
    request: Request,
    profile_request: ProfileSwitchRequest,
    api_key: str = Depends(verify_api_key)
):
    """Switch to a different model profile (hot-swap)."""
    try:
        registry = get_model_registry()
        
        # Validate profile exists
        is_valid, error_msg = registry.validate_profile(profile_request.profile_name)
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid profile '{profile_request.profile_name}': {error_msg}"
            )
        
        # Get router instance and switch profile
        router = get_dynamic_router()
        success = router.switch_profile(profile_request.profile_name)
        
        if not success:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to switch to profile '{profile_request.profile_name}'"
            )
        
        # Get updated router stats
        stats = router.get_router_stats()
        
        return {
            'success': True,
            'message': f"Successfully switched to profile '{profile_request.profile_name}'",
            'current_profile': stats['current_profile'],
            'profile_details': stats['profile_details'],
            'clients_status': stats['clients_status']
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error switching profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to switch profile")


@app.get("/api/models/current")
@limiter.limit("60/minute")
async def get_current_model_status(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """Get current model status and router statistics."""
    try:
        router = get_dynamic_router()
        registry = get_model_registry()
        
        # Get router stats
        router_stats = router.get_router_stats()
        
        # Get registry stats
        registry_stats = registry.get_registry_stats()
        
        # Health check
        health = router.health_check()
        
        return {
            'router': router_stats,
            'registry': registry_stats,
            'health': health,
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting model status: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve model status")


@app.get("/api/models/cache-metrics")
@limiter.limit("60/minute")
async def get_cache_metrics(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """Get OpenAI prompt cache metrics for optimization monitoring."""
    try:
        # Get SupervisorAgent instance from global supervisor
        # This assumes you have a global supervisor instance
        # If not, you'd need to adapt this to your application structure
        
        # For now, return structure that will be populated when supervisor is available
        return {
            'cache_metrics': {
                'stable_tokens': 0,
                'persona_file': 'persona/nadia_v1.md',
                'cache_ratio': 0.0,
                'last_cost': 0.0,
                'cache_status': 'unknown'
            },
            'optimizations': {
                'cache_enabled': True,
                'warm_up_completed': False,
                'tokens_minimum_met': False,
                'persona_loaded': False
            },
            'recommendations': [
                'Cache metrics will be available after first LLM2 refinement call',
                'Monitor cache ratio - should be >70% for optimal cost savings',
                'Warm-up is performed automatically on first refinement'
            ],
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting cache metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve cache metrics")


@app.post("/api/models/reload")
@limiter.limit("5/minute")
async def reload_model_registry(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """Force reload the model registry configuration."""
    try:
        registry = get_model_registry()
        router = get_dynamic_router()
        
        # Reload registry
        registry_success = registry.reload_config()
        
        # Reload router (which will use updated registry)
        router_success = router.reload_registry()
        
        if not registry_success:
            raise HTTPException(status_code=500, detail="Failed to reload model registry")
        
        return {
            'success': True,
            'message': 'Model registry and router reloaded successfully',
            'registry_reloaded': registry_success,
            'router_reloaded': router_success,
            'timestamp': datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reloading model registry: {e}")
        raise HTTPException(status_code=500, detail="Failed to reload model registry")


@app.get("/api/models/cost-estimate")
@limiter.limit("30/minute")
async def get_cost_estimate(
    request: Request,
    profile: str = Query(..., description="Profile name to estimate cost for"),
    input_tokens: int = Query(100, ge=1, le=100000, description="Number of input tokens"),
    output_tokens: int = Query(100, ge=1, le=100000, description="Number of output tokens"),
    api_key: str = Depends(verify_api_key)
):
    """Get cost estimate for a profile with given token usage."""
    try:
        registry = get_model_registry()
        
        # Validate profile
        is_valid, error_msg = registry.validate_profile(profile)
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid profile '{profile}': {error_msg}"
            )
        
        # Calculate cost estimate
        cost = registry.get_cost_estimate(profile, input_tokens, output_tokens)
        
        # Get profile details for context
        profile_config = registry.get_profile(profile)
        
        return {
            'profile': profile,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'estimated_cost_usd': cost,
            'profile_details': {
                'name': profile_config.name,
                'llm1': f"{profile_config.llm1_provider}/{profile_config.llm1_model}",
                'llm2': f"{profile_config.llm2_provider}/{profile_config.llm2_model}",
                'estimated_cost_per_1k_messages': profile_config.estimated_cost_per_1k_messages
            } if profile_config else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error calculating cost estimate: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate cost estimate")


# ===== NEW DASHBOARD HELPER ENDPOINTS =====

@app.get("/api/dashboard/cost-tracking")
@limiter.limit("60/minute")
async def get_cost_tracking(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """Get comprehensive cost tracking data for the dashboard."""
    try:
        registry = get_model_registry()
        router = get_dynamic_router()
        
        # Get current profile
        current_profile = router.current_profile
        
        # Calculate today's costs
        async with db_manager._pool.acquire() as conn:
            # Get today's interaction counts and costs
            today_stats = await conn.fetchrow(
                """
                SELECT 
                    COUNT(*) as total_interactions,
                    SUM(COALESCE(llm1_cost_usd, 0)) as llm1_total_cost,
                    SUM(COALESCE(llm2_cost_usd, 0)) as llm2_total_cost,
                    COUNT(DISTINCT user_id) as unique_users
                FROM interactions 
                WHERE DATE(created_at) = CURRENT_DATE
                """
            )
            
            # Get model distribution with costs
            model_costs = await conn.fetch(
                """
                SELECT 
                    llm1_model,
                    llm2_model,
                    COUNT(*) as count,
                    SUM(COALESCE(llm1_cost_usd, 0) + COALESCE(llm2_cost_usd, 0)) as total_cost
                FROM interactions 
                WHERE DATE(created_at) = CURRENT_DATE
                GROUP BY llm1_model, llm2_model
                ORDER BY count DESC
                """
            )
        
        # Calculate projections for current profile
        messages_today = today_stats['total_interactions'] or 0
        cost_estimate = registry.estimate_conversation_cost(
            messages=messages_today,
            profile=current_profile
        )
        
        # Get cheapest available model
        cheapest = registry.get_cheapest_available_model(
            min_capabilities=['text'],
            consider_quota=True,
            consider_cache=True
        )
        
        return {
            'current_profile': current_profile,
            'today': {
                'total_interactions': messages_today,
                'unique_users': today_stats['unique_users'] or 0,
                'actual_cost': float((today_stats['llm1_total_cost'] or 0) + (today_stats['llm2_total_cost'] or 0)),
                'estimated_cost': cost_estimate.get('total_cost', 0),
                'free_tier_usage': cost_estimate.get('free_tier_messages', 0),
                'paid_messages': cost_estimate.get('paid_messages', 0)
            },
            'projections': {
                'daily_cost': cost_estimate.get('daily_cost', 0),
                'monthly_cost': cost_estimate.get('monthly_projection', 0),
                'cost_per_message': cost_estimate.get('cost_per_message', 0)
            },
            'savings': {
                'vs_openai_only': cost_estimate.get('savings_vs_openai', 0),
                'savings_percentage': cost_estimate.get('savings_percentage', 0),
                'cache_savings': cost_estimate.get('cache_savings', 0)
            },
            'model_breakdown': [
                {
                    'llm1': row['llm1_model'],
                    'llm2': row['llm2_model'],
                    'count': row['count'],
                    'cost': float(row['total_cost'] or 0)
                }
                for row in model_costs
            ],
            'recommendations': {
                'cheapest_model': cheapest,
                'optimal_profile': 'smart_economic' if messages_today > 100 else 'free_tier'
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting cost tracking data: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve cost tracking data")


@app.get("/api/dashboard/profile-comparison")
@limiter.limit("30/minute")
async def get_profile_comparison(
    request: Request,
    messages: int = Query(1000, ge=1, le=1000000, description="Number of messages to estimate"),
    api_key: str = Depends(verify_api_key)
):
    """Compare cost estimates across all profiles."""
    try:
        registry = get_model_registry()
        profiles = registry.list_available_profiles()
        
        comparisons = []
        for profile_name in profiles:
            profile_config = registry.get_profile(profile_name)
            if profile_config:
                estimate = registry.estimate_conversation_cost(
                    messages=messages,
                    profile=profile_name
                )
                
                comparisons.append({
                    'profile': profile_name,
                    'name': profile_config.name,
                    'description': profile_config.description,
                    'llm1': f"{profile_config.llm1_provider}/{profile_config.llm1_model}",
                    'llm2': f"{profile_config.llm2_provider}/{profile_config.llm2_model}",
                    'use_case': profile_config.use_case,
                    'cost_estimate': {
                        'total': estimate.get('total_cost', 0),
                        'per_message': estimate.get('cost_per_message', 0),
                        'monthly': estimate.get('monthly_projection', 0),
                        'free_tier_usage': estimate.get('free_tier_messages', 0),
                        'cache_savings': estimate.get('cache_savings', 0)
                    }
                })
        
        # Sort by total cost
        comparisons.sort(key=lambda x: x['cost_estimate']['total'])
        
        return {
            'messages': messages,
            'profiles': comparisons,
            'cheapest': comparisons[0] if comparisons else None,
            'most_expensive': comparisons[-1] if comparisons else None
        }
        
    except Exception as e:
        logger.error(f"Error comparing profiles: {e}")
        raise HTTPException(status_code=500, detail="Failed to compare profiles")


@app.post("/users/{user_id}/customer-status")
@limiter.limit("10/minute")
async def update_customer_status(
    request: Request,
    user_id: str,
    status_request: CustomerStatusUpdateRequest,
    api_key: str = Depends(verify_api_key)
):
    """Update customer status for a specific user"""
    
    try:
        database_mode = os.getenv("DATABASE_MODE", "normal")
        if database_mode == "skip":
            return {"status": "success", "message": "Database mode is skip, status not updated"}
        
        # Simple update to single source of truth
        async with db_manager._pool.acquire() as conn:
            # Update or insert into user_current_status table
            await conn.execute(
                """
                INSERT INTO user_current_status (user_id, customer_status, ltv_usd, updated_at)
                VALUES ($1, $2, $3, NOW())
                ON CONFLICT (user_id) 
                DO UPDATE SET 
                    customer_status = EXCLUDED.customer_status,
                    ltv_usd = CASE 
                        WHEN EXCLUDED.customer_status = 'CUSTOMER' 
                        THEN user_current_status.ltv_usd + EXCLUDED.ltv_usd
                        ELSE user_current_status.ltv_usd
                    END,
                    updated_at = NOW()
                """,
                user_id,
                status_request.customer_status,
                status_request.ltv_amount
            )
        
        logger.info(f"Customer status updated for user {user_id} to {status_request.customer_status}")
        
        return {
            "status": "success",
            "user_id": user_id,
            "new_status": status_request.customer_status,
            "ltv_added": status_request.ltv_amount
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating customer status for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update customer status")


@app.post("/users/{user_id}/nickname")
@limiter.limit("10/minute")
async def update_nickname(
    request: Request,
    user_id: str,
    nickname_request: NicknameUpdateRequest,
    api_key: str = Depends(verify_api_key)
):
    """Update nickname for a specific user"""
    
    try:
        database_mode = os.getenv("DATABASE_MODE", "normal")
        if database_mode == "skip":
            return {"status": "success", "message": "Database mode is skip, nickname not updated"}
        
        # Update or insert nickname in user_current_status table
        async with db_manager._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO user_current_status (user_id, nickname, updated_at)
                VALUES ($1, $2, NOW())
                ON CONFLICT (user_id) 
                DO UPDATE SET 
                    nickname = EXCLUDED.nickname,
                    updated_at = NOW()
                """,
                user_id,
                nickname_request.nickname
            )
        
        logger.info(f"Nickname updated for user {user_id} to '{nickname_request.nickname}'")
        
        return {
            "status": "success",
            "user_id": user_id,
            "new_nickname": nickname_request.nickname
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating nickname for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update nickname")


@app.post("/interactions/{interaction_id}/reviewer-notes")
@limiter.limit("10/minute")
async def update_reviewer_notes(
    request: Request,
    interaction_id: str,
    notes_request: ReviewerNotesUpdateRequest,
    api_key: str = Depends(verify_api_key)
):
    """Update reviewer notes for a specific interaction"""
    
    try:
        database_mode = os.getenv("DATABASE_MODE", "normal")
        if database_mode == "skip":
            return {"status": "success", "message": "Database mode is skip, notes not updated"}
        
        # Update reviewer notes in interactions table
        async with db_manager._pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE interactions 
                SET reviewer_notes = $1, updated_at = NOW()
                WHERE id = $2::UUID
                """,
                notes_request.reviewer_notes,
                interaction_id
            )
            
            # Check if any row was updated
            if result == "UPDATE 0":
                raise HTTPException(status_code=404, detail="Interaction not found")
        
        logger.info(f"Reviewer notes updated for interaction {interaction_id}")
        
        return {
            "status": "success",
            "interaction_id": interaction_id,
            "reviewer_notes": notes_request.reviewer_notes
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating reviewer notes for interaction {interaction_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update reviewer notes")


@app.get("/users/{user_id}/customer-status")
@limiter.limit("30/minute")
async def get_customer_status(
    request: Request,
    user_id: str,
    api_key: str = Depends(verify_api_key)
):
    """Get current customer status for a specific user"""
    
    try:
        database_mode = os.getenv("DATABASE_MODE", "normal")
        if database_mode == "skip":
            return {"customer_status": "PROSPECT", "ltv_usd": 0.0, "message": "Database mode is skip"}
        
        async with db_manager._pool.acquire() as conn:
            # Simple query from single source of truth
            user_status = await conn.fetchrow(
                """
                SELECT 
                    customer_status,
                    ltv_usd,
                    nickname,
                    updated_at
                FROM user_current_status
                WHERE user_id = $1
                """,
                user_id
            )
            
            if not user_status:
                # User not in status table yet - default to PROSPECT
                return {
                    "customer_status": "PROSPECT",
                    "ltv_usd": 0.0,
                    "nickname": None,
                    "updated_at": None
                }
            
            return {
                "customer_status": user_status['customer_status'],
                "ltv_usd": float(user_status['ltv_usd'] or 0),
                "nickname": user_status['nickname'],
                "updated_at": user_status['updated_at'].isoformat() if user_status['updated_at'] else None
            }
        
    except Exception as e:
        logger.error(f"Error getting customer status for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get customer status")


# =================== DATA ANALYTICS ENDPOINTS ===================

@app.get("/api/analytics/data")
@limiter.limit("30/minute")
async def get_analytics_data(
    request: Request,
    page: int = Query(1, ge=1, le=1000),
    limit: int = Query(50, ge=10, le=500),
    sort_by: str = Query("created_at", pattern="^[a-zA-Z_][a-zA-Z0-9_]*$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
    search: Optional[str] = Query(None, max_length=200),
    date_from: Optional[str] = Query(None, pattern="^(\\d{4}-\\d{2}-\\d{2}|)$"),
    date_to: Optional[str] = Query(None, pattern="^(\\d{4}-\\d{2}-\\d{2}|)$"),
    user_id: Optional[str] = Query(None, max_length=50),
    customer_status: Optional[str] = Query(None, pattern="^(PROSPECT|LEAD_QUALIFIED|CUSTOMER|CHURNED|LEAD_EXHAUSTED|)$"),
    _: Optional[str] = Query(None, description="Cache buster parameter"),
    api_key: str = Depends(verify_api_key)
):
    """Get paginated analytics data with filtering and sorting."""
    params = AnalyticsDataRequest(
        page=page,
        limit=limit,
        sort_by=sort_by,
        sort_order=sort_order,
        search=search,
        date_from=date_from,
        date_to=date_to,
        user_id=user_id,
        customer_status=customer_status
    )
    return await analytics_manager.get_analytics_data(params)


@app.get("/api/analytics/metrics")
@limiter.limit("60/minute")
async def get_analytics_metrics(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """Get aggregated metrics for dashboard charts."""
    return await analytics_manager.get_analytics_metrics()


@app.post("/api/analytics/backup")
@limiter.limit("5/minute")
async def create_backup(
    request: Request,
    backup_request: BackupRequest,
    api_key: str = Depends(verify_api_key)
):
    """Create a database backup."""
    return await analytics_manager.create_backup(backup_request)


@app.get("/api/analytics/backups")
@limiter.limit("30/minute")
async def list_backups(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """List all available backups."""
    return await analytics_manager.list_backups()


@app.post("/api/analytics/restore/{backup_id}")
@limiter.limit("2/minute")
async def restore_backup(
    request: Request,
    backup_id: str,
    api_key: str = Depends(verify_api_key)
):
    """Restore from a specific backup."""
    return await analytics_manager.restore_backup(backup_id)


@app.delete("/api/analytics/backups/{backup_id}")
@limiter.limit("10/minute")
async def delete_backup(
    request: Request,
    backup_id: str,
    api_key: str = Depends(verify_api_key)
):
    """Delete a specific backup."""
    return await analytics_manager.delete_backup(backup_id)


@app.post("/api/analytics/clean")
@limiter.limit("5/minute")
async def clean_data(
    request: Request,
    clean_request: CleanDataRequest,
    api_key: str = Depends(verify_api_key)
):
    """Clean data with specified filters."""
    return await analytics_manager.clean_data(clean_request)


@app.get("/api/analytics/export")
@limiter.limit("10/minute")
async def export_data(
    request: Request,
    format: str = Query("csv", pattern="^(csv|json|xlsx)$"),
    date_from: Optional[str] = Query(None, pattern="^\\d{4}-\\d{2}-\\d{2}$"),
    date_to: Optional[str] = Query(None, pattern="^\\d{4}-\\d{2}-\\d{2}$"),
    user_id: Optional[str] = Query(None, max_length=50),
    api_key: str = Depends(verify_api_key)
):
    """Export data in specified format."""
    filters = {}
    if date_from:
        filters['date_from'] = date_from
    if date_to:
        filters['date_to'] = date_to
    if user_id:
        filters['user_id'] = user_id
    
    return await analytics_manager.export_data(format, filters)


@app.get("/api/analytics/raw/{message_id}")
@limiter.limit("30/minute")
async def get_raw_interaction(
    request: Request,
    message_id: str,
    api_key: str = Depends(verify_api_key)
):
    """Get raw interaction data directly from PostgreSQL without transformations.
    
    This endpoint returns the EXACT database record for debugging purposes.
    Includes schema information and column names for verification.
    """
    return await analytics_manager.get_raw_interaction(message_id)


@app.get("/api/analytics/integrity")
@limiter.limit("10/minute")
async def get_data_integrity_report(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """Get comprehensive data integrity report.
    
    Returns:
    - Schema validation (expected vs actual fields)
    - Data quality metrics (null values, inconsistencies)
    - Integrity alerts and recommendations
    - List of data transformations applied
    """
    return await analytics_manager.get_data_integrity_report()


# =================== PROTOCOL DE SILENCIO ENDPOINTS ===================

@app.post("/users/{user_id}/protocol")
@limiter.limit("10/minute")
async def manage_protocol(
    request: Request,
    user_id: str,
    action: str = Query(..., regex="^(activate|deactivate)$", description="Action to perform"),
    reason: Optional[str] = Query(None, max_length=200, description="Reason for action"),
    api_key: str = Depends(verify_api_key)
):
    """Activate or deactivate silence protocol for a user."""
    try:
        database_mode = os.getenv("DATABASE_MODE", "normal")
        if database_mode == "skip":
            return {"status": "success", "message": "Database mode is skip, protocol not updated"}
        
        # Get ProtocolManager instance (this would need to be initialized somewhere)
        # For now, we'll interact directly with the database
        
        activated_by = "dashboard_user"  # TODO: Get from authentication context
        
        if action == "activate":
            success = await db_manager.activate_protocol(user_id, activated_by, reason)
            message = f"Protocol activated for user {user_id}"
        else:  # deactivate
            success = await db_manager.deactivate_protocol(user_id, activated_by, reason)
            message = f"Protocol deactivated for user {user_id}"
        
        if success:
            logger.info(f"Protocol {action} successful for user {user_id}")
            return {
                "status": "success",
                "action": action,
                "user_id": user_id,
                "message": message
            }
        else:
            raise HTTPException(status_code=400, detail=f"Failed to {action} protocol")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error managing protocol for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to {action} protocol")


@app.get("/quarantine/messages")
@limiter.limit("30/minute")
async def get_quarantine_messages(
    request: Request,
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of messages"),
    include_processed: bool = Query(False, description="Include already processed messages"),
    api_key: str = Depends(verify_api_key)
):
    """Get messages in quarantine queue."""
    try:
        database_mode = os.getenv("DATABASE_MODE", "normal")
        if database_mode == "skip":
            return {"messages": [], "message": "Database mode is skip"}
        
        messages = await db_manager.get_quarantine_messages(
            user_id=user_id,
            limit=limit,
            include_processed=include_processed
        )
        
        return {
            "messages": messages,
            "total": len(messages),
            "filters": {
                "user_id": user_id,
                "include_processed": include_processed
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting quarantine messages: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve quarantine messages")


@app.post("/quarantine/{message_id}/process")
@limiter.limit("20/minute")
async def process_quarantine_message(
    request: Request,
    message_id: str,
    action: str = Query(..., regex="^(process|process_and_deactivate)$", description="Action to perform"),
    api_key: str = Depends(verify_api_key)
):
    """Process a single quarantine message."""
    try:
        database_mode = os.getenv("DATABASE_MODE", "normal")
        if database_mode == "skip":
            return {"status": "success", "message": "Database mode is skip"}
        
        processed_by = "dashboard_user"  # TODO: Get from authentication context
        
        # Mark message as processed
        message_data = await db_manager.process_quarantine_message(message_id, processed_by)
        
        if not message_data:
            raise HTTPException(status_code=404, detail="Message not found or already processed")
        
        # If action is process_and_deactivate, also deactivate protocol
        if action == "process_and_deactivate":
            user_id = message_data['user_id']
            await db_manager.deactivate_protocol(
                user_id, 
                processed_by, 
                "Deactivated after processing quarantine message"
            )
            
            return {
                "status": "success",
                "message": "Message processed and protocol deactivated",
                "message_id": message_id,
                "user_id": user_id,
                "protocol_deactivated": True
            }
        
        return {
            "status": "success",
            "message": "Message processed successfully",
            "message_id": message_id,
            "user_id": message_data['user_id'],
            "protocol_deactivated": False
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing quarantine message {message_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to process quarantine message")


@app.post("/quarantine/batch-process")
@limiter.limit("5/minute")
async def batch_process_quarantine(
    request: Request,
    message_ids: List[str],
    action: str = Query(..., regex="^(process|delete)$", description="Batch action to perform"),
    api_key: str = Depends(verify_api_key)
):
    """Process multiple quarantine messages in batch."""
    try:
        database_mode = os.getenv("DATABASE_MODE", "normal")
        if database_mode == "skip":
            return {"status": "success", "message": "Database mode is skip"}
        
        if len(message_ids) > 100:
            raise HTTPException(status_code=400, detail="Maximum 100 messages per batch")
        
        processed_by = "dashboard_user"  # TODO: Get from authentication context
        results = {"processed": 0, "failed": 0, "errors": []}
        
        for message_id in message_ids:
            try:
                if action == "process":
                    result = await db_manager.process_quarantine_message(message_id, processed_by)
                    if result:
                        results["processed"] += 1
                    else:
                        results["failed"] += 1
                        results["errors"].append(f"Message {message_id} not found")
                else:  # delete
                    success = await db_manager.delete_quarantine_message(message_id)
                    if success:
                        results["processed"] += 1
                    else:
                        results["failed"] += 1
                        results["errors"].append(f"Message {message_id} not found")
                        
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(f"Message {message_id}: {str(e)}")
        
        return {
            "status": "completed",
            "action": action,
            "results": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in batch processing: {e}")
        raise HTTPException(status_code=500, detail="Batch processing failed")


@app.delete("/quarantine/{message_id}")
@limiter.limit("30/minute")
async def delete_quarantine_message(
    request: Request,
    message_id: str,
    api_key: str = Depends(verify_api_key)
):
    """Delete a quarantine message."""
    try:
        database_mode = os.getenv("DATABASE_MODE", "normal")
        if database_mode == "skip":
            return {"status": "success", "message": "Database mode is skip"}
        
        success = await db_manager.delete_quarantine_message(message_id)
        
        if success:
            return {
                "status": "success",
                "message": "Message deleted successfully",
                "message_id": message_id
            }
        else:
            raise HTTPException(status_code=404, detail="Message not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting quarantine message {message_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete quarantine message")


@app.get("/quarantine/stats")
@limiter.limit("60/minute")
async def get_quarantine_stats(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """Get protocol statistics and metrics."""
    try:
        database_mode = os.getenv("DATABASE_MODE", "normal")
        if database_mode == "skip":
            return {
                "active_protocols": 0,
                "total_cost_saved_usd": 0.0,
                "messages_last_24h": 0,
                "message": "Database mode is skip"
            }
        
        stats = await db_manager.get_protocol_stats()
        
        # Auto-cleanup expired messages (older than 7 days)
        try:
            await db_manager.cleanup_expired_quarantine_messages()
        except Exception as e:
            logger.warning(f"Failed to cleanup expired messages: {e}")
        
        return {
            "active_protocols": stats["active_protocols"],
            "total_messages_quarantined": stats["total_messages_quarantined"],
            "total_cost_saved_usd": stats["total_cost_saved_usd"],
            "avg_messages_per_user": stats["avg_messages_per_user"],
            "messages_last_24h": stats["messages_last_24h"],
            "estimated_monthly_savings": stats["total_cost_saved_usd"] * 30,  # Rough estimate
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting quarantine stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve quarantine statistics")


@app.get("/quarantine/audit-log")
@limiter.limit("30/minute")
async def get_protocol_audit_log(
    request: Request,
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    limit: int = Query(50, ge=1, le=200, description="Maximum number of entries"),
    api_key: str = Depends(verify_api_key)
):
    """Get protocol audit log entries."""
    try:
        database_mode = os.getenv("DATABASE_MODE", "normal")
        if database_mode == "skip":
            return {"audit_log": [], "message": "Database mode is skip"}
        
        audit_entries = await db_manager.get_protocol_audit_log(user_id=user_id, limit=limit)
        
        return {
            "audit_log": audit_entries,
            "total": len(audit_entries),
            "filters": {
                "user_id": user_id,
                "limit": limit
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting protocol audit log: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve audit log")


@app.get("/users/{user_id}/protocol-stats")
@limiter.limit("60/minute")
async def get_user_protocol_stats(
    request: Request,
    user_id: str,
    api_key: str = Depends(verify_api_key)
):
    """Get detailed protocol statistics for a specific user."""
    try:
        database_mode = os.getenv("DATABASE_MODE", "normal")
        if database_mode == "skip":
            return {"message": "Database mode is skip"}
        
        stats = await db_manager.get_protocol_user_stats(user_id)
        return stats
        
    except Exception as e:
        logger.error(f"Error getting user protocol stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve user protocol statistics")


@app.post("/quarantine/cleanup")
@limiter.limit("5/minute")
async def cleanup_expired_messages(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """Manually trigger cleanup of expired quarantine messages."""
    try:
        database_mode = os.getenv("DATABASE_MODE", "normal")
        if database_mode == "skip":
            return {"deleted_count": 0, "message": "Database mode is skip"}
        
        deleted_count = await db_manager.cleanup_expired_quarantine_messages()
        
        return {
            "status": "success",
            "deleted_count": deleted_count,
            "message": f"Cleaned up {deleted_count} expired messages"
        }
        
    except Exception as e:
        logger.error(f"Error cleaning up expired messages: {e}")
        raise HTTPException(status_code=500, detail="Failed to cleanup expired messages")


# ════════════════════════════════════════════════════════════════════════════════
# RECOVERY AGENT API ENDPOINTS
# ════════════════════════════════════════════════════════════════════════════════

@app.get("/recovery/status")
@limiter.limit("30/minute")
async def get_recovery_status(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """Get current recovery system status."""
    try:
        # Import recovery modules (lazy loading to avoid circular imports)
        from agents.recovery_agent import RecoveryAgent
        from utils.telegram_history import TelegramHistoryManager
        from utils.recovery_config import get_recovery_config
        
        recovery_config = get_recovery_config()
        
        if not recovery_config.enabled:
            return {
                "enabled": False,
                "status": "disabled",
                "message": "Recovery system is disabled in configuration"
            }
        
        # Get recovery stats from database
        database_mode = os.getenv("DATABASE_MODE", "normal")
        if database_mode == "skip":
            return {
                "enabled": recovery_config.enabled,
                "status": "database_skip_mode",
                "config": recovery_config.to_dict()
            }
        
        stats = await db_manager.get_recovery_stats()
        operations = await db_manager.get_recovery_operations(limit=5)
        cursors = await db_manager.get_all_user_cursors()
        
        cursor_summary = {
            "total_users": len(cursors),
            "users_with_recent_recovery": sum(1 for c in cursors 
                                            if (datetime.now(timezone.utc) - c["last_recovery_check"]).days < 1),
            "oldest_recovery_check": min(c["last_recovery_check"] for c in cursors) if cursors else None
        }
        
        return {
            "enabled": True,
            "status": "healthy",
            "config": recovery_config.to_dict(),
            "stats": stats,
            "recent_operations": operations,
            "cursor_summary": cursor_summary,
            "last_updated": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting recovery status: {e}")
        return {
            "enabled": False,
            "status": "error",
            "error": str(e)
        }


@app.get("/recovery/messages")
@limiter.limit("30/minute")
async def get_recovered_messages(
    request: Request,
    limit: int = Query(50, ge=1, le=200, description="Maximum number of messages"),
    user_id: Optional[str] = Query(None, description="Filter by user ID"),
    api_key: str = Depends(verify_api_key)
):
    """Get list of recovered messages."""
    try:
        database_mode = os.getenv("DATABASE_MODE", "normal")
        if database_mode == "skip":
            return {"messages": [], "message": "Database mode is skip"}
        
        messages = await db_manager.get_recovered_messages(limit=limit, user_id=user_id)
        
        return {
            "messages": messages,
            "total": len(messages),
            "filters": {
                "user_id": user_id,
                "limit": limit
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting recovered messages: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve recovered messages")


@app.post("/recovery/trigger")
@limiter.limit("5/minute")
async def trigger_recovery(
    request: Request,
    trigger_request: RecoveryTriggerRequest,
    api_key: str = Depends(verify_api_key)
):
    """Manually trigger recovery operation."""
    try:
        database_mode = os.getenv("DATABASE_MODE", "normal")
        if database_mode == "skip":
            return {"status": "skipped", "message": "Database mode is skip"}
        
        # Import recovery modules
        from agents.recovery_agent import RecoveryAgent
        from utils.telegram_history import TelegramHistoryManager
        from utils.recovery_config import get_recovery_config
        
        recovery_config = get_recovery_config()
        
        if not recovery_config.enabled:
            raise HTTPException(status_code=400, detail="Recovery system is disabled")
        
        # Note: In a real implementation, you'd need access to the actual telegram client
        # For now, we'll create a placeholder response
        operation_id = await db_manager.start_recovery_operation(
            operation_type="manual",
            metadata={
                "triggered_by": "api",
                "user_id": trigger_request.user_id,
                "max_messages": trigger_request.max_messages,
                "api_trigger_time": datetime.now().isoformat()
            }
        )
        
        # Update operation as completed (placeholder - in real implementation this would be async)
        await db_manager.update_recovery_operation(
            operation_id=operation_id,
            status="completed",
            users_checked=1 if trigger_request.user_id else 0,
            messages_recovered=0,  # Would be actual count
            messages_skipped=0
        )
        
        return {
            "status": "triggered",
            "operation_id": operation_id,
            "user_id": trigger_request.user_id,
            "max_messages": trigger_request.max_messages,
            "message": f"Recovery operation started for {'user ' + trigger_request.user_id if trigger_request.user_id else 'all users'}"
        }
        
    except Exception as e:
        logger.error(f"Error triggering recovery: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to trigger recovery: {str(e)}")


@app.get("/recovery/history")
@limiter.limit("60/minute")
async def get_recovery_history(
    request: Request,
    limit: int = Query(50, ge=1, le=200, description="Number of operations to retrieve"),
    operation_type: Optional[str] = Query(None, regex="^(startup|periodic|manual)$", description="Filter by operation type"),
    api_key: str = Depends(verify_api_key)
):
    """Get recovery operations history."""
    try:
        database_mode = os.getenv("DATABASE_MODE", "normal")
        if database_mode == "skip":
            return {"operations": [], "message": "Database mode is skip"}
        
        operations = await db_manager.get_recovery_operations(limit=limit, operation_type=operation_type)
        
        # Add calculated fields for frontend
        for op in operations:
            if op.get("started_at") and op.get("completed_at"):
                start = op["started_at"]
                end = op["completed_at"]
                if isinstance(start, str):
                    start = datetime.fromisoformat(start.replace('Z', '+00:00'))
                if isinstance(end, str):
                    end = datetime.fromisoformat(end.replace('Z', '+00:00'))
                op["duration_seconds"] = (end - start).total_seconds()
            
            # Add efficiency metrics
            messages_recovered = op.get("messages_recovered", 0)
            users_checked = op.get("users_checked", 0)
            if users_checked > 0:
                op["messages_per_user"] = messages_recovered / users_checked
            else:
                op["messages_per_user"] = 0
        
        return {
            "operations": operations,
            "total_count": len(operations),
            "filters": {
                "limit": limit,
                "operation_type": operation_type
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting recovery history: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve recovery history")


@app.get("/recovery/cursor/{user_id}")
@limiter.limit("60/minute")
async def get_recovery_cursor(
    request: Request,
    user_id: str,
    api_key: str = Depends(verify_api_key)
):
    """Get message processing cursor for a specific user."""
    try:
        database_mode = os.getenv("DATABASE_MODE", "normal")
        if database_mode == "skip":
            return {"cursor": None, "message": "Database mode is skip"}
        
        cursor = await db_manager.get_user_cursor(user_id)
        
        if not cursor:
            raise HTTPException(status_code=404, detail=f"No cursor found for user {user_id}")
        
        # Add calculated fields
        last_recovery = cursor.get("last_recovery_check")
        if last_recovery:
            if isinstance(last_recovery, str):
                last_recovery = datetime.fromisoformat(last_recovery.replace('Z', '+00:00'))
            cursor["hours_since_last_recovery"] = (datetime.now() - last_recovery).total_seconds() / 3600
        
        return {
            "cursor": cursor,
            "user_id": user_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting recovery cursor for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve recovery cursor")


@app.post("/recovery/cursor/{user_id}")
@limiter.limit("30/minute")
async def update_recovery_cursor(
    request: Request,
    user_id: str,
    cursor_request: CursorUpdateRequest,
    api_key: str = Depends(verify_api_key)
):
    """Update message processing cursor for a specific user."""
    try:
        database_mode = os.getenv("DATABASE_MODE", "normal")
        if database_mode == "skip":
            return {"status": "skipped", "message": "Database mode is skip"}
        
        # Parse the telegram_date
        try:
            telegram_date = datetime.fromisoformat(cursor_request.telegram_date.replace('Z', '+00:00'))
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid telegram_date format: {e}")
        
        # Update cursor in database
        await db_manager.update_user_cursor(
            user_id=user_id,
            telegram_message_id=cursor_request.telegram_message_id,
            telegram_date=telegram_date,
            messages_recovered=cursor_request.messages_recovered
        )
        
        # Get updated cursor to return
        updated_cursor = await db_manager.get_user_cursor(user_id)
        
        return {
            "status": "updated",
            "user_id": user_id,
            "cursor": updated_cursor,
            "message": f"Cursor updated for user {user_id}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating recovery cursor for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to update recovery cursor")


@app.get("/recovery/health")
@limiter.limit("10/minute")
async def get_recovery_health(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """Get comprehensive recovery system health status."""
    try:
        database_mode = os.getenv("DATABASE_MODE", "normal")
        if database_mode == "skip":
            return {
                "overall_status": "disabled",
                "message": "Database mode is skip",
                "timestamp": datetime.now().isoformat()
            }
        
        # Import health check module
        from monitoring.recovery_health_check import RecoveryHealthChecker
        
        health_checker = RecoveryHealthChecker(db_manager)
        health_report = await health_checker.perform_health_check()
        
        return health_report
        
    except ImportError:
        return {
            "overall_status": "error",
            "error": "Health check module not available",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error performing recovery health check: {e}")
        return {
            "overall_status": "critical",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


# =============================================
# COHERENCE & SCHEDULE SYSTEM ENDPOINTS
# =============================================

class CommitmentRequest(BaseModel):
    commitment_text: str = Field(..., min_length=5, max_length=200)
    timestamp: str = Field(..., description="ISO timestamp for the commitment")
    details: Optional[Dict[str, Any]] = Field(default_factory=dict)

class CoherenceAnalysisRequest(BaseModel):
    llm1_response: str = Field(..., min_length=1, max_length=1000)
    user_id: str = Field(..., min_length=1)
    time_context: Dict[str, str] = Field(default_factory=dict)

@app.get("/api/coherence/metrics")
@limiter.limit("30/minute")
async def get_coherence_metrics(
    request: Request,
    api_key: str = Depends(verify_api_key)
):
    """Get coherence and schedule metrics for dashboard."""
    try:
        async with db_manager.get_connection() as conn:
            # Count active commitments
            active_commitments = await conn.fetchval("""
                SELECT COUNT(*) FROM nadia_commitments 
                WHERE status = 'active' AND commitment_timestamp > NOW()
            """)
            
            # Calculate coherence score (percentage of OK analyses)
            coherence_stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) as total_analyses,
                    COUNT(*) FILTER (WHERE analysis_status = 'OK') as ok_count,
                    COUNT(*) FILTER (WHERE json_parse_success = false) as json_failures
                FROM coherence_analysis 
                WHERE created_at > NOW() - INTERVAL '24 hours'
            """)
            
            total = coherence_stats['total_analyses'] if coherence_stats else 0
            ok_count = coherence_stats['ok_count'] if coherence_stats else 0
            json_failures = coherence_stats['json_failures'] if coherence_stats else 0
            
            coherence_score = (ok_count / total * 100) if total > 0 else 100.0
            json_success_rate = ((total - json_failures) / total * 100) if total > 0 else 100.0
            
            # Count schedule conflicts (last 24h)
            schedule_conflicts = await conn.fetchval("""
                SELECT COUNT(*) FROM coherence_analysis 
                WHERE analysis_status = 'CONFLICTO_DE_DISPONIBILIDAD'
                AND created_at > NOW() - INTERVAL '24 hours'
            """)
            
            # Count identity conflicts (last 24h)
            identity_conflicts = await conn.fetchval("""
                SELECT COUNT(*) FROM coherence_analysis 
                WHERE analysis_status = 'CONFLICTO_DE_IDENTIDAD'
                AND created_at > NOW() - INTERVAL '24 hours'
            """)
            
            return {
                "active_commitments": active_commitments or 0,
                "coherence_score": round(coherence_score, 1),
                "schedule_conflicts_24h": schedule_conflicts or 0,
                "identity_conflicts_24h": identity_conflicts or 0,
                "total_analyses_24h": total,
                "json_success_rate": round(json_success_rate, 1),
                "last_updated": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error getting coherence metrics: {e}")
        raise HTTPException(status_code=500, detail="Failed to get coherence metrics")

@app.get("/users/{user_id}/commitments")
@limiter.limit("60/minute")
async def get_user_commitments(
    user_id: str,
    status: Optional[str] = Query(None, regex="^(active|fulfilled|expired|cancelled)$"),
    limit: int = Query(20, ge=1, le=100),
    request: Request = None,
    api_key: str = Depends(verify_api_key)
):
    """Get commitments for a specific user."""
    try:
        async with db_manager.get_connection() as conn:
            where_clause = "WHERE user_id = $1"
            params = [user_id]
            
            if status:
                where_clause += " AND status = $2"
                params.append(status)
                
            query = f"""
                SELECT id, commitment_timestamp, details, commitment_text, status, created_at
                FROM nadia_commitments 
                {where_clause}
                ORDER BY commitment_timestamp DESC
                LIMIT ${len(params) + 1}
            """
            params.append(limit)
            
            rows = await conn.fetch(query, *params)
            
            commitments = []
            for row in rows:
                commitments.append({
                    "id": str(row['id']),
                    "timestamp": row['commitment_timestamp'].isoformat(),
                    "details": row['details'],
                    "text": row['commitment_text'],
                    "status": row['status'],
                    "created_at": row['created_at'].isoformat()
                })
            
            return {
                "commitments": commitments,
                "total": len(commitments),
                "user_id": user_id
            }
            
    except Exception as e:
        logger.error(f"Error getting commitments for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get user commitments")

@app.get("/api/coherence/violations")
@limiter.limit("30/minute")
async def get_coherence_violations(
    limit: int = Query(50, ge=1, le=200),
    severity: Optional[str] = Query(None, regex="^(CONFLICTO_DE_IDENTIDAD|CONFLICTO_DE_DISPONIBILIDAD)$"),
    request: Request = None,
    api_key: str = Depends(verify_api_key)
):
    """Get recent coherence violations for monitoring."""
    try:
        async with db_manager.get_connection() as conn:
            where_clause = "WHERE analysis_status != 'OK'"
            params = []
            
            if severity:
                where_clause += " AND analysis_status = $1"
                params.append(severity)
                
            query = f"""
                SELECT ca.id, ca.interaction_id, ca.analysis_status, ca.conflict_details,
                       ca.created_at, ca.json_parse_success, ca.llm_model_used
                FROM coherence_analysis ca
                {where_clause}
                ORDER BY ca.created_at DESC
                LIMIT ${len(params) + 1}
            """
            params.append(limit)
            
            rows = await conn.fetch(query, *params)
            
            violations = []
            for row in rows:
                violations.append({
                    "id": str(row['id']),
                    "interaction_id": str(row['interaction_id']) if row['interaction_id'] else None,
                    "type": row['analysis_status'],
                    "details": row['conflict_details'],
                    "created_at": row['created_at'].isoformat(),
                    "json_success": row['json_parse_success'],
                    "model_used": row['llm_model_used']
                })
            
            return {
                "violations": violations,
                "total": len(violations),
                "last_updated": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Error getting coherence violations: {e}")
        raise HTTPException(status_code=500, detail="Failed to get coherence violations")

@app.get("/schedule/conflicts/{user_id}")
@limiter.limit("60/minute")
async def check_schedule_conflicts(
    user_id: str,
    proposed_time: str = Query(..., description="ISO timestamp for proposed activity"),
    duration_minutes: int = Query(60, ge=5, le=480),
    request: Request = None,
    api_key: str = Depends(verify_api_key)
):
    """Check for schedule conflicts with a proposed time."""
    try:
        from datetime import datetime, timedelta
        
        # Parse proposed time
        try:
            proposed_dt = datetime.fromisoformat(proposed_time)
            end_time = proposed_dt + timedelta(minutes=duration_minutes)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid timestamp format")
        
        async with db_manager.get_connection() as conn:
            conflicts = await conn.fetch("""
                SELECT id, commitment_timestamp, details, commitment_text
                FROM nadia_commitments
                WHERE user_id = $1 
                AND status = 'active'
                AND commitment_timestamp BETWEEN $2 AND $3
                ORDER BY commitment_timestamp ASC
            """, user_id, proposed_dt, end_time)
            
            conflict_list = []
            for conflict in conflicts:
                conflict_list.append({
                    "id": str(conflict['id']),
                    "timestamp": conflict['commitment_timestamp'].isoformat(),
                    "activity": conflict['details'].get('activity', 'unknown'),
                    "text": conflict['commitment_text']
                })
            
            return {
                "has_conflicts": len(conflict_list) > 0,
                "conflicts": conflict_list,
                "proposed_time": proposed_time,
                "duration_minutes": duration_minutes,
                "user_id": user_id
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error checking schedule conflicts: {e}")
        raise HTTPException(status_code=500, detail="Failed to check schedule conflicts")


# Configuration endpoint for frontend
@app.get("/api/config")
async def get_config():
    """Get configuration for frontend dashboard."""
    return {
        "apiKey": API_KEY,
        "apiBase": "http://localhost:8000"
    }


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
