"""Critical imports test - prevents startup failures due to import errors.

EPIC 1: CRITICAL FOUNDATION TESTS
Issue: https://github.com/RobeHGC/proyecto_nadia/issues/22

This test ensures all core modules can be imported without errors,
preventing production startup failures.
"""
import pytest
import importlib
import sys
from typing import List


class TestCriticalImports:
    """Test that all critical modules can be imported successfully."""
    
    CRITICAL_MODULES = [
        # Main entry points
        "userbot",
        "api.server",
        
        # Core agents
        "agents.supervisor_agent",
        "agents.intermediary_agent", 
        "agents.post_llm2_agent",
        "agents.recovery_agent",
        "agents.types",
        
        # Database and storage
        "database.models",
        "memory.user_memory",
        
        # LLM providers
        "llms.openai_client",
        "llms.gemini_client",
        "llms.model_registry",
        "llms.dynamic_router",
        
        # Utilities
        "utils.config",
        "utils.constants",
        "utils.error_handling",
        "utils.logging_config",
        "utils.redis_mixin",
        "utils.protocol_manager",
        
        # Cognition system
        "cognition.cognitive_controller",
        "cognition.constitution",
    ]
    
    def test_userbot_imports(self):
        """Test that userbot.py can be imported without errors."""
        try:
            import userbot
            assert hasattr(userbot, 'UserBot'), "UserBot class not found in userbot module"
        except ImportError as e:
            pytest.fail(f"Failed to import userbot: {e}")
    
    def test_api_server_imports(self):
        """Test that api/server.py can be imported without errors."""
        try:
            from api import server
            assert hasattr(server, 'app'), "FastAPI app not found in api.server module"
        except ImportError as e:
            pytest.fail(f"Failed to import api.server: {e}")
    
    @pytest.mark.parametrize("module_name", CRITICAL_MODULES)
    def test_critical_module_import(self, module_name: str):
        """Test that each critical module can be imported."""
        try:
            importlib.import_module(module_name)
        except ImportError as e:
            pytest.fail(f"Failed to import critical module '{module_name}': {e}")
    
    def test_all_critical_imports_at_once(self):
        """Test importing all critical modules in sequence to catch dependency issues."""
        failed_imports = []
        
        for module_name in self.CRITICAL_MODULES:
            try:
                importlib.import_module(module_name)
            except ImportError as e:
                failed_imports.append(f"{module_name}: {str(e)}")
        
        if failed_imports:
            error_msg = "The following critical modules failed to import:\n" + "\n".join(failed_imports)
            pytest.fail(error_msg)
    
    def test_dependency_chain_integrity(self):
        """Test that core dependency chains are intact."""
        dependency_chains = [
            # UserBot dependency chain
            ["utils.config", "database.models", "agents.supervisor_agent", "userbot"],
            # API server dependency chain  
            ["utils.config", "database.models", "api.server"],
            # LLM provider chain
            ["llms.model_registry", "llms.dynamic_router", "agents.supervisor_agent"],
        ]
        
        for chain in dependency_chains:
            for module_name in chain:
                try:
                    importlib.import_module(module_name)
                except ImportError as e:
                    pytest.fail(f"Dependency chain broken at '{module_name}': {e}")
    
    def test_no_circular_imports(self):
        """Test that there are no circular import issues."""
        # Store initial modules
        initial_modules = set(sys.modules.keys())
        
        # Import all critical modules
        for module_name in self.CRITICAL_MODULES:
            try:
                importlib.import_module(module_name)
            except ImportError as e:
                # Only fail on circular import errors
                if "circular import" in str(e).lower():
                    pytest.fail(f"Circular import detected in '{module_name}': {e}")
        
        # Clean up - remove newly imported modules
        current_modules = set(sys.modules.keys())
        new_modules = current_modules - initial_modules
        for module_name in new_modules:
            if module_name.startswith(('agents.', 'api.', 'database.', 'memory.', 'llms.', 'utils.', 'cognition.')):
                sys.modules.pop(module_name, None)