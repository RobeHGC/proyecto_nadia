# agents/intermediary_agent.py
"""
Agente Intermediario: Preparador de datos entre LLM1 y LLM2
Responsabilidades:
- Recibir respuesta de LLM1
- Obtener commitments activos del usuario
- Formatear datos para análisis LLM2
- NO modifica contenido, solo prepara
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from database.models import DatabaseManager
from llms.base_client import BaseLLMClient

logger = logging.getLogger(__name__)


class IntermediaryAgent:
    """Agente que prepara datos entre LLM1 y LLM2 para análisis de coherencia."""

    def __init__(self, db_manager: DatabaseManager, llm2_client: BaseLLMClient):
        """
        Inicializa el agente intermediario.

        Args:
            db_manager: Manager de base de datos para consultar commitments
            llm2_client: Cliente LLM2 para análisis de coherencia
        """
        self.db = db_manager
        self.llm2 = llm2_client
        self.logger = logging.getLogger(__name__)

    async def process(
        self,
        llm1_response: str,
        user_id: str,
        time_context: Dict[str, str],
        interaction_id: Optional[str] = None,
    ) -> str:
        """
        Procesa la respuesta de LLM1 y la analiza con LLM2.

        Args:
            llm1_response: Respuesta generada por LLM1
            user_id: ID del usuario
            time_context: Contexto temporal de Monterrey
            interaction_id: ID de la interacción (opcional)

        Returns:
            Respuesta final procesada por Post-LLM2 Agent
        """
        try:
            # 1. Obtener commitments activos
            commitments = await self._get_active_commitments(user_id)

            # 2. Preparar paquete estructurado para LLM2
            analysis_payload = await self._prepare_llm2_payload(
                llm1_response, user_id, time_context, commitments
            )

            # 3. Llamar LLM2 con prompt estático
            llm2_json = await self._call_llm2_analysis(analysis_payload)

            # 4. Log del análisis para debugging
            self.logger.info(f"LLM2 analysis completed for user {user_id}")
            self.logger.debug(f"LLM2 response: {llm2_json}")

            # 5. Guardar análisis en DB si tenemos interaction_id
            if interaction_id:
                await self._save_analysis_result(
                    interaction_id, analysis_payload, llm2_json
                )

            # 6. Retornar para procesamiento por Post-LLM2 Agent
            return llm2_json

        except Exception as e:
            self.logger.error(f"Error in intermediary processing: {e}")
            # Fallback: retornar estructura OK para que pase sin modificación
            return json.dumps(
                {
                    "status": "OK",
                    "detalle_conflicto": None,
                    "propuesta_correccion": {
                        "oracion_original": llm1_response,
                        "oracion_corregida": llm1_response,
                    },
                    "nuevos_compromisos": [],
                }
            )

    async def _get_active_commitments(self, user_id: str) -> List[Dict[str, Any]]:
        """
        Obtiene commitments activos del usuario desde la base de datos.

        Args:
            user_id: ID del usuario

        Returns:
            Lista de commitments activos
        """
        try:
            async with self.db.get_connection() as conn:
                # Consultar commitments activos (futuro + próximas 2 horas)
                query = """
                SELECT id, commitment_timestamp, details, commitment_text
                FROM nadia_commitments
                WHERE user_id = $1
                AND status = 'active'
                AND commitment_timestamp > NOW() - INTERVAL '2 hours'
                ORDER BY commitment_timestamp ASC
                LIMIT 20
                """

                rows = await conn.fetch(query, user_id)

                commitments = []
                for row in rows:
                    commitments.append(
                        {
                            "id": str(row["id"]),
                            "timestamp": row["commitment_timestamp"].isoformat(),
                            "details": row["details"],
                            "text": row["commitment_text"],
                            "time_until": self._calculate_time_until(
                                row["commitment_timestamp"]
                            ),
                        }
                    )

                self.logger.debug(
                    f"Found {len(commitments)} active commitments for user {user_id}"
                )
                return commitments

        except Exception as e:
            self.logger.error(f"Error fetching commitments for user {user_id}: {e}")
            return []

    def _calculate_time_until(self, commitment_time: datetime) -> str:
        """
        Calcula tiempo relativo hasta el commitment.

        Args:
            commitment_time: Timestamp del commitment

        Returns:
            Descripción temporal relativa
        """
        try:
            now = datetime.now(ZoneInfo("America/Monterrey"))
            if commitment_time.tzinfo is None:
                commitment_time = commitment_time.replace(
                    tzinfo=ZoneInfo("America/Monterrey")
                )

            delta = commitment_time - now

            if delta.total_seconds() < 0:
                return "overdue"
            elif delta.total_seconds() < 3600:  # < 1 hora
                minutes = int(delta.total_seconds() / 60)
                return f"in {minutes} minutes"
            elif delta.days == 0:  # Hoy
                return f"today at {commitment_time.strftime('%I:%M %p')}"
            elif delta.days == 1:  # Mañana
                return f"tomorrow at {commitment_time.strftime('%I:%M %p')}"
            else:
                return commitment_time.strftime("%A at %I:%M %p")

        except Exception as e:
            self.logger.error(f"Error calculating time until commitment: {e}")
            return "unknown time"

    async def _prepare_llm2_payload(
        self,
        llm1_response: str,
        user_id: str,
        time_context: Dict[str, str],
        commitments: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Prepara el payload estructurado para enviar a LLM2.

        Args:
            llm1_response: Respuesta de LLM1
            user_id: ID del usuario
            time_context: Contexto temporal
            commitments: Lista de commitments activos

        Returns:
            Payload estructurado para LLM2
        """
        # Formatear commitments para LLM2
        formatted_commitments = []
        for commitment in commitments:
            formatted_commitments.append(
                {
                    "activity": commitment["details"].get("activity", "unknown"),
                    "scheduled_time": commitment["timestamp"],
                    "time_description": commitment["time_until"],
                    "original_text": commitment["text"],
                }
            )

        return {
            "llm1_response": llm1_response,
            "current_time_monterrey": time_context["current_time"],
            "current_date": time_context["current_date"],
            "current_period": time_context["period"],
            "user_id": user_id,
            "active_schedule": formatted_commitments,
            "analysis_timestamp": datetime.now().isoformat(),
        }

    async def _call_llm2_analysis(self, payload: Dict[str, Any]) -> str:
        """
        Llama a LLM2 con el prompt estático para análisis de coherencia.

        Args:
            payload: Datos estructurados para análisis

        Returns:
            Respuesta JSON de LLM2
        """
        # Construir prompt estático para LLM2
        prompt_messages = [
            {"role": "system", "content": self._get_llm2_static_prompt()},
            {"role": "user", "content": self._format_analysis_request(payload)},
        ]

        # Llamar LLM2
        response = await self.llm2.generate_response(
            prompt_messages,
            temperature=0.1,  # Muy baja para consistencia
            seed=42,
        )

        return response.strip()

    def _get_llm2_static_prompt(self) -> str:
        """
        Retorna el prompt estático para LLM2 (optimizado para cache 75%).

        Returns:
            Prompt estático para análisis de coherencia
        """
        return """You are a SCHEDULE ANALYST for Nadia's conversational responses.

YOUR TASKS (in order):
1. ANALYZE: Check Nadia's response against her current schedule
2. COMPARE: Identify any conflicts (DISPONIBILIDAD or IDENTIDAD)
3. CLASSIFY: Categorize the type of conflict if any
4. GENERATE: Suggest corrections and extract new commitments

CONFLICT TYPES:
- CONFLICTO_DE_DISPONIBILIDAD: New activity conflicts with existing schedule timing
- CONFLICTO_DE_IDENTIDAD: Same activity mentioned repeatedly (postponing pattern)

OUTPUT FORMAT (JSON only):
{
  "status": "OK | CONFLICTO_DE_IDENTIDAD | CONFLICTO_DE_DISPONIBILIDAD",
  "detalle_conflicto": "Description of conflict or null",
  "propuesta_correccion": {
      "oracion_original": "exact original sentence",
      "oracion_corregida": "improved sentence that resolves conflict"
  },
  "nuevos_compromisos": ["Text of new commitment to track..."]
}

IMPORTANT: Output ONLY valid JSON. No explanations or additional text."""

    def _format_analysis_request(self, payload: Dict[str, Any]) -> str:
        """
        Formatea la request para análisis de LLM2.

        Args:
            payload: Datos para análisis

        Returns:
            Request formateada
        """
        schedule_text = "No active commitments"
        if payload["active_schedule"]:
            schedule_items = []
            for item in payload["active_schedule"]:
                schedule_items.append(
                    f"- {item['activity']}: {item['time_description']}"
                )
            schedule_text = "\n".join(schedule_items)

        return f"""NADIA'S RESPONSE TO ANALYZE:
"{payload['llm1_response']}"

CURRENT TIME: {payload['current_time_monterrey']} ({payload['current_period']})
DATE: {payload['current_date']}

NADIA'S CURRENT SCHEDULE:
{schedule_text}

ANALYZE FOR CONFLICTS AND PROVIDE JSON RESPONSE:"""

    async def _save_analysis_result(
        self, interaction_id: str, input_payload: Dict[str, Any], llm2_output: str
    ) -> None:
        """
        Guarda el resultado del análisis en la base de datos.

        Args:
            interaction_id: ID de la interacción
            input_payload: Datos de entrada
            llm2_output: Respuesta de LLM2
        """
        try:
            # Parsear JSON para obtener status
            try:
                analysis_result = json.loads(llm2_output)
                status = analysis_result.get("status", "UNKNOWN")
                json_parse_success = True
            except json.JSONDecodeError:
                status = "JSON_PARSE_ERROR"
                json_parse_success = False

            async with self.db.get_connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO coherence_analysis (
                        interaction_id, llm2_input, llm2_output, analysis_status,
                        conflict_details, json_parse_success, llm_model_used
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                    interaction_id,
                    json.dumps(input_payload),
                    llm2_output,
                    status,
                    analysis_result.get("detalle_conflicto")
                    if json_parse_success
                    else None,
                    json_parse_success,
                    self.llm2.get_model_name()
                    if hasattr(self.llm2, "get_model_name")
                    else "unknown",
                )

            self.logger.debug(
                f"Saved coherence analysis for interaction {interaction_id}"
            )

        except Exception as e:
            self.logger.error(f"Error saving analysis result: {e}")
            # No fallar el proceso principal por error de logging
