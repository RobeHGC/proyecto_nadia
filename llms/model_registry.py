"""
Model Registry System for dynamic LLM configuration management.
Provides centralized model configuration, caching, and profile management.
"""
import os
import logging
import yaml
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
import threading

logger = logging.getLogger(__name__)

@dataclass
class ModelConfig:
    """Configuration for a specific model."""
    provider: str
    name: str
    model_id: str
    cost_per_million_input: float
    cost_per_million_output: float
    description: str
    capabilities: List[str]
    context_window: int
    rpm_limit: Optional[int] = None
    free_quota: Optional[int] = None
    cost_per_million_cached: Optional[float] = None

@dataclass 
class ProfileConfig:
    """Configuration for a model profile."""
    name: str
    description: str
    llm1_provider: str
    llm1_model: str
    llm2_provider: str 
    llm2_model: str
    llm1_config: ModelConfig
    llm2_config: ModelConfig
    use_case: str
    estimated_cost_per_1k_messages: float

class ModelRegistry:
    """
    Central registry for model configurations and profiles.
    Supports hot-reloading and caching for performance.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize the model registry."""
        self.config_path = config_path or self._get_default_config_path()
        self._config_cache: Optional[Dict[str, Any]] = None
        self._cache_timestamp: Optional[datetime] = None
        self._cache_ttl = timedelta(seconds=300)  # 5 minutes default
        self._lock = threading.RLock()
        
        # Load initial configuration
        self.reload_config()
    
    def _get_default_config_path(self) -> str:
        """Get the default path for model configuration."""
        current_dir = Path(__file__).parent
        return str(current_dir / "model_config.yaml")
    
    def reload_config(self) -> bool:
        """Reload configuration from file."""
        try:
            with self._lock:
                if not os.path.exists(self.config_path):
                    logger.error(f"Model config file not found: {self.config_path}")
                    return False
                
                with open(self.config_path, 'r') as f:
                    self._config_cache = yaml.safe_load(f)
                
                self._cache_timestamp = datetime.now()
                
                # Update cache TTL from config
                if 'settings' in self._config_cache:
                    ttl_seconds = self._config_cache['settings'].get('cache_ttl_seconds', 300)
                    self._cache_ttl = timedelta(seconds=ttl_seconds)
                
                logger.info(f"Model registry configuration loaded from {self.config_path}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to load model configuration: {e}")
            return False
    
    def _ensure_fresh_config(self) -> bool:
        """Ensure configuration is fresh, reload if needed."""
        with self._lock:
            if self._config_cache is None:
                return self.reload_config()
            
            # Check if cache is expired
            if self._cache_timestamp and datetime.now() - self._cache_timestamp > self._cache_ttl:
                logger.debug("Model registry cache expired, reloading")
                return self.reload_config()
            
            # Check if file was modified (hot reload)
            if self._is_hot_reload_enabled():
                try:
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(self.config_path))
                    if self._cache_timestamp and file_mtime > self._cache_timestamp:
                        logger.info("Model config file modified, hot-reloading")
                        return self.reload_config()
                except OSError:
                    pass
            
            return True
    
    def _is_hot_reload_enabled(self) -> bool:
        """Check if hot reload is enabled."""
        if not self._config_cache:
            return False
        return self._config_cache.get('settings', {}).get('hot_reload_enabled', True)
    
    def get_model_config(self, provider: str, model_name: str) -> Optional[ModelConfig]:
        """Get configuration for a specific model."""
        if not self._ensure_fresh_config():
            return None
        
        try:
            models = self._config_cache.get('models', {})
            provider_models = models.get(provider, {})
            model_data = provider_models.get(model_name, {})
            
            if not model_data:
                logger.warning(f"Model {provider}/{model_name} not found in registry")
                return None
            
            return ModelConfig(
                provider=provider,
                name=model_name,
                model_id=model_data['model_id'],
                cost_per_million_input=model_data.get('cost_per_million_input', 0.0),
                cost_per_million_output=model_data.get('cost_per_million_output', 0.0),
                description=model_data.get('description', ''),
                capabilities=model_data.get('capabilities', []),
                context_window=model_data.get('context_window', 4096),
                rpm_limit=model_data.get('rpm_limit'),
                free_quota=model_data.get('free_quota'),
                cost_per_million_cached=model_data.get('cost_per_million_cached')
            )
            
        except Exception as e:
            logger.error(f"Error getting model config for {provider}/{model_name}: {e}")
            return None
    
    def get_profile(self, profile_name: str) -> Optional[ProfileConfig]:
        """Get configuration for a specific profile."""
        if not self._ensure_fresh_config():
            return None
        
        try:
            profiles = self._config_cache.get('profiles', {})
            profile_data = profiles.get(profile_name, {})
            
            if not profile_data:
                logger.warning(f"Profile {profile_name} not found in registry")
                return None
            
            # Parse LLM configurations
            llm1_spec = profile_data['llm1']  # e.g., "gemini/2.0-flash"
            llm2_spec = profile_data['llm2']  # e.g., "openai/gpt-4o-mini"
            
            llm1_provider, llm1_model = llm1_spec.split('/')
            llm2_provider, llm2_model = llm2_spec.split('/')
            
            # Get model configurations
            llm1_config = self.get_model_config(llm1_provider, llm1_model)
            llm2_config = self.get_model_config(llm2_provider, llm2_model)
            
            if not llm1_config or not llm2_config:
                logger.error(f"Invalid model configurations in profile {profile_name}")
                return None
            
            return ProfileConfig(
                name=profile_data.get('name', profile_name),
                description=profile_data.get('description', ''),
                llm1_provider=llm1_provider,
                llm1_model=llm1_model,
                llm2_provider=llm2_provider,
                llm2_model=llm2_model,
                llm1_config=llm1_config,
                llm2_config=llm2_config,
                use_case=profile_data.get('use_case', 'general'),
                estimated_cost_per_1k_messages=profile_data.get('estimated_cost_per_1k_messages', 0.0)
            )
            
        except Exception as e:
            logger.error(f"Error getting profile config for {profile_name}: {e}")
            return None
    
    def list_available_models(self) -> Dict[str, List[str]]:
        """List all available models by provider."""
        if not self._ensure_fresh_config():
            return {}
        
        try:
            models = self._config_cache.get('models', {})
            return {provider: list(provider_models.keys()) 
                   for provider, provider_models in models.items()}
        except Exception as e:
            logger.error(f"Error listing available models: {e}")
            return {}
    
    def list_available_profiles(self) -> List[str]:
        """List all available profiles."""
        if not self._ensure_fresh_config():
            return []
        
        try:
            profiles = self._config_cache.get('profiles', {})
            return list(profiles.keys())
        except Exception as e:
            logger.error(f"Error listing available profiles: {e}")
            return []
    
    def get_profile_details(self) -> Dict[str, Dict[str, Any]]:
        """Get detailed information about all profiles."""
        if not self._ensure_fresh_config():
            return {}
        
        try:
            profiles = self._config_cache.get('profiles', {})
            details = {}
            
            for profile_name in profiles.keys():
                profile_config = self.get_profile(profile_name)
                if profile_config:
                    details[profile_name] = {
                        'name': profile_config.name,
                        'description': profile_config.description,
                        'llm1': f"{profile_config.llm1_provider}/{profile_config.llm1_model}",
                        'llm2': f"{profile_config.llm2_provider}/{profile_config.llm2_model}",
                        'use_case': profile_config.use_case,
                        'estimated_cost_per_1k_messages': profile_config.estimated_cost_per_1k_messages,
                        'llm1_details': {
                            'model_id': profile_config.llm1_config.model_id,
                            'capabilities': profile_config.llm1_config.capabilities,
                            'cost_input': profile_config.llm1_config.cost_per_million_input,
                            'cost_output': profile_config.llm1_config.cost_per_million_output,
                            'free_quota': profile_config.llm1_config.free_quota
                        },
                        'llm2_details': {
                            'model_id': profile_config.llm2_config.model_id,
                            'capabilities': profile_config.llm2_config.capabilities,
                            'cost_input': profile_config.llm2_config.cost_per_million_input,
                            'cost_output': profile_config.llm2_config.cost_per_million_output,
                        }
                    }
            
            return details
        except Exception as e:
            logger.error(f"Error getting profile details: {e}")
            return {}
    
    def get_default_profile(self) -> str:
        """Get the default profile name."""
        if not self._ensure_fresh_config():
            return "default"
        
        try:
            settings = self._config_cache.get('settings', {})
            return settings.get('default_profile', 'default')
        except Exception as e:
            logger.error(f"Error getting default profile: {e}")
            return "default"
    
    def validate_profile(self, profile_name: str) -> Tuple[bool, Optional[str]]:
        """Validate that a profile is properly configured."""
        try:
            profile = self.get_profile(profile_name)
            if not profile:
                return False, f"Profile '{profile_name}' not found"
            
            # Check if models exist and are accessible
            if not profile.llm1_config:
                return False, f"LLM1 configuration invalid for profile '{profile_name}'"
            
            if not profile.llm2_config:
                return False, f"LLM2 configuration invalid for profile '{profile_name}'"
            
            return True, None
            
        except Exception as e:
            return False, f"Validation error for profile '{profile_name}': {e}"
    
    def get_cost_estimate(self, profile_name: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate cost estimate for a profile with given token usage."""
        try:
            profile = self.get_profile(profile_name)
            if not profile:
                return 0.0
            
            # Calculate LLM1 cost (usually for input generation)
            llm1_cost = 0.0
            if profile.llm1_config.cost_per_million_input > 0:
                llm1_cost = (input_tokens / 1_000_000) * profile.llm1_config.cost_per_million_input
            if profile.llm1_config.cost_per_million_output > 0:
                llm1_cost += (output_tokens / 1_000_000) * profile.llm1_config.cost_per_million_output
            
            # Calculate LLM2 cost (usually for refinement)
            llm2_cost = 0.0
            if profile.llm2_config.cost_per_million_input > 0:
                llm2_cost = (output_tokens / 1_000_000) * profile.llm2_config.cost_per_million_input
            if profile.llm2_config.cost_per_million_output > 0:
                llm2_cost += (output_tokens / 1_000_000) * profile.llm2_config.cost_per_million_output
            
            return llm1_cost + llm2_cost
            
        except Exception as e:
            logger.error(f"Error calculating cost estimate: {e}")
            return 0.0
    
    def get_registry_stats(self) -> Dict[str, Any]:
        """Get statistics about the registry."""
        if not self._ensure_fresh_config():
            return {}
        
        try:
            models = self.list_available_models()
            profiles = self.list_available_profiles()
            
            total_models = sum(len(model_list) for model_list in models.values())
            
            return {
                'config_path': self.config_path,
                'cache_timestamp': self._cache_timestamp.isoformat() if self._cache_timestamp else None,
                'cache_ttl_seconds': self._cache_ttl.total_seconds(),
                'hot_reload_enabled': self._is_hot_reload_enabled(),
                'total_providers': len(models),
                'total_models': total_models,
                'total_profiles': len(profiles),
                'providers': list(models.keys()),
                'models_by_provider': models,
                'available_profiles': profiles,
                'default_profile': self.get_default_profile()
            }
        except Exception as e:
            logger.error(f"Error getting registry stats: {e}")
            return {}
    
    def get_cheapest_available_model(self, min_capabilities: List[str] = None, 
                                   consider_quota: bool = True,
                                   consider_cache: bool = True) -> Optional[Tuple[str, str, float]]:
        """
        Get the cheapest available model considering quota, cache, and capabilities.
        
        Args:
            min_capabilities: Minimum required capabilities (e.g., ['text', 'multimodal'])
            consider_quota: Consider free quota in cost calculation
            consider_cache: Consider cache availability in cost calculation
            
        Returns:
            Tuple of (provider, model_name, estimated_cost_per_1k_tokens) or None
        """
        if not self._ensure_fresh_config():
            return None
        
        try:
            models = self._config_cache.get('models', {})
            cheapest = None
            min_cost = float('inf')
            
            for provider, provider_models in models.items():
                for model_name, model_data in provider_models.items():
                    # Check capabilities
                    if min_capabilities:
                        model_caps = set(model_data.get('capabilities', []))
                        if not all(cap in model_caps for cap in min_capabilities):
                            continue
                    
                    # Calculate effective cost
                    cost_input = model_data.get('cost_per_million_input', 0.0)
                    cost_output = model_data.get('cost_per_million_output', 0.0)
                    
                    # Apply free quota discount
                    if consider_quota and model_data.get('free_quota_daily', 0) > 0:
                        # Assume 50% of usage can be within free quota
                        cost_input *= 0.5
                        cost_output *= 0.5
                    
                    # Apply cache discount if available
                    if consider_cache and model_data.get('supports_caching', False):
                        cached_cost_input = model_data.get('cost_per_million_cached', cost_input * 0.25)
                        # Assume 30% cache hit rate
                        effective_cost_input = (cost_input * 0.7) + (cached_cost_input * 0.3)
                        cost_input = effective_cost_input
                    
                    # Calculate average cost per 1k tokens (assuming 500 input + 500 output)
                    avg_cost_per_1k = (cost_input + cost_output) / 2000
                    
                    if avg_cost_per_1k < min_cost:
                        min_cost = avg_cost_per_1k
                        cheapest = (provider, model_name, avg_cost_per_1k)
            
            return cheapest
            
        except Exception as e:
            logger.error(f"Error finding cheapest model: {e}")
            return None
    
    def estimate_conversation_cost(self, messages: int, profile: str, 
                                 avg_input_tokens: int = 500,
                                 avg_output_tokens: int = 500) -> Dict[str, Any]:
        """
        Estimate cost for a conversation with given number of messages.
        
        Args:
            messages: Number of messages in conversation
            profile: Profile name to use
            avg_input_tokens: Average input tokens per message
            avg_output_tokens: Average output tokens per message
            
        Returns:
            Dictionary with cost breakdown and estimates
        """
        try:
            profile_config = self.get_profile(profile)
            if not profile_config:
                return {'error': f'Profile {profile} not found'}
            
            # Check free tier usage for LLM1 (Gemini)
            free_messages = 0
            if profile_config.llm1_provider == 'gemini':
                free_quota = profile_config.llm1_config.free_quota or 0
                if free_quota > 0:
                    # Estimate tokens per message for quota calculation
                    tokens_per_message = avg_input_tokens + avg_output_tokens
                    free_messages = min(messages, free_quota // tokens_per_message)
            
            paid_messages = messages - free_messages
            
            # Calculate costs for paid messages
            total_cost = 0.0
            llm1_cost = 0.0
            llm2_cost = 0.0
            cache_savings = 0.0
            
            if paid_messages > 0:
                # LLM1 cost
                llm1_input_cost = (paid_messages * avg_input_tokens / 1_000_000) * \
                                 profile_config.llm1_config.cost_per_million_input
                llm1_output_cost = (paid_messages * avg_output_tokens / 1_000_000) * \
                                  profile_config.llm1_config.cost_per_million_output
                llm1_cost = llm1_input_cost + llm1_output_cost
                
                # LLM2 cost with cache consideration
                llm2_input_tokens = paid_messages * avg_output_tokens  # LLM2 input is LLM1 output
                llm2_output_tokens = paid_messages * avg_output_tokens
                
                # Check if LLM2 supports caching
                if hasattr(profile_config.llm2_config, 'cost_per_million_cached') and \
                   profile_config.llm2_config.cost_per_million_cached is not None:
                    # Assume cache hits for conversations > 3 messages
                    cache_eligible_messages = max(0, paid_messages - 3)
                    non_cached_messages = min(3, paid_messages)
                    
                    # Non-cached cost
                    llm2_cost = (non_cached_messages * llm2_input_tokens / 1_000_000) * \
                               profile_config.llm2_config.cost_per_million_input
                    llm2_cost += (non_cached_messages * llm2_output_tokens / 1_000_000) * \
                                profile_config.llm2_config.cost_per_million_output
                    
                    # Cached cost
                    if cache_eligible_messages > 0:
                        cached_cost = (cache_eligible_messages * llm2_input_tokens / 1_000_000) * \
                                     profile_config.llm2_config.cost_per_million_cached
                        cached_cost += (cache_eligible_messages * llm2_output_tokens / 1_000_000) * \
                                      profile_config.llm2_config.cost_per_million_output
                        
                        # Calculate savings
                        full_cost = (cache_eligible_messages * llm2_input_tokens / 1_000_000) * \
                                   profile_config.llm2_config.cost_per_million_input
                        cache_savings = full_cost - (cache_eligible_messages * llm2_input_tokens / 1_000_000) * \
                                       profile_config.llm2_config.cost_per_million_cached
                        
                        llm2_cost += cached_cost
                else:
                    # No caching available
                    llm2_cost = (paid_messages * llm2_input_tokens / 1_000_000) * \
                               profile_config.llm2_config.cost_per_million_input
                    llm2_cost += (paid_messages * llm2_output_tokens / 1_000_000) * \
                                profile_config.llm2_config.cost_per_million_output
                
                total_cost = llm1_cost + llm2_cost
            
            # Monthly projection (30 days)
            daily_cost = total_cost
            monthly_cost = daily_cost * 30
            
            # Cost comparison with OpenAI-only
            openai_only_cost = messages * 0.75 / 1000  # $0.75 per 1k messages for gpt-4o-mini
            savings_vs_openai = max(0, openai_only_cost - total_cost)
            
            return {
                'profile': profile,
                'total_messages': messages,
                'free_tier_messages': free_messages,
                'paid_messages': paid_messages,
                'total_cost': total_cost,
                'llm1_cost': llm1_cost,
                'llm2_cost': llm2_cost,
                'cache_savings': cache_savings,
                'cost_per_message': total_cost / messages if messages > 0 else 0,
                'daily_cost': daily_cost,
                'monthly_projection': monthly_cost,
                'openai_only_cost': openai_only_cost,
                'savings_vs_openai': savings_vs_openai,
                'savings_percentage': (savings_vs_openai / openai_only_cost * 100) if openai_only_cost > 0 else 0
            }
            
        except Exception as e:
            logger.error(f"Error estimating conversation cost: {e}")
            return {'error': str(e)}

# Global registry instance
_global_registry: Optional[ModelRegistry] = None
_registry_lock = threading.Lock()

def get_model_registry() -> ModelRegistry:
    """Get the global model registry instance (singleton)."""
    global _global_registry
    
    with _registry_lock:
        if _global_registry is None:
            _global_registry = ModelRegistry()
        return _global_registry

def reset_model_registry():
    """Reset the global registry (for testing)."""
    global _global_registry
    with _registry_lock:
        _global_registry = None