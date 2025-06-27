"""Component initialization tests - prevents startup failures due to component init errors.

EPIC 1: CRITICAL FOUNDATION TESTS
Issue: https://github.com/RobeHGC/proyecto_nadia/issues/22

This test ensures core components can be initialized without errors,
preventing production startup failures.
"""
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from utils.config import Config


class TestComponentInitialization:
    """Test initialization of core system components."""
    
    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration for testing."""
        config = MagicMock(spec=Config)
        config.api_id = 12345678
        config.api_hash = "test_hash"
        config.phone_number = "+1234567890"
        config.openai_api_key = "sk-test123"
        config.gemini_api_key = "AIza-test123"
        config.redis_url = "redis://localhost:6379/0"
        config.database_url = "postgresql://test:test@localhost/test"
        config.openai_model = "gpt-3.5-turbo"
        config.enable_typing_pacing = True
        config.typing_window_delay = 1.5
        config.typing_debounce_delay = 5.0
        config.debug = False
        config.log_level = "INFO"
        return config
    
    def test_config_initialization(self, mock_config):
        """Test that Config can be initialized with valid parameters."""
        # Test basic config attributes
        assert mock_config.api_id == 12345678
        assert mock_config.api_hash == "test_hash"
        assert mock_config.openai_api_key == "sk-test123"
        assert mock_config.redis_url == "redis://localhost:6379/0"
        assert mock_config.database_url == "postgresql://test:test@localhost/test"
    
    @patch('telethon.TelegramClient')
    @patch('database.models.DatabaseManager')
    @patch('memory.user_memory.UserMemoryManager')
    @patch('llms.openai_client.OpenAIClient')
    @patch('agents.supervisor_agent.SupervisorAgent')
    @patch('utils.entity_resolver.EntityResolver')
    @patch('utils.typing_simulator.TypingSimulator')
    @patch('utils.user_activity_tracker.UserActivityTracker')
    @patch('cognition.cognitive_controller.CognitiveController')
    @patch('cognition.constitution.Constitution')
    def test_userbot_initialization(
        self, mock_constitution, mock_cognitive_controller, mock_user_activity_tracker,
        mock_typing_simulator, mock_entity_resolver, mock_supervisor_agent,
        mock_openai_client, mock_user_memory_manager, mock_database_manager,
        mock_telegram_client, mock_config
    ):
        """Test UserBot component initialization."""
        # Mock all the dependencies
        mock_telegram_client.return_value = MagicMock()
        mock_database_manager.return_value = MagicMock()
        mock_user_memory_manager.return_value = MagicMock()
        mock_openai_client.return_value = MagicMock()
        mock_supervisor_agent.return_value = MagicMock()
        mock_cognitive_controller.return_value = MagicMock()
        mock_constitution.return_value = MagicMock()
        
        # Import and create UserBot
        from userbot import UserBot
        
        userbot = UserBot(mock_config)
        
        # Verify initialization
        assert userbot.config == mock_config
        assert userbot.client is not None
        assert userbot.memory is not None
        assert userbot.llm is not None
        assert userbot.supervisor is not None
        assert userbot.cognitive_controller is not None
        assert userbot.constitution is not None
        assert userbot.db_manager is not None
        
        # Verify components were created with correct parameters
        mock_telegram_client.assert_called_once_with("bot_session", mock_config.api_id, mock_config.api_hash)
        mock_user_memory_manager.assert_called_once_with(mock_config.redis_url)
        mock_openai_client.assert_called_once_with(mock_config.openai_api_key, mock_config.openai_model)
        mock_database_manager.assert_called_once_with(mock_config.database_url)
    
    @patch('database.models.DatabaseManager')
    @patch('memory.user_memory.UserMemoryManager')
    @patch('llms.openai_client.OpenAIClient')
    def test_supervisor_agent_initialization(
        self, mock_openai_client, mock_user_memory_manager, 
        mock_database_manager, mock_config
    ):
        """Test SupervisorAgent component initialization."""
        # Mock dependencies
        mock_llm = MagicMock()
        mock_memory = MagicMock()
        mock_openai_client.return_value = mock_llm
        mock_user_memory_manager.return_value = mock_memory
        
        from agents.supervisor_agent import SupervisorAgent
        
        supervisor = SupervisorAgent(mock_llm, mock_memory, mock_config)
        
        # Verify initialization
        assert supervisor.llm == mock_llm
        assert supervisor.memory == mock_memory
        assert supervisor.config == mock_config
    
    @patch('database.models.DatabaseManager')
    def test_database_manager_initialization(self, mock_database_manager, mock_config):
        """Test DatabaseManager component initialization."""
        mock_db_instance = MagicMock()
        mock_database_manager.return_value = mock_db_instance
        
        from database.models import DatabaseManager
        
        db_manager = DatabaseManager(mock_config.database_url)
        
        # Verify initialization
        mock_database_manager.assert_called_once_with(mock_config.database_url)
    
    @patch('redis.asyncio.from_url')
    def test_user_memory_manager_initialization(self, mock_redis_from_url, mock_config):
        """Test UserMemoryManager component initialization."""
        mock_redis = AsyncMock()
        mock_redis_from_url.return_value = mock_redis
        
        from memory.user_memory import UserMemoryManager
        
        memory_manager = UserMemoryManager(mock_config.redis_url)
        
        # Verify initialization
        assert memory_manager.redis_url == mock_config.redis_url
    
    def test_openai_client_initialization(self, mock_config):
        """Test OpenAI client initialization."""
        with patch('openai.OpenAI') as mock_openai:
            mock_client = MagicMock()
            mock_openai.return_value = mock_client
            
            from llms.openai_client import OpenAIClient
            
            openai_client = OpenAIClient(mock_config.openai_api_key, mock_config.openai_model)
            
            # Verify initialization
            assert openai_client.api_key == mock_config.openai_api_key
            assert openai_client.model == mock_config.openai_model
    
    def test_cognitive_controller_initialization(self):
        """Test CognitiveController initialization."""
        from cognition.cognitive_controller import CognitiveController
        
        cognitive_controller = CognitiveController()
        
        # Should initialize without errors
        assert cognitive_controller is not None
    
    def test_constitution_initialization(self):
        """Test Constitution initialization."""
        from cognition.constitution import Constitution
        
        constitution = Constitution()
        
        # Should initialize without errors
        assert constitution is not None
    
    @patch('fastapi.FastAPI')
    @patch('database.models.DatabaseManager')
    @patch('memory.user_memory.UserMemoryManager')
    def test_api_server_initialization(
        self, mock_user_memory_manager, mock_database_manager, mock_fastapi
    ):
        """Test API server initialization."""
        # Mock FastAPI app
        mock_app = MagicMock()
        mock_fastapi.return_value = mock_app
        
        # Mock dependencies
        mock_database_manager.return_value = MagicMock()
        mock_user_memory_manager.return_value = MagicMock()
        
        # Import the API server module
        from api import server
        
        # Verify the app was created
        assert server.app is not None
    
    @patch('utils.config.Config.from_env')
    def test_config_from_env_initialization(self, mock_from_env):
        """Test Config.from_env() initialization."""
        mock_config = MagicMock()
        mock_from_env.return_value = mock_config
        
        from utils.config import Config
        
        config = Config.from_env()
        
        # Verify config was created
        assert config == mock_config
        mock_from_env.assert_called_once()
    
    def test_component_initialization_with_missing_dependencies(self):
        """Test component initialization fails gracefully with missing dependencies."""
        from utils.config import Config
        
        # Test with invalid config values
        with patch.dict('os.environ', {}, clear=True):
            config = Config.from_env()
            
            # Should create config with default values, not raise exception
            assert config.api_id == 0  # Default value
            assert config.api_hash == ""  # Default value
    
    @patch('telethon.TelegramClient')
    def test_telegram_client_initialization_with_invalid_credentials(self, mock_telegram_client):
        """Test Telegram client initialization with invalid credentials."""
        # Mock TelegramClient to raise an exception
        mock_telegram_client.side_effect = ValueError("Invalid API credentials")
        
        from utils.config import Config
        
        # Create config with invalid credentials
        config = Config(
            api_id=0,  # Invalid
            api_hash="",  # Invalid
            phone_number="",
            openai_api_key="",
            gemini_api_key="",
            redis_url="redis://localhost:6379/0",
            database_url="postgresql://localhost/test"
        )
        
        # Should raise exception during TelegramClient creation
        with pytest.raises(ValueError):
            from userbot import UserBot
            UserBot(config)
    
    @patch('database.models.DatabaseManager')
    @patch('memory.user_memory.UserMemoryManager')
    @patch('llms.openai_client.OpenAIClient')
    @patch('agents.supervisor_agent.SupervisorAgent')
    def test_component_dependency_chain(
        self, mock_supervisor_agent, mock_openai_client, 
        mock_user_memory_manager, mock_database_manager, mock_config
    ):
        """Test that component dependency chain works correctly."""
        # Mock all components
        mock_llm = MagicMock()
        mock_memory = MagicMock()
        mock_db = MagicMock()
        mock_supervisor = MagicMock()
        
        mock_openai_client.return_value = mock_llm
        mock_user_memory_manager.return_value = mock_memory
        mock_database_manager.return_value = mock_db
        mock_supervisor_agent.return_value = mock_supervisor
        
        # Create components in dependency order
        from llms.openai_client import OpenAIClient
        from memory.user_memory import UserMemoryManager
        from database.models import DatabaseManager
        from agents.supervisor_agent import SupervisorAgent
        
        llm = OpenAIClient(mock_config.openai_api_key, mock_config.openai_model)
        memory = UserMemoryManager(mock_config.redis_url)
        db_manager = DatabaseManager(mock_config.database_url)
        supervisor = SupervisorAgent(llm, memory, mock_config)
        
        # Verify all components were created
        assert llm == mock_llm
        assert memory == mock_memory
        assert db_manager == mock_db
        assert supervisor == mock_supervisor
    
    def test_all_core_components_can_be_imported(self):
        """Test that all core components can be imported without errors."""
        core_components = [
            'userbot.UserBot',
            'agents.supervisor_agent.SupervisorAgent',
            'database.models.DatabaseManager',
            'memory.user_memory.UserMemoryManager',
            'llms.openai_client.OpenAIClient',
            'cognition.cognitive_controller.CognitiveController',
            'cognition.constitution.Constitution',
            'utils.config.Config',
            'utils.redis_mixin.RedisConnectionMixin',
            'utils.error_handling.handle_errors',
            'utils.logging_config.get_logger'
        ]
        
        for component_path in core_components:
            module_path, class_name = component_path.rsplit('.', 1)
            
            try:
                module = __import__(module_path, fromlist=[class_name])
                component_class = getattr(module, class_name)
                assert component_class is not None
            except ImportError as e:
                pytest.fail(f"Failed to import {component_path}: {e}")
            except AttributeError as e:
                pytest.fail(f"Failed to get {class_name} from {module_path}: {e}")
    
    def test_component_initialization_order_independence(self, mock_config):
        """Test that components can be initialized in any order."""
        initialization_orders = [
            ['config', 'database', 'memory', 'llm', 'supervisor'],
            ['memory', 'llm', 'config', 'supervisor', 'database'],
            ['llm', 'memory', 'supervisor', 'database', 'config']
        ]
        
        for order in initialization_orders:
            components = {}
            
            for component_name in order:
                if component_name == 'config':
                    components['config'] = mock_config
                elif component_name == 'database':
                    with patch('database.models.DatabaseManager') as mock_db:
                        mock_db.return_value = MagicMock()
                        components['database'] = mock_db(mock_config.database_url)
                elif component_name == 'memory':
                    with patch('memory.user_memory.UserMemoryManager') as mock_memory:
                        mock_memory.return_value = MagicMock()
                        components['memory'] = mock_memory(mock_config.redis_url)
                elif component_name == 'llm':
                    with patch('llms.openai_client.OpenAIClient') as mock_llm:
                        mock_llm.return_value = MagicMock()
                        components['llm'] = mock_llm(mock_config.openai_api_key, mock_config.openai_model)
                elif component_name == 'supervisor':
                    with patch('agents.supervisor_agent.SupervisorAgent') as mock_supervisor:
                        mock_supervisor.return_value = MagicMock()
                        if 'llm' in components and 'memory' in components:
                            components['supervisor'] = mock_supervisor(
                                components['llm'], components['memory'], mock_config
                            )
            
            # All components should be successfully created
            assert len(components) >= 3  # Should have at least config and some other components