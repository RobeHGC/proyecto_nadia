#!/usr/bin/env python3
# run_api.py
"""Script para ejecutar el servidor API de Nadia."""
import sys
from pathlib import Path

# Añadir el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent))

if __name__ == "__main__":
    import uvicorn

    from utils.config import Config

    config = Config.from_env()
    port = 8000  # Puerto por defecto

    print(f"🚀 Iniciando API Server de Nadia en puerto {port}")
    print(f"📍 Documentación disponible en: http://localhost:{port}/docs")
    print(f"🔐 Endpoint GDPR: DELETE http://localhost:{port}/users/{{user_id}}/memory")

    uvicorn.run(
        "api.server:app",
        host="0.0.0.0",
        port=port,
        reload=config.debug,
        log_level=config.log_level.lower()
    )
