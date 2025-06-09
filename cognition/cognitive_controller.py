# cognition/cognitive_controller.py
"""Controlador cognitivo que actúa como router entre vías de procesamiento."""
import logging
import re
from typing import Literal

logger = logging.getLogger(__name__)


class CognitiveController:
    """
    Controlador que decide si un mensaje debe ir por la vía rápida o lenta.

    El Controlador Cognitivo actúa como el "neocórtex" del sistema, tomando
    decisiones rápidas sobre cómo procesar cada mensaje entrante.
    """

    def __init__(self):
        """Inicializa el controlador con patrones de comandos rápidos."""
        # Patrones de comandos que siempre van por vía rápida
        self.fast_path_patterns = [
            r'^/ayuda$',
            r'^/help$',
            r'^/start$',
            r'^/stop$',
            r'^/estado$',
            r'^/status$',
            r'^/version$',
            r'^/comandos$',
        ]

        # Compilar regex para mejor rendimiento
        self.compiled_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.fast_path_patterns
        ]

        logger.info("CognitiveController inicializado con patrones de vía rápida")

    def route_message(self, message: str) -> Literal['fast_path', 'slow_path']:
        """
        Determina la ruta de procesamiento para un mensaje.

        Args:
            message: El mensaje del usuario a analizar

        Returns:
            'fast_path' para comandos simples
            'slow_path' para conversaciones complejas
        """
        # Sanitizar mensaje
        message = message.strip()

        # Verificar si es un comando de vía rápida
        for pattern in self.compiled_patterns:
            if pattern.match(message):
                logger.info(f"Mensaje '{message}' enrutado a fast_path")
                return 'fast_path'

        # TODO: En el futuro, aquí irá la lógica de embeddings para:
        # - Detectar preguntas frecuentes
        # - Analizar complejidad semántica
        # - Evaluar carga emocional
        # - Determinar necesidad de contexto histórico

        # Por ahora, todo lo demás va por vía lenta (personalizada)
        logger.info(f"Mensaje '{message[:50]}...' enrutado a slow_path")
        return 'slow_path'

    def add_fast_path_pattern(self, pattern: str):
        """
        Añade un nuevo patrón a la lista de vía rápida.

        Args:
            pattern: Expresión regular para comandos rápidos
        """
        self.fast_path_patterns.append(pattern)
        self.compiled_patterns.append(re.compile(pattern, re.IGNORECASE))
        logger.info(f"Nuevo patrón añadido a fast_path: {pattern}")
