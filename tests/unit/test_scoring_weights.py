"""
Unit tests for scoring dimension weights and letter grade mapping.
"""

from decimal import Decimal
import pytest

from backend.api.schemas.contracts import EvidenceCategory, LetterGrade
from backend.scoring.weights import (
    DIMENSION_SPECIFICATIONS,
    calculate_letter_grade,
)


def test_ten_dimensions_registered():
    """Verify exactly 10 dimensions are defined matching EvidenceCategory (SCORE-001)."""
    assert len(DIMENSION_SPECIFICATIONS) == 10
    categories = set(DIMENSION_SPECIFICATIONS.keys())
    assert categories == set(EvidenceCategory)


def test_weights_sum_to_exact_unity():
    """Verify sum of all 10 weights equals exactly 1.000 (SCORE-001)."""
    total = sum(spec.weight for spec in DIMENSION_SPECIFICATIONS.values())
    assert total == Decimal("1.00")


def test_dimension_weights_individual():
    """Verify individual weights adhere to SCORE-001 specifications."""
    assert DIMENSION_SPECIFICATIONS[EvidenceCategory.CORRECTNESS].weight == Decimal("0.18")
    assert DIMENSION_SPECIFICATIONS[EvidenceCategory.SECURITY].weight == Decimal("0.16")
    assert DIMENSION_SPECIFICATIONS[EvidenceCategory.RELIABILITY].weight == Decimal("0.14")
    assert DIMENSION_SPECIFICATIONS[EvidenceCategory.TESTING].weight == Decimal("0.12")
    assert DIMENSION_SPECIFICATIONS[EvidenceCategory.MAINTAINABILITY].weight == Decimal("0.10")
    assert DIMENSION_SPECIFICATIONS[EvidenceCategory.ARCHITECTURE].weight == Decimal("0.08")
    assert DIMENSION_SPECIFICATIONS[EvidenceCategory.PERFORMANCE].weight == Decimal("0.06")
    assert DIMENSION_SPECIFICATIONS[EvidenceCategory.DEPENDENCY_HEALTH].weight == Decimal("0.06")
    assert DIMENSION_SPECIFICATIONS[EvidenceCategory.DOCUMENTATION].weight == Decimal("0.05")
    assert DIMENSION_SPECIFICATIONS[EvidenceCategory.ENGINEERING_MATURITY].weight == Decimal("0.05")


@pytest.mark.parametrize(
    ("score", "expected_grade"),
    [
        (Decimal("100.0"), LetterGrade.A_PLUS),
        (Decimal("95.0"), LetterGrade.A_PLUS),
        (Decimal("94.9"), LetterGrade.A),
        (Decimal("85.0"), LetterGrade.A),
        (Decimal("84.9"), LetterGrade.B),
        (Decimal("70.0"), LetterGrade.B),
        (Decimal("69.9"), LetterGrade.C),
        (Decimal("55.0"), LetterGrade.C),
        (Decimal("54.9"), LetterGrade.D),
        (Decimal("40.0"), LetterGrade.D),
        (Decimal("39.9"), LetterGrade.F),
        (Decimal("0.0"), LetterGrade.F),
    ],
)
def test_letter_grade_mapping_thresholds(score: Decimal, expected_grade: LetterGrade):
    """Verify standard letter grade mapping thresholds (SCORE-004)."""
    assert calculate_letter_grade(score) == expected_grade
