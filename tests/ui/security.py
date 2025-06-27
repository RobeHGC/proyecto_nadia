"""
Security and Input Validation for UI Testing

Provides input validation, path sanitization, rate limiting, and security controls
for the UI testing framework to prevent abuse and ensure safe operation.
"""
import os
import re
import time
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, Set, List
from dataclasses import dataclass, field
from collections import defaultdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class SecurityConfig:
    """Security configuration for UI testing."""
    
    # Path validation
    allowed_screenshot_dirs: Set[str] = field(default_factory=lambda: {
        'tests/ui/screenshots/baseline',
        'tests/ui/screenshots/current', 
        'tests/ui/screenshots/diff'
    })
    max_filename_length: int = 255
    allowed_file_extensions: Set[str] = field(default_factory=lambda: {'.png', '.jpg', '.jpeg'})
    
    # URL validation
    allowed_domains: Set[str] = field(default_factory=lambda: {
        'localhost',
        '127.0.0.1',
        '0.0.0.0'
    })
    allowed_schemes: Set[str] = field(default_factory=lambda: {'http', 'https'})
    
    # Rate limiting
    max_mcp_calls_per_minute: int = 60
    max_screenshots_per_minute: int = 30
    max_navigation_per_minute: int = 20
    
    # Input size limits
    max_selector_length: int = 1000
    max_script_length: int = 10000
    max_text_input_length: int = 5000
    
    # Sensitive data patterns
    sensitive_patterns: List[str] = field(default_factory=lambda: [
        r'password\s*[:=]\s*[\'"][^\'"]+[\'"]',
        r'api[_-]?key\s*[:=]\s*[\'"][^\'"]+[\'"]',
        r'secret\s*[:=]\s*[\'"][^\'"]+[\'"]',
        r'token\s*[:=]\s*[\'"][^\'"]+[\'"]',
    ])


class PathValidator:
    """Validates and sanitizes file paths for security."""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.project_root = Path(__file__).parent.parent.parent
    
    def validate_screenshot_path(self, path: str) -> str:
        """
        Validate and sanitize screenshot file path.
        
        Args:
            path: File path to validate
            
        Returns:
            Sanitized absolute path
            
        Raises:
            ValueError: If path is invalid or unsafe
        """
        # Convert to Path object
        path_obj = Path(path)
        
        # Check filename length
        if len(path_obj.name) > self.config.max_filename_length:
            raise ValueError(f"Filename too long: {len(path_obj.name)} > {self.config.max_filename_length}")
        
        # Check file extension
        if path_obj.suffix.lower() not in self.config.allowed_file_extensions:
            raise ValueError(f"Invalid file extension: {path_obj.suffix}")
        
        # Sanitize filename
        safe_name = self._sanitize_filename(path_obj.name)
        
        # If path is relative, resolve against project root
        if not path_obj.is_absolute():
            path_obj = self.project_root / path_obj.parent / safe_name
        else:
            path_obj = path_obj.parent / safe_name
        
        # Resolve to absolute path
        abs_path = path_obj.resolve()
        
        # Check that resolved path is within allowed directories
        path_str = str(abs_path)
        allowed = False
        
        for allowed_dir in self.config.allowed_screenshot_dirs:
            allowed_abs = (self.project_root / allowed_dir).resolve()
            if path_str.startswith(str(allowed_abs)):
                allowed = True
                break
        
        if not allowed:
            raise ValueError(f"Path not in allowed directories: {path_str}")
        
        # Check for path traversal attempts
        if '..' in path_obj.parts:
            raise ValueError("Path traversal detected")
        
        return str(abs_path)
    
    def _sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename to prevent malicious names.
        
        Args:
            filename: Original filename
            
        Returns:
            Sanitized filename
        """
        # Remove or replace dangerous characters
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        
        # Remove control characters
        filename = re.sub(r'[\x00-\x1f\x7f]', '', filename)
        
        # Ensure filename doesn't start with dot or dash
        filename = re.sub(r'^[.-]+', '', filename)
        
        # Limit length
        if len(filename) > self.config.max_filename_length:
            name, ext = os.path.splitext(filename)
            max_name_len = self.config.max_filename_length - len(ext)
            filename = name[:max_name_len] + ext
        
        return filename


class URLValidator:
    """Validates URLs for security."""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
    
    def validate_url(self, url: str) -> str:
        """
        Validate URL for security.
        
        Args:
            url: URL to validate
            
        Returns:
            Validated URL
            
        Raises:
            ValueError: If URL is invalid or unsafe
        """
        from urllib.parse import urlparse
        
        if not url:
            raise ValueError("URL cannot be empty")
        
        if len(url) > 2048:  # RFC 2616 recommendation
            raise ValueError("URL too long")
        
        try:
            parsed = urlparse(url)
        except Exception as e:
            raise ValueError(f"Invalid URL format: {e}")
        
        # Check scheme
        if parsed.scheme not in self.config.allowed_schemes:
            raise ValueError(f"Scheme not allowed: {parsed.scheme}")
        
        # Check domain (for localhost testing)
        if parsed.hostname:
            # Allow localhost variants and configured domains
            allowed = (
                parsed.hostname in self.config.allowed_domains or
                parsed.hostname.endswith('.localhost') or
                self._is_local_ip(parsed.hostname)
            )
            
            if not allowed:
                raise ValueError(f"Domain not allowed: {parsed.hostname}")
        
        return url
    
    def _is_local_ip(self, hostname: str) -> bool:
        """Check if hostname is a local IP address."""
        import ipaddress
        try:
            ip = ipaddress.ip_address(hostname)
            return ip.is_loopback or ip.is_private
        except ValueError:
            return False


class InputValidator:
    """Validates input parameters for MCP calls."""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
    
    def validate_selector(self, selector: str) -> str:
        """
        Validate CSS selector.
        
        Args:
            selector: CSS selector to validate
            
        Returns:
            Validated selector
            
        Raises:
            ValueError: If selector is invalid
        """
        if not selector or not selector.strip():
            raise ValueError("Selector cannot be empty")
        
        if len(selector) > self.config.max_selector_length:
            raise ValueError(f"Selector too long: {len(selector)} > {self.config.max_selector_length}")
        
        # Check for potentially dangerous patterns
        dangerous_patterns = [
            r'javascript:',
            r'data:',
            r'<script',
            r'</script>',
            r'onclick\s*=',
            r'onerror\s*=',
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, selector, re.IGNORECASE):
                raise ValueError(f"Dangerous pattern detected in selector: {pattern}")
        
        return selector.strip()
    
    def validate_script(self, script: str) -> str:
        """
        Validate JavaScript code.
        
        Args:
            script: JavaScript code to validate
            
        Returns:
            Validated script
            
        Raises:
            ValueError: If script is invalid or dangerous
        """
        if not script or not script.strip():
            raise ValueError("Script cannot be empty")
        
        if len(script) > self.config.max_script_length:
            raise ValueError(f"Script too long: {len(script)} > {self.config.max_script_length}")
        
        # Check for potentially dangerous patterns
        dangerous_patterns = [
            r'fetch\s*\(',
            r'XMLHttpRequest',
            r'document\.cookie',
            r'localStorage',
            r'sessionStorage',
            r'eval\s*\(',
            r'Function\s*\(',
            r'setTimeout\s*\(',
            r'setInterval\s*\(',
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, script, re.IGNORECASE):
                logger.warning(f"Potentially dangerous pattern in script: {pattern}")
                # Don't reject, but log the warning
        
        return script.strip()
    
    def validate_text_input(self, text: str) -> str:
        """
        Validate text input.
        
        Args:
            text: Text to validate
            
        Returns:
            Validated text
            
        Raises:
            ValueError: If text is invalid
        """
        if text is None:
            text = ""
        
        if len(text) > self.config.max_text_input_length:
            raise ValueError(f"Text input too long: {len(text)} > {self.config.max_text_input_length}")
        
        # Check for sensitive data patterns
        for pattern in self.config.sensitive_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                logger.warning("Potential sensitive data detected in text input")
                # Redact the text for logging
                redacted_text = re.sub(pattern, '[REDACTED]', text, flags=re.IGNORECASE)
                logger.warning(f"Redacted text: {redacted_text}")
        
        return text


class RateLimiter:
    """Rate limiting for MCP operations."""
    
    def __init__(self, config: SecurityConfig):
        self.config = config
        self.call_history: Dict[str, List[float]] = defaultdict(list)
        self.limits = {
            'mcp_call': config.max_mcp_calls_per_minute,
            'screenshot': config.max_screenshots_per_minute,
            'navigation': config.max_navigation_per_minute,
        }
    
    def check_rate_limit(self, operation_type: str) -> bool:
        """
        Check if operation is within rate limits.
        
        Args:
            operation_type: Type of operation (mcp_call, screenshot, navigation)
            
        Returns:
            True if within limits, False otherwise
        """
        current_time = time.time()
        minute_ago = current_time - 60
        
        # Clean old entries
        self.call_history[operation_type] = [
            timestamp for timestamp in self.call_history[operation_type] 
            if timestamp > minute_ago
        ]
        
        # Check limit
        limit = self.limits.get(operation_type, float('inf'))
        current_count = len(self.call_history[operation_type])
        
        if current_count >= limit:
            logger.warning(f"Rate limit exceeded for {operation_type}: {current_count}/{limit} per minute")
            return False
        
        # Record this call
        self.call_history[operation_type].append(current_time)
        return True
    
    def get_rate_limit_status(self) -> Dict[str, Dict[str, int]]:
        """Get current rate limit status for all operation types."""
        current_time = time.time()
        minute_ago = current_time - 60
        
        status = {}
        for op_type, limit in self.limits.items():
            # Clean old entries
            recent_calls = [
                timestamp for timestamp in self.call_history[op_type]
                if timestamp > minute_ago
            ]
            
            status[op_type] = {
                'current': len(recent_calls),
                'limit': limit,
                'remaining': max(0, limit - len(recent_calls))
            }
        
        return status


class SecurityManager:
    """Main security manager that orchestrates all security components."""
    
    def __init__(self, config: Optional[SecurityConfig] = None):
        self.config = config or SecurityConfig()
        self.path_validator = PathValidator(self.config)
        self.url_validator = URLValidator(self.config)
        self.input_validator = InputValidator(self.config)
        self.rate_limiter = RateLimiter(self.config)
    
    def validate_mcp_params(self, tool_name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate parameters for MCP tool calls.
        
        Args:
            tool_name: Name of the MCP tool
            params: Parameters to validate
            
        Returns:
            Validated parameters
            
        Raises:
            ValueError: If parameters are invalid
            RuntimeError: If rate limit exceeded
        """
        # Check rate limits
        if not self.rate_limiter.check_rate_limit('mcp_call'):
            raise RuntimeError("MCP call rate limit exceeded")
        
        validated_params = params.copy()
        
        # Tool-specific validation
        if tool_name == 'puppeteer_navigate':
            if 'url' in params:
                validated_params['url'] = self.url_validator.validate_url(params['url'])
                if not self.rate_limiter.check_rate_limit('navigation'):
                    raise RuntimeError("Navigation rate limit exceeded")
        
        elif tool_name == 'puppeteer_screenshot':
            if 'name' in params:
                # Validate screenshot filename
                screenshot_path = f"tests/ui/screenshots/current/{params['name']}.png"
                validated_params['name'] = Path(self.path_validator.validate_screenshot_path(screenshot_path)).stem
            if not self.rate_limiter.check_rate_limit('screenshot'):
                raise RuntimeError("Screenshot rate limit exceeded")
        
        elif tool_name == 'puppeteer_click':
            if 'selector' in params:
                validated_params['selector'] = self.input_validator.validate_selector(params['selector'])
        
        elif tool_name == 'puppeteer_fill':
            if 'selector' in params:
                validated_params['selector'] = self.input_validator.validate_selector(params['selector'])
            if 'value' in params:
                validated_params['value'] = self.input_validator.validate_text_input(params['value'])
        
        elif tool_name == 'puppeteer_evaluate':
            if 'script' in params:
                validated_params['script'] = self.input_validator.validate_script(params['script'])
        
        return validated_params
    
    def get_security_status(self) -> Dict[str, Any]:
        """Get current security status and metrics."""
        return {
            'rate_limits': self.rate_limiter.get_rate_limit_status(),
            'config': {
                'max_mcp_calls_per_minute': self.config.max_mcp_calls_per_minute,
                'max_screenshots_per_minute': self.config.max_screenshots_per_minute,
                'max_navigation_per_minute': self.config.max_navigation_per_minute,
            }
        }


# Global security manager instance
_security_manager: Optional[SecurityManager] = None

def get_security_manager() -> SecurityManager:
    """Get the global security manager instance."""
    global _security_manager
    if _security_manager is None:
        _security_manager = SecurityManager()
    return _security_manager

def set_security_manager(manager: SecurityManager):
    """Set the global security manager instance."""
    global _security_manager
    _security_manager = manager