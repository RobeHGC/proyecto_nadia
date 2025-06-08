# utils/config.py
"""Configuración centralizada del proyecto."""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

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

    # opcionales / con default
    openai_model: str = "gpt-3.5-turbo"
    debug: bool = False
    log_level: str = "INFO"

    @classmethod
    def from_env(cls) -> "Config":
        """Crea configuración desde variables de entorno."""
        return cls(
            api_id=int(os.getenv("API_ID", "0")),
            api_hash=os.getenv("API_HASH", ""),
            phone_number=os.getenv("PHONE_NUMBER", ""),
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
            debug=os.getenv("DEBUG", "False").lower() == "true",
            log_level=os.getenv("LOG_LEVEL", "INFO")
        )


