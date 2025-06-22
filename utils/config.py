# utils/config.py
"""Configuración centralizada del proyecto."""
import os
from dataclasses import dataclass
from typing import Dict, Any, Optional

from dotenv import load_dotenv
from llms.model_registry import get_model_registry, ProfileConfig

load_dotenv()


@dataclass
class Config:
    """Configuración de la aplicación."""
    # Telegram
    api_id: int
    api_hash: str
    phone_number: str
    openai_api_key: str
    redis_url: str

    # Database
    database_url: str

    # Multi-LLM Support
    gemini_api_key: str
    llm_profile: str = "default"  # Model profile to use (replaces individual model config)
    
    # Legacy Multi-LLM config (for backward compatibility)
    llm1_provider: str = "gemini"  # Creative LLM provider
    llm1_model: str = "gemini-2.0-flash-exp"  # Creative LLM model
    llm2_provider: str = "openai"  # Refinement LLM provider  
    llm2_model: str = "gpt-4o-mini"  # Refinement LLM model

    # Legacy OpenAI config (for backward compatibility)
    openai_model: str = "gpt-3.5-turbo"
    
    # opcionales / con default
    debug: bool = False
    log_level: str = "INFO"

    # App
    api_port: int = 8000

    @classmethod
    def from_env(cls) -> "Config":
        """Crea configuración desde variables de entorno."""
        return cls(
            api_id=int(os.getenv("API_ID", "0")),
            api_hash=os.getenv("API_HASH", ""),
            phone_number=os.getenv("PHONE_NUMBER", ""),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            database_url=os.getenv("DATABASE_URL", "postgresql://localhost/nadia_hitl"),
            
            # Multi-LLM configuration
            gemini_api_key=os.getenv("GEMINI_API_KEY", ""),
            llm_profile=os.getenv("LLM_PROFILE", "default"),
            
            # Legacy Multi-LLM configuration (for backward compatibility)
            llm1_provider=os.getenv("LLM1_PROVIDER", "gemini"),
            llm1_model=os.getenv("LLM1_MODEL", "gemini-2.0-flash-exp"),
            llm2_provider=os.getenv("LLM2_PROVIDER", "openai"),
            llm2_model=os.getenv("LLM2_MODEL", "gpt-4o-mini"),
            
            # Legacy and optional
            openai_model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
            debug=os.getenv("DEBUG", "False").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            api_port=int(os.getenv("API_PORT", "8000"))
        )
    
    def get_llm_config(self) -> Optional[ProfileConfig]:
        """Get LLM configuration from model registry using the current profile."""
        try:
            registry = get_model_registry()
            return registry.get_profile(self.llm_profile)
        except Exception as e:
            # Fallback to legacy configuration if registry fails
            print(f"Warning: Model registry failed, using legacy config: {e}")
            return None
    
    def get_profile_models(self) -> Dict[str, str]:
        """Get the model IDs for the current profile."""
        profile_config = self.get_llm_config()
        if profile_config:
            return {
                'llm1': profile_config.llm1_config.model_id,
                'llm2': profile_config.llm2_config.model_id,
                'llm1_provider': profile_config.llm1_provider,
                'llm2_provider': profile_config.llm2_provider
            }
        else:
            # Fallback to legacy configuration
            return {
                'llm1': self.llm1_model,
                'llm2': self.llm2_model,
                'llm1_provider': self.llm1_provider,
                'llm2_provider': self.llm2_provider
            }
    
    def validate_profile(self) -> bool:
        """Validate that the current profile is available and valid."""
        try:
            registry = get_model_registry()
            is_valid, error = registry.validate_profile(self.llm_profile)
            if not is_valid:
                print(f"Profile validation failed: {error}")
            return is_valid
        except Exception as e:
            print(f"Error validating profile: {e}")
            return False


