# utils/recovery_config.py
"""Configuration management for Recovery Agent."""
import os
from dataclasses import dataclass
from typing import Dict, Any, Optional, List


@dataclass
class RecoveryConfig:
    """Configuration settings for the Recovery Agent."""
    
    # Core functionality
    enabled: bool = True
    startup_check_enabled: bool = True
    
    # Message processing limits
    max_message_age_hours: int = 12  # Messages older than this are skipped
    max_messages_per_user: int = 100  # Max messages to recover per user per session
    max_users_per_startup_check: int = 50  # Max users to check during startup
    max_concurrent_users: int = 5  # Max users processed concurrently
    
    # Rate limiting (Telegram API compliance)
    telegram_rate_limit: int = 30  # Max requests per second to Telegram API
    batch_processing_delay: float = 2.0  # Default delay between batch messages
    
    # Recovery operation timeouts
    user_recovery_timeout_minutes: int = 10  # Max time per user recovery
    startup_recovery_timeout_minutes: int = 30  # Max time for full startup recovery
    
    # Batch size configurations
    tier1_batch_size: int = 5  # High priority batch size (<2h messages)
    tier2_batch_size: int = 10  # Medium priority batch size (2-12h messages)  
    tier3_batch_size: int = 20  # Low priority batch size (12-24h messages)
    
    # Processing delays by priority tier
    tier1_delay_seconds: float = 0.5  # Fast processing for recent messages
    tier2_delay_seconds: float = 2.0  # Medium delay for older messages
    tier3_delay_seconds: float = 5.0  # Slow processing for old messages
    
    # Monitoring and alerting
    enable_recovery_metrics: bool = True
    alert_on_high_recovery_count: int = 50  # Alert if more than X messages recovered
    alert_on_recovery_errors: int = 5  # Alert if more than X errors during recovery
    
    # Integration settings
    integrate_with_protocol_silence: bool = True  # Check quarantine status before recovery
    preserve_message_order: bool = True  # Maintain chronological order during recovery
    add_temporal_context: bool = True  # Add time-gap context to recovered messages
    
    @classmethod
    def from_environment(cls) -> 'RecoveryConfig':
        """Create configuration from environment variables."""
        return cls(
            enabled=os.getenv('RECOVERY_ENABLED', 'true').lower() == 'true',
            startup_check_enabled=os.getenv('RECOVERY_STARTUP_CHECK', 'true').lower() == 'true',
            
            max_message_age_hours=int(os.getenv('RECOVERY_MAX_AGE_HOURS', '12')),
            max_messages_per_user=int(os.getenv('RECOVERY_MAX_PER_USER', '100')),
            max_users_per_startup_check=int(os.getenv('RECOVERY_MAX_USERS_STARTUP', '50')),
            max_concurrent_users=int(os.getenv('RECOVERY_MAX_CONCURRENT', '5')),
            
            telegram_rate_limit=int(os.getenv('TELEGRAM_RECOVERY_RATE_LIMIT', '30')),
            batch_processing_delay=float(os.getenv('RECOVERY_BATCH_DELAY', '2.0')),
            
            user_recovery_timeout_minutes=int(os.getenv('RECOVERY_USER_TIMEOUT_MIN', '10')),
            startup_recovery_timeout_minutes=int(os.getenv('RECOVERY_STARTUP_TIMEOUT_MIN', '30')),
            
            tier1_batch_size=int(os.getenv('RECOVERY_TIER1_BATCH_SIZE', '5')),
            tier2_batch_size=int(os.getenv('RECOVERY_TIER2_BATCH_SIZE', '10')),
            tier3_batch_size=int(os.getenv('RECOVERY_TIER3_BATCH_SIZE', '20')),
            
            tier1_delay_seconds=float(os.getenv('RECOVERY_TIER1_DELAY', '0.5')),
            tier2_delay_seconds=float(os.getenv('RECOVERY_TIER2_DELAY', '2.0')),
            tier3_delay_seconds=float(os.getenv('RECOVERY_TIER3_DELAY', '5.0')),
            
            enable_recovery_metrics=os.getenv('RECOVERY_ENABLE_METRICS', 'true').lower() == 'true',
            alert_on_high_recovery_count=int(os.getenv('RECOVERY_ALERT_HIGH_COUNT', '50')),
            alert_on_recovery_errors=int(os.getenv('RECOVERY_ALERT_ERROR_COUNT', '5')),
            
            integrate_with_protocol_silence=os.getenv('RECOVERY_INTEGRATE_PROTOCOL', 'true').lower() == 'true',
            preserve_message_order=os.getenv('RECOVERY_PRESERVE_ORDER', 'true').lower() == 'true',
            add_temporal_context=os.getenv('RECOVERY_ADD_TEMPORAL_CONTEXT', 'true').lower() == 'true'
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary for API responses."""
        return {
            'enabled': self.enabled,
            'startup_check_enabled': self.startup_check_enabled,
            'limits': {
                'max_message_age_hours': self.max_message_age_hours,
                'max_messages_per_user': self.max_messages_per_user,
                'max_users_per_startup_check': self.max_users_per_startup_check,
                'max_concurrent_users': self.max_concurrent_users
            },
            'rate_limiting': {
                'telegram_rate_limit': self.telegram_rate_limit,
                'batch_processing_delay': self.batch_processing_delay
            },
            'timeouts': {
                'user_recovery_timeout_minutes': self.user_recovery_timeout_minutes,
                'startup_recovery_timeout_minutes': self.startup_recovery_timeout_minutes
            },
            'batch_processing': {
                'tier1_batch_size': self.tier1_batch_size,
                'tier2_batch_size': self.tier2_batch_size,
                'tier3_batch_size': self.tier3_batch_size,
                'tier1_delay_seconds': self.tier1_delay_seconds,
                'tier2_delay_seconds': self.tier2_delay_seconds,
                'tier3_delay_seconds': self.tier3_delay_seconds
            },
            'monitoring': {
                'enable_recovery_metrics': self.enable_recovery_metrics,
                'alert_on_high_recovery_count': self.alert_on_high_recovery_count,
                'alert_on_recovery_errors': self.alert_on_recovery_errors
            },
            'integration': {
                'integrate_with_protocol_silence': self.integrate_with_protocol_silence,
                'preserve_message_order': self.preserve_message_order,
                'add_temporal_context': self.add_temporal_context
            }
        }
    
    def validate(self) -> List[str]:
        """Validate configuration and return list of validation errors."""
        errors = []
        
        # Check positive values
        if self.max_message_age_hours <= 0:
            errors.append("max_message_age_hours must be positive")
        
        if self.max_messages_per_user <= 0:
            errors.append("max_messages_per_user must be positive")
        
        if self.max_concurrent_users <= 0:
            errors.append("max_concurrent_users must be positive")
            
        if self.telegram_rate_limit <= 0:
            errors.append("telegram_rate_limit must be positive")
        
        # Check reasonable limits
        if self.max_message_age_hours > 168:  # 1 week
            errors.append("max_message_age_hours should not exceed 168 hours (1 week)")
        
        if self.telegram_rate_limit > 30:
            errors.append("telegram_rate_limit should not exceed 30 requests/second")
        
        if self.max_concurrent_users > 20:
            errors.append("max_concurrent_users should not exceed 20 for system stability")
        
        # Check batch sizes are reasonable
        if self.tier1_batch_size > 20:
            errors.append("tier1_batch_size should not exceed 20 for responsive processing")
        
        # Check delays are reasonable
        if self.tier1_delay_seconds < 0.1:
            errors.append("tier1_delay_seconds should be at least 0.1 seconds")
        
        if self.tier3_delay_seconds > 30:
            errors.append("tier3_delay_seconds should not exceed 30 seconds")
        
        return errors
    
    def get_tier_config(self, tier: str) -> Dict[str, Any]:
        """Get configuration for a specific processing tier."""
        tier_configs = {
            'TIER_1': {
                'batch_size': self.tier1_batch_size,
                'delay_seconds': self.tier1_delay_seconds,
                'priority': 'high',
                'description': 'Recent messages (<2h) - fast processing'
            },
            'TIER_2': {
                'batch_size': self.tier2_batch_size,
                'delay_seconds': self.tier2_delay_seconds,
                'priority': 'medium',
                'description': 'Medium age messages (2-6h) - normal processing'
            },
            'TIER_3': {
                'batch_size': self.tier3_batch_size,
                'delay_seconds': self.tier3_delay_seconds,
                'priority': 'low',
                'description': 'Older messages (6-12h) - slow processing'
            }
        }
        
        return tier_configs.get(tier, {})
    
    def __str__(self) -> str:
        """String representation for logging."""
        return (f"RecoveryConfig(enabled={self.enabled}, "
                f"max_age={self.max_message_age_hours}h, "
                f"max_per_user={self.max_messages_per_user}, "
                f"rate_limit={self.telegram_rate_limit}/s)")


# Default configuration instance
DEFAULT_RECOVERY_CONFIG = RecoveryConfig()


def get_recovery_config() -> RecoveryConfig:
    """Get recovery configuration from environment or defaults."""
    try:
        config = RecoveryConfig.from_environment()
        
        # Validate configuration
        validation_errors = config.validate()
        if validation_errors:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Recovery configuration validation errors: {validation_errors}")
            logger.warning("Using default configuration")
            return DEFAULT_RECOVERY_CONFIG
        
        return config
        
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error loading recovery configuration: {e}")
        logger.info("Using default recovery configuration")
        return DEFAULT_RECOVERY_CONFIG