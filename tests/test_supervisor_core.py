"""Unit tests for SupervisorAgent core functionality."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from dataclasses import asdict

from agents.supervisor_agent import SupervisorAgent, AIResponse, ReviewItem
from llms.openai_client import OpenAIClient
from memory.user_memory import UserMemoryManager
from utils.config import Config
from cognition.constitution import ConstitutionAnalysis


class TestSupervisorAgent:
    """Test suite for SupervisorAgent core functionality."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration."""
        config = MagicMock(spec=Config)
        config.llm_profile = "production"
        config.llm1_provider = "gemini"
        config.llm1_model = "gemini-2.0-flash-exp"
        config.llm2_provider = "openai"
        config.llm2_model = "gpt-4o-mini"
        config.gemini_api_key = "test_gemini_key"
        config.openai_api_key = "test_openai_key"
        return config

    @pytest.fixture
    def mock_llm_client(self):
        """Mock LLM client."""
        return AsyncMock(spec=OpenAIClient)

    @pytest.fixture
    def mock_memory(self):
        """Mock memory manager."""
        return AsyncMock(spec=UserMemoryManager)

    @pytest.fixture
    def constitution_analysis(self):
        """Sample constitution analysis."""
        return ConstitutionAnalysis(
            is_safe=True,
            risk_score=0.1,
            flagged_categories=[],
            explanation="Safe content",
            safety_version="4.2"
        )

    @pytest.fixture
    def ai_response(self, constitution_analysis):
        """Sample AI response."""
        return AIResponse(
            llm1_raw="Hello! How can I help you?",
            llm2_bubbles=["Hello!", "How can I help you?"],
            constitution_analysis=constitution_analysis,
            tokens_used=50,
            generation_time=1.2,
            llm1_model="gemini-2.0",
            llm2_model="gpt-4o-mini",
            llm1_cost=0.001,
            llm2_cost=0.002
        )

    @patch('agents.supervisor_agent.get_dynamic_router')
    @patch('agents.supervisor_agent.os.path.exists')
    @patch('builtins.open')
    def test_supervisor_initialization_success(self, mock_open, mock_exists, mock_get_router, 
                                             mock_llm_client, mock_memory, mock_config):
        """Test successful supervisor initialization."""
        # Setup
        mock_exists.return_value = True
        mock_open.return_value.__enter__.return_value.read.return_value = "# Nadia Persona\nFriendly AI"
        
        mock_router = MagicMock()
        mock_router.select_llm1.return_value = MagicMock()
        mock_router.select_llm2.return_value = MagicMock()
        mock_get_router.return_value = mock_router
        
        # Execute
        supervisor = SupervisorAgent(mock_llm_client, mock_memory, mock_config)
        
        # Verify
        assert supervisor.llm == mock_llm_client
        assert supervisor.memory == mock_memory
        assert supervisor.config == mock_config
        assert supervisor.constitution is not None
        assert supervisor.turn_count == 0
        assert supervisor._llm1_persona is not None

    @patch('agents.supervisor_agent.get_dynamic_router')
    @patch('agents.supervisor_agent.create_llm_client')
    @patch('agents.supervisor_agent.os.path.exists')
    @patch('builtins.open')
    def test_supervisor_initialization_fallback(self, mock_open, mock_exists, mock_create_llm, 
                                              mock_get_router, mock_llm_client, mock_memory, mock_config):
        """Test supervisor initialization with router fallback."""
        # Setup
        mock_exists.return_value = True
        mock_open.return_value.__enter__.return_value.read.return_value = "# Nadia Persona"
        mock_get_router.side_effect = Exception("Router failed")
        mock_create_llm.return_value = MagicMock()
        
        # Execute
        supervisor = SupervisorAgent(mock_llm_client, mock_memory, mock_config)
        
        # Verify
        assert supervisor.llm_router is None
        assert mock_create_llm.call_count == 2  # LLM1 and LLM2

    def test_ai_response_dataclass(self, constitution_analysis):
        """Test AIResponse dataclass functionality."""
        response = AIResponse(
            llm1_raw="Test response",
            llm2_bubbles=["Test", "Response"],
            constitution_analysis=constitution_analysis,
            tokens_used=25,
            generation_time=0.5,
            llm1_model="gemini",
            llm2_model="gpt-4",
            llm1_cost=0.001,
            llm2_cost=0.002
        )
        
        assert response.llm1_raw == "Test response"
        assert len(response.llm2_bubbles) == 2
        assert response.tokens_used == 25
        assert response.generation_time == 0.5

    def test_review_item_dataclass(self, ai_response):
        """Test ReviewItem dataclass functionality."""
        review_item = ReviewItem(
            id="review_123",
            user_id="user_456",
            user_message="Hello",
            ai_suggestion=ai_response,
            priority=0.8,
            timestamp=datetime.now(),
            conversation_context={"recent_messages": []}
        )
        
        assert review_item.id == "review_123"
        assert review_item.user_id == "user_456"
        assert review_item.priority == 0.8
        assert isinstance(review_item.conversation_context, dict)

    @patch('agents.supervisor_agent.get_dynamic_router')
    @patch('agents.supervisor_agent.os.path.exists')
    @patch('builtins.open')
    def test_load_llm1_persona_success(self, mock_open, mock_exists, mock_get_router,
                                     mock_llm_client, mock_memory, mock_config):
        """Test successful LLM1 persona loading."""
        # Setup
        mock_exists.return_value = True
        persona_content = "# Nadia LLM1 Persona\nYou are a friendly AI assistant."
        mock_open.return_value.__enter__.return_value.read.return_value = persona_content
        mock_get_router.return_value = MagicMock()
        
        # Execute
        supervisor = SupervisorAgent(mock_llm_client, mock_memory, mock_config)
        
        # Verify
        assert supervisor._llm1_persona == persona_content

    @patch('agents.supervisor_agent.get_dynamic_router')
    @patch('agents.supervisor_agent.os.path.exists')
    def test_load_llm1_persona_file_not_found(self, mock_exists, mock_get_router,
                                            mock_llm_client, mock_memory, mock_config):
        """Test LLM1 persona loading with missing file."""
        # Setup
        mock_exists.return_value = False
        mock_get_router.return_value = MagicMock()
        
        # Execute & Verify
        with pytest.raises(FileNotFoundError):
            SupervisorAgent(mock_llm_client, mock_memory, mock_config)

    @patch('agents.supervisor_agent.get_dynamic_router')
    @patch('agents.supervisor_agent.os.path.exists')
    @patch('builtins.open')
    def test_turn_count_increment(self, mock_open, mock_exists, mock_get_router,
                                 mock_llm_client, mock_memory, mock_config):
        """Test turn count is managed correctly."""
        # Setup
        mock_exists.return_value = True
        mock_open.return_value.__enter__.return_value.read.return_value = "Persona"
        mock_get_router.return_value = MagicMock()
        
        supervisor = SupervisorAgent(mock_llm_client, mock_memory, mock_config)
        
        # Verify initial state
        assert supervisor.turn_count == 0
        
        # Simulate turn increment (would happen in actual methods)
        supervisor.turn_count += 1
        assert supervisor.turn_count == 1

    @patch('agents.supervisor_agent.get_dynamic_router')
    @patch('agents.supervisor_agent.os.path.exists')
    @patch('builtins.open')
    def test_conversation_summaries_cache(self, mock_open, mock_exists, mock_get_router,
                                        mock_llm_client, mock_memory, mock_config):
        """Test conversation summaries cache functionality."""
        # Setup
        mock_exists.return_value = True
        mock_open.return_value.__enter__.return_value.read.return_value = "Persona"
        mock_get_router.return_value = MagicMock()
        
        supervisor = SupervisorAgent(mock_llm_client, mock_memory, mock_config)
        
        # Test cache operations
        user_id = "user123"
        summary = "User discussed work and hobbies"
        
        supervisor._conversation_summaries[user_id] = summary
        assert supervisor._conversation_summaries[user_id] == summary
        assert len(supervisor._conversation_summaries) == 1

    @patch('agents.supervisor_agent.get_dynamic_router')
    @patch('agents.supervisor_agent.os.path.exists')
    @patch('builtins.open')
    def test_cache_warmed_up_flag(self, mock_open, mock_exists, mock_get_router,
                                 mock_llm_client, mock_memory, mock_config):
        """Test cache warm-up flag management."""
        # Setup
        mock_exists.return_value = True
        mock_open.return_value.__enter__.return_value.read.return_value = "Persona"
        mock_get_router.return_value = MagicMock()
        
        supervisor = SupervisorAgent(mock_llm_client, mock_memory, mock_config)
        
        # Verify initial state
        assert supervisor._cache_warmed_up is False
        
        # Simulate cache warm-up
        supervisor._cache_warmed_up = True
        assert supervisor._cache_warmed_up is True

    def test_constitution_analysis_dataclass(self):
        """Test ConstitutionAnalysis integration."""
        analysis = ConstitutionAnalysis(
            is_safe=False,
            risk_score=0.7,
            flagged_categories=["inappropriate_content"],
            explanation="Content flagged for review",
            safety_version="4.2"
        )
        
        assert analysis.is_safe is False
        assert analysis.risk_score == 0.7
        assert "inappropriate_content" in analysis.flagged_categories
        assert "review" in analysis.explanation

    @patch('agents.supervisor_agent.get_dynamic_router')
    @patch('agents.supervisor_agent.os.path.exists')
    @patch('builtins.open')
    def test_llm_clients_initialization(self, mock_open, mock_exists, mock_get_router,
                                      mock_llm_client, mock_memory, mock_config):
        """Test LLM clients are properly initialized."""
        # Setup
        mock_exists.return_value = True
        mock_open.return_value.__enter__.return_value.read.return_value = "Persona"
        
        mock_router = MagicMock()
        mock_llm1 = MagicMock()
        mock_llm2 = MagicMock()
        mock_router.select_llm1.return_value = mock_llm1
        mock_router.select_llm2.return_value = mock_llm2
        mock_get_router.return_value = mock_router
        
        # Execute
        supervisor = SupervisorAgent(mock_llm_client, mock_memory, mock_config)
        
        # Verify
        assert supervisor.llm1 == mock_llm1
        assert supervisor.llm2 == mock_llm2
        assert supervisor.llm_router == mock_router

    @patch('agents.supervisor_agent.get_dynamic_router')  
    @patch('agents.supervisor_agent.os.path.exists')
    @patch('builtins.open')
    def test_prefix_manager_initialization(self, mock_open, mock_exists, mock_get_router,
                                         mock_llm_client, mock_memory, mock_config):
        """Test StablePrefixManager is initialized."""
        # Setup
        mock_exists.return_value = True
        mock_open.return_value.__enter__.return_value.read.return_value = "Persona"
        mock_get_router.return_value = MagicMock()
        
        # Execute
        supervisor = SupervisorAgent(mock_llm_client, mock_memory, mock_config)
        
        # Verify
        assert supervisor.prefix_manager is not None
        assert hasattr(supervisor.prefix_manager, 'get_stable_prefix')

    def test_review_item_serialization(self, ai_response):
        """Test ReviewItem can be serialized (important for queue storage)."""
        review_item = ReviewItem(
            id="test_123",
            user_id="user_456", 
            user_message="Test message",
            ai_suggestion=ai_response,
            priority=0.5,
            timestamp=datetime.now(),
            conversation_context={"test": "data"}
        )
        
        # Test that it can be converted to dict (for JSON serialization)
        item_dict = asdict(review_item)
        assert item_dict["id"] == "test_123"
        assert item_dict["user_id"] == "user_456"
        assert item_dict["priority"] == 0.5
        assert isinstance(item_dict["ai_suggestion"], dict)

    def test_ai_response_cost_tracking(self, constitution_analysis):
        """Test AIResponse properly tracks costs for both LLMs."""
        response = AIResponse(
            llm1_raw="Response",
            llm2_bubbles=["Bubble1", "Bubble2"],
            constitution_analysis=constitution_analysis,
            tokens_used=100,
            generation_time=2.0,
            llm1_model="gemini-2.0",
            llm2_model="gpt-4o-mini",
            llm1_cost=0.0005,  # Gemini free tier
            llm2_cost=0.001    # OpenAI cost
        )
        
        total_cost = response.llm1_cost + response.llm2_cost
        assert total_cost == 0.0015
        assert response.llm1_cost < response.llm2_cost  # Gemini should be cheaper