"""
Integration tests for score reproducibility, golden tests, and persistence.
Adheres strictly to SCORE-008, SCORE-009, and SCORE-024.
"""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.analyzers.models import NormalizedFinding
from backend.api.schemas.contracts import EvidenceCategory, SeverityLevel
from backend.database.models import (
    Score,
    ScoreDimension,
)
from backend.scoring.calculator import DeterministicScoringEngine


@pytest.fixture
def golden_evidence_set():
    """Diverse, fixed set of multi-domain evidence items."""
    return [
        NormalizedFinding(
            analyzer_id="runtime-engine",
            tool_version="1.0.0",
            rule_id="RUN-BUILD-001-FAILURE",
            category=EvidenceCategory.CORRECTNESS,
            severity=SeverityLevel.CRITICAL,
            confidence=1.0,
            title="Repository Build Failed",
            description="Compilation syntax error in module",
        ),
        NormalizedFinding(
            analyzer_id="secret-scanner",
            tool_version="1.0.0",
            rule_id="SEC-001-GITHUB-PAT",
            category=EvidenceCategory.SECURITY,
            severity=SeverityLevel.CRITICAL,
            confidence=1.0,
            title="Hardcoded GitHub PAT",
            description="Detected ghp_ token",
        ),
        NormalizedFinding(
            analyzer_id="dependency-scanner",
            tool_version="1.0.0",
            rule_id="DEP-CVE-2023-4567",
            category=EvidenceCategory.SECURITY,
            severity=SeverityLevel.HIGH,
            confidence=0.8,
            title="High CVE in pyyaml",
            description="Arbitrary code execution",
        ),
        NormalizedFinding(
            analyzer_id="runtime-engine",
            tool_version="1.0.0",
            rule_id="RUN-EXC-001-UNHANDLED",
            category=EvidenceCategory.RELIABILITY,
            severity=SeverityLevel.HIGH,
            confidence=1.0,
            title="Unhandled Exception",
            description="KeyError during dispatch",
        ),
        NormalizedFinding(
            analyzer_id="ast-metrics",
            tool_version="1.0.0",
            rule_id="AST-001-COMPLEXITY",
            category=EvidenceCategory.MAINTAINABILITY,
            severity=SeverityLevel.MEDIUM,
            confidence=1.0,
            title="High Cyclomatic Complexity",
            description="Complexity 28",
        ),
        NormalizedFinding(
            analyzer_id="runtime-http",
            tool_version="1.0.0",
            rule_id="RUN-HTTP-002-HIGH-LATENCY",
            category=EvidenceCategory.PERFORMANCE,
            severity=SeverityLevel.MEDIUM,
            confidence=0.9,
            title="High Latency",
            description="p95 latency 2200ms",
        ),
    ]


def test_golden_reproducibility(golden_evidence_set):
    """
    Given the exact same evidence inputs and scoring version,
    the score must be 100% bit-for-bit reproducible across independent engine instances.
    """
    eval_id = uuid.uuid4()
    metadata = {
        "has_readme": True,
        "ci_cd_detected": ["GitHub Actions"],
        "lockfile_present": True,
    }

    engine_a = DeterministicScoringEngine(version="1.0.0")
    engine_b = DeterministicScoringEngine(version="1.0.0")

    result_a = engine_a.compute_scorecard(eval_id, golden_evidence_set, repo_metadata=metadata)
    result_b = engine_b.compute_scorecard(eval_id, golden_evidence_set, repo_metadata=metadata)

    assert result_a.overall_score == result_b.overall_score
    assert result_a.grade == result_b.grade
    assert result_a.total_deductions == result_b.total_deductions
    assert result_a.total_credits == result_b.total_credits

    for dim_name in result_a.dimensions:
        dim_a = result_a.dimensions[dim_name]
        dim_b = result_b.dimensions[dim_name]
        assert dim_a.score == dim_b.score
        assert dim_a.total_deductions == dim_b.total_deductions
        assert dim_a.total_credits == dim_b.total_credits
        assert len(dim_a.receipt) == len(dim_b.receipt)


def test_idempotency_over_100_runs(golden_evidence_set):
    """
    Assert mathematical consistency over 100 consecutive runs (SCORE-009).
    """
    engine = DeterministicScoringEngine()
    eval_id = uuid.UUID("01925b4a-8cf2-7612-882f-3d18c9ba1100")
    metadata = {"has_readme": True, "lockfile_present": True}

    baseline = engine.compute_scorecard(eval_id, golden_evidence_set, repo_metadata=metadata)

    for _ in range(100):
        iteration = engine.compute_scorecard(eval_id, golden_evidence_set, repo_metadata=metadata)
        assert iteration.overall_score == baseline.overall_score
        assert iteration.grade == baseline.grade
        assert iteration.total_deductions == baseline.total_deductions


@pytest.mark.asyncio
async def test_database_persistence_of_scorecard(golden_evidence_set):
    """
    Verify that Score and ScoreDimension entities are cleanly populated and added
    to the database session with receipt attribution (SCORE-024).
    """
    from unittest.mock import AsyncMock

    eval_id = uuid.uuid4()
    engine = DeterministicScoringEngine()
    scorecard = engine.compute_scorecard(eval_id, golden_evidence_set)

    added_entities = []
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.add.side_effect = lambda obj: added_entities.append(obj)
    mock_session.flush.return_value = None

    persisted_score = await engine.persist_scorecard(mock_session, scorecard)

    assert persisted_score.evaluation_id == eval_id
    assert persisted_score.overall_score == scorecard.overall_score
    assert persisted_score.grade == scorecard.grade.value
    assert persisted_score.scoring_version == "1.0.0"

    # Verify Score + 10 ScoreDimensions were added
    scores_added = [e for e in added_entities if isinstance(e, Score)]
    dims_added = [e for e in added_entities if isinstance(e, ScoreDimension)]

    assert len(scores_added) == 1
    assert len(dims_added) == 10
    dim_names = {d.dimension_name for d in dims_added}
    assert len(dim_names) == 10
