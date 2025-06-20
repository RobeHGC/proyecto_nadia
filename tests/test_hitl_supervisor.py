# tests/test_hitl_supervisor.py
"""Tests for HITL Supervisor Agent functionality."""
from datetime import datetime
from unittest.mock import AsyncMock

from agents.supervisor_agent import AIResponse, ReviewItem, SupervisorAgent
from llms.openai_client import OpenAIClient
from memory.user_memory import UserMemoryManager


class TestSupervisorAgentHITL:
    """Test the new HITL functionality in SupervisorAgent."""

    def setup_method(self):
        """Setup test fixtures."""
        # Mock dependencies
        self.mock_llm = AsyncMock(spec=OpenAIClient)
        self.mock_memory = AsyncMock(spec=UserMemoryManager)

        # Create supervisor with mocked dependencies
        self.supervisor = SupervisorAgent(self.mock_llm, self.mock_memory)

    async def test_process_message_returns_review_item(self):
        """Test that process_message now returns ReviewItem instead of string."""
        # Setup mocks
        self.mock_memory.get_user_context.return_value = {"name": "Alice"}
        self.mock_llm.generate_response.side_effect = [
            "Hello Alice! How can I help you today?",  # LLM-1 response
            "Hello Alice! 😊 [GLOBO] How can I help you today?"  # LLM-2 response
        ]

        # Execute
        result = await self.supervisor.process_message("123", "Hello!")

        # Assert
        assert isinstance(result, ReviewItem)
        assert result.user_id == "123"
        assert result.user_message == "Hello!"
        assert isinstance(result.ai_suggestion, AIResponse)
        assert result.priority > 0.0
        assert isinstance(result.timestamp, datetime)

    async def test_two_llm_pipeline(self):
        """Test that both LLM calls are made in sequence."""
        # Setup mocks
        self.mock_memory.get_user_context.return_value = {}
        self.mock_llm.generate_response.side_effect = [
            "Raw creative response",
            "Refined response [GLOBO] with bubbles"
        ]

        # Execute
        result = await self.supervisor.process_message("123", "Test message")

        # Assert both LLM calls were made
        assert self.mock_llm.generate_response.call_count == 2

        # Check that different temperatures were used
        calls = self.mock_llm.generate_response.call_args_list
        assert calls[0][1]['temperature'] == 0.8  # Creative LLM
        assert calls[1][1]['temperature'] == 0.5  # Refinement LLM

        # Check that responses are stored correctly
        assert result.ai_suggestion.llm1_raw == "Raw creative response"
        assert "Refined response" in result.ai_suggestion.llm2_bubbles[0]

    async def test_bubble_splitting(self):
        """Test that [GLOBO] markers split responses into bubbles."""
        self.mock_memory.get_user_context.return_value = {}
        self.mock_llm.generate_response.side_effect = [
            "Raw response",
            "First bubble [GLOBO] Second bubble [GLOBO] Third bubble"
        ]

        result = await self.supervisor.process_message("123", "Test")

        bubbles = result.ai_suggestion.llm2_bubbles
        assert len(bubbles) == 3
        assert bubbles[0] == "First bubble"
        assert bubbles[1] == "Second bubble"
        assert bubbles[2] == "Third bubble"

    async def test_bubble_splitting_no_markers(self):
        """Test bubble splitting when no [GLOBO] markers exist."""
        self.mock_memory.get_user_context.return_value = {}
        self.mock_llm.generate_response.side_effect = [
            "Raw response",
            "Single response without markers"
        ]

        result = await self.supervisor.process_message("123", "Test")

        bubbles = result.ai_suggestion.llm2_bubbles
        assert len(bubbles) == 1
        assert bubbles[0] == "Single response without markers"

    async def test_constitution_analysis_integration(self):
        """Test that constitution analysis is included in ReviewItem."""
        self.mock_memory.get_user_context.return_value = {}
        self.mock_llm.generate_response.side_effect = [
            "I love you so much!",  # Risky response
            "I love you! [GLOBO] Have a great day!"
        ]

        result = await self.supervisor.process_message("123", "Test")

        analysis = result.ai_suggestion.constitution_analysis
        assert analysis is not None
        assert analysis.risk_score > 0.0
        assert len(analysis.violations) > 0

    async def test_priority_calculation(self):
        """Test priority calculation logic."""
        # Test with risky content
        self.mock_memory.get_user_context.return_value = {}
        self.mock_llm.generate_response.side_effect = [
            "I love you!",  # Risky
            "Refined response"
        ]

        risky_result = await self.supervisor.process_message("123", "Test")

        # Test with safe content
        self.mock_llm.generate_response.side_effect = [
            "Hello there!",  # Safe
            "Hello there!"
        ]

        safe_result = await self.supervisor.process_message("123", "Test")

        # Risky content should have higher priority
        assert risky_result.priority > safe_result.priority

    async def test_priority_with_known_user(self):
        """Test that known users get priority boost."""
        # Unknown user
        self.mock_memory.get_user_context.return_value = {}
        self.mock_llm.generate_response.side_effect = [
            "Hello!",
            "Hello!"
        ]

        unknown_result = await self.supervisor.process_message("123", "Test")

        # Known user
        self.mock_memory.get_user_context.return_value = {"name": "Alice"}
        self.mock_llm.generate_response.side_effect = [
            "Hello!",
            "Hello!"
        ]

        known_result = await self.supervisor.process_message("123", "Test")

        # Known user should have higher priority
        assert known_result.priority > unknown_result.priority

    async def test_name_extraction_still_works(self):
        """Test that name extraction functionality is preserved."""
        self.mock_memory.get_user_context.return_value = {}
        self.mock_llm.generate_response.side_effect = [
            "Nice to meet you!",
            "Nice to meet you!"
        ]

        # Execute with name introduction
        await self.supervisor.process_message("123", "Hi, my name is Bob")

        # Check that name was extracted and stored
        self.mock_memory.set_name.assert_called_once_with("123", "Bob")

    async def test_review_id_uniqueness(self):
        """Test that each ReviewItem gets a unique ID."""
        self.mock_memory.get_user_context.return_value = {}
        self.mock_llm.generate_response.side_effect = [
            "Response 1", "Response 1",
            "Response 2", "Response 2"
        ]

        result1 = await self.supervisor.process_message("123", "Message 1")
        result2 = await self.supervisor.process_message("123", "Message 2")

        assert result1.id != result2.id

    async def test_creative_prompt_building(self):
        """Test that creative prompts are built correctly."""
        self.mock_memory.get_user_context.return_value = {"name": "Alice"}
        self.mock_llm.generate_response.side_effect = ["Response", "Response"]

        await self.supervisor.process_message("123", "Hello!")

        # Check first call (creative prompt)
        creative_call = self.mock_llm.generate_response.call_args_list[0]
        messages = creative_call[0][0]  # First positional argument

        # Should contain system message with NADIA persona
        system_msg = next(msg for msg in messages if msg["role"] == "system")
        assert "NADIA" in system_msg["content"]
        assert "creative" in system_msg["content"].lower()

        # Should contain user name context
        name_msg = next((msg for msg in messages if "Alice" in msg.get("content", "")), None)
        assert name_msg is not None

    async def test_refinement_prompt_building(self):
        """Test that refinement prompts include constitution feedback."""
        self.mock_memory.get_user_context.return_value = {}
        self.mock_llm.generate_response.side_effect = [
            "I love you!",  # Risky response
            "Refined response"
        ]

        await self.supervisor.process_message("123", "Hello!")

        # Check second call (refinement prompt)
        refinement_call = self.mock_llm.generate_response.call_args_list[1]
        messages = refinement_call[0][0]

        # Should contain system message about refinement
        system_msg = next(msg for msg in messages if msg["role"] == "system")
        assert "refinement" in system_msg["content"].lower()
        assert "[GLOBO]" in system_msg["content"]
