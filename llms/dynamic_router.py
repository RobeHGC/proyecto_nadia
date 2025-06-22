"""
Dynamic LLM Router for intelligent model selection and hot-swapping.
Manages model instantiation, profile switching, and automatic fallbacks.
"""
import logging
import threading
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime

from llms.base_client import BaseLLMClient
from llms.llm_factory import create_llm_client
from llms.model_registry import ModelRegistry, ProfileConfig, get_model_registry
from llms.quota_manager import GeminiQuotaManager

logger = logging.getLogger(__name__)

@dataclass
class RouterStats:
    """Statistics for the dynamic router."""
    current_profile: str
    profile_switches: int
    llm1_calls: int
    llm2_calls: int
    fallback_events: int
    last_switch_time: Optional[datetime]
    total_cost: float

class DynamicLLMRouter:
    """
    Dynamic router that manages LLM selection and hot-swapping.
    Supports profile switching without restarting the application.
    """
    
    def __init__(self, initial_profile: str = "default", config: Optional[Any] = None):
        """Initialize the dynamic router."""
        self.config = config
        self.registry = get_model_registry()
        
        # Initialize quota manager with Redis URL
        try:
            import os
            redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
            self.quota_manager = GeminiQuotaManager(redis_url)
        except Exception as e:
            logger.warning(f"Failed to initialize quota manager: {e}")
            self.quota_manager = None
        
        # Current state
        self._current_profile = initial_profile
        self._current_profile_config: Optional[ProfileConfig] = None
        self._llm1_client: Optional[BaseLLMClient] = None
        self._llm2_client: Optional[BaseLLMClient] = None
        
        # Threading and safety
        self._lock = threading.RLock()
        
        # Statistics
        self._stats = RouterStats(
            current_profile=initial_profile,
            profile_switches=0,
            llm1_calls=0,
            llm2_calls=0,
            fallback_events=0,
            last_switch_time=None,
            total_cost=0.0
        )
        
        # Initialize with profile
        self._initialize_profile(initial_profile)
    
    def _initialize_profile(self, profile_name: str) -> bool:
        """Initialize the router with a specific profile."""
        try:
            with self._lock:
                # Validate profile
                is_valid, error_msg = self.registry.validate_profile(profile_name)
                if not is_valid:
                    logger.error(f"Invalid profile '{profile_name}': {error_msg}")
                    return False
                
                # Get profile configuration
                profile_config = self.registry.get_profile(profile_name)
                if not profile_config:
                    logger.error(f"Failed to load profile configuration: {profile_name}")
                    return False
                
                # Store previous clients for cleanup
                old_llm1 = self._llm1_client
                old_llm2 = self._llm2_client
                
                # Create new LLM clients
                new_llm1 = self._create_llm_client(
                    profile_config.llm1_provider,
                    profile_config.llm1_config.model_id
                )
                
                new_llm2 = self._create_llm_client(
                    profile_config.llm2_provider,
                    profile_config.llm2_config.model_id
                )
                
                if not new_llm1 or not new_llm2:
                    logger.error(f"Failed to create LLM clients for profile '{profile_name}'")
                    return False
                
                # Update state
                self._current_profile = profile_name
                self._current_profile_config = profile_config
                self._llm1_client = new_llm1
                self._llm2_client = new_llm2
                
                # Update stats
                if self._stats.current_profile != profile_name:
                    self._stats.profile_switches += 1
                    self._stats.last_switch_time = datetime.now()
                    self._stats.current_profile = profile_name
                
                # Cleanup old clients (if any)
                if old_llm1:
                    self._cleanup_client(old_llm1)
                if old_llm2:
                    self._cleanup_client(old_llm2)
                
                logger.info(f"Successfully switched to profile: {profile_name}")
                logger.info(f"  LLM1: {profile_config.llm1_provider}/{profile_config.llm1_model}")
                logger.info(f"  LLM2: {profile_config.llm2_provider}/{profile_config.llm2_model}")
                
                return True
                
        except Exception as e:
            logger.error(f"Error initializing profile '{profile_name}': {e}")
            return False
    
    def _create_llm_client(self, provider: str, model_id: str) -> Optional[BaseLLMClient]:
        """Create an LLM client for the specified provider and model."""
        try:
            # Get API key based on provider
            api_key = self._get_api_key_for_provider(provider)
            if not api_key:
                logger.error(f"No API key available for provider: {provider}")
                return None
            
            # Create client using factory
            client = create_llm_client(
                provider=provider,
                model=model_id,
                api_key=api_key
            )
            
            if client:
                logger.debug(f"Created {provider} client for model: {model_id}")
            else:
                logger.error(f"Failed to create {provider} client for model: {model_id}")
            
            return client
            
        except Exception as e:
            logger.error(f"Error creating LLM client for {provider}/{model_id}: {e}")
            return None
    
    def _get_api_key_for_provider(self, provider: str) -> Optional[str]:
        """Get the appropriate API key for a provider."""
        if not self.config:
            logger.warning("No config available for API key lookup")
            return None
        
        if provider == "openai":
            return getattr(self.config, 'openai_api_key', None)
        elif provider == "gemini":
            return getattr(self.config, 'gemini_api_key', None)
        else:
            logger.warning(f"Unknown provider for API key: {provider}")
            return None
    
    def _cleanup_client(self, client: BaseLLMClient):
        """Cleanup an LLM client safely."""
        try:
            # Add any cleanup logic here if needed
            # For now, just log the cleanup
            logger.debug(f"Cleaning up LLM client: {type(client).__name__}")
        except Exception as e:
            logger.warning(f"Error during client cleanup: {e}")
    
    def select_llm1(self) -> Optional[BaseLLMClient]:
        """Get the LLM1 client (creative generation)."""
        with self._lock:
            if self._should_check_quota():
                # Check if we need to fallback due to quota limits
                if not self._check_llm1_quota():
                    logger.warning("LLM1 quota exceeded, attempting fallback")
                    if self._attempt_fallback():
                        self._stats.fallback_events += 1
            
            self._stats.llm1_calls += 1
            return self._llm1_client
    
    def select_llm2(self) -> Optional[BaseLLMClient]:
        """Get the LLM2 client (refinement)."""
        with self._lock:
            self._stats.llm2_calls += 1
            return self._llm2_client
    
    def switch_profile(self, profile_name: str) -> bool:
        """Switch to a different profile (hot-swap)."""
        with self._lock:
            if profile_name == self._current_profile:
                logger.info(f"Already using profile: {profile_name}")
                return True
            
            logger.info(f"Switching from profile '{self._current_profile}' to '{profile_name}'")
            return self._initialize_profile(profile_name)
    
    def get_current_profile(self) -> str:
        """Get the current active profile name."""
        return self._current_profile
    
    def get_current_profile_config(self) -> Optional[ProfileConfig]:
        """Get the current profile configuration."""
        return self._current_profile_config
    
    def get_available_profiles(self) -> Dict[str, Dict[str, Any]]:
        """Get all available profiles with details."""
        return self.registry.get_profile_details()
    
    def validate_profile_switch(self, profile_name: str) -> Tuple[bool, Optional[str]]:
        """Validate if a profile switch is possible."""
        return self.registry.validate_profile(profile_name)
    
    def _should_check_quota(self) -> bool:
        """Check if quota checking is enabled."""
        if not self.quota_manager:
            return False
        
        # Check if current LLM1 has quota limits
        if self._current_profile_config:
            return self._current_profile_config.llm1_config.free_quota is not None
        
        return False
    
    def _check_llm1_quota(self) -> bool:
        """Check if LLM1 has available quota."""
        try:
            if not self.quota_manager or not self._current_profile_config:
                return True
            
            # For simplicity, check a modest token amount
            test_tokens = 1000
            return self.quota_manager.can_use_tokens("system", test_tokens)
            
        except Exception as e:
            logger.warning(f"Error checking quota: {e}")
            return True  # Assume available on error
    
    def _attempt_fallback(self) -> bool:
        """Attempt to fallback to a different profile."""
        try:
            # Try to fallback to 'fallback' profile
            fallback_profile = "fallback"
            if fallback_profile in self.registry.list_available_profiles():
                logger.info(f"Falling back to profile: {fallback_profile}")
                return self._initialize_profile(fallback_profile)
            
            # Try to fallback to 'testing' profile
            testing_profile = "testing"
            if testing_profile in self.registry.list_available_profiles():
                logger.info(f"Falling back to profile: {testing_profile}")
                return self._initialize_profile(testing_profile)
            
            logger.warning("No fallback profile available")
            return False
            
        except Exception as e:
            logger.error(f"Error during fallback: {e}")
            return False
    
    def get_router_stats(self) -> Dict[str, Any]:
        """Get router statistics and current state."""
        with self._lock:
            profile_details = {}
            if self._current_profile_config:
                profile_details = {
                    'name': self._current_profile_config.name,
                    'description': self._current_profile_config.description,
                    'llm1': f"{self._current_profile_config.llm1_provider}/{self._current_profile_config.llm1_model}",
                    'llm2': f"{self._current_profile_config.llm2_provider}/{self._current_profile_config.llm2_model}",
                    'use_case': self._current_profile_config.use_case,
                    'estimated_cost_per_1k': self._current_profile_config.estimated_cost_per_1k_messages
                }
            
            return {
                'current_profile': self._stats.current_profile,
                'profile_details': profile_details,
                'statistics': {
                    'profile_switches': self._stats.profile_switches,
                    'llm1_calls': self._stats.llm1_calls,
                    'llm2_calls': self._stats.llm2_calls,
                    'fallback_events': self._stats.fallback_events,
                    'total_cost': self._stats.total_cost,
                    'last_switch_time': self._stats.last_switch_time.isoformat() if self._stats.last_switch_time else None
                },
                'clients_status': {
                    'llm1_available': self._llm1_client is not None,
                    'llm2_available': self._llm2_client is not None,
                    'llm1_type': type(self._llm1_client).__name__ if self._llm1_client else None,
                    'llm2_type': type(self._llm2_client).__name__ if self._llm2_client else None
                },
                'available_profiles': list(self.get_available_profiles().keys())
            }
    
    def record_usage_cost(self, llm_type: str, cost: float):
        """Record usage cost for statistics."""
        with self._lock:
            self._stats.total_cost += cost
            logger.debug(f"Recorded {llm_type} cost: ${cost:.6f}, Total: ${self._stats.total_cost:.6f}")
    
    def reload_registry(self) -> bool:
        """Force reload the model registry."""
        try:
            success = self.registry.reload_config()
            if success:
                logger.info("Model registry reloaded successfully")
                # Re-validate current profile
                is_valid, error = self.registry.validate_profile(self._current_profile)
                if not is_valid:
                    logger.warning(f"Current profile '{self._current_profile}' is no longer valid: {error}")
                    # Try to switch to default profile
                    default_profile = self.registry.get_default_profile()
                    if default_profile != self._current_profile:
                        logger.info(f"Switching to default profile: {default_profile}")
                        return self.switch_profile(default_profile)
            return success
        except Exception as e:
            logger.error(f"Error reloading registry: {e}")
            return False
    
    def health_check(self) -> Dict[str, Any]:
        """Perform a health check on the router."""
        with self._lock:
            health = {
                'status': 'healthy',
                'issues': [],
                'current_profile': self._current_profile,
                'clients_initialized': True,
                'registry_accessible': True
            }
            
            # Check if clients are available
            if not self._llm1_client:
                health['status'] = 'degraded'
                health['issues'].append('LLM1 client not available')
                health['clients_initialized'] = False
            
            if not self._llm2_client:
                health['status'] = 'degraded'
                health['issues'].append('LLM2 client not available')
                health['clients_initialized'] = False
            
            # Check if registry is accessible
            try:
                self.registry.get_default_profile()
            except Exception as e:
                health['status'] = 'unhealthy'
                health['issues'].append(f'Registry not accessible: {e}')
                health['registry_accessible'] = False
            
            # Check current profile validity
            is_valid, error = self.registry.validate_profile(self._current_profile)
            if not is_valid:
                health['status'] = 'degraded'
                health['issues'].append(f'Current profile invalid: {error}')
            
            return health

# Global router instance for singleton pattern
_global_router: Optional[DynamicLLMRouter] = None
_router_lock = threading.Lock()

def get_dynamic_router(profile: str = "default", config: Optional[Any] = None) -> DynamicLLMRouter:
    """Get the global dynamic router instance."""
    global _global_router
    
    with _router_lock:
        if _global_router is None:
            _global_router = DynamicLLMRouter(profile, config)
        return _global_router

def reset_dynamic_router():
    """Reset the global router (for testing)."""
    global _global_router
    with _router_lock:
        if _global_router:
            # Cleanup if needed
            pass
        _global_router = None