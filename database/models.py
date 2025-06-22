# database/models.py
"""Database models for HITL system."""
import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import asyncpg

from agents.supervisor_agent import ReviewItem

logger = logging.getLogger(__name__)


class ReviewStatus(Enum):
    """Review status enumeration."""
    PENDING = "pending"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    REJECTED = "rejected"


class DatabaseManager:
    """Manages PostgreSQL connections and operations for HITL system."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self._pool: Optional[asyncpg.Pool] = None

    async def initialize(self):
        """Initialize connection pool."""
        try:
            self._pool = await asyncpg.create_pool(self.database_url)
            logger.info("Database connection pool initialized")
        except Exception as e:
            logger.error(f"Failed to initialize database pool: {e}")
            raise

    async def close(self):
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            logger.info("Database connection pool closed")

    async def save_interaction(self, review_item: ReviewItem) -> str:
        """Save a new interaction to the database."""
        async with self._pool.acquire() as conn:
            # Generate conversation ID (could be improved with better logic)
            conversation_id = f"{review_item.user_id}_{datetime.now().strftime('%Y%m%d')}"

            interaction_id = await conn.fetchval(
                """
                INSERT INTO interactions (
                    user_id, conversation_id, message_number,
                    user_message, user_message_timestamp,
                    llm1_raw_response, llm2_bubbles,
                    constitution_risk_score, constitution_flags, constitution_recommendation,
                    review_status, priority_score,
                    llm1_model, llm2_model, llm1_cost_usd, llm2_cost_usd,
                    customer_status
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
                RETURNING id
                """,
                review_item.user_id,
                conversation_id,
                1,  # TODO: Track message number properly
                review_item.user_message,
                review_item.timestamp,
                review_item.ai_suggestion.llm1_raw,
                review_item.ai_suggestion.llm2_bubbles,
                review_item.ai_suggestion.constitution_analysis.risk_score,
                review_item.ai_suggestion.constitution_analysis.flags,
                review_item.ai_suggestion.constitution_analysis.recommendation.value,
                ReviewStatus.PENDING.value,
                review_item.priority,
                # Multi-LLM tracking
                review_item.ai_suggestion.llm1_model,
                review_item.ai_suggestion.llm2_model,
                review_item.ai_suggestion.llm1_cost,
                review_item.ai_suggestion.llm2_cost,
                # Customer status - default to PROSPECT for new interactions
                'PROSPECT'
            )

            # Guardar métricas de cache
            if hasattr(review_item.ai_suggestion, 'cache_metrics'):
                cached_tokens = review_item.ai_suggestion.cache_metrics.get('cached_tokens', 0)
                total_tokens = review_item.ai_suggestion.cache_metrics.get('total_tokens', 0)
                cache_ratio = cached_tokens / total_tokens if total_tokens > 0 else 0.0
            else:
                cached_tokens = 0
                total_tokens = 0
                cache_ratio = 0.0

            logger.info(f"Saved interaction {interaction_id} for user {review_item.user_id}")
            return str(interaction_id)

    async def get_pending_reviews(self, limit: int = 20, min_priority: float = 0.0) -> List[Dict[str, Any]]:
        """Get pending reviews ordered by priority."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT
                    id, user_id, user_message, llm1_raw_response, llm2_bubbles,
                    constitution_risk_score, constitution_flags, constitution_recommendation,
                    priority_score, created_at,
                    llm1_model, llm2_model, llm1_cost_usd, llm2_cost_usd, customer_status
                FROM interactions
                WHERE review_status = 'pending' AND priority_score >= $1
                ORDER BY priority_score DESC, created_at ASC
                LIMIT $2
                """,
                min_priority, limit
            )

            return [dict(row) for row in rows]

    async def start_review(self, interaction_id: str, reviewer_id: str) -> bool:
        """Mark an interaction as being reviewed."""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE interactions
                SET review_status = 'reviewing',
                    reviewer_id = $1,
                    review_started_at = NOW()
                WHERE id = $2 AND review_status = 'pending'
                """,
                reviewer_id, interaction_id
            )

            return result == "UPDATE 1"

    async def approve_review(self, interaction_id: str, final_bubbles: List[str],
                           edit_tags: List[str], quality_score: int,
                           reviewer_notes: Optional[str] = None,
                           cta_data: Optional[Dict[str, Any]] = None) -> bool:
        """Approve a review with final bubbles and metadata."""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE interactions
                SET review_status = 'approved',
                    review_completed_at = NOW(),
                    review_time_seconds = EXTRACT(EPOCH FROM (NOW() - review_started_at)),
                    final_bubbles = $1,
                    edit_tags = $2,
                    quality_score = $3,
                    reviewer_notes = $4,
                    messages_sent_at = NOW()
                WHERE id = $5 AND review_status = 'reviewing'
                """,
                final_bubbles, edit_tags, quality_score, reviewer_notes, interaction_id
            )

            return result == "UPDATE 1"

    async def reject_review(self, interaction_id: str, reviewer_notes: Optional[str] = None) -> bool:
        """Reject a review."""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE interactions
                SET review_status = 'rejected',
                    review_completed_at = NOW(),
                    review_time_seconds = EXTRACT(EPOCH FROM (NOW() - review_started_at)),
                    reviewer_notes = $1
                WHERE id = $2 AND review_status = 'reviewing'
                """,
                reviewer_notes, interaction_id
            )

            return result == "UPDATE 1"

    async def cancel_review(self, interaction_id: str, reason: Optional[str] = None) -> bool:
        """Cancel a review without saving to database.
        
        This removes the review from the reviewing state and returns it to pending,
        ensuring no data contamination occurs when reviewers cancel their work.
        
        Args:
            interaction_id: The review ID to cancel
            reason: Optional reason for cancellation (for logging)
            
        Returns:
            bool: True if successfully cancelled, False if review not found
        """
        async with self._pool.acquire() as conn:
            # Check if the review exists and is in reviewing state
            existing = await conn.fetchrow(
                "SELECT id, review_status FROM interactions WHERE id = $1",
                interaction_id
            )
            
            if not existing:
                logger.warning(f"Attempted to cancel non-existent review: {interaction_id}")
                return False
                
            if existing['review_status'] != 'reviewing':
                logger.warning(f"Attempted to cancel review in wrong state: {interaction_id} (status: {existing['review_status']})")
                return False
            
            # Return review to pending state without saving any edited content
            result = await conn.execute(
                """
                UPDATE interactions
                SET review_status = 'pending',
                    review_started_at = NULL,
                    reviewer_id = NULL
                WHERE id = $1 AND review_status = 'reviewing'
                """,
                interaction_id
            )
            
            if result == "UPDATE 1":
                logger.info(f"Review cancelled successfully: {interaction_id}" + (f" (reason: {reason})" if reason else ""))
                return True
            else:
                logger.error(f"Failed to cancel review: {interaction_id}")
                return False

    async def get_interaction(self, interaction_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific interaction by ID."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM interactions WHERE id = $1",
                interaction_id
            )

            return dict(row) if row else None

    async def get_dashboard_metrics(self) -> Dict[str, Any]:
        """Get metrics for dashboard."""
        async with self._pool.acquire() as conn:
            # Get basic counts
            pending_count = await conn.fetchval(
                "SELECT COUNT(*) FROM interactions WHERE review_status = 'pending'"
            )

            reviewed_today = await conn.fetchval(
                """
                SELECT COUNT(*) FROM interactions
                WHERE review_status IN ('approved', 'rejected')
                AND DATE(review_completed_at) = CURRENT_DATE
                """
            )

            avg_review_time = await conn.fetchval(
                """
                SELECT AVG(review_time_seconds) FROM interactions
                WHERE review_status IN ('approved', 'rejected')
                AND review_completed_at >= CURRENT_DATE - INTERVAL '7 days'
                """
            )

            # Get edit tag distribution
            edit_tags_rows = await conn.fetch(
                """
                SELECT unnest(edit_tags) as tag, COUNT(*) as count
                FROM interactions
                WHERE edit_tags IS NOT NULL
                AND review_completed_at >= CURRENT_DATE - INTERVAL '7 days'
                GROUP BY tag
                ORDER BY count DESC
                LIMIT 10
                """
            )

            return {
                "pending_reviews": pending_count,
                "reviewed_today": reviewed_today,
                "avg_review_time_seconds": float(avg_review_time) if avg_review_time else 0,
                "popular_edit_tags": [{"tag": row["tag"], "count": row["count"]} for row in edit_tags_rows]
            }

    async def get_edit_taxonomy(self) -> List[Dict[str, Any]]:
        """Get available edit tags."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT code, category, description FROM edit_taxonomy ORDER BY category, code"
            )

            return [dict(row) for row in rows]
