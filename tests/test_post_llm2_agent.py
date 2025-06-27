"""Unit tests for PostLLM2Agent - Decision execution and commitment storage."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import json

from agents.post_llm2_agent import PostLLM2Agent
from agents.types import AIResponse
from database.models import DatabaseManager


class TestPostLLM2Agent:
    """Test suite for PostLLM2Agent functionality."""

    @pytest.fixture
    async def mock_db(self):
        """Mock database manager."""
        db = AsyncMock(spec=DatabaseManager)
        # Default return values
        db.store_commitment.return_value = True
        db.store_coherence_analysis.return_value = 1
        db.update_prompt_rotation.return_value = True
        return db

    @pytest.fixture
    async def post_llm2_agent(self, mock_db):
        """Create PostLLM2Agent instance."""
        agent = PostLLM2Agent(mock_db)
        return agent

    @pytest.fixture
    def sample_llm2_response(self):
        """Sample structured response from LLM2."""
        return {
            "has_temporal_commitment": True,
            "commitment_details": {
                "activity_type": "dinner",
                "proposed_time": "tomorrow at 7 PM",
                "parsed_datetime": "2024-01-20T19:00:00",
                "duration_minutes": 120
            },
            "conflicts_detected": True,
            "conflict_analysis": {
                "type": "CONFLICTO_DE_DISPONIBILIDAD",
                "severity": "HIGH",
                "reason": "User already has dinner plans with family at this time"
            },
            "recommended_action": "MODIFY_RESPONSE",
            "suggested_correction": "I'd love to have dinner with you! However, I just remembered I have plans tomorrow at 7. How about we meet for lunch instead, or perhaps dinner another day?"
        }

    @pytest.fixture
    def sample_context(self):
        """Sample processing context."""
        return {
            "user_id": "user123",
            "interaction_id": "int_456",
            "original_response": "Sure, let's have dinner tomorrow at 7 PM!",
            "timestamp": datetime.now().isoformat()
        }

    async def test_initialization(self, post_llm2_agent, mock_db):
        """Test PostLLM2Agent initialization."""
        assert post_llm2_agent.db_manager == mock_db
        assert hasattr(post_llm2_agent, 'execute_decision')

    async def test_execute_decision_no_conflicts(self, post_llm2_agent, mock_db):
        """Test decision execution when no conflicts detected."""
        llm2_response = {
            "has_temporal_commitment": False,
            "conflicts_detected": False,
            "recommended_action": "SEND_ORIGINAL"
        }
        
        result = await post_llm2_agent.execute_decision(
            llm2_response=llm2_response,
            original_response="Hello! How are you?",
            user_id="user123",
            interaction_id="int_456"
        )
        
        assert result["action_taken"] == "SEND_ORIGINAL"
        assert result["final_response"] == "Hello! How are you?"
        assert result["coherence_score"] == 100
        assert result["modifications_made"] is False

    async def test_execute_decision_with_correction(self, post_llm2_agent, sample_llm2_response, mock_db):
        """Test decision execution with conflict correction."""
        result = await post_llm2_agent.execute_decision(
            llm2_response=sample_llm2_response,
            original_response="Sure, let's have dinner tomorrow at 7 PM!",
            user_id="user123",
            interaction_id="int_456"
        )
        
        assert result["action_taken"] == "MODIFIED_RESPONSE"
        assert result["final_response"] == sample_llm2_response["suggested_correction"]
        assert result["modifications_made"] is True
        assert result["conflict_type"] == "CONFLICTO_DE_DISPONIBILIDAD"
        assert result["coherence_score"] < 100

    async def test_commitment_storage(self, post_llm2_agent, sample_llm2_response, mock_db):
        """Test that commitments are properly stored in database."""
        await post_llm2_agent.execute_decision(
            llm2_response=sample_llm2_response,
            original_response="Sure, let's have dinner tomorrow at 7 PM!",
            user_id="user123",
            interaction_id="int_456"
        )
        
        # Verify commitment was stored
        mock_db.store_commitment.assert_called_once()
        call_args = mock_db.store_commitment.call_args[1]
        assert call_args["user_id"] == "user123"
        assert call_args["activity_type"] == "dinner"
        assert "parsed_datetime" in call_args

    async def test_coherence_analysis_storage(self, post_llm2_agent, sample_llm2_response, mock_db):
        """Test that coherence analysis is stored."""
        await post_llm2_agent.execute_decision(
            llm2_response=sample_llm2_response,
            original_response="Sure, let's have dinner tomorrow at 7 PM!",
            user_id="user123",
            interaction_id="int_456"
        )
        
        # Verify coherence analysis was stored
        mock_db.store_coherence_analysis.assert_called_once()
        call_args = mock_db.store_coherence_analysis.call_args[1]
        assert call_args["interaction_id"] == "int_456"
        assert call_args["conflict_type"] == "CONFLICTO_DE_DISPONIBILIDAD"
        assert call_args["was_corrected"] is True

    async def test_coherence_score_calculation(self, post_llm2_agent):
        """Test coherence score calculation for different conflict types."""
        # No conflicts = 100
        score = post_llm2_agent._calculate_coherence_score(False, None)
        assert score == 100
        
        # Identity conflict = 70
        score = post_llm2_agent._calculate_coherence_score(True, "CONFLICTO_DE_IDENTIDAD")
        assert score == 70
        
        # Availability conflict = 85
        score = post_llm2_agent._calculate_coherence_score(True, "CONFLICTO_DE_DISPONIBILIDAD")
        assert score == 85
        
        # Other conflict = 90
        score = post_llm2_agent._calculate_coherence_score(True, "OTHER")
        assert score == 90

    async def test_prompt_rotation_on_identity_conflict(self, post_llm2_agent, mock_db):
        """Test that prompt rotation is triggered for identity conflicts."""
        llm2_response = {
            "has_temporal_commitment": True,
            "conflicts_detected": True,
            "conflict_analysis": {
                "type": "CONFLICTO_DE_IDENTIDAD",
                "severity": "HIGH"
            },
            "recommended_action": "MODIFY_RESPONSE",
            "suggested_correction": "Let me check my schedule and get back to you!"
        }
        
        await post_llm2_agent.execute_decision(
            llm2_response=llm2_response,
            original_response="Going to the gym as always",
            user_id="user123",
            interaction_id="int_456"
        )
        
        # Verify prompt rotation was triggered
        mock_db.update_prompt_rotation.assert_called_once()
        call_args = mock_db.update_prompt_rotation.call_args[1]
        assert call_args["should_rotate"] is True

    async def test_no_prompt_rotation_on_availability_conflict(self, post_llm2_agent, mock_db):
        """Test that prompt rotation is NOT triggered for availability conflicts."""
        llm2_response = {
            "conflicts_detected": True,
            "conflict_analysis": {
                "type": "CONFLICTO_DE_DISPONIBILIDAD"
            },
            "recommended_action": "MODIFY_RESPONSE",
            "suggested_correction": "How about a different time?"
        }
        
        await post_llm2_agent.execute_decision(
            llm2_response=llm2_response,
            original_response="See you at 7",
            user_id="user123",
            interaction_id="int_456"
        )
        
        # Prompt rotation should NOT be triggered
        mock_db.update_prompt_rotation.assert_not_called()

    async def test_missing_correction_fallback(self, post_llm2_agent):
        """Test fallback when LLM2 recommends modification but provides no correction."""
        llm2_response = {
            "conflicts_detected": True,
            "recommended_action": "MODIFY_RESPONSE",
            "suggested_correction": None  # Missing correction
        }
        
        result = await post_llm2_agent.execute_decision(
            llm2_response=llm2_response,
            original_response="Original message",
            user_id="user123",
            interaction_id="int_456"
        )
        
        # Should fall back to original
        assert result["action_taken"] == "SEND_ORIGINAL"
        assert result["final_response"] == "Original message"

    async def test_database_error_handling(self, post_llm2_agent, sample_llm2_response, mock_db):
        """Test graceful handling of database errors."""
        # Mock database error
        mock_db.store_commitment.side_effect = Exception("Database error")
        
        # Should not raise exception
        result = await post_llm2_agent.execute_decision(
            llm2_response=sample_llm2_response,
            original_response="Original",
            user_id="user123",
            interaction_id="int_456"
        )
        
        # Should still return a result
        assert "final_response" in result
        assert result["modifications_made"] is True

    async def test_complex_commitment_parsing(self, post_llm2_agent, mock_db):
        """Test handling of complex commitment details."""
        llm2_response = {
            "has_temporal_commitment": True,
            "commitment_details": {
                "activity_type": "multi_event",
                "proposed_time": "dinner at 7 PM and then movies at 9 PM",
                "parsed_datetime": "2024-01-20T19:00:00",
                "duration_minutes": 240,
                "location": "Downtown",
                "participants": ["user", "nadia"]
            },
            "conflicts_detected": False,
            "recommended_action": "SEND_ORIGINAL"
        }
        
        result = await post_llm2_agent.execute_decision(
            llm2_response=llm2_response,
            original_response="Dinner and movie sounds great!",
            user_id="user123",
            interaction_id="int_456"
        )
        
        # Verify complex commitment was stored
        mock_db.store_commitment.assert_called_once()
        call_args = mock_db.store_commitment.call_args[1]
        assert call_args["activity_type"] == "multi_event"
        assert call_args["duration_minutes"] == 240

    async def test_metrics_tracking(self, post_llm2_agent, sample_llm2_response, mock_db):
        """Test that metrics are properly tracked."""
        result = await post_llm2_agent.execute_decision(
            llm2_response=sample_llm2_response,
            original_response="Original",
            user_id="user123",
            interaction_id="int_456"
        )
        
        # Check all required metrics are present
        assert "action_taken" in result
        assert "coherence_score" in result
        assert "modifications_made" in result
        assert "conflict_type" in result
        assert "processing_time_ms" in result
        assert result["processing_time_ms"] >= 0

    async def test_edge_case_empty_response(self, post_llm2_agent):
        """Test handling of empty LLM2 response."""
        result = await post_llm2_agent.execute_decision(
            llm2_response={},  # Empty response
            original_response="Hello!",
            user_id="user123",
            interaction_id="int_456"
        )
        
        # Should default to sending original
        assert result["action_taken"] == "SEND_ORIGINAL"
        assert result["final_response"] == "Hello!"
        assert result["coherence_score"] == 100