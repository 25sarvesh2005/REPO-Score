"""
Evaluation Dimension Definitions, Mathematical Weights, and Letter Grade Mapping.
Adheres strictly to SCORING_ARCHITECTURE.md, ADR-004, and SCORE-001 through SCORE-004.
"""

from decimal import Decimal
from typing import Dict, NamedTuple
from backend.api.schemas.contracts import EvidenceCategory, LetterGrade


class DimensionSpec(NamedTuple):
    """Specification and weight definition for an individual scorecard dimension."""
    category: EvidenceCategory
    name: str
    weight: Decimal
    description: str


# The 10 discrete engineering dimensions with normalized weights summing to 1.000 (SCORE-001)
DIMENSION_SPECIFICATIONS: Dict[EvidenceCategory, DimensionSpec] = {
    EvidenceCategory.CORRECTNESS: DimensionSpec(
        category=EvidenceCategory.CORRECTNESS,
        name="Correctness",
        weight=Decimal("0.18"),
        description="Build passes, application runs, zero syntax errors, test suite passes, zero crash traces.",
    ),
    EvidenceCategory.SECURITY: DimensionSpec(
        category=EvidenceCategory.SECURITY,
        name="Security",
        weight=Decimal("0.16"),
        description="Zero critical/high CVEs, no hardcoded secrets, no OWASP Top 10 vulnerabilities, safe crypto.",
    ),
    EvidenceCategory.RELIABILITY: DimensionSpec(
        category=EvidenceCategory.RELIABILITY,
        name="Reliability",
        weight=Decimal("0.14"),
        description="Graceful error handling, steady memory under load, clean SIGTERM exit, low runtime error rates.",
    ),
    EvidenceCategory.TESTING: DimensionSpec(
        category=EvidenceCategory.TESTING,
        name="Testing",
        weight=Decimal("0.12"),
        description="Code coverage %, test-to-code volume ratio, automated unit and integration test presence.",
    ),
    EvidenceCategory.MAINTAINABILITY: DimensionSpec(
        category=EvidenceCategory.MAINTAINABILITY,
        name="Maintainability",
        weight=Decimal("0.10"),
        description="Cyclomatic/cognitive complexity, function length, comment clarity, linter cleanliness.",
    ),
    EvidenceCategory.ARCHITECTURE: DimensionSpec(
        category=EvidenceCategory.ARCHITECTURE,
        name="Architecture",
        weight=Decimal("0.08"),
        description="Absence of circular dependencies, modular separation of concerns, clean layer boundaries.",
    ),
    EvidenceCategory.PERFORMANCE: DimensionSpec(
        category=EvidenceCategory.PERFORMANCE,
        name="Performance",
        weight=Decimal("0.06"),
        description="Cold startup latency, idle/load memory usage, p95/p99 HTTP response times, CPU efficiency.",
    ),
    EvidenceCategory.DEPENDENCY_HEALTH: DimensionSpec(
        category=EvidenceCategory.DEPENDENCY_HEALTH,
        name="Dependency Health",
        weight=Decimal("0.06"),
        description="Minimal dependency bloat, pinned versions, actively maintained dependencies, zero deprecated packages.",
    ),
    EvidenceCategory.DOCUMENTATION: DimensionSpec(
        category=EvidenceCategory.DOCUMENTATION,
        name="Documentation",
        weight=Decimal("0.05"),
        description="Comprehensive README, setup/run guides, API reference, docstrings on exported functions.",
    ),
    EvidenceCategory.ENGINEERING_MATURITY: DimensionSpec(
        category=EvidenceCategory.ENGINEERING_MATURITY,
        name="Engineering Maturity",
        weight=Decimal("0.05"),
        description="CI workflows (GitHub Actions), commit history hygiene, issue templates, semantic versioning.",
    ),
}

# Verify at import time that dimension weights sum to exactly 1.000 (SCORE-001)
TOTAL_WEIGHT = sum(spec.weight for spec in DIMENSION_SPECIFICATIONS.values())
if TOTAL_WEIGHT != Decimal("1.00"):
    raise ValueError(f"Dimension weights must sum to exactly 1.00, got {TOTAL_WEIGHT}")


def calculate_letter_grade(score: Decimal) -> LetterGrade:
    """
    Map overall composite score to standard letter grade (SCORE-004):
      A+: 95.0 - 100.0
      A : 85.0 - 94.9
      B : 70.0 - 84.9
      C : 55.0 - 69.9
      D : 40.0 - 54.9
      F : 0.0  - 39.9
    """
    if score >= Decimal("95.0"):
        return LetterGrade.A_PLUS
    if score >= Decimal("85.0"):
        return LetterGrade.A
    if score >= Decimal("70.0"):
        return LetterGrade.B
    if score >= Decimal("55.0"):
        return LetterGrade.C
    if score >= Decimal("40.0"):
        return LetterGrade.D
    return LetterGrade.F
