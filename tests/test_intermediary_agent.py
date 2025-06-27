"""Unit tests for IntermediaryAgent - LLM1 to LLM2 data preparation and conflict analysis."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
import json

from agents.intermediary_agent import IntermediaryAgent
from agents.types import AIResponse
from database.models import DatabaseManager


class TestIntermediaryAgent:
    """Test suite for IntermediaryAgent functionality."""

    @pytest.fixture
    async def mock_db(self):
        """Mock database manager."""
        db = AsyncMock(spec=DatabaseManager)
        # Default return values
        db.get_user_commitments.return_value = []
        db.check_schedule_conflicts.return_value = []
        return db

    @pytest.fixture
    async def intermediary_agent(self, mock_db):
        """Create IntermediaryAgent instance."""
        agent = IntermediaryAgent(mock_db)
        return agent

    @pytest.fixture
    def sample_ai_response(self):
        """Sample AI response from LLM1."""
        return AIResponse(
            response="I'd love to have dinner with you tomorrow at 7 PM! Looking forward to it.",
            confidence=0.95,
            model="gemini-2.0-flash-exp",
            tokens_used=150,
            cost=0.0001,
            llm_id="llm1",
            raw_response=None
        )

    @pytest.fixture
    def sample_context(self):
        """Sample conversation context."""
        return {
            "user_id": "user123",
            "username": "testuser",
            "message": "Want to have dinner tomorrow at 7?",
            "current_time": datetime.now().isoformat(),
            "timezone": "America/Monterrey"
        }

    async def test_initialization(self, intermediary_agent, mock_db):
        """Test IntermediaryAgent initialization."""
        assert intermediary_agent.db_manager == mock_db
        assert intermediary_agent.conflict_keywords is not None
        assert len(intermediary_agent.conflict_keywords) > 0

    async def test_prepare_for_llm2_basic(self, intermediary_agent, sample_ai_response, sample_context):
        """Test basic LLM2 data preparation without conflicts."""
        result = await intermediary_agent.prepare_for_llm2(
            ai_response=sample_ai_response,
            user_id=sample_context["user_id"],
            context=sample_context
        )
        
        assert "llm1_response" in result
        assert result["llm1_response"] == sample_ai_response.response
        assert "user_id" in result
        assert result["user_id"] == sample_context["user_id"]
        assert "current_time_monterrey" in result
        assert "potential_conflicts" in result

    async def test_extract_time_commitment(self, intermediary_agent):
        """Test time commitment extraction from responses."""
        # Test with clear time commitment
        response = "Sure, let's meet tomorrow at 3 PM for coffee!"
        commitment = intermediary_agent._extract_time_commitment(response)
        
        assert commitment is not None
        assert "tomorrow" in commitment["time_mention"]
        assert "3 PM" in commitment["time_mention"]
        assert commitment["commitment_type"] == "meeting"

        # Test with no time commitment
        response = "That sounds interesting, tell me more about it."
        commitment = intermediary_agent._extract_time_commitment(response)
        assert commitment is None

    async def test_detect_identity_conflicts(self, intermediary_agent, mock_db):
        """Test identity conflict detection (repetitive patterns)."""
        # Mock previous commitments showing repetitive pattern
        mock_db.get_user_commitments.return_value = [
            {
                "activity_type": "gym",
                "scheduled_time": datetime.now() - timedelta(days=1),
                "details": "Going to the gym"
            },
            {
                "activity_type": "gym",
                "scheduled_time": datetime.now() - timedelta(days=2),
                "details": "Going to the gym"
            },
            {
                "activity_type": "gym", 
                "scheduled_time": datetime.now() - timedelta(days=3),
                "details": "Going to the gym"
            }
        ]
        
        response = "I'll be at the gym as usual"
        conflicts = await intermediary_agent._detect_conflicts(
            response, "user123", {"activity_type": "gym"}
        )
        
        assert len(conflicts) > 0
        assert any(c["type"] == "CONFLICTO_DE_IDENTIDAD" for c in conflicts)

    async def test_detect_availability_conflicts(self, intermediary_agent, mock_db):
        """Test availability conflict detection (schedule overlaps)."""
        # Mock schedule conflict
        mock_db.check_schedule_conflicts.return_value = [
            {
                "conflict_type": "double_booking",
                "existing_commitment": "Dinner with family",
                "proposed_time": "2024-01-20 19:00:00"
            }
        ]
        
        response = "I can meet you for drinks at 7 PM tomorrow"
        commitment = {"scheduled_time": datetime.now() + timedelta(days=1, hours=19)}
        
        conflicts = await intermediary_agent._detect_conflicts(
            response, "user123", commitment
        )
        
        assert len(conflicts) > 0
        assert any(c["type"] == "CONFLICTO_DE_DISPONIBILIDAD" for c in conflicts)

    async def test_conflict_priority_ordering(self, intermediary_agent, mock_db):
        """Test that conflicts are properly prioritized."""
        # Set up both types of conflicts
        mock_db.get_user_commitments.return_value = [
            {"activity_type": "gym", "scheduled_time": datetime.now() - timedelta(days=i)}
            for i in range(5)
        ]
        mock_db.check_schedule_conflicts.return_value = [{
            "conflict_type": "double_booking"
        }]
        
        response = "Going to the gym at 7 PM tomorrow"
        result = await intermediary_agent.prepare_for_llm2(
            ai_response=AIResponse(response=response, confidence=0.9, model="test", 
                                  tokens_used=100, cost=0.0001, llm_id="llm1"),
            user_id="user123",
            context={"current_time": datetime.now().isoformat()}
        )
        
        conflicts = result["potential_conflicts"]
        # Availability conflicts should be listed first (higher priority)
        if len(conflicts) > 1:
            assert conflicts[0]["type"] == "CONFLICTO_DE_DISPONIBILIDAD"

    async def test_time_extraction_variations(self, intermediary_agent):
        """Test various time mention formats."""
        test_cases = [
            ("See you at 3:30 PM", "3:30 PM"),
            ("Let's meet tomorrow morning", "tomorrow morning"),
            ("I'm free this weekend", "this weekend"),
            ("Available Monday at noon", "Monday at noon"),
            ("Can do Friday evening", "Friday evening")
        ]
        
        for response, expected_mention in test_cases:
            commitment = intermediary_agent._extract_time_commitment(response)
            if expected_mention:
                assert commitment is not None
                assert expected_mention in commitment["time_mention"]

    async def test_commitment_type_detection(self, intermediary_agent):
        """Test detection of different commitment types."""
        test_cases = [
            ("Let's have dinner tomorrow", "meal"),
            ("Want to grab coffee?", "coffee"),
            ("Going to the gym later", "gym"),
            ("I have a meeting at 3", "meeting"),
            ("Doctor's appointment tomorrow", "appointment")
        ]
        
        for response, expected_type in test_cases:
            commitment = intermediary_agent._extract_time_commitment(response)
            if commitment:
                assert commitment["commitment_type"] == expected_type

    async def test_monterrey_timezone_handling(self, intermediary_agent, sample_ai_response):
        """Test Monterrey timezone is properly included."""
        result = await intermediary_agent.prepare_for_llm2(
            ai_response=sample_ai_response,
            user_id="user123",
            context={"timezone": "America/Monterrey"}
        )
        
        assert "current_time_monterrey" in result
        # Should be a valid ISO format timestamp
        datetime.fromisoformat(result["current_time_monterrey"].replace('Z', '+00:00'))

    async def test_empty_response_handling(self, intermediary_agent):
        """Test handling of empty or minimal responses."""
        ai_response = AIResponse(
            response="",
            confidence=0.5,
            model="test",
            tokens_used=0,
            cost=0,
            llm_id="llm1"
        )
        
        result = await intermediary_agent.prepare_for_llm2(
            ai_response=ai_response,
            user_id="user123",
            context={}
        )
        
        assert result["llm1_response"] == ""
        assert result["potential_conflicts"] == []

    async def test_database_error_handling(self, intermediary_agent, mock_db, sample_ai_response):
        """Test graceful handling of database errors."""
        # Mock database error
        mock_db.get_user_commitments.side_effect = Exception("Database connection error")
        
        # Should not raise exception
        result = await intermediary_agent.prepare_for_llm2(
            ai_response=sample_ai_response,
            user_id="user123",
            context={}
        )
        
        # Should return result without conflicts
        assert "potential_conflicts" in result
        assert isinstance(result["potential_conflicts"], list)

    async def test_complex_conflict_scenario(self, intermediary_agent, mock_db):
        """Test complex scenario with multiple conflict types."""
        # Set up identity loop (gym pattern)
        mock_db.get_user_commitments.return_value = [
            {
                "activity_type": "gym",
                "scheduled_time": datetime.now() - timedelta(days=i),
                "details": f"Gym session {i}"
            }
            for i in range(7)  # 7 days of gym
        ]
        
        # Set up availability conflict
        mock_db.check_schedule_conflicts.return_value = [
            {
                "conflict_type": "double_booking",
                "existing_commitment": "Date with Sarah",
                "proposed_time": "2024-01-20 19:00:00"
            }
        ]
        
        response = "I'll be at the gym at 7 PM as always"
        result = await intermediary_agent.prepare_for_llm2(
            ai_response=AIResponse(response=response, confidence=0.9, model="test",
                                  tokens_used=100, cost=0.0001, llm_id="llm1"),
            user_id="user123",
            context={"current_time": datetime.now().isoformat()}
        )
        
        conflicts = result["potential_conflicts"]
        assert len(conflicts) >= 2
        assert any(c["type"] == "CONFLICTO_DE_IDENTIDAD" for c in conflicts)
        assert any(c["type"] == "CONFLICTO_DE_DISPONIBILIDAD" for c in conflicts)