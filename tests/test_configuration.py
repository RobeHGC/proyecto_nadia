"""Configuration validation tests - prevents startup failures due to invalid config.

EPIC 1: CRITICAL FOUNDATION TESTS
Issue: https://github.com/RobeHGC/proyecto_nadia/issues/22

This test ensures configuration validation catches errors before they cause
production startup failures.
"""
import os
import pytest
from unittest.mock import patch
from utils.config import Config


class TestConfigurationValidation:
    """Test configuration validation and environment variable handling."""
    
    REQUIRED_ENV_VARS = [
        "API_ID",
        "API_HASH", 
        "PHONE_NUMBER",
        "OPENAI_API_KEY",
        "GEMINI_API_KEY",
        "DATABASE_URL",
        "REDIS_URL"
    ]
    
    VALID_ENV_VARS = {
        "API_ID": "12345678",
        "API_HASH": "abcdef1234567890abcdef1234567890",
        "PHONE_NUMBER": "+1234567890",
        "OPENAI_API_KEY": "sk-test1234567890abcdef",
        "GEMINI_API_KEY": "AIzaTest1234567890",
        "DATABASE_URL": "postgresql://user:pass@localhost/nadia_hitl_test",
        "REDIS_URL": "redis://localhost:6379/1",
        "LLM_PROFILE": "default"
    }
    
    def test_valid_configuration_creation(self):
        """Test that Config.from_env() works with valid environment variables."""
        with patch.dict(os.environ, self.VALID_ENV_VARS, clear=False):
            config = Config.from_env()
            
            assert config.api_id == 12345678
            assert config.api_hash == "abcdef1234567890abcdef1234567890"
            assert config.phone_number == "+1234567890"
            assert config.openai_api_key == "sk-test1234567890abcdef"
            assert config.gemini_api_key == "AIzaTest1234567890"
            assert config.database_url == "postgresql://user:pass@localhost/nadia_hitl_test"
            assert config.redis_url == "redis://localhost:6379/1"
    
    def test_api_id_validation(self):
        """Test API_ID validation - must be valid integer."""
        invalid_api_ids = ["", "not_a_number", "0", "-123", "12.34"]
        
        for invalid_id in invalid_api_ids:
            env_vars = self.VALID_ENV_VARS.copy()
            env_vars["API_ID"] = invalid_id
            
            with patch.dict(os.environ, env_vars, clear=False):
                if invalid_id in ["", "not_a_number", "12.34"]:
                    with pytest.raises(ValueError):
                        Config.from_env()
                else:
                    # For "0" and "-123", config is created but invalid
                    config = Config.from_env()
                    assert config.api_id in [0, -123]
    
    def test_missing_required_environment_variables(self):
        """Test behavior when required environment variables are missing."""
        # Test with completely empty environment
        with patch.dict(os.environ, {}, clear=True):
            config = Config.from_env()
            
            # Should use default values, which may be invalid
            assert config.api_id == 0  # Default from int(os.getenv("API_ID", "0"))
            assert config.api_hash == ""
            assert config.phone_number == ""
            assert config.openai_api_key == ""
            assert config.gemini_api_key == ""
    
    @pytest.mark.parametrize("missing_var", REQUIRED_ENV_VARS)
    def test_missing_individual_environment_variables(self, missing_var):
        """Test behavior when individual required environment variables are missing."""
        env_vars = self.VALID_ENV_VARS.copy()
        del env_vars[missing_var]
        
        with patch.dict(os.environ, env_vars, clear=True):
            config = Config.from_env()
            
            # Check that the missing variable gets default value
            if missing_var == "API_ID":
                assert config.api_id == 0
            elif missing_var == "DATABASE_URL":
                assert config.database_url == "postgresql://localhost/nadia_hitl"  # Default value
            elif missing_var == "REDIS_URL":
                assert config.redis_url == "redis://localhost:6379/0"  # Default value
            else:
                attr_name = missing_var.lower()
                assert getattr(config, attr_name) == ""
    
    def test_environment_variable_comment_cleaning(self):
        """Test that comments are properly removed from environment variables."""
        env_vars_with_comments = {
            "TYPING_WINDOW_DELAY": "2.5 # Custom delay",
            "MIN_BATCH_SIZE": "3 # Minimum batch size for testing",
            "MAX_BATCH_WAIT_TIME": "45.0 # Maximum wait time in seconds"
        }
        
        with patch.dict(os.environ, {**self.VALID_ENV_VARS, **env_vars_with_comments}, clear=False):
            config = Config.from_env()
            
            assert config.typing_window_delay == 2.5
            assert config.min_batch_size == 3
            assert config.max_batch_wait_time == 45.0
    
    def test_boolean_environment_variable_parsing(self):
        """Test boolean environment variable parsing."""
        boolean_test_cases = [
            ("true", True),
            ("True", True), 
            ("TRUE", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("", False),
            ("1", False),  # Only "true" values are True
            ("yes", False)
        ]
        
        for env_value, expected in boolean_test_cases:
            env_vars = self.VALID_ENV_VARS.copy()
            env_vars["ENABLE_TYPING_PACING"] = env_value
            env_vars["DEBUG"] = env_value
            
            with patch.dict(os.environ, env_vars, clear=False):
                config = Config.from_env()
                assert config.enable_typing_pacing == expected
                assert config.debug == expected
    
    def test_numeric_environment_variable_parsing(self):
        """Test numeric environment variable parsing with edge cases."""
        numeric_test_cases = [
            ("API_PORT", "8080", 8080),
            ("API_PORT", "0", 0),
            ("ENTITY_CACHE_SIZE", "1000", 1000),
            ("TYPING_WINDOW_DELAY", "1.5", 1.5),
            ("TYPING_WINDOW_DELAY", "0.1", 0.1)
        ]
        
        for env_var, env_value, expected in numeric_test_cases:
            env_vars = self.VALID_ENV_VARS.copy()
            env_vars[env_var] = env_value
            
            with patch.dict(os.environ, env_vars, clear=False):
                config = Config.from_env()
                attr_name = env_var.lower()
                assert getattr(config, attr_name) == expected
    
    def test_profile_validation(self):
        """Test LLM profile validation."""
        with patch.dict(os.environ, self.VALID_ENV_VARS, clear=False):
            config = Config.from_env()
            
            # Test profile validation (may return False if model registry has issues)
            # This should not raise an exception
            is_valid = config.validate_profile()
            assert isinstance(is_valid, bool)
    
    def test_get_profile_models(self):
        """Test getting profile models configuration."""
        with patch.dict(os.environ, self.VALID_ENV_VARS, clear=False):
            config = Config.from_env()
            
            # This should return a dictionary with model configuration
            models = config.get_profile_models()
            assert isinstance(models, dict)
            assert 'llm1' in models
            assert 'llm2' in models
            assert 'llm1_provider' in models
            assert 'llm2_provider' in models
    
    def test_invalid_numeric_values_raise_errors(self):
        """Test that invalid numeric values raise appropriate errors."""
        invalid_numeric_cases = [
            ("API_ID", "not_a_number"),
            ("API_PORT", "not_a_port"),
            ("ENTITY_CACHE_SIZE", "invalid"),
            ("TYPING_WINDOW_DELAY", "not_a_float")
        ]
        
        for env_var, invalid_value in invalid_numeric_cases:
            env_vars = self.VALID_ENV_VARS.copy()
            env_vars[env_var] = invalid_value
            
            with patch.dict(os.environ, env_vars, clear=False):
                with pytest.raises(ValueError):
                    Config.from_env()
    
    def test_configuration_defaults(self):
        """Test that configuration defaults are reasonable."""
        with patch.dict(os.environ, {}, clear=True):
            config = Config.from_env()
            
            # Check that defaults are reasonable
            assert config.redis_url == "redis://localhost:6379/0"
            assert config.database_url == "postgresql://localhost/nadia_hitl"
            assert config.llm_profile == "default"
            assert config.enable_typing_pacing is True
            assert config.debug is False
            assert config.log_level == "INFO"
            assert config.api_port == 8000
    
    def test_env_comment_cleaning_edge_cases(self):
        """Test edge cases in environment variable comment cleaning."""
        edge_cases = [
            ("1.5", "1.5"),  # No comment
            ("1.5 #", "1.5"),  # Empty comment
            ("1.5 # comment", "1.5"),  # Normal comment
            ("1.5#comment", "1.5"),  # No space before comment
            ("1.5 # comment # another", "1.5"),  # Multiple # symbols
            ("  1.5  # comment  ", "1.5"),  # Extra whitespace
        ]
        
        for input_value, expected_cleaned in edge_cases:
            cleaned = Config._clean_env_value(input_value)
            assert cleaned == expected_cleaned