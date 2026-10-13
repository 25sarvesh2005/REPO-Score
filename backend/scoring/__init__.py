"""
Deterministic Evidence-Backed Scoring Engine Module.
"""

from backend.scoring.calculator import (
    SCORING_VERSION,
    DeterministicScoringEngine,
)
from backend.scoring.models import (
    DimensionScoreResult,
    ReceiptItem,
    ScorecardResult,
)
from backend.scoring.rules import evaluate_evidence_item
from backend.scoring.weights import (
    DIMENSION_SPECIFICATIONS,
    DimensionSpec,
    calculate_letter_grade,
)

__all__ = [
    "DIMENSION_SPECIFICATIONS",
    "DeterministicScoringEngine",
    "DimensionScoreResult",
    "DimensionSpec",
    "ReceiptItem",
    "SCORING_VERSION",
    "ScorecardResult",
    "calculate_letter_grade",
    "evaluate_evidence_item",
]
