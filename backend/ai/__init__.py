"""
AI Auxiliary Reasoning, Explanation, and Remediation Subsystem.
"""

from backend.ai.local_provider import LocalProvider
from backend.ai.mock_provider import MockProvider
from backend.ai.models import (
    AIAnalysisPayload,
    AIAnalysisResult,
    AIRecommendationItem,
    RecommendationPriority,
)
from backend.ai.prompts import (
    PROMPT_VERSION,
    SYSTEM_INSTRUCTION,
    build_analysis_prompt,
)
from backend.ai.provider import IAIProvider
from backend.ai.service import AIInterpretationService

__all__ = [
    "AIAnalysisPayload",
    "AIAnalysisResult",
    "AIInterpretationService",
    "AIRecommendationItem",
    "IAIProvider",
    "LocalProvider",
    "MockProvider",
    "PROMPT_VERSION",
    "RecommendationPriority",
    "SYSTEM_INSTRUCTION",
    "build_analysis_prompt",
]
