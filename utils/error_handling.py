# utils/error_handling.py
"""Error handling utilities to reduce duplication."""
import functools
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


def handle_errors(default: Any = None, action: str = "operation", log_level: int = logging.ERROR):
    """
    Decorator to handle exceptions with consistent logging.
    
    Args:
        default: Default value to return on error
        action: Description of the action for logging
        log_level: Logging level for the error
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.log(log_level, f"Error in {action}: {e}")
                return default
        
        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.log(log_level, f"Error in {action}: {e}")
                return default
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator


# Import asyncio at the end to avoid circular imports
import asyncio