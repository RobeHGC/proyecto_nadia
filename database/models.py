# database/models.py
"""Database models for HITL system."""
import json
import logging
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import asyncpg

from agents.types import ReviewItem

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

            # Extract recovery tracking data from conversation context
            telegram_message_id = review_item.conversation_context.get("telegram_message_id")
            telegram_date = review_item.conversation_context.get("telegram_date")
            is_recovered = review_item.conversation_context.get("is_recovered_message", False)
            
            # Convert telegram_date from string if needed
            if telegram_date and isinstance(telegram_date, str):
                try:
                    telegram_date = datetime.fromisoformat(telegram_date.replace('Z', '+00:00'))
                except ValueError:
                    telegram_date = None

            interaction_id = await conn.fetchval(
                """
                INSERT INTO interactions (
                    user_id, conversation_id, message_number,
                    user_message, user_message_timestamp,
                    llm1_raw_response, llm2_bubbles,
                    constitution_risk_score, constitution_flags, constitution_recommendation,
                    review_status, priority_score,
                    llm1_model, llm2_model, llm1_cost_usd, llm2_cost_usd,
                    customer_status, telegram_message_id, telegram_date, is_recovered_message
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19, $20)
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
                'PROSPECT',
                # Recovery tracking fields
                telegram_message_id,
                telegram_date,
                is_recovered
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
                    i.id, i.user_id, i.user_message, i.llm1_raw_response, i.llm2_bubbles,
                    i.constitution_risk_score, i.constitution_flags, i.constitution_recommendation,
                    i.priority_score, i.created_at,
                    i.llm1_model, i.llm2_model, i.llm1_cost_usd, i.llm2_cost_usd,
                    COALESCE(ucs.customer_status, 'PROSPECT') as current_customer_status
                FROM interactions i
                LEFT JOIN user_current_status ucs ON i.user_id = ucs.user_id
                WHERE i.review_status = 'pending' AND i.priority_score >= $1
                ORDER BY i.created_at ASC
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
            # First, get the user_id and current status from the interaction
            interaction = await conn.fetchrow(
                "SELECT user_id, review_status FROM interactions WHERE id = $1",
                interaction_id
            )
            
            if not interaction:
                logger.error(f"Interaction {interaction_id} not found")
                return False
            
            # If already processed, return False to indicate it shouldn't be in queue
            if interaction['review_status'] in ['approved', 'rejected']:
                logger.warning(f"Interaction {interaction_id} already processed with status {interaction['review_status']}")
                return False
            
            user_id = interaction['user_id']
            
            # Get the current customer status from user_current_status table
            user_status = await conn.fetchrow(
                "SELECT customer_status FROM user_current_status WHERE user_id = $1",
                user_id
            )
            
            # Use the current status or default to PROSPECT
            current_customer_status = user_status['customer_status'] if user_status else 'PROSPECT'
            
            # Update the interaction - allow from both 'pending' and 'reviewing' states
            result = await conn.execute(
                """
                UPDATE interactions
                SET review_status = 'approved',
                    review_completed_at = NOW(),
                    review_time_seconds = EXTRACT(EPOCH FROM (NOW() - COALESCE(review_started_at, created_at))),
                    final_bubbles = $1,
                    edit_tags = $2,
                    quality_score = $3,
                    reviewer_notes = $4,
                    messages_sent_at = NOW(),
                    customer_status = $6,
                    review_started_at = COALESCE(review_started_at, NOW())
                WHERE id = $5 AND review_status IN ('pending', 'reviewing')
                """,
                final_bubbles, edit_tags, quality_score, reviewer_notes, interaction_id, current_customer_status
            )

            return result == "UPDATE 1"

    async def reject_review(self, interaction_id: str, reviewer_notes: Optional[str] = None) -> bool:
        """Reject a review."""
        async with self._pool.acquire() as conn:
            # First check if interaction exists and current status
            interaction = await conn.fetchrow(
                "SELECT review_status FROM interactions WHERE id = $1",
                interaction_id
            )
            
            if not interaction:
                logger.error(f"Interaction {interaction_id} not found")
                return False
            
            # If already processed, return False to indicate it shouldn't be in queue
            if interaction['review_status'] in ['approved', 'rejected']:
                logger.warning(f"Interaction {interaction_id} already processed with status {interaction['review_status']}")
                return False
            
            # Update the interaction - allow from both 'pending' and 'reviewing' states
            result = await conn.execute(
                """
                UPDATE interactions
                SET review_status = 'rejected',
                    review_completed_at = NOW(),
                    review_time_seconds = EXTRACT(EPOCH FROM (NOW() - COALESCE(review_started_at, created_at))),
                    reviewer_notes = $1,
                    review_started_at = COALESCE(review_started_at, NOW())
                WHERE id = $2 AND review_status IN ('pending', 'reviewing')
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

    # Protocol de Silencio methods
    async def get_protocol_status(self, user_id: str) -> Dict[str, Any]:
        """Get protocol status for a user."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT 
                    user_id, status, activated_by, activated_at, 
                    reason, messages_quarantined, cost_saved_usd,
                    last_message_at, updated_at
                FROM user_protocol_status
                WHERE user_id = $1
                """,
                user_id
            )
            
            if row:
                return dict(row)
            
            # Return default inactive status if not found
            return {
                'user_id': user_id,
                'status': 'INACTIVE',
                'messages_quarantined': 0,
                'cost_saved_usd': 0.0
            }

    async def activate_protocol(self, user_id: str, activated_by: str, reason: Optional[str] = None) -> bool:
        """Activate silence protocol for a user."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Insert or update protocol status
                await conn.execute(
                    """
                    INSERT INTO user_protocol_status (user_id, status, activated_by, activated_at, reason)
                    VALUES ($1, 'ACTIVE', $2, NOW(), $3)
                    ON CONFLICT (user_id) 
                    DO UPDATE SET 
                        status = 'ACTIVE',
                        activated_by = EXCLUDED.activated_by,
                        activated_at = EXCLUDED.activated_at,
                        reason = EXCLUDED.reason,
                        updated_at = NOW()
                    """,
                    user_id, activated_by, reason
                )
                
                # Log the action
                await conn.execute(
                    """
                    INSERT INTO protocol_audit_log (user_id, action, performed_by, reason, previous_status, new_status)
                    VALUES ($1, 'ACTIVATED', $2, $3, 
                        (SELECT status FROM user_protocol_status WHERE user_id = $1 LIMIT 1),
                        'ACTIVE'
                    )
                    """,
                    user_id, activated_by, reason
                )
                
                logger.info(f"Activated protocol for user {user_id} by {activated_by}")
                return True

    async def deactivate_protocol(self, user_id: str, deactivated_by: str, reason: Optional[str] = None) -> bool:
        """Deactivate silence protocol for a user."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Update protocol status
                result = await conn.execute(
                    """
                    UPDATE user_protocol_status 
                    SET status = 'INACTIVE', updated_at = NOW()
                    WHERE user_id = $1 AND status = 'ACTIVE'
                    """,
                    user_id
                )
                
                if result.split()[-1] == '0':
                    return False  # No active protocol to deactivate
                
                # Log the action
                await conn.execute(
                    """
                    INSERT INTO protocol_audit_log (user_id, action, performed_by, reason, previous_status, new_status)
                    VALUES ($1, 'DEACTIVATED', $2, $3, 'ACTIVE', 'INACTIVE')
                    """,
                    user_id, deactivated_by, reason
                )
                
                logger.info(f"Deactivated protocol for user {user_id} by {deactivated_by}")
                return True

    async def save_quarantine_message(self, user_id: str, message_id: str, message_text: str, 
                                    telegram_message_id: Optional[int] = None) -> str:
        """Save a message to quarantine."""
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # Save to quarantine
                quarantine_id = await conn.fetchval(
                    """
                    INSERT INTO quarantine_messages (message_id, user_id, message_text, telegram_message_id, received_at)
                    VALUES ($1, $2, $3, $4, NOW())
                    RETURNING id
                    """,
                    message_id, user_id, message_text, telegram_message_id
                )
                
                # Update protocol stats
                await conn.execute(
                    """
                    UPDATE user_protocol_status 
                    SET messages_quarantined = messages_quarantined + 1,
                        cost_saved_usd = cost_saved_usd + $2,
                        last_message_at = NOW(),
                        updated_at = NOW()
                    WHERE user_id = $1
                    """,
                    user_id, 0.000307  # Average cost per message from CLAUDE.md
                )
                
                return str(quarantine_id)

    async def get_quarantine_messages(self, user_id: Optional[str] = None, 
                                    limit: int = 50, include_processed: bool = False) -> List[Dict[str, Any]]:
        """Get quarantined messages, optionally filtered by user."""
        async with self._pool.acquire() as conn:
            # Build query with proper parameter handling
            base_query = """
                SELECT 
                    q.id,
                    q.message_id,
                    q.user_id,
                    q.message_text,
                    q.telegram_message_id,
                    q.received_at,
                    q.expires_at,
                    q.processed,
                    q.processed_at,
                    q.processed_by,
                    q.created_at,
                    u.nickname,
                    u.customer_status,
                    EXTRACT(EPOCH FROM (NOW() - q.received_at)) / 3600.0 as age_hours
                FROM quarantine_messages q
                LEFT JOIN user_current_status u ON q.user_id = u.user_id
            """
            
            conditions = []
            params = []
            
            # Add processed filter
            if not include_processed:
                conditions.append("q.processed = FALSE")
            
            # Add user filter
            if user_id:
                conditions.append("q.user_id = $" + str(len(params) + 1))
                params.append(user_id)
            
            # Build WHERE clause
            if conditions:
                base_query += " WHERE " + " AND ".join(conditions)
            
            # Add ORDER BY
            base_query += " ORDER BY q.received_at DESC"
            
            # Add LIMIT
            if limit and limit > 0:
                base_query += " LIMIT $" + str(len(params) + 1)
                params.append(limit)
            
            try:
                rows = await conn.fetch(base_query, *params)
                return [dict(row) for row in rows]
            except Exception as e:
                logger.error(f"Error in get_quarantine_messages: {e}")
                logger.error(f"Query: {base_query}")
                logger.error(f"Params: {params}")
                raise

    async def process_quarantine_message(self, message_id: str, processed_by: str) -> Dict[str, Any]:
        """Mark a quarantine message as processed and return its data."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                UPDATE quarantine_messages
                SET processed = TRUE, processed_at = NOW(), processed_by = $2
                WHERE message_id = $1 AND NOT processed
                RETURNING *
                """,
                message_id, processed_by
            )
            
            if row:
                # Log one-time pass
                await conn.execute(
                    """
                    INSERT INTO protocol_audit_log (user_id, action, performed_by, reason)
                    VALUES ($1, 'ONE_TIME_PASS', $2, 'Processed single quarantine message')
                    """,
                    row['user_id'], processed_by
                )
                
                return dict(row)
            return None

    async def delete_quarantine_message(self, message_id: str) -> bool:
        """Delete a quarantine message."""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM quarantine_messages WHERE message_id = $1",
                message_id
            )
            return result.split()[-1] != '0'

    async def get_protocol_stats(self) -> Dict[str, Any]:
        """Get protocol statistics."""
        async with self._pool.acquire() as conn:
            stats = await conn.fetchrow(
                """
                SELECT 
                    COUNT(DISTINCT user_id) as active_protocols,
                    SUM(messages_quarantined) as total_messages_quarantined,
                    SUM(cost_saved_usd) as total_cost_saved_usd,
                    AVG(messages_quarantined) as avg_messages_per_user
                FROM user_protocol_status
                WHERE status = 'ACTIVE'
                """
            )
            
            recent = await conn.fetchval(
                """
                SELECT COUNT(*) 
                FROM quarantine_messages 
                WHERE received_at > NOW() - INTERVAL '24 hours' 
                AND NOT processed
                """
            )
            
            return {
                'active_protocols': stats['active_protocols'] or 0,
                'total_messages_quarantined': stats['total_messages_quarantined'] or 0,
                'total_cost_saved_usd': float(stats['total_cost_saved_usd'] or 0),
                'avg_messages_per_user': float(stats['avg_messages_per_user'] or 0),
                'messages_last_24h': recent
            }

    async def get_active_protocol_users(self) -> List[str]:
        """Get list of all users with active protocol."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT user_id FROM user_protocol_status WHERE status = 'ACTIVE'"
            )
            return [row['user_id'] for row in rows]

    async def cleanup_expired_quarantine_messages(self) -> int:
        """Clean up quarantine messages older than 7 days."""
        async with self._pool.acquire() as conn:
            # Delete expired messages
            result = await conn.execute(
                """
                DELETE FROM quarantine_messages 
                WHERE expires_at < NOW() 
                AND NOT processed
                """
            )
            
            deleted_count = int(result.split()[-1]) if result else 0
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} expired quarantine messages")
            
            return deleted_count

    async def get_protocol_audit_log(self, user_id: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get protocol audit log entries."""
        async with self._pool.acquire() as conn:
            if user_id:
                rows = await conn.fetch(
                    """
                    SELECT * FROM protocol_audit_log 
                    WHERE user_id = $1 
                    ORDER BY created_at DESC 
                    LIMIT $2
                    """,
                    user_id, limit
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT 
                        pal.*,
                        ucs.nickname
                    FROM protocol_audit_log pal
                    LEFT JOIN user_current_status ucs ON pal.user_id = ucs.user_id
                    ORDER BY pal.created_at DESC 
                    LIMIT $1
                    """,
                    limit
                )
            
            return [dict(row) for row in rows]

    async def get_protocol_user_stats(self, user_id: str) -> Dict[str, Any]:
        """Get detailed protocol statistics for a specific user."""
        async with self._pool.acquire() as conn:
            # Get protocol status
            protocol_status = await conn.fetchrow(
                "SELECT * FROM user_protocol_status WHERE user_id = $1",
                user_id
            )
            
            # Get quarantine message count
            quarantine_count = await conn.fetchval(
                "SELECT COUNT(*) FROM quarantine_messages WHERE user_id = $1 AND NOT processed",
                user_id
            )
            
            # Get recent audit entries
            recent_actions = await conn.fetch(
                """
                SELECT action, performed_by, reason, created_at 
                FROM protocol_audit_log 
                WHERE user_id = $1 
                ORDER BY created_at DESC 
                LIMIT 5
                """,
                user_id
            )
            
            return {
                'user_id': user_id,
                'protocol_status': dict(protocol_status) if protocol_status else None,
                'quarantine_count': quarantine_count,
                'recent_actions': [dict(row) for row in recent_actions]
            }

    # === RECOVERY AGENT CRUD METHODS ===

    async def save_interaction_with_recovery_data(self, review_item: ReviewItem, 
                                                telegram_message_id: Optional[int] = None,
                                                telegram_date: Optional[datetime] = None,
                                                is_recovered: bool = False) -> str:
        """Save interaction with recovery tracking data."""
        async with self._pool.acquire() as conn:
            conversation_id = f"{review_item.user_id}_{datetime.now().strftime('%Y%m%d')}"
            
            interaction_id = await conn.fetchval(
                """
                INSERT INTO interactions (
                    id, user_id, conversation_id, user_message, ai_response, 
                    status, created_at, telegram_message_id, telegram_date, is_recovered_message
                ) VALUES (uuid_generate_v4(), $1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING id
                """,
                review_item.user_id,
                conversation_id,
                review_item.original_message,
                review_item.ai_response,
                review_item.status.value,
                review_item.timestamp,
                telegram_message_id,
                telegram_date,
                is_recovered
            )
            
            return str(interaction_id)

    async def get_user_cursor(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get message processing cursor for a user."""
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM message_processing_cursors WHERE user_id = $1",
                user_id
            )
            return dict(row) if row else None

    async def update_user_cursor(self, user_id: str, telegram_message_id: int, 
                               telegram_date: datetime, messages_recovered: int = 0) -> None:
        """Update or create message processing cursor for a user."""
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO message_processing_cursors (
                    user_id, last_processed_telegram_id, last_processed_telegram_date,
                    last_recovery_check, total_recovered_messages
                ) VALUES ($1, $2, $3, NOW(), $4)
                ON CONFLICT (user_id) DO UPDATE SET
                    last_processed_telegram_id = EXCLUDED.last_processed_telegram_id,
                    last_processed_telegram_date = EXCLUDED.last_processed_telegram_date,
                    last_recovery_check = NOW(),
                    total_recovered_messages = message_processing_cursors.total_recovered_messages + EXCLUDED.total_recovered_messages,
                    updated_at = NOW()
                """,
                user_id, telegram_message_id, telegram_date, messages_recovered
            )

    async def get_all_user_cursors(self) -> List[Dict[str, Any]]:
        """Get all user cursors for recovery operations."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM message_processing_cursors 
                ORDER BY last_recovery_check ASC
                """
            )
            return [dict(row) for row in rows]

    async def get_last_message_per_user(self, user_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Get the last processed message for each user from interactions table.
        Core method for comprehensive recovery strategy.
        
        Args:
            user_ids: List of user IDs to check
            
        Returns:
            Dict mapping user_id to last message info {telegram_message_id, telegram_date}
            Missing users will not be in the returned dict (indicating no messages processed)
        """
        if not user_ids:
            return {}
            
        async with self._pool.acquire() as conn:
            # Query to get the maximum telegram_message_id for each user
            rows = await conn.fetch(
                """
                SELECT 
                    user_id,
                    MAX(telegram_message_id) as last_telegram_message_id,
                    MAX(telegram_date) as last_telegram_date
                FROM interactions 
                WHERE user_id = ANY($1) 
                    AND telegram_message_id IS NOT NULL
                    AND telegram_date IS NOT NULL
                GROUP BY user_id
                """,
                user_ids
            )
            
            result = {}
            for row in rows:
                result[row['user_id']] = {
                    'telegram_message_id': row['last_telegram_message_id'],
                    'telegram_date': row['last_telegram_date']
                }
            
            logger.info(f"📊 Last message lookup: {len(result)} users with SQL history from {len(user_ids)} total users")
            return result

    async def start_recovery_operation(self, operation_type: str, metadata: Optional[Dict] = None) -> str:
        """Start a new recovery operation and return its ID."""
        async with self._pool.acquire() as conn:
            operation_id = await conn.fetchval(
                """
                INSERT INTO recovery_operations (operation_type, metadata)
                VALUES ($1, $2)
                RETURNING id
                """,
                operation_type, json.dumps(metadata) if metadata else None
            )
            return str(operation_id)

    async def update_recovery_operation(self, operation_id: str, status: str = None,
                                      users_checked: int = None, messages_recovered: int = None,
                                      messages_skipped: int = None, errors_encountered: int = None,
                                      error_details: Optional[Dict] = None) -> None:
        """Update recovery operation progress."""
        async with self._pool.acquire() as conn:
            updates = []
            params = []
            param_count = 1
            
            if status:
                updates.append(f"status = ${param_count}")
                params.append(status)
                param_count += 1
                
                if status in ['completed', 'failed']:
                    updates.append(f"completed_at = NOW()")
            
            if users_checked is not None:
                updates.append(f"users_checked = ${param_count}")
                params.append(users_checked)
                param_count += 1
            
            if messages_recovered is not None:
                updates.append(f"messages_recovered = ${param_count}")
                params.append(messages_recovered)
                param_count += 1
            
            if messages_skipped is not None:
                updates.append(f"messages_skipped = ${param_count}")
                params.append(messages_skipped)
                param_count += 1
            
            if errors_encountered is not None:
                updates.append(f"errors_encountered = ${param_count}")
                params.append(errors_encountered)
                param_count += 1
            
            if error_details:
                updates.append(f"error_details = ${param_count}")
                params.append(json.dumps(error_details))
                param_count += 1
            
            if updates:
                params.append(operation_id)
                query = f"UPDATE recovery_operations SET {', '.join(updates)} WHERE id = ${param_count}"
                await conn.execute(query, *params)

    async def get_recovery_operations(self, limit: int = 50, operation_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recovery operations history."""
        async with self._pool.acquire() as conn:
            if operation_type:
                rows = await conn.fetch(
                    """
                    SELECT * FROM recovery_operations 
                    WHERE operation_type = $1 
                    ORDER BY started_at DESC 
                    LIMIT $2
                    """,
                    operation_type, limit
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM recovery_operations 
                    ORDER BY started_at DESC 
                    LIMIT $1
                    """,
                    limit
                )
            
            return [dict(row) for row in rows]

    async def get_recovery_stats(self) -> Dict[str, Any]:
        """Get recovery system statistics."""
        async with self._pool.acquire() as conn:
            # Get total recovered messages
            total_recovered = await conn.fetchval(
                "SELECT SUM(total_recovered_messages) FROM message_processing_cursors"
            ) or 0
            
            # Get recent operations
            recent_ops = await conn.fetch(
                """
                SELECT status, COUNT(*) as count
                FROM recovery_operations 
                WHERE started_at > NOW() - INTERVAL '24 hours'
                GROUP BY status
                """
            )
            
            # Get last successful operation
            last_success = await conn.fetchrow(
                """
                SELECT started_at, messages_recovered, users_checked
                FROM recovery_operations
                WHERE status = 'completed' AND messages_recovered > 0
                ORDER BY started_at DESC
                LIMIT 1
                """
            )
            
            return {
                'total_recovered_messages': total_recovered,
                'recent_operations': {dict(row)['status']: dict(row)['count'] for row in recent_ops},
                'last_successful_recovery': dict(last_success) if last_success else None
            }

    async def get_recovered_messages(self, limit: int = 50, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get list of recovered messages from interactions table."""
        async with self._pool.acquire() as conn:
            base_query = """
                SELECT 
                    i.id,
                    i.user_id,
                    i.user_message,
                    i.user_message_timestamp,
                    i.telegram_message_id,
                    i.telegram_date,
                    i.created_at,
                    i.review_status,
                    u.nickname,
                    u.customer_status,
                    EXTRACT(EPOCH FROM (i.created_at - i.telegram_date)) / 3600.0 as recovery_delay_hours
                FROM interactions i
                LEFT JOIN user_current_status u ON i.user_id = u.user_id
                WHERE i.is_recovered_message = TRUE
            """
            
            params = []
            if user_id:
                base_query += " AND i.user_id = $1"
                params.append(user_id)
                base_query += " ORDER BY i.telegram_date DESC LIMIT $2"
                params.append(limit)
            else:
                base_query += " ORDER BY i.telegram_date DESC LIMIT $1"
                params.append(limit)
            
            rows = await conn.fetch(base_query, *params)
            return [dict(row) for row in rows]
