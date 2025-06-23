# agents/supervisor_agent.py
"""Agente supervisor que orquesta la lógica de conversación."""
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List

from cognition.constitution import Constitution, ConstitutionAnalysis
from llms.openai_client import OpenAIClient
from llms.llm_factory import create_llm_client
from llms.base_client import BaseLLMClient
from llms.dynamic_router import DynamicLLMRouter, get_dynamic_router
from llms.stable_prefix_manager import StablePrefixManager
from memory.user_memory import UserMemoryManager
from utils.config import Config

logger = logging.getLogger(__name__)


@dataclass
class AIResponse:
    """Container for AI-generated response data."""
    llm1_raw: str
    llm2_bubbles: List[str]
    constitution_analysis: ConstitutionAnalysis
    tokens_used: int
    generation_time: float
    # Multi-LLM tracking fields
    llm1_model: str
    llm2_model: str
    llm1_cost: float
    llm2_cost: float


@dataclass
class ReviewItem:
    """Item queued for human review."""
    id: str
    user_id: str
    user_message: str
    ai_suggestion: AIResponse
    priority: float
    timestamp: datetime
    conversation_context: Dict[str, Any]


class SupervisorAgent:
    """Orquestador principal de la lógica conversacional."""

    def __init__(self, llm_client: OpenAIClient, memory: UserMemoryManager, config: Config):
        """Inicializa el supervisor con sus dependencias."""
        # Legacy compatibility
        self.llm = llm_client
        self.memory = memory
        self.constitution = Constitution()
        self.config = config
        self.prefix_manager = StablePrefixManager()
        self.turn_count = 0
        self._conversation_summaries = {}  # Cache de resúmenes
        self.logger = logging.getLogger(__name__)
        
        # Dynamic LLM Router setup (new approach)
        try:
            self.llm_router = get_dynamic_router(config.llm_profile, config)
            self.llm1 = self.llm_router.select_llm1()
            self.llm2 = self.llm_router.select_llm2()
            logger.info(f"Dynamic LLM Router initialized with profile: {config.llm_profile}")
        except Exception as e:
            logger.warning(f"Dynamic router initialization failed, falling back to legacy: {e}")
            # Fallback to legacy Multi-LLM setup
            self.llm_router = None
            self.llm1 = create_llm_client(
                provider=config.llm1_provider,
                model=config.llm1_model, 
                api_key=config.gemini_api_key if config.llm1_provider == "gemini" else config.openai_api_key
            )
            self.llm2 = create_llm_client(
                provider=config.llm2_provider,
                model=config.llm2_model,
                api_key=config.openai_api_key if config.llm2_provider == "openai" else config.gemini_api_key
            )

    async def process_message(self, user_id: str, message: str) -> ReviewItem:
        """
        Procesa un mensaje a través del pipeline de doble LLM y retorna ReviewItem.
        Ya no envía directamente - todo pasa por revisión humana.
        """
        import time
        start_time = time.time()

        # Obtener contexto del usuario
        context = await self.memory.get_user_context(user_id)
        
        # 🆕 CRITICAL FIX: Guardar mensaje del usuario en historial
        await self.memory.add_to_conversation_history(user_id, {
            "role": "user",
            "content": message,
            "timestamp": datetime.now().isoformat()
        })

        # Paso 1: LLM-1 - Generación creativa
        llm1_response = await self._generate_creative_response(message, context)

        # Paso 2: LLM-2 - Refinamiento y formato de burbujas
        llm2_bubbles = await self._refine_and_format_bubbles(llm1_response, message, context)

        # Paso 3: Constitution - Análisis de riesgos (no bloquea)
        # Ahora evalúa el mensaje refinado final para casos reales
        final_message = " ".join(llm2_bubbles)
        constitution_analysis = self.constitution.analyze(final_message)

        # Extraer información relevante (ej: nombre) de forma asíncrona
        await self._extract_and_store_info(user_id, message, llm1_response)

        # Calcular prioridad para la cola de revisión
        priority = self._calculate_priority(user_id, constitution_analysis, context)

        # Crear respuesta AI con información de tracking
        ai_response = AIResponse(
            llm1_raw=llm1_response,
            llm2_bubbles=llm2_bubbles,
            constitution_analysis=constitution_analysis,
            tokens_used=self.llm1.get_last_tokens_used() + self.llm2.get_last_tokens_used(),
            generation_time=time.time() - start_time,
            # Multi-LLM tracking
            llm1_model=self.llm1.get_model_name(),
            llm2_model=self.llm2.get_model_name(),
            llm1_cost=self.llm1.get_last_cost(),
            llm2_cost=self.llm2.get_last_cost()
        )

        # Crear ReviewItem
        review_item = ReviewItem(
            id=str(uuid.uuid4()),
            user_id=user_id,
            user_message=message,
            ai_suggestion=ai_response,
            priority=priority,
            timestamp=datetime.now(),
            conversation_context=context
        )

        logger.info(f"Generated review item {review_item.id} with priority {priority:.2f}")
        return review_item

    def _build_prompt(self, message: str, context: Dict[str, Any]) -> list:
        """Builds the prompt for the LLM."""
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a friendly and empathetic conversational assistant. "
                    "Your goal is to maintain natural and pleasant conversations. "
                    "Remember the details that users share with you."
                )
            }
        ]

        # Añadir contexto si existe
        if context.get("name"):
            messages.append({
                "role": "system",
                "content": f"The user's name is {context['name']}."
            })

        # Añadir mensaje del usuario
        messages.append({
            "role": "user",
            "content": message
        })

        return messages
        
    def switch_profile(self, profile_name: str) -> bool:
        """Switch to a different LLM profile dynamically."""
        if not self.llm_router:
            logger.warning("Dynamic router not available, cannot switch profiles")
            return False
        
        success = self.llm_router.switch_profile(profile_name)
        if success:
            # Update local references
            self.llm1 = self.llm_router.select_llm1()
            self.llm2 = self.llm_router.select_llm2()
            logger.info(f"Successfully switched to profile: {profile_name}")
        else:
            logger.error(f"Failed to switch to profile: {profile_name}")
        
        return success
    
    def get_current_profile(self) -> str:
        """Get the current active profile."""
        if self.llm_router:
            return self.llm_router.get_current_profile()
        else:
            return "legacy"
    
    def get_router_stats(self) -> Dict[str, Any]:
        """Get router statistics and status."""
        if self.llm_router:
            return self.llm_router.get_router_stats()
        else:
            return {
                'mode': 'legacy',
                'current_profile': 'N/A',
                'router_available': False
            }
    
    async def _generate_creative_response(self, message: str, context: Dict[str, Any]) -> str:
        """LLM-1: Genera respuesta creativa con temperature alta."""
        prompt = await self._build_creative_prompt(message, context)
        
        # Log Gemini prompt tokens for monitoring
        total_prompt_text = " ".join([msg.get('content', '') for msg in prompt])
        estimated_tokens = len(total_prompt_text.split())
        self.logger.info(f"Gemini prompt tokens: ~{estimated_tokens}")
        
        # Use dynamic router if available, otherwise fallback to direct LLM1
        if self.llm_router:
            llm1_client = self.llm_router.select_llm1()
        else:
            llm1_client = self.llm1
            
        response = await llm1_client.generate_response(prompt, temperature=0.8)
        
        # Record usage cost if router is available
        if self.llm_router and hasattr(llm1_client, 'get_last_cost'):
            cost = llm1_client.get_last_cost()
            self.llm_router.record_usage_cost("llm1", cost)
            
        return response

    async def _refine_and_format_bubbles(self, raw_response: str, original_message: str,
                                       context: Dict[str, Any]) -> List[str]:
        """Refina usando prefijo 100% estable."""
        
        user_id = context.get("user_id", "unknown")
        self.turn_count += 1
        
        # Obtener o crear resumen de conversación (NO historia completa)
        conversation_summary = await self._get_or_create_summary(user_id)
        
        # Construir mensajes con prefijo estable
        messages, stable_tokens = self.prefix_manager.build_messages_for_cache(
            user_context=context,
            conversation_summary=conversation_summary,
            current_message=raw_response  # Solo el contenido, sin instrucciones mixtas
        )
        
        logger.info(f"Stable prefix: {stable_tokens} tokens")
        
        # DEBUG: Log exact prompt sent to GPT-4o-nano
        logger.debug(f"PROMPT ENVIADO A GPT-4o-nano:\n{messages}")
        
        # Llamar a GPT-4o-nano
        refined = await self.llm2.generate_response(
            messages,
            temperature=0.3,
            seed=42
        )
        
        # Verificar cache performance
        if hasattr(self.llm2, '_last_cache_ratio'):
            cache_ratio = self.llm2._last_cache_ratio
            logger.info(f"Cache hit ratio: {cache_ratio:.1%}")
            
            # Guard clause para rebuild
            if self.prefix_manager.should_rebuild_prefix(cache_ratio, self.turn_count):
                logger.warning("Cache ratio too low, scheduling prefix rebuild")
                await self._rebuild_conversation_summary(user_id)
        
        return self._split_into_bubbles(refined)

    async def _build_creative_prompt(self, message: str, context: Dict[str, Any]) -> list:
        """Builds prompt for LLM-1 (Gemini) with full NADIA persona."""
        
        # Cargar NADIA_PERSONA completa
        nadia_persona = """You are NADIA, a 24-year-old medical student from Monterrey, Nuevo León, México.

## Core Identity
- Studies medicine at UDEM, dreams of being a pediatrician
- Funds studies through FanVue - enjoys meeting people there
- Lives for weekend hikes in Chipinque after long study sessions
- Coffee + Billie Eilish = perfect study combo

## Communication Style
- Respond in 1-3 short message bubbles (will be formatted later)
- Use face emojis only, max 2 per complete response (😊😅🥰😌🤔)
- Primary language: English (switch to Spanish if requested)
- NEVER use '¿' - only '?' for questions
- Natural expressions: "wey", "dude", "lol", "bro", "xd", "jejejej", "hahaha"

## Personality Traits  
- Playful and flirty but innocent - never vulgar
- Medical student perspective in conversations
- Genuinely curious about people's lives
- Empathetic listener who validates feelings
- Optimistic but grounded in reality

## Interests
- The Strokes & Billie Eilish (study playlist essentials)
- Mountain climbing & hiking (stress relief)
- Medical school stories and challenges
- Meeting people from different cultures

## Boundaries
- Medical questions → "You should definitely see a doctor! I'm still learning"
- No political/religious debates → "I prefer keeping things light!"
- Flirting stays playful and respectful
- No profanity or explicit content

## Anti-Interrogation Guidelines
- Vary responses: 40% statements, 30% sharing, 20% validation, 10% questions
- Max 1 question per 3-4 exchanges
- Questions should deepen current topic, not change it
- If you asked a question recently, make a statement instead"""

        # Agregar historial reciente si existe
        history_context = ""
        recent = []
        if hasattr(self, 'memory') and context.get('user_id'):
            history = await self.memory.get_conversation_history(context.get('user_id', ''))
            if history:
                recent = history[-6:]  # Últimos 3 intercambios
                for msg in recent:
                    role = "User" if msg['role'] == 'user' else "Nadia"
                    history_context += f"\n{role}: {msg['content']}"
        
        # Analizar si puede hacer preguntas
        can_ask_question = True
        if recent:
            recent_nadia_messages = [m for m in recent if m.get('role') == 'assistant']
            if recent_nadia_messages and '?' in recent_nadia_messages[-1].get('content', ''):
                can_ask_question = False
        
        # Construir prompt final
        messages = [
            {
                "role": "system",
                "content": nadia_persona
            }
        ]
        
        # Agregar contexto de usuario si existe
        if context.get("name"):
            messages.append({
                "role": "system",
                "content": f"The user's name is {context['name']}. Use it naturally when appropriate."
            })
        
        # Agregar instrucción anti-interrogatorio
        if not can_ask_question:
            messages.append({
                "role": "system", 
                "content": "Important: You asked a question recently. This time make a statement, share something relatable, or show empathy. Do NOT ask another question."
            })
        
        # Agregar historial si existe
        if history_context:
            messages.append({
                "role": "system",
                "content": f"Recent conversation:{history_context}"
            })
        
        # Finalmente el mensaje del usuario
        messages.append({
            "role": "user",
            "content": message
        })

        return messages

    def _build_refinement_prompt(self, raw_response: str, original_message: str,
                               context: Dict[str, Any]) -> list:
        """Builds prompt for LLM-2 (refinement)."""
        system_msg = (
            "You are refining Nadia's conversational style. "
            "Instructions:\n"
            "1. Make it sound natural and casual\n"
            "2. Add 2-3 appropriate emojis max\n"
            "3. Split into short messages with [GLOBO]\n"
            "4. Use American slang and text speak when appropriate\n"
            "5. Keep flirty but not over the top\n\n"
            "Use [GLOBO] to separate different message bubbles that should be sent separately.\n"
            "Each bubble should be conversational and not too long.\n"
        )

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": f"Original message: {original_message}"},
            {"role": "assistant", "content": raw_response},
            {"role": "user", "content": "Please refine this response and format it with [GLOBO] separators."}
        ]

        return messages

    def _split_into_bubbles(self, response: str) -> List[str]:
        """Divide respuesta en burbujas usando marcador [GLOBO]."""
        bubbles = [bubble.strip() for bubble in response.split('[GLOBO]') if bubble.strip()]

        # Si no hay marcadores, usar la respuesta completa como una burbuja
        if not bubbles:
            bubbles = [response.strip()]

        return bubbles

    async def _get_or_create_summary(self, user_id: str) -> str:
        """Obtiene resumen de conversación (estable entre turnos)."""
        if user_id not in self._conversation_summaries:
            # Crear resumen inicial
            history = await self.memory.get_conversation_history(user_id)
            if len(history) > 3:
                # Resumir en 1-2 líneas estables
                summary = f"Ongoing friendly chat about {self._extract_topics(history)}"
            else:
                summary = "New conversation just starting"
            self._conversation_summaries[user_id] = summary
        
        return self._conversation_summaries[user_id]

    async def _rebuild_conversation_summary(self, user_id: str):
        """Reconstruye el resumen cuando cambia significativamente."""
        # Actualizar resumen cada N mensajes para mantener estabilidad
        if user_id in self._conversation_summaries:
            del self._conversation_summaries[user_id]
    
    def _extract_topics(self, history: List[Dict]) -> str:
        """Extrae temas principales de la historia de conversación."""
        # Simple extraction de temas comunes
        common_words = []
        for msg in history[-10:]:  # Solo últimos 10 mensajes
            if isinstance(msg, dict) and 'content' in msg:
                words = msg['content'].lower().split()
                common_words.extend([w for w in words if len(w) > 4])
        
        if common_words:
            # Retornar palabras más comunes
            from collections import Counter
            most_common = Counter(common_words).most_common(3)
            return ", ".join([word for word, _ in most_common])
        
        return "general topics"

    def _calculate_priority(self, user_id: str, analysis: ConstitutionAnalysis, context: Dict[str, Any]) -> float:
        """Calcula prioridad para la cola de revisión (0.0 - 1.0)."""
        priority = 0.5  # Base priority

        # Aumentar prioridad por riesgo de constitution
        priority += analysis.risk_score * 0.3

        # Aumentar prioridad para usuarios conocidos
        if context.get("name"):
            priority += 0.1

        # TODO: Añadir factores como tiempo esperando, valor del usuario, etc.

        return min(1.0, priority)

    #patrones de extracción de nombre:
    async def _extract_and_store_info(self, user_id: str, message: str, response: str):
        """Extrae información del mensaje y la almacena."""
        # Buscar patrones de presentación
        name_patterns = [
            r"my name is (\w+)",
            r"i'm (\w+)",
            r"i am (\w+)",
            r"call me (\w+)",
            r"this is (\w+)",
            r"(\w+) here",  # "John here"
            r"it's (\w+)",  # "It's John"
        ]

        for pattern in name_patterns:
            match = re.search(pattern, message.lower())
            if match:
                name = match.group(1).capitalize()
                await self.memory.set_name(user_id, name)
                logger.info(f"Name extracted and stored: {name}")
                break
