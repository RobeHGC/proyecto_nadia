# utils/datetime_helpers.py
"""Consistent datetime formatting helpers."""
from datetime import datetime, timedelta
from typing import Union
import time


def now_iso() -> str:
    """Get current datetime in ISO format."""
    return datetime.now().isoformat()


def now_formatted() -> str:
    """Get current datetime in standard format."""
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def now_timestamp() -> float:
    """Get current Unix timestamp."""
    return time.time()


def format_datetime(dt: datetime, format_type: str = "iso") -> str:
    """
    Format datetime consistently.
    
    Args:
        dt: DateTime object to format
        format_type: "iso", "standard", or custom format string
    """
    if format_type == "iso":
        return dt.isoformat()
    elif format_type == "standard":
        return dt.strftime('%Y-%m-%d %H:%M:%S')
    else:
        # Assume custom format string
        return dt.strftime(format_type)


def time_ago_text(dt: datetime) -> str:
    """
    Generate human-readable 'time ago' text.
    
    Args:
        dt: DateTime to compare against now
        
    Returns:
        Human readable string like "2 hours ago", "Yesterday"
    """
    now = datetime.now()
    diff = now - dt
    
    if diff.days > 1:
        return f"{diff.days} days ago"
    elif diff.days == 1:
        return "Yesterday"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    else:
        return "Just now"


def parse_datetime(dt_string: str) -> datetime:
    """
    Parse datetime string in common formats.
    
    Args:
        dt_string: DateTime string in ISO or standard format
        
    Returns:
        Parsed datetime object
    """
    # Try ISO format first
    try:
        return datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
    except ValueError:
        pass
    
    # Try standard format
    try:
        return datetime.strptime(dt_string, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        pass
    
    # If all fails, raise error
    raise ValueError(f"Unable to parse datetime string: {dt_string}")