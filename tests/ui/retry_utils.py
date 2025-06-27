"""
Retry Utilities for UI Testing

Provides robust retry mechanisms for flaky UI tests with exponential backoff,
conditional retry logic, and comprehensive error handling.
"""
import asyncio
import time
import logging
from typing import Callable, Any, Optional, List, Type, Union
from functools import wraps
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class RetryStrategy(Enum):
    """Retry strategy types."""
    LINEAR = "linear"           # Fixed delay between retries
    EXPONENTIAL = "exponential" # Exponential backoff
    FIBONACCI = "fibonacci"     # Fibonacci sequence delays


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0        # seconds
    max_delay: float = 30.0        # seconds
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    backoff_factor: float = 2.0
    jitter: bool = True            # Add randomness to prevent thundering herd
    
    # Exception handling
    retryable_exceptions: List[Type[Exception]] = None
    non_retryable_exceptions: List[Type[Exception]] = None
    
    def __post_init__(self):
        if self.retryable_exceptions is None:
            self.retryable_exceptions = [
                ConnectionError,
                TimeoutError,
                OSError,
                asyncio.TimeoutError
            ]
        
        if self.non_retryable_exceptions is None:
            self.non_retryable_exceptions = [
                ValueError,
                TypeError,
                AttributeError,
                AssertionError  # Don't retry test assertions
            ]


class RetryableError(Exception):
    """Exception that indicates an operation should be retried."""
    pass


class NonRetryableError(Exception):
    """Exception that indicates an operation should not be retried."""
    pass


def calculate_delay(attempt: int, config: RetryConfig) -> float:
    """
    Calculate delay for next retry attempt.
    
    Args:
        attempt: Current attempt number (0-based)
        config: Retry configuration
        
    Returns:
        Delay in seconds
    """
    if config.strategy == RetryStrategy.LINEAR:
        delay = config.base_delay
    elif config.strategy == RetryStrategy.EXPONENTIAL:
        delay = config.base_delay * (config.backoff_factor ** attempt)
    elif config.strategy == RetryStrategy.FIBONACCI:
        # Generate fibonacci sequence for delays
        if attempt <= 1:
            delay = config.base_delay
        else:
            fib_a, fib_b = 1, 1
            for _ in range(attempt - 1):
                fib_a, fib_b = fib_b, fib_a + fib_b
            delay = config.base_delay * fib_b
    else:
        delay = config.base_delay
    
    # Apply max delay limit
    delay = min(delay, config.max_delay)
    
    # Add jitter to prevent thundering herd
    if config.jitter:
        import random
        jitter_factor = random.uniform(0.8, 1.2)
        delay *= jitter_factor
    
    return delay


def should_retry(exception: Exception, config: RetryConfig) -> bool:
    """
    Determine if an exception should trigger a retry.
    
    Args:
        exception: The exception that occurred
        config: Retry configuration
        
    Returns:
        True if should retry, False otherwise
    """
    # Check non-retryable exceptions first
    if any(isinstance(exception, exc_type) for exc_type in config.non_retryable_exceptions):
        return False
    
    # Check retryable exceptions
    if any(isinstance(exception, exc_type) for exc_type in config.retryable_exceptions):
        return True
    
    # Check for specific retry indicators
    if isinstance(exception, RetryableError):
        return True
    
    if isinstance(exception, NonRetryableError):
        return False
    
    # Default: don't retry unknown exceptions
    return False


def retry_async(config: Optional[RetryConfig] = None):
    """
    Decorator for async functions that provides retry functionality.
    
    Args:
        config: Retry configuration. If None, uses default configuration.
        
    Usage:
        @retry_async(RetryConfig(max_attempts=3, base_delay=1.0))
        async def flaky_function():
            # Function that might fail
            pass
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    logger.debug(f"Attempting {func.__name__} (attempt {attempt + 1}/{config.max_attempts})")
                    result = await func(*args, **kwargs)
                    
                    if attempt > 0:
                        logger.info(f"{func.__name__} succeeded on attempt {attempt + 1}")
                    
                    return result
                    
                except Exception as e:
                    last_exception = e
                    
                    # Check if we should retry
                    if not should_retry(e, config):
                        logger.error(f"{func.__name__} failed with non-retryable error: {e}")
                        raise e
                    
                    # Check if we have more attempts
                    if attempt >= config.max_attempts - 1:
                        logger.error(f"{func.__name__} failed after {config.max_attempts} attempts")
                        break
                    
                    # Calculate delay and wait
                    delay = calculate_delay(attempt, config)
                    logger.warning(f"{func.__name__} failed (attempt {attempt + 1}): {e}. Retrying in {delay:.2f}s")
                    
                    await asyncio.sleep(delay)
            
            # All attempts failed
            raise last_exception
        
        return wrapper
    return decorator


def retry_sync(config: Optional[RetryConfig] = None):
    """
    Decorator for sync functions that provides retry functionality.
    
    Args:
        config: Retry configuration. If None, uses default configuration.
    """
    if config is None:
        config = RetryConfig()
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(config.max_attempts):
                try:
                    logger.debug(f"Attempting {func.__name__} (attempt {attempt + 1}/{config.max_attempts})")
                    result = func(*args, **kwargs)
                    
                    if attempt > 0:
                        logger.info(f"{func.__name__} succeeded on attempt {attempt + 1}")
                    
                    return result
                    
                except Exception as e:
                    last_exception = e
                    
                    # Check if we should retry
                    if not should_retry(e, config):
                        logger.error(f"{func.__name__} failed with non-retryable error: {e}")
                        raise e
                    
                    # Check if we have more attempts
                    if attempt >= config.max_attempts - 1:
                        logger.error(f"{func.__name__} failed after {config.max_attempts} attempts")
                        break
                    
                    # Calculate delay and wait
                    delay = calculate_delay(attempt, config)
                    logger.warning(f"{func.__name__} failed (attempt {attempt + 1}): {e}. Retrying in {delay:.2f}s")
                    
                    time.sleep(delay)
            
            # All attempts failed
            raise last_exception
        
        return wrapper
    return decorator


# Specialized retry configurations for common UI testing scenarios

class UIRetryConfigs:
    """Pre-configured retry settings for common UI testing scenarios."""
    
    @staticmethod
    def mcp_call() -> RetryConfig:
        """Retry configuration for MCP tool calls."""
        return RetryConfig(
            max_attempts=3,
            base_delay=1.0,
            strategy=RetryStrategy.EXPONENTIAL,
            retryable_exceptions=[
                ConnectionError,
                TimeoutError,
                OSError,
                asyncio.TimeoutError,
                RetryableError
            ]
        )
    
    @staticmethod
    def element_wait() -> RetryConfig:
        """Retry configuration for waiting for elements."""
        return RetryConfig(
            max_attempts=5,
            base_delay=0.5,
            max_delay=5.0,
            strategy=RetryStrategy.LINEAR,
            retryable_exceptions=[
                TimeoutError,
                RetryableError
            ]
        )
    
    @staticmethod
    def screenshot() -> RetryConfig:
        """Retry configuration for screenshot operations."""
        return RetryConfig(
            max_attempts=3,
            base_delay=2.0,
            strategy=RetryStrategy.EXPONENTIAL,
            retryable_exceptions=[
                ConnectionError,
                OSError,
                RetryableError
            ]
        )
    
    @staticmethod
    def navigation() -> RetryConfig:
        """Retry configuration for page navigation."""
        return RetryConfig(
            max_attempts=3,
            base_delay=2.0,
            strategy=RetryStrategy.EXPONENTIAL,
            retryable_exceptions=[
                ConnectionError,
                TimeoutError,
                OSError,
                RetryableError
            ]
        )
    
    @staticmethod
    def ci_tolerant() -> RetryConfig:
        """More tolerant retry configuration for CI environments."""
        return RetryConfig(
            max_attempts=5,
            base_delay=2.0,
            max_delay=60.0,
            strategy=RetryStrategy.EXPONENTIAL,
            backoff_factor=1.5,  # Slower backoff
            jitter=True
        )


# Context managers for temporary retry behavior

class retry_context:
    """
    Context manager for temporary retry behavior.
    
    Usage:
        async with retry_context(UIRetryConfigs.mcp_call()):
            result = await some_flaky_operation()
    """
    
    def __init__(self, config: RetryConfig):
        self.config = config
        self.original_config = None
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
    
    async def execute(self, func: Callable, *args, **kwargs):
        """Execute a function with retry logic."""
        @retry_async(self.config)
        async def wrapper():
            return await func(*args, **kwargs)
        
        return await wrapper()


# Utility functions for test frameworks

async def retry_until_success(
    func: Callable,
    condition: Optional[Callable[[Any], bool]] = None,
    config: Optional[RetryConfig] = None,
    *args, **kwargs
) -> Any:
    """
    Retry a function until it succeeds or meets a condition.
    
    Args:
        func: Function to retry
        condition: Optional condition function to check result
        config: Retry configuration
        *args, **kwargs: Arguments to pass to func
        
    Returns:
        Function result when successful
    """
    if config is None:
        config = RetryConfig()
    
    @retry_async(config)
    async def wrapper():
        result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
        
        if condition and not condition(result):
            raise RetryableError(f"Condition not met for {func.__name__}")
        
        return result
    
    return await wrapper()


def create_element_wait_retry(selector: str, timeout: int = 30000) -> RetryConfig:
    """
    Create a retry configuration specifically for element waiting.
    
    Args:
        selector: CSS selector being waited for
        timeout: Total timeout in milliseconds
        
    Returns:
        Configured retry config
    """
    # Calculate attempts based on timeout
    base_delay = 0.5
    max_attempts = min(int(timeout / (base_delay * 1000)), 10)
    
    return RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        strategy=RetryStrategy.LINEAR,
        retryable_exceptions=[TimeoutError, RetryableError]
    )