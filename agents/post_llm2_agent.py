# agents/post_llm2_agent.py
"""
Post-LLM2 Agent: Ejecutor de decisiones basadas en análisis de coherencia
Responsabilidades:
- Parsear JSON de LLM2
- Aplicar correcciones si hay conflictos
- Guardar nuevos commitments en DB
- Trigger rotación de prompts (conflicto identidad)
- Manejar fallbacks si JSON inválido
"""

import json
import logging
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from zoneinfo import ZoneInfo

from database.models import DatabaseManager
from llms.base_client import BaseLLMClient

logger = logging.getLogger(__name__)


class PostLLM2Agent:
    """Agente que ejecuta decisiones basadas en el análisis de coherencia de LLM2."""

    def __init__(
        self,
        db_manager: DatabaseManager,
        llm_nano_client: Optional[BaseLLMClient] = None,
    ):
        """
        Inicializa el Post-LLM2 Agent.

        Args:
            db_manager: Manager de base de datos
            llm_nano_client: Cliente LLM nano para fallback (GPT-4o-nano)
        """
        self.db = db_manager
        self.llm_nano = llm_nano_client
        self.logger = logging.getLogger(__name__)

        # Patrones para extracción de commitments
        self._commitment_patterns = [
            r"tomorrow.*?(?:exam|test|quiz|appointment|meeting)",
            r"later.*?(?:gym|workout|exercise|call|text|message)",
            r"tonight.*?(?:movie|netflix|date|dinner)",
            r"next week.*?(?:meeting|event|class|appointment)",
            r"this weekend.*?(?:hiking|party|trip|visit)",
            r"at \d{1,2}(?::\d{2})?\s?(?:am|pm).*?(?:meeting|appointment|class|exam)",
        ]

    async def execute(
        self, llm2_json: str, original_response: str, user_id: str
    ) -> str:
        """
        Ejecuta el procesamiento post-LLM2.

        Args:
            llm2_json: Respuesta JSON de LLM2
            original_response: Respuesta original de LLM1
            user_id: ID del usuario

        Returns:
            Texto final para enviar al usuario
        """
        try:
            # 1. Parsear JSON de LLM2
            analysis_data = await self._parse_llm2_response(
                llm2_json, original_response
            )

            # 2. Aplicar lógica de decisión
            final_text = await self._apply_decision_logic(
                analysis_data, original_response, user_id
            )

            # 3. Guardar nuevos commitments si existen
            if analysis_data["nuevos_compromisos"]:
                await self._save_new_commitments(
                    user_id, analysis_data["nuevos_compromisos"]
                )

            # 4. Trigger rotación de prompt si es conflicto de identidad
            if analysis_data["status"] == "CONFLICTO_DE_IDENTIDAD":
                await self._trigger_prompt_rotation(user_id)

            # 5. Log resultado para monitoring
            self._log_execution_result(analysis_data, user_id)

            return final_text

        except Exception as e:
            self.logger.error(f"Error in post-LLM2 execution: {e}")
            # Fallback: retornar respuesta original
            return original_response

    async def _parse_llm2_response(
        self, llm2_json: str, original_response: str
    ) -> Dict[str, Any]:
        """
        Parsea la respuesta JSON de LLM2 con fallback robusto.

        Args:
            llm2_json: Respuesta JSON de LLM2
            original_response: Respuesta original por si falla parsing

        Returns:
            Datos de análisis parseados
        """
        try:
            # Intento principal de parsing
            analysis = json.loads(llm2_json.strip())

            # Validar estructura requerida
            if not self._validate_json_structure(analysis):
                raise ValueError("Invalid JSON structure")

            self.logger.debug("LLM2 JSON parsed successfully")
            return analysis

        except (json.JSONDecodeError, ValueError) as e:
            self.logger.warning(f"LLM2 JSON parse failed: {e}")

            # Fallback 1: Intentar con GPT-4o-nano
            if self.llm_nano:
                try:
                    nano_response = await self._retry_with_nano(
                        llm2_json, original_response
                    )
                    nano_analysis = json.loads(nano_response.strip())

                    if self._validate_json_structure(nano_analysis):
                        self.logger.info("Nano fallback successful")
                        return nano_analysis

                except Exception as nano_error:
                    self.logger.error(f"Nano fallback also failed: {nano_error}")

            # Fallback final: estructura por defecto
            self.logger.warning("Using default fallback structure")
            return self._get_fallback_structure(original_response)

    def _validate_json_structure(self, analysis: Dict[str, Any]) -> bool:
        """
        Valida que el JSON tenga la estructura esperada.

        Args:
            analysis: Datos parseados del JSON

        Returns:
            True si la estructura es válida
        """
        required_fields = [
            "status",
            "detalle_conflicto",
            "propuesta_correccion",
            "nuevos_compromisos",
        ]

        if not all(field in analysis for field in required_fields):
            return False

        if "propuesta_correccion" in analysis:
            correction = analysis["propuesta_correccion"]
            if (
                not isinstance(correction, dict)
                or "oracion_original" not in correction
                or "oracion_corregida" not in correction
            ):
                return False

        valid_statuses = ["OK", "CONFLICTO_DE_IDENTIDAD", "CONFLICTO_DE_DISPONIBILIDAD"]
        if analysis["status"] not in valid_statuses:
            return False

        return True

    async def _retry_with_nano(
        self, failed_response: str, original_response: str
    ) -> str:
        """
        Reintentar análisis con GPT-4o-nano.

        Args:
            failed_response: Respuesta que falló al parsear
            original_response: Respuesta original de LLM1

        Returns:
            Nueva respuesta JSON de nano
        """
        retry_prompt = [
            {
                "role": "system",
                "content": "You are a JSON response corrector. Fix the malformed JSON response to match the required structure.",
            },
            {
                "role": "user",
                "content": f"""The following JSON response failed to parse:
{failed_response}

Please fix it to match this exact structure:
{{
  "status": "OK | CONFLICTO_DE_IDENTIDAD | CONFLICTO_DE_DISPONIBILIDAD",
  "detalle_conflicto": "Description or null",
  "propuesta_correccion": {{
      "oracion_original": "{original_response[:100]}...",
      "oracion_corregida": "corrected version"
  }},
  "nuevos_compromisos": []
}}

Return ONLY valid JSON:""",
            },
        ]

        return await self.llm_nano.generate_response(retry_prompt, temperature=0.1)

    def _get_fallback_structure(self, original_response: str) -> Dict[str, Any]:
        """
        Genera estructura fallback cuando el JSON parsing falla completamente.

        Args:
            original_response: Respuesta original de LLM1

        Returns:
            Estructura por defecto
        """
        return {
            "status": "OK",
            "detalle_conflicto": None,
            "propuesta_correccion": {
                "oracion_original": original_response,
                "oracion_corregida": original_response,
            },
            "nuevos_compromisos": [],
        }

    async def _apply_decision_logic(
        self, analysis_data: Dict[str, Any], original_response: str, user_id: str
    ) -> str:
        """
        Aplica la lógica de decisión basada en el análisis.

        Args:
            analysis_data: Datos del análisis de LLM2
            original_response: Respuesta original de LLM1
            user_id: ID del usuario

        Returns:
            Texto final a enviar
        """
        status = analysis_data["status"]

        if status == "OK":
            # No hay conflictos, usar respuesta original
            self.logger.debug(f"No conflicts detected for user {user_id}")
            return original_response

        elif status in ["CONFLICTO_DE_IDENTIDAD", "CONFLICTO_DE_DISPONIBILIDAD"]:
            # Hay conflicto, aplicar corrección
            correction = analysis_data["propuesta_correccion"]
            corrected_text = correction.get("oracion_corregida", original_response)

            self.logger.info(f"Applied correction for {status} - user {user_id}")
            self.logger.debug(f"Original: {correction.get('oracion_original', '')}")
            self.logger.debug(f"Corrected: {corrected_text}")

            return corrected_text

        else:
            # Status desconocido, usar original
            self.logger.warning(f"Unknown status '{status}' for user {user_id}")
            return original_response

    async def _save_new_commitments(self, user_id: str, commitments: List[str]) -> None:
        """
        Guarda nuevos commitments extraídos por LLM2.

        Args:
            user_id: ID del usuario
            commitments: Lista de textos de commitments
        """
        if not commitments:
            return

        try:
            async with self.db.get_connection() as conn:
                for commitment_text in commitments:
                    # Extraer timestamp del commitment
                    timestamp = self._extract_timestamp_from_text(commitment_text)

                    if timestamp:
                        # Extraer detalles del commitment
                        details = self._extract_commitment_details(commitment_text)

                        await conn.execute(
                            """
                            INSERT INTO nadia_commitments (
                                user_id, commitment_timestamp, details, commitment_text, status
                            ) VALUES ($1, $2, $3, $4, 'active')
                        """,
                            user_id,
                            timestamp,
                            json.dumps(details),
                            commitment_text,
                        )

                        self.logger.info(
                            f"Saved commitment for user {user_id}: {commitment_text}"
                        )
                    else:
                        self.logger.warning(
                            f"Could not extract timestamp from: {commitment_text}"
                        )

        except Exception as e:
            self.logger.error(f"Error saving commitments: {e}")

    def _extract_timestamp_from_text(self, text: str) -> Optional[datetime]:
        """
        Extrae timestamp de un texto de commitment.

        Args:
            text: Texto del commitment

        Returns:
            Timestamp extraído o None
        """
        try:
            monterrey_tz = ZoneInfo("America/Monterrey")
            now = datetime.now(monterrey_tz)

            # Patterns para diferentes tipos de tiempo
            time_patterns = [
                (r"tomorrow", lambda: now + timedelta(days=1)),
                (r"later", lambda: now + timedelta(hours=3)),
                (
                    r"tonight",
                    lambda: now.replace(hour=20, minute=0, second=0, microsecond=0),
                ),
                (r"next week", lambda: now + timedelta(days=7)),
                (
                    r"this weekend",
                    lambda: now + timedelta(days=(5 - now.weekday()) % 7),
                ),
                (r"at (\d{1,2})(?::(\d{2}))?\s?(am|pm)", self._parse_time_today),
            ]

            for pattern, time_func in time_patterns:
                if re.search(pattern, text.lower()):
                    if callable(time_func):
                        if "at" in pattern:
                            return self._parse_time_today(text, now)
                        else:
                            return time_func()

            # Fallback: 3 horas desde ahora
            return now + timedelta(hours=3)

        except Exception as e:
            self.logger.error(f"Error extracting timestamp: {e}")
            return None

    def _parse_time_today(self, text: str, base_time: datetime) -> datetime:
        """
        Parsea tiempo específico para hoy.

        Args:
            text: Texto con tiempo
            base_time: Tiempo base

        Returns:
            Timestamp parseado
        """
        match = re.search(r"at (\d{1,2})(?::(\d{2}))?\s?(am|pm)", text.lower())
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2)) if match.group(2) else 0
            am_pm = match.group(3)

            if am_pm == "pm" and hour != 12:
                hour += 12
            elif am_pm == "am" and hour == 12:
                hour = 0

            return base_time.replace(hour=hour, minute=minute, second=0, microsecond=0)

        return base_time + timedelta(hours=3)

    def _extract_commitment_details(self, text: str) -> Dict[str, Any]:
        """
        Extrae detalles estructurados del commitment.

        Args:
            text: Texto del commitment

        Returns:
            Detalles estructurados
        """
        details = {
            "activity": "unknown",
            "type": "general",
            "flexibility": "medium",
            "extracted_from_llm2": True,
        }

        # Detectar tipo de actividad
        activity_types = {
            "exam|test|quiz": {
                "activity": "exam",
                "type": "academic",
                "flexibility": "rigid",
            },
            "gym|workout|exercise": {
                "activity": "gym",
                "type": "fitness",
                "flexibility": "medium",
            },
            "meeting|appointment": {
                "activity": "meeting",
                "type": "professional",
                "flexibility": "rigid",
            },
            "movie|netflix": {
                "activity": "entertainment",
                "type": "leisure",
                "flexibility": "flexible",
            },
            "date|dinner": {
                "activity": "social",
                "type": "personal",
                "flexibility": "medium",
            },
        }

        for pattern, info in activity_types.items():
            if re.search(pattern, text.lower()):
                details.update(info)
                break

        return details

    async def _trigger_prompt_rotation(self, user_id: str) -> None:
        """
        Trigger rotación de prompt para prevenir loops de identidad.

        Args:
            user_id: ID del usuario
        """
        try:
            # TODO: Implementar lógica de rotación de prompts
            # Por ahora solo loggear que se necesita rotación
            self.logger.info(
                f"Prompt rotation triggered for user {user_id} due to identity conflict"
            )

            async with self.db.get_connection() as conn:
                await conn.execute(
                    """
                    INSERT INTO prompt_rotations (
                        user_id, new_prompt_id, rotation_reason
                    ) VALUES ($1, $2, $3)
                """,
                    user_id,
                    "rotation_needed",
                    "CONFLICTO_DE_IDENTIDAD",
                )

        except Exception as e:
            self.logger.error(f"Error triggering prompt rotation: {e}")

    def _log_execution_result(
        self, analysis_data: Dict[str, Any], user_id: str
    ) -> None:
        """
        Log resultado de la ejecución para monitoring.

        Args:
            analysis_data: Datos del análisis
            user_id: ID del usuario
        """
        status = analysis_data["status"]
        conflict_count = 1 if status != "OK" else 0
        commitment_count = len(analysis_data.get("nuevos_compromisos", []))

        self.logger.info(
            f"Post-LLM2 execution complete - User: {user_id}, Status: {status}, "
            f"Conflicts: {conflict_count}, New commitments: {commitment_count}"
        )
