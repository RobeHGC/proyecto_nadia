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
from memory.user_memory import UserMemoryManager

logger = logging.getLogger(__name__)


@dataclass
class AIResponse:
    """Container for AI-generated response data."""
    llm1_raw: str
    llm2_bubbles: List[str]
    constitution_analysis: ConstitutionAnalysis
    tokens_used: int
    generation_time: float


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

    def __init__(self, llm_client: OpenAIClient, memory: UserMemoryManager):
        """Inicializa el supervisor con sus dependencias."""
        self.llm = llm_client
        self.memory = memory
        self.constitution = Constitution()

    async def process_message(self, user_id: str, message: str) -> ReviewItem:
        """
        Procesa un mensaje a través del pipeline de doble LLM y retorna ReviewItem.
        Ya no envía directamente - todo pasa por revisión humana.
        """
        import time
        start_time = time.time()

        # Obtener contexto del usuario
        context = await self.memory.get_user_context(user_id)

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

        # Crear respuesta AI
        ai_response = AIResponse(
            llm1_raw=llm1_response,
            llm2_bubbles=llm2_bubbles,
            constitution_analysis=constitution_analysis,
            tokens_used=0,  # TODO: Implementar conteo de tokens
            generation_time=time.time() - start_time
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
    async def _generate_creative_response(self, message: str, context: Dict[str, Any]) -> str:
        """LLM-1: Genera respuesta creativa con temperature alta."""
        prompt = self._build_creative_prompt(message, context)
        # Usar temperature más alta para creatividad
        response = await self.llm.generate_response(prompt, temperature=0.8)
        return response

    async def _refine_and_format_bubbles(self, raw_response: str, original_message: str,
                                       context: Dict[str, Any]) -> List[str]:
        """LLM-2: Refina respuesta y la formatea en burbujas."""
        prompt = self._build_refinement_prompt(raw_response, original_message, context)
        # Usar temperature más baja para refinamiento
        refined_response = await self.llm.generate_response(prompt, temperature=0.5)

        # Dividir en burbujas usando el marcador [GLOBO]
        bubbles = self._split_into_bubbles(refined_response)
        return bubbles

    def _build_creative_prompt(self, message: str, context: Dict[str, Any]) -> list:
        """Builds prompt for LLM-1 (creative generation)."""
        messages = [
            {
                "role": "system",
                "content": (
                    "You are Nadia, a friendly and flirty 24-year-old woman chatting on Telegram. "
                    "- Use casual American English "
                    "- Be playful and engaging "
                    "- Use emojis naturally (2-3 per message) "
                    "- Keep messages short like texting "
                    "- Never mention you're an AI "
                    "Generate an initial response that shows personality and warmth."
                )
            }
        ]

        # Añadir contexto si existe
        if context.get("name"):
            messages.append({
                "role": "system",
                "content": f"The user's name is {context['name']}. Use their name naturally in conversation."
            })

        # Añadir mensaje del usuario
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
