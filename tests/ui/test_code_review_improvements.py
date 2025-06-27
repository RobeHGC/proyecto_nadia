"""
Test Code Review Improvements for UI Testing Framework

Validates the implementation of high-priority improvements suggested in the code review:
1. Configuration management
2. Retry mechanisms  
3. Input validation and security
"""
import pytest
import asyncio
import os
from pathlib import Path
from tests.ui.config import UITestConfig, get_config, EnvironmentConfig
from tests.ui.retry_utils import retry_async, UIRetryConfigs, RetryableError
from tests.ui.security import SecurityManager, get_security_manager
from tests.ui.mcp_adapter import PuppeteerMCPAdapter, MCPResult


class TestConfigurationManagement:
    """Test configuration management system."""
    
    def test_default_configuration(self):
        """Test default configuration values."""
        config = UITestConfig()
        
        # Test default values
        assert config.default_timeout == 30000
        assert config.headless is True
        assert config.viewport_width == 1280
        assert config.viewport_height == 720
        assert config.visual_tolerance == 0.1
        
        # Test validation
        assert 0.0 <= config.visual_tolerance <= 1.0
        assert config.default_timeout > 0
        assert config.viewport_width > 0
        assert config.viewport_height > 0
    
    def test_environment_configuration(self):
        """Test environment-specific configurations."""
        # Test CI configuration
        ci_config = EnvironmentConfig.ci()
        assert ci_config.ci_mode is True
        assert ci_config.headless is True
        assert ci_config.visual_tolerance >= 0.15  # More tolerant in CI
        
        # Test development configuration
        dev_config = EnvironmentConfig.development()
        assert dev_config.environment in ['development', 'ci']  # May inherit from CI env
    
    def test_configuration_validation(self):
        """Test configuration validation."""
        # Test invalid timeout
        with pytest.raises(ValueError, match="timeout must be positive"):
            UITestConfig(default_timeout=-1)
        
        # Test invalid visual tolerance
        with pytest.raises(ValueError, match="visual_tolerance must be between"):
            UITestConfig(visual_tolerance=1.5)
        
        # Test invalid viewport
        with pytest.raises(ValueError, match="Viewport dimensions must be positive"):
            UITestConfig(viewport_width=-100)
    
    def test_browser_options_generation(self):
        """Test browser options generation."""
        config = UITestConfig(headless=True)
        options = config.get_browser_options()
        
        assert 'headless' in options
        assert 'defaultViewport' in options
        assert 'timeout' in options
        assert options['headless'] is True
    
    def test_screenshot_paths(self):
        """Test screenshot path configuration."""
        config = UITestConfig()
        paths = config.get_screenshot_paths()
        
        assert 'baseline' in paths
        assert 'current' in paths
        assert 'diff' in paths
        
        # Verify directories are created
        for path in paths.values():
            assert Path(path).exists()


class TestRetryMechanisms:
    """Test retry mechanisms for flaky tests."""
    
    @pytest.mark.asyncio
    async def test_basic_retry_success(self):
        """Test successful retry after failure."""
        call_count = 0
        
        @retry_async(UIRetryConfigs.mcp_call())
        async def flaky_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RetryableError("Simulated failure")
            return "success"
        
        result = await flaky_function()
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_retry_configuration(self):
        """Test different retry configurations."""
        # Test MCP call configuration
        mcp_config = UIRetryConfigs.mcp_call()
        assert mcp_config.max_attempts == 3
        assert mcp_config.base_delay == 1.0
        
        # Test screenshot configuration
        screenshot_config = UIRetryConfigs.screenshot()
        assert screenshot_config.max_attempts == 3
        assert screenshot_config.base_delay == 2.0
        
        # Test navigation configuration
        nav_config = UIRetryConfigs.navigation()
        assert nav_config.max_attempts == 3
        assert nav_config.base_delay == 2.0
    
    @pytest.mark.asyncio
    async def test_non_retryable_error(self):
        """Test that non-retryable errors are not retried."""
        call_count = 0
        
        @retry_async(UIRetryConfigs.mcp_call())
        async def function_with_assertion_error():
            nonlocal call_count
            call_count += 1
            raise AssertionError("Test assertion failure")
        
        with pytest.raises(AssertionError):
            await function_with_assertion_error()
        
        # Should only be called once (no retries for AssertionError)
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_max_attempts_exceeded(self):
        """Test behavior when max attempts are exceeded."""
        call_count = 0
        
        @retry_async(UIRetryConfigs.mcp_call())
        async def always_fails():
            nonlocal call_count
            call_count += 1
            raise RetryableError("Always fails")
        
        with pytest.raises(RetryableError):
            await always_fails()
        
        # Should be called max_attempts times
        assert call_count == 3


class TestSecurityValidation:
    """Test security and input validation."""
    
    def test_security_manager_initialization(self):
        """Test security manager initialization."""
        security_manager = SecurityManager()
        assert security_manager is not None
        assert security_manager.config is not None
        assert security_manager.path_validator is not None
        assert security_manager.url_validator is not None
        assert security_manager.input_validator is not None
        assert security_manager.rate_limiter is not None
    
    def test_url_validation(self):
        """Test URL validation."""
        security_manager = get_security_manager()
        
        # Valid URLs
        valid_urls = [
            "http://localhost:8000",
            "https://127.0.0.1:3000",
            "http://0.0.0.0:8080"
        ]
        
        for url in valid_urls:
            params = security_manager.validate_mcp_params("puppeteer_navigate", {"url": url})
            assert params["url"] == url
        
        # Invalid URLs
        with pytest.raises((ValueError, RuntimeError)):
            security_manager.validate_mcp_params("puppeteer_navigate", {"url": "javascript:alert(1)"})
        
        with pytest.raises((ValueError, RuntimeError)):
            security_manager.validate_mcp_params("puppeteer_navigate", {"url": "http://malicious.com"})
    
    def test_selector_validation(self):
        """Test CSS selector validation."""
        security_manager = get_security_manager()
        
        # Valid selectors
        valid_selectors = [
            "body",
            ".class-name",
            "#element-id",
            "div.container",
            "input[type='text']"
        ]
        
        for selector in valid_selectors:
            params = security_manager.validate_mcp_params("puppeteer_click", {"selector": selector})
            assert params["selector"] == selector
        
        # Invalid selectors
        with pytest.raises((ValueError, RuntimeError)):
            security_manager.validate_mcp_params("puppeteer_click", {"selector": "javascript:alert(1)"})
        
        with pytest.raises((ValueError, RuntimeError)):
            security_manager.validate_mcp_params("puppeteer_click", {"selector": "<script>alert(1)</script>"})
    
    def test_screenshot_path_validation(self):
        """Test screenshot path validation."""
        security_manager = get_security_manager()
        
        # Valid screenshot names
        valid_names = [
            "test_screenshot",
            "dashboard_load",
            "component_test_123"
        ]
        
        for name in valid_names:
            params = security_manager.validate_mcp_params("puppeteer_screenshot", {"name": name})
            assert params["name"] == name
        
        # Invalid names (path traversal attempts)
        with pytest.raises((ValueError, RuntimeError)):
            security_manager.validate_mcp_params("puppeteer_screenshot", {"name": "../../../etc/passwd"})
    
    def test_rate_limiting(self):
        """Test rate limiting functionality."""
        security_manager = get_security_manager()
        
        # Should allow normal operations
        for _ in range(5):
            params = security_manager.validate_mcp_params("puppeteer_click", {"selector": "body"})
            assert params["selector"] == "body"
        
        # Get rate limit status
        status = security_manager.get_security_status()
        assert 'rate_limits' in status
        assert 'mcp_call' in status['rate_limits']
    
    def test_text_input_validation(self):
        """Test text input validation and sensitive data detection."""
        security_manager = get_security_manager()
        
        # Normal text input
        params = security_manager.validate_mcp_params("puppeteer_fill", {
            "selector": "input",
            "value": "normal text input"
        })
        assert params["value"] == "normal text input"
        
        # Long text input should be rejected
        long_text = "x" * 10000
        with pytest.raises((ValueError, RuntimeError)):
            security_manager.validate_mcp_params("puppeteer_fill", {
                "selector": "input",
                "value": long_text
            })


class TestMCPAdapterImprovements:
    """Test MCP adapter improvements."""
    
    def test_adapter_initialization_with_config(self):
        """Test adapter initialization with configuration."""
        config = UITestConfig()
        security_manager = SecurityManager()
        
        adapter = PuppeteerMCPAdapter(config=config, security_manager=security_manager)
        
        assert adapter.config == config
        assert adapter.security_manager == security_manager
        assert adapter._launch_options is not None
    
    @pytest.mark.asyncio
    async def test_adapter_with_retry_mechanisms(self):
        """Test that adapter methods have retry decorators."""
        config = UITestConfig()
        adapter = PuppeteerMCPAdapter(config=config)
        
        # Test that methods have retry decorators by checking they're wrapped
        assert hasattr(adapter.navigate, '__wrapped__')
        assert hasattr(adapter.screenshot, '__wrapped__')
        assert hasattr(adapter.click, '__wrapped__')
        assert hasattr(adapter.fill, '__wrapped__')
        assert hasattr(adapter.evaluate, '__wrapped__')
    
    @pytest.mark.asyncio
    async def test_security_validation_in_adapter(self):
        """Test that adapter validates parameters through security manager."""
        config = UITestConfig()
        adapter = PuppeteerMCPAdapter(config=config)
        
        # Test with invalid URL (should fail validation)
        result = await adapter.navigate("javascript:alert(1)")
        assert not result.success
        assert any(keyword in result.error.lower() for keyword in ["validation", "scheme", "not allowed"])
        
        # Test with invalid selector (should fail validation)
        result = await adapter.click("<script>alert(1)</script>")
        assert not result.success
        assert any(keyword in result.error.lower() for keyword in ["validation", "dangerous", "pattern"])


class TestIntegrationImprovements:
    """Test integration of all improvements together."""
    
    @pytest.mark.asyncio
    async def test_end_to_end_improved_workflow(self):
        """Test complete workflow with all improvements."""
        # Use CI configuration for more tolerant settings
        config = EnvironmentConfig.ci()
        security_manager = SecurityManager()
        adapter = PuppeteerMCPAdapter(config=config, security_manager=security_manager)
        
        # Test navigation with validation and retry
        result = await adapter.navigate("http://localhost:8000")
        assert result.success  # Should work with mock implementation
        
        # Test screenshot with validation
        result = await adapter.screenshot("integration_test")
        assert result.success
        
        # Test security status
        status = security_manager.get_security_status()
        assert status is not None
        assert 'rate_limits' in status
    
    def test_configuration_environment_integration(self):
        """Test configuration works with different environments."""
        # Set environment variables
        os.environ['UI_TEST_TIMEOUT'] = '45000'
        os.environ['VISUAL_TOLERANCE'] = '0.2'
        
        # Create new config instance
        config = UITestConfig()
        
        # Should pick up environment variables
        assert config.default_timeout == 45000
        assert config.visual_tolerance == 0.2
        
        # Clean up
        os.environ.pop('UI_TEST_TIMEOUT', None)
        os.environ.pop('VISUAL_TOLERANCE', None)
    
    def test_backward_compatibility(self):
        """Test that improvements maintain backward compatibility."""
        # Test that existing BrowserConfig still works
        from tests.ui.conftest import BrowserConfig
        
        browser_config = BrowserConfig()
        assert browser_config.headless is True
        assert browser_config.timeout == 30000
        
        # Test conversion from UITestConfig
        ui_config = UITestConfig()
        browser_config = BrowserConfig.from_ui_config(ui_config)
        assert browser_config.viewport == ui_config.get_viewport()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])