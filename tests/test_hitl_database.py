# tests/test_hitl_database.py
"""Tests for HITL database functionality."""
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import asyncpg
import pytest

from agents.supervisor_agent import AIResponse, ReviewItem
from cognition.constitution import ConstitutionAnalysis, RecommendationType
from database.models import DatabaseManager


class TestDatabaseManager:
    """Test the DatabaseManager class."""

    def setup_method(self):
        """Setup test fixtures."""
        self.db_url = "postgresql://test:test@localhost/test_db"
        self.db_manager = DatabaseManager(self.db_url)

        # Mock the connection pool
        self.mock_pool = AsyncMock()
        self.mock_conn = AsyncMock()
        self.mock_pool.acquire.return_value.__aenter__.return_value = self.mock_conn
        self.db_manager._pool = self.mock_pool

    async def test_initialize_creates_pool(self):
        """Test that initialize creates a connection pool."""
        with patch('asyncpg.create_pool') as mock_create_pool:
            mock_pool = AsyncMock()
            mock_create_pool.return_value = mock_pool

            db_manager = DatabaseManager(self.db_url)
            await db_manager.initialize()

            assert db_manager._pool == mock_pool
            mock_create_pool.assert_called_once_with(self.db_url)

    async def test_close_closes_pool(self):
        """Test that close properly closes the connection pool."""
        await self.db_manager.close()
        self.mock_pool.close.assert_called_once()

    async def test_save_interaction(self):
        """Test saving a ReviewItem to the database."""
        # Create test data
        constitution_analysis = ConstitutionAnalysis(
            flags=["KEYWORD:test"],
            risk_score=0.3,
            recommendation=RecommendationType.REVIEW,
            normalized_text="test message",
            violations=["test violation"]
        )

        ai_response = AIResponse(
            llm1_raw="Raw response",
            llm2_bubbles=["Bubble 1", "Bubble 2"],
            constitution_analysis=constitution_analysis,
            tokens_used=100,
            generation_time=1.5
        )

        review_item = ReviewItem(
            id="test-id",
            user_id="123",
            user_message="Test message",
            ai_suggestion=ai_response,
            priority=0.7,
            timestamp=datetime.now(),
            conversation_context={"name": "Alice"}
        )

        # Mock database response
        self.mock_conn.fetchval.return_value = "db-generated-id"

        # Execute
        result_id = await self.db_manager.save_interaction(review_item)

        # Assert
        assert result_id == "db-generated-id"
        self.mock_conn.fetchval.assert_called_once()

        # Check that SQL was called with correct parameters
        call_args = self.mock_conn.fetchval.call_args
        sql = call_args[0][0]
        params = call_args[0][1:]

        assert "INSERT INTO interactions" in sql
        assert params[0] == "123"  # user_id
        assert params[3] == "Test message"  # user_message
        assert params[5] == "Raw response"  # llm1_raw_response
        assert params[6] == ["Bubble 1", "Bubble 2"]  # llm2_bubbles
        assert params[7] == 0.3  # risk_score

    async def test_get_pending_reviews(self):
        """Test retrieving pending reviews."""
        # Mock database response
        self.mock_conn.fetch.return_value = [
            {
                "id": "review-1",
                "user_id": "123",
                "user_message": "Hello!",
                "llm1_raw_response": "Hi there!",
                "llm2_bubbles": ["Hi there! 😊"],
                "constitution_risk_score": 0.0,
                "constitution_flags": [],
                "constitution_recommendation": "approve",
                "priority_score": 0.5,
                "created_at": datetime.now()
            }
        ]

        # Execute
        reviews = await self.db_manager.get_pending_reviews(limit=10, min_priority=0.3)

        # Assert
        assert len(reviews) == 1
        assert reviews[0]["id"] == "review-1"
        assert reviews[0]["user_id"] == "123"

        # Check SQL parameters
        call_args = self.mock_conn.fetch.call_args
        assert call_args[0][1] == 0.3  # min_priority
        assert call_args[0][2] == 10   # limit

    async def test_start_review(self):
        """Test starting a review (marking as reviewing)."""
        self.mock_conn.execute.return_value = "UPDATE 1"

        result = await self.db_manager.start_review("review-id", "reviewer-123")

        assert result is True

        # Check SQL was called correctly
        call_args = self.mock_conn.execute.call_args
        sql = call_args[0][0]
        params = call_args[0][1:]

        assert "UPDATE interactions" in sql
        assert "review_status = 'reviewing'" in sql
        assert params[0] == "reviewer-123"
        assert params[1] == "review-id"

    async def test_start_review_not_found(self):
        """Test starting a review that doesn't exist."""
        self.mock_conn.execute.return_value = "UPDATE 0"

        result = await self.db_manager.start_review("nonexistent", "reviewer-123")

        assert result is False

    async def test_approve_review(self):
        """Test approving a review."""
        self.mock_conn.execute.return_value = "UPDATE 1"

        result = await self.db_manager.approve_review(
            "review-id",
            ["Final bubble 1", "Final bubble 2"],
            ["TONE_CASUAL", "CONTENT_EMOJI_ADD"],
            4,
            "Good response"
        )

        assert result is True

        # Check SQL was called correctly
        call_args = self.mock_conn.execute.call_args
        sql = call_args[0][0]
        params = call_args[0][1:]

        assert "review_status = 'approved'" in sql
        assert params[0] == ["Final bubble 1", "Final bubble 2"]
        assert params[1] == ["TONE_CASUAL", "CONTENT_EMOJI_ADD"]
        assert params[2] == 4
        assert params[3] == "Good response"
        assert params[4] == "review-id"

    async def test_reject_review(self):
        """Test rejecting a review."""
        self.mock_conn.execute.return_value = "UPDATE 1"

        result = await self.db_manager.reject_review("review-id", "Inappropriate content")

        assert result is True

        # Check SQL was called correctly
        call_args = self.mock_conn.execute.call_args
        sql = call_args[0][0]
        params = call_args[0][1:]

        assert "review_status = 'rejected'" in sql
        assert params[0] == "Inappropriate content"
        assert params[1] == "review-id"

    async def test_get_interaction(self):
        """Test retrieving a specific interaction."""
        mock_row = MagicMock()
        mock_row.__dict__ = {
            "id": "review-id",
            "user_message": "Hello!",
            "review_status": "pending"
        }
        self.mock_conn.fetchrow.return_value = mock_row

        result = await self.db_manager.get_interaction("review-id")

        assert result is not None
        assert result["id"] == "review-id"
        self.mock_conn.fetchrow.assert_called_once_with(
            "SELECT * FROM interactions WHERE id = $1",
            "review-id"
        )

    async def test_get_interaction_not_found(self):
        """Test retrieving a non-existent interaction."""
        self.mock_conn.fetchrow.return_value = None

        result = await self.db_manager.get_interaction("nonexistent")

        assert result is None

    async def test_get_dashboard_metrics(self):
        """Test retrieving dashboard metrics."""
        # Mock multiple database calls for metrics
        self.mock_conn.fetchval.side_effect = [
            5,    # pending_count
            12,   # reviewed_today
            45.5  # avg_review_time
        ]

        # Mock edit tags query
        self.mock_conn.fetch.return_value = [
            {"tag": "TONE_CASUAL", "count": 8},
            {"tag": "CONTENT_EMOJI_ADD", "count": 5}
        ]

        # Execute
        metrics = await self.db_manager.get_dashboard_metrics()

        # Assert
        assert metrics["pending_reviews"] == 5
        assert metrics["reviewed_today"] == 12
        assert metrics["avg_review_time_seconds"] == 45.5
        assert len(metrics["popular_edit_tags"]) == 2
        assert metrics["popular_edit_tags"][0]["tag"] == "TONE_CASUAL"

    async def test_get_edit_taxonomy(self):
        """Test retrieving edit taxonomy."""
        self.mock_conn.fetch.return_value = [
            {
                "code": "TONE_CASUAL",
                "category": "tone",
                "description": "Made more casual/informal"
            },
            {
                "code": "CONTENT_EMOJI_ADD",
                "category": "content",
                "description": "Added emojis"
            }
        ]

        result = await self.db_manager.get_edit_taxonomy()

        assert len(result) == 2
        assert result[0]["code"] == "TONE_CASUAL"
        assert result[1]["code"] == "CONTENT_EMOJI_ADD"

    async def test_database_connection_error(self):
        """Test handling of database connection errors."""
        self.mock_pool.acquire.side_effect = asyncpg.PostgresError("Connection failed")

        with pytest.raises(asyncpg.PostgresError):
            await self.db_manager.save_interaction(MagicMock())

    async def test_sql_injection_protection(self):
        """Test that parameters are properly escaped to prevent SQL injection."""
        # This is more of a conceptual test since asyncpg handles parameterization
        review_item = MagicMock()
        review_item.user_id = "'; DROP TABLE interactions; --"
        review_item.user_message = "Test"
        review_item.ai_suggestion = MagicMock()
        review_item.ai_suggestion.llm1_raw = "Response"
        review_item.ai_suggestion.llm2_bubbles = ["Bubble"]
        review_item.ai_suggestion.constitution_analysis = MagicMock()
        review_item.ai_suggestion.constitution_analysis.risk_score = 0.0
        review_item.ai_suggestion.constitution_analysis.flags = []
        review_item.ai_suggestion.constitution_analysis.recommendation = MagicMock()
        review_item.ai_suggestion.constitution_analysis.recommendation.value = "approve"
        review_item.priority = 0.5
        review_item.timestamp = datetime.now()

        self.mock_conn.fetchval.return_value = "safe-id"

        # This should not raise an exception if properly parameterized
        result = await self.db_manager.save_interaction(review_item)
        assert result == "safe-id"
