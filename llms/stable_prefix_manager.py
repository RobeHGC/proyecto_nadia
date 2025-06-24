import tiktoken
import os
import logging
from typing import List, Dict, Tuple

logger = logging.getLogger(__name__)

class StablePrefixManager:
    """Gestiona prefijos 100% estables ≥1024 tokens para máximo cache hit."""
    
    def __init__(self, persona_file: str = "persona/nadia_v1.md"):
        # Inicializar tokenizer para gpt-4 (compatible con GPT-4o)
        self.encoding = tiktoken.get_encoding("cl100k_base")
        self._stable_token_count = None
        self._stable_prefix = None
        self.persona_file = persona_file
        
        # Cargar prefijo desde archivo
        self._load_stable_prefix()
        
    def _load_stable_prefix(self):
        """Carga el prefijo estable desde archivo externo."""
        try:
            # Buscar archivo relativo al directorio del proyecto
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            persona_path = os.path.join(base_dir, self.persona_file)
            
            if not os.path.exists(persona_path):
                raise FileNotFoundError(f"Persona file not found: {persona_path}")
            
            with open(persona_path, "r", encoding="utf-8", newline="\n") as f:
                self._stable_prefix = f.read().strip()
            
            # Validar que cumple con requisitos de cache
            tokens = len(self.encoding.encode(self._stable_prefix))
            assert tokens >= 1024, f"Stable prefix has only {tokens} tokens, need ≥1024 for cache!"
            
            self._stable_token_count = tokens
            logger.info(f"Loaded stable prefix: {tokens} tokens from {persona_path}")
            
        except Exception as e:
            logger.error(f"Failed to load persona file {self.persona_file}: {e}")
            raise RuntimeError(f"StablePrefixManager initialization failed: {e}")
    
    @property
    def STABLE_PREFIX(self) -> str:
        """Retorna el prefijo estable cargado."""
        return self._stable_prefix
        
    def get_stable_prefix_tokens(self) -> int:
        """Calcula tokens reales del prefijo estable (solo una vez)."""
        if self._stable_token_count is None:
            tokens = self.encoding.encode(self.STABLE_PREFIX)
            self._stable_token_count = len(tokens)
        return self._stable_token_count
    
    def build_messages_for_cache(
        self, 
        user_context: Dict[str, any],
        conversation_summary: str,
        current_message: str
    ) -> Tuple[List[Dict[str, str]], int]:
        """
        Construye mensajes con prefijo estable + contenido dinámico.
        
        Returns:
            (messages, stable_token_count)
        """
        messages = []
        
        # BLOQUE A: Prefijo 100% estable (SIEMPRE primero, NUNCA cambia)
        messages.append({
            "role": "system",
            "content": self.STABLE_PREFIX
        })
        
        stable_tokens = self.get_stable_prefix_tokens()
        
        # Verificar que tenemos ≥1024 tokens
        if stable_tokens < 1024:
            raise ValueError(f"Stable prefix only has {stable_tokens} tokens! Need ≥1024")
        
        # BLOQUE B: Contenido dinámico (DESPUÉS del prefijo estable)
        
        # Contexto de usuario (si existe)
        if user_context.get("name"):
            messages.append({
                "role": "system",
                "content": f"Current user: {user_context['name']}"
            })
            
        # Resumen de conversación (en lugar de historia completa)
        if conversation_summary:
            messages.append({
                "role": "system", 
                "content": f"Conversation context: {conversation_summary}"
            })
            
        # Instrucción clara de refinamiento (no conversación)
        messages.append({
            "role": "user",
            "content": f"ORIGINAL DRAFT:\n\"{current_message}\"\n\nREFORMAT TASK: Take the exact same message content and rewrite it in casual bubbles using [GLOBO] separators. You are an EDITOR, not a conversational partner. Keep the same meaning but make it more humanized and casual."
        })
        
        return messages, stable_tokens
    
    def should_rebuild_prefix(self, cache_ratio: float, turn_count: int) -> bool:
        """Determina si reconstruir el prefijo (con guard clause)."""
        # Solo reconstruir cada 3 turnos si el cache está muy bajo
        return cache_ratio < 0.2 and turn_count % 3 == 0
    
    async def warm_up_cache(self, llm_client, test_message: str = "Hello!") -> bool:
        """
        Realiza warm-up del cache enviando un mensaje de prueba.
        
        Args:
            llm_client: Cliente LLM para hacer la llamada
            test_message: Mensaje de prueba para warm-up
            
        Returns:
            True si el warm-up fue exitoso
        """
        try:
            logger.info("Starting cache warm-up...")
            
            # Construir mensaje de warm-up
            messages, stable_tokens = self.build_messages_for_cache(
                user_context={"name": "TestUser"},
                conversation_summary="Test conversation for cache warm-up",
                current_message=test_message
            )
            
            # Hacer llamada de warm-up
            response = await llm_client.generate_response(
                messages,
                temperature=0.3,
                seed=42
            )
            
            # Verificar cache ratio si está disponible
            cache_ratio = getattr(llm_client, '_last_cache_ratio', 0.0)
            
            if cache_ratio > 0.0:
                logger.info(f"Cache warm-up completed. Cache ratio: {cache_ratio:.1%}")
            else:
                logger.info("Cache warm-up completed. First call - cache priming.")
            
            return True
            
        except Exception as e:
            logger.error(f"Cache warm-up failed: {e}")
            return False
    
    def get_cache_metrics(self, llm_client) -> Dict[str, any]:
        """
        Obtiene métricas de cache del cliente LLM.
        
        Returns:
            Dict con métricas de cache
        """
        metrics = {
            "stable_tokens": self._stable_token_count,
            "persona_file": self.persona_file,
            "cache_ratio": getattr(llm_client, '_last_cache_ratio', 0.0),
            "last_cost": getattr(llm_client, '_last_cost', 0.0),
            "cache_status": "active" if getattr(llm_client, '_last_cache_ratio', 0.0) > 0.7 else "low"
        }
        
        return metrics