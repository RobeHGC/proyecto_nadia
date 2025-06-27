# agents/types.py
"""Common types used across agents to avoid circular imports."""
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from cognition.constitution import ConstitutionAnalysis


@dataclass
class AIResponse:
    """Container for AI-generated response data."""
    llm1_raw: str
    llm2_bubbles: List[str]
    constitution_analysis: ConstitutionAnalysis
    tokens_used: int
    generation_time: float
    # Multi-LLM tracking
    llm1_model: str = "unknown"
    llm2_model: str = "unknown"
    llm1_cost: float = 0.0
    llm2_cost: float = 0.0


@dataclass
class ReviewItem:
    """Item in the review queue waiting for human approval."""
    id: str
    user_id: str
    user_message: str
    ai_suggestion: AIResponse
    priority: float
    timestamp: datetime
    conversation_context: Dict[str, Any]
    supervisor_approved: bool = False
    reviewer_notes: Optional[str] = None