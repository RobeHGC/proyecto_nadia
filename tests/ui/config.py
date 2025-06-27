"""
UI Testing Configuration Management

Centralized configuration for UI testing framework with environment-based settings,
validation, and type safety.
"""
import os
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from pathlib import Path


@dataclass
class UITestConfig:
    """
    Centralized configuration for UI testing framework.
    
    All settings can be overridden via environment variables for different environments
    (development, staging, production, CI/CD).
    """
    
    # Browser Configuration
    default_timeout: int = field(default_factory=lambda: int(os.getenv('UI_TEST_TIMEOUT', 30000)))
    headless: bool = field(default_factory=lambda: os.getenv('UI_TEST_HEADLESS', 'true').lower() == 'true')
    viewport_width: int = field(default_factory=lambda: int(os.getenv('UI_VIEWPORT_WIDTH', 1280)))
    viewport_height: int = field(default_factory=lambda: int(os.getenv('UI_VIEWPORT_HEIGHT', 720)))
    
    # Dashboard Configuration  
    dashboard_url: str = field(default_factory=lambda: os.getenv('DASHBOARD_URL', 'http://localhost:8000'))
    dashboard_api_key: str = field(default_factory=lambda: os.getenv('DASHBOARD_API_KEY', 'miclavesegura45mil'))
    
    # Visual Regression Configuration
    visual_tolerance: float = field(default_factory=lambda: float(os.getenv('VISUAL_TOLERANCE', 0.1)))
    screenshot_base_path: str = field(default_factory=lambda: os.getenv('SCREENSHOT_PATH', 'tests/ui/screenshots'))
    baseline_update_mode: bool = field(default_factory=lambda: os.getenv('UPDATE_BASELINES', 'false').lower() == 'true')
    
    # Performance Configuration
    max_page_load_time: int = field(default_factory=lambda: int(os.getenv('MAX_PAGE_LOAD_TIME', 3000)))  # ms
    max_interaction_time: int = field(default_factory=lambda: int(os.getenv('MAX_INTERACTION_TIME', 1000)))  # ms
    
    # MCP Configuration
    mcp_timeout: int = field(default_factory=lambda: int(os.getenv('MCP_TIMEOUT', 10000)))  # ms
    mcp_retry_attempts: int = field(default_factory=lambda: int(os.getenv('MCP_RETRY_ATTEMPTS', 3)))
    mcp_retry_delay: float = field(default_factory=lambda: float(os.getenv('MCP_RETRY_DELAY', 1.0)))  # seconds
    
    # Test Execution Configuration  
    test_parallel: bool = field(default_factory=lambda: os.getenv('UI_TEST_PARALLEL', 'false').lower() == 'true')
    test_max_workers: int = field(default_factory=lambda: int(os.getenv('UI_TEST_MAX_WORKERS', 4)))
    test_verbose: bool = field(default_factory=lambda: os.getenv('UI_TEST_VERBOSE', 'false').lower() == 'true')
    
    # Environment Detection
    environment: str = field(default_factory=lambda: os.getenv('TEST_ENV', 'development'))
    ci_mode: bool = field(default_factory=lambda: os.getenv('CI', 'false').lower() == 'true')
    
    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate_config()
        self._setup_directories()
    
    def _validate_config(self):
        """Validate configuration values and ranges."""
        # Timeout validations
        if self.default_timeout <= 0:
            raise ValueError(f"default_timeout must be positive, got {self.default_timeout}")
        if self.mcp_timeout <= 0:
            raise ValueError(f"mcp_timeout must be positive, got {self.mcp_timeout}")
        
        # Viewport validations
        if self.viewport_width <= 0 or self.viewport_height <= 0:
            raise ValueError(f"Viewport dimensions must be positive: {self.viewport_width}x{self.viewport_height}")
        
        # Visual tolerance validation
        if not 0.0 <= self.visual_tolerance <= 1.0:
            raise ValueError(f"visual_tolerance must be between 0.0 and 1.0, got {self.visual_tolerance}")
        
        # Retry attempts validation
        if self.mcp_retry_attempts < 0:
            raise ValueError(f"mcp_retry_attempts must be non-negative, got {self.mcp_retry_attempts}")
        
        # URL validation
        if not self.dashboard_url.startswith(('http://', 'https://')):
            raise ValueError(f"dashboard_url must be a valid URL, got {self.dashboard_url}")
    
    def _setup_directories(self):
        """Ensure required directories exist."""
        base_path = Path(self.screenshot_base_path)
        for subdir in ['baseline', 'current', 'diff']:
            (base_path / subdir).mkdir(parents=True, exist_ok=True)
    
    def get_viewport(self) -> Dict[str, int]:
        """Get viewport configuration as dictionary."""
        return {
            'width': self.viewport_width,
            'height': self.viewport_height
        }
    
    def get_screenshot_paths(self) -> Dict[str, str]:
        """Get screenshot directory paths."""
        base_path = Path(self.screenshot_base_path)
        return {
            'baseline': str(base_path / 'baseline'),
            'current': str(base_path / 'current'),
            'diff': str(base_path / 'diff')
        }
    
    def get_browser_options(self) -> Dict[str, Any]:
        """Get browser launch options."""
        options = {
            'headless': self.headless,
            'defaultViewport': self.get_viewport(),
            'timeout': self.default_timeout
        }
        
        # Add CI-specific options
        if self.ci_mode:
            options['args'] = [
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-extensions',
                '--no-first-run'
            ]
        elif self.headless:
            options['args'] = ['--no-sandbox', '--disable-dev-shm-usage']
        
        return options
    
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == 'development'
    
    def is_ci(self) -> bool:
        """Check if running in CI environment."""
        return self.ci_mode
    
    def get_performance_thresholds(self) -> Dict[str, int]:
        """Get performance testing thresholds."""
        return {
            'page_load': self.max_page_load_time,
            'interaction': self.max_interaction_time
        }
    
    def get_retry_config(self) -> Dict[str, Any]:
        """Get retry configuration for MCP calls."""
        return {
            'attempts': self.mcp_retry_attempts,
            'delay': self.mcp_retry_delay,
            'timeout': self.mcp_timeout
        }
    
    @classmethod
    def for_environment(cls, env: str) -> 'UITestConfig':
        """
        Create configuration for specific environment.
        
        Args:
            env: Environment name (development, staging, production, ci)
        """
        # Set environment-specific defaults
        env_overrides = {
            'ci': {
                'TEST_ENV': 'ci',
                'CI': 'true',
                'UI_TEST_HEADLESS': 'true',
                'UI_TEST_TIMEOUT': '45000',  # Longer timeout for CI
                'VISUAL_TOLERANCE': '0.15',  # More tolerant in CI
                'MCP_RETRY_ATTEMPTS': '5'    # More retries in CI
            },
            'staging': {
                'TEST_ENV': 'staging',
                'DASHBOARD_URL': 'https://staging-dashboard.example.com',
                'VISUAL_TOLERANCE': '0.05'   # Stricter in staging
            },
            'production': {
                'TEST_ENV': 'production',
                'DASHBOARD_URL': 'https://dashboard.example.com',
                'VISUAL_TOLERANCE': '0.02',  # Very strict in production
                'UI_TEST_HEADLESS': 'true'
            }
        }
        
        # Apply environment overrides
        if env in env_overrides:
            for key, value in env_overrides[env].items():
                os.environ[key] = value
        
        return cls()
    
    def __str__(self) -> str:
        """String representation of configuration."""
        return f"UITestConfig(env={self.environment}, headless={self.headless}, timeout={self.default_timeout}ms)"


# Global configuration instance
_config_instance: Optional[UITestConfig] = None

def get_config() -> UITestConfig:
    """
    Get the global UI test configuration instance.
    
    Returns:
        UITestConfig: The configuration instance
    """
    global _config_instance
    if _config_instance is None:
        _config_instance = UITestConfig()
    return _config_instance

def set_config(config: UITestConfig):
    """
    Set the global UI test configuration instance.
    
    Args:
        config: The configuration instance to use
    """
    global _config_instance
    _config_instance = config

def reset_config():
    """Reset the global configuration instance."""
    global _config_instance
    _config_instance = None


# Environment-specific configurations
class EnvironmentConfig:
    """Pre-configured settings for different environments."""
    
    @staticmethod
    def development() -> UITestConfig:
        """Development environment configuration."""
        return UITestConfig.for_environment('development')
    
    @staticmethod
    def ci() -> UITestConfig:
        """CI environment configuration."""
        return UITestConfig.for_environment('ci')
    
    @staticmethod
    def staging() -> UITestConfig:
        """Staging environment configuration."""
        return UITestConfig.for_environment('staging')
    
    @staticmethod
    def production() -> UITestConfig:
        """Production environment configuration."""
        return UITestConfig.for_environment('production')


# Configuration validation utilities
def validate_environment():
    """Validate that the current environment is properly configured."""
    config = get_config()
    
    # Check required environment variables
    required_vars = ['DASHBOARD_URL']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        raise EnvironmentError(f"Missing required environment variables: {missing_vars}")
    
    # Validate configuration
    try:
        config._validate_config()
    except ValueError as e:
        raise EnvironmentError(f"Invalid configuration: {e}")
    
    return True