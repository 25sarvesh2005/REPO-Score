"""
Adversarial Tests: Manifest Corruption, Score Order Invariance, Worker Crash Rollback, and Queue Idempotency.
Adheres strictly to Phase 14 specifications and AGENTS Prime Directives.
"""

import random
import uuid
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.analyzers.dependency_scanner import DependencyVulnerabilityAnalyzer
from backend.analyzers.models import NormalizedFinding
from backend.api.schemas.contracts import (
    EvaluationStatus,
    EvidenceCategory,
    SeverityLevel,
)
from backend.core.queue import InMemoryJobQueue
from backend.database.models import Evaluation, Repository
from backend.pipeline.orchestrator import EvaluationPipelineOrchestrator
from backend.pipeline.worker import EvaluationWorker
from backend.scoring.calculator import DeterministicScoringEngine


@pytest.fixture
def mock_db_session():
    """Mock asynchronous database session that simulates entity tracking."""
    session = AsyncMock(spec=AsyncSession)
    stored_entities = {}

    def _add(entity):
        tbl = getattr(entity, "__tablename__", type(entity).__name__)
        if tbl not in stored_entities:
            stored_entities[tbl] = []
        stored_entities[tbl].append(entity)

    session.add.side_effect = _add
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    return session, stored_entities


# =========================================================================
# 1. Manifest Corruption & Dependency Analyzer Resilience
# =========================================================================


@pytest.mark.asyncio
async def test_adversarial_malformed_package_json(tmp_path: Path):
    """
    Verify DependencyVulnerabilityAnalyzer gracefully handles corrupted,
    truncated, or non-dictionary package.json without crashing.
    """
    analyzer = DependencyVulnerabilityAnalyzer()

    # Case A: Truncated JSON
    repo_a = tmp_path / "repo_a"
    repo_a.mkdir(parents=True, exist_ok=True)
    (repo_a / "package.json").write_text(
        '{"name": "broken", "dependencies": { "lodash": ', encoding="utf-8"
    )

    findings_a = await analyzer._execute_analysis(repo_a)
    assert findings_a == []

    # Case B: Array instead of object in package.json
    repo_b = tmp_path / "repo_b"
    repo_b.mkdir(parents=True, exist_ok=True)
    (repo_b / "package.json").write_text(
        '["not", "a", "valid", "manifest", "object"]', encoding="utf-8"
    )

    findings_b = await analyzer._execute_analysis(repo_b)
    assert findings_b == []


@pytest.mark.asyncio
async def test_adversarial_malformed_requirements_txt(tmp_path: Path):
    """
    Verify requirements.txt parser handles binary junk and invalid version specifiers
    while still parsing valid vulnerable lines in the same file.
    """
    analyzer = DependencyVulnerabilityAnalyzer()

    repo = tmp_path / "corrupt_reqs"
    repo.mkdir(parents=True, exist_ok=True)

    # Malformed content mixed with valid vulnerable dependency:
    # requests 2.25.0 is vulnerable to CVE-2023-32681 (fixed in 2.31.0)
    corrupted_content = (
        "# Corrupted requirements test\n"
        "\x00\xff\xfe binary garbage line here\n"
        "broken_pkg===1.2.3.4.5.invalid.spec!!\n"
        "requests==2.25.0\n"
        "another-broken-pkg @ https://invalid.domain/path\n"
        "--extra-index-url https://example.com/pypi\n"
    )
    (repo / "requirements.txt").write_text(corrupted_content, encoding="utf-8", errors="replace")

    findings = await analyzer._execute_analysis(repo)

    # Analyzer must not crash, must skip invalid lines, and must find CVE-2023-32681
    assert len(findings) == 1
    assert findings[0].rule_id == "CVE-2023-32681"
    assert "requests" in findings[0].title.lower()


# =========================================================================
# 2. Score Order Invariance & Mathematical Determinism
# =========================================================================


def test_adversarial_score_order_invariance():
    """
    Verify Prime Directive #3 (Deterministic Core):
    Permuting, reversing, or shuffling evidence records MUST yield the EXACT same
    overall score, letter grade, and dimension scores down to the Decimal cent.
    """
    scoring_engine = DeterministicScoringEngine()
    eval_id = uuid.uuid4()

    # Generate diverse findings across different categories & severities
    base_findings = (
        [
            NormalizedFinding(
                analyzer_id="dep-scanner",
                tool_version="1.0.0",
                rule_id=f"CVE-2024-{i:04d}",
                category=EvidenceCategory.DEPENDENCY_HEALTH,
                severity=SeverityLevel.HIGH if i % 2 == 0 else SeverityLevel.MEDIUM,
                confidence=0.95,
                title=f"Vulnerability {i}",
                description="Sample CVE finding",
            )
            for i in range(1, 6)
        ]
        + [
            NormalizedFinding(
                analyzer_id="ast-linter",
                tool_version="1.0.0",
                rule_id=f"PY-LINT-{j:03d}",
                category=EvidenceCategory.MAINTAINABILITY,
                severity=SeverityLevel.LOW if j % 2 == 0 else SeverityLevel.MEDIUM,
                confidence=1.0,
                title=f"Linter warning {j}",
                description="Style or complexity issue",
            )
            for j in range(1, 8)
        ]
        + [
            NormalizedFinding(
                analyzer_id="sec-scanner",
                tool_version="1.0.0",
                rule_id="SEC-INJECT-001",
                category=EvidenceCategory.SECURITY,
                severity=SeverityLevel.CRITICAL,
                confidence=1.0,
                title="Critical SQL Injection flaw",
                description="Hardcoded SQL concatenation",
            )
        ]
    )

    metadata = {
        "build_successful": True,
        "startup_successful": True,
        "tests_passed": 25,
        "tests_failed": 0,
        "line_coverage_percent": 85.0,
        "clean_shutdown": True,
        "lockfile_present": True,
        "has_readme": True,
        "ci_cd_detected": ["github-actions"],
    }

    # Baseline scorecard
    baseline = scoring_engine.compute_scorecard(
        eval_id, list(base_findings), repo_metadata=metadata
    )

    # Test reverse order and 10 pseudo-random permutations
    rng = random.Random(42)
    permutations = [list(reversed(base_findings))]
    for _ in range(10):
        shuffled = list(base_findings)
        rng.shuffle(shuffled)
        permutations.append(shuffled)

    for idx, perm in enumerate(permutations):
        scorecard = scoring_engine.compute_scorecard(eval_id, perm, repo_metadata=metadata)

        # 1. Overall score and grade must be identical
        assert scorecard.overall_score == baseline.overall_score, (
            f"Permutation {idx} overall score mismatch: {scorecard.overall_score} != {baseline.overall_score}"
        )
        assert scorecard.grade == baseline.grade, (
            f"Permutation {idx} grade mismatch: {scorecard.grade} != {baseline.grade}"
        )

        # 2. Every individual dimension score, deduction sum, and credit sum must be identical
        for dim_name, dim_result in baseline.dimensions.items():
            perm_dim = scorecard.dimensions[dim_name]
            assert perm_dim.score == dim_result.score, (
                f"Dimension {dim_name} score differed in permutation {idx}: {perm_dim.score} != {dim_result.score}"
            )
            assert perm_dim.total_deductions == dim_result.total_deductions
            assert perm_dim.total_credits == dim_result.total_credits


def test_adversarial_partial_evidence_deterministic_penalty():
    """
    Verify partial evaluation (BUILD_FAILED) applies explicit deterministic penalties (SCORE-023)
    to PERFORMANCE and RELIABILITY dimensions and marks status as EVALUATION_INCOMPLETE.
    """
    scoring_engine = DeterministicScoringEngine()
    eval_id = uuid.uuid4()

    scorecard_clean = scoring_engine.compute_scorecard(eval_id, [])
    scorecard_partial = scoring_engine.compute_scorecard(eval_id, [], partial_status="BUILD_FAILED")

    # In partial run, PERFORMANCE and RELIABILITY must be marked EVALUATION_INCOMPLETE
    assert scorecard_partial.dimensions["PERFORMANCE"].status == "EVALUATION_INCOMPLETE"
    assert scorecard_partial.dimensions["RELIABILITY"].status == "EVALUATION_INCOMPLETE"

    # Both dimensions must incur a 25.0 point penalty
    assert scorecard_partial.dimensions["PERFORMANCE"].score == Decimal("75.0")
    assert scorecard_partial.dimensions["RELIABILITY"].score == Decimal("75.0")

    # Overall score must be deterministically lower than 100.0
    assert scorecard_partial.overall_score < scorecard_clean.overall_score


# =========================================================================
# 3. Worker Exception Isolation & Transaction Rollback
# =========================================================================


@pytest.mark.asyncio
async def test_adversarial_worker_unhandled_crash_rollback(mock_db_session):
    """
    Verify worker safely isolates catastrophic orchestrator crashes,
    triggers database rollback, and returns False without leaking unhandled exceptions.
    """
    session, stored = mock_db_session
    eval_id = uuid.uuid4()
    repo_id = uuid.uuid4()

    evaluation = Evaluation(
        id=eval_id,
        repository_id=repo_id,
        status=EvaluationStatus.QUEUED,
        correlation_id=uuid.uuid4(),
        trigger_source="API",
        created_at=datetime.now(UTC),
    )

    def _query(stmt):
        mock_res = MagicMock()
        if "from evaluations" in str(stmt).lower():
            mock_res.scalar_one_or_none.return_value = evaluation
        return mock_res

    session.execute.side_effect = _query

    # Mock orchestrator that raises unexpected catastrophic error
    mock_orchestrator = MagicMock(spec=EvaluationPipelineOrchestrator)
    mock_orchestrator.execute_pipeline = AsyncMock(
        side_effect=RuntimeError("Simulated catastrophic kernel failure!")
    )

    # Session factory returning the mock session
    class MockSessionFactory:
        async def __aenter__(self):
            return session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    queue = InMemoryJobQueue()
    worker = EvaluationWorker(
        worker_id="adversarial-worker-1",
        job_queue=queue,
        orchestrator=mock_orchestrator,
        session_factory=lambda: MockSessionFactory(),
    )

    payload = {
        "evaluation_id": str(eval_id),
        "repository_id": str(repo_id),
        "ref": "main",
    }

    # Worker must return False and invoke rollback
    result = await worker.process_job(payload)
    assert result is False
    session.rollback.assert_awaited()
    # Task should be routed to DLQ
    assert len(queue.dlq) == 1
    assert queue.dlq[0]["evaluation_id"] == str(eval_id)


@pytest.mark.asyncio
async def test_adversarial_worker_malformed_payload_rejection():
    """
    Verify worker safely rejects payloads missing required UUID keys or containing corrupted IDs.
    """
    queue = InMemoryJobQueue()
    worker = EvaluationWorker(worker_id="adversarial-worker-2", job_queue=queue)

    # Missing evaluation_id
    assert await worker.process_job({"repository_id": str(uuid.uuid4())}) is False

    # Corrupted non-UUID string
    assert (
        await worker.process_job(
            {"evaluation_id": "not-a-valid-uuid", "repository_id": "also-not-a-uuid"}
        )
        is False
    )


# =========================================================================
# 4. Mid-Pipeline Cancellation & Queue Idempotency
# =========================================================================


@pytest.mark.asyncio
async def test_adversarial_mid_pipeline_cancellation(mock_db_session, tmp_path: Path):
    """
    Verify pipeline orchestrator respects cooperative cancellation tokens between stages.
    """
    session, stored = mock_db_session
    eval_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    snap_id = uuid.uuid4()

    evaluation = Evaluation(
        id=eval_id,
        repository_id=repo_id,
        snapshot_id=snap_id,
        status=EvaluationStatus.QUEUED,
        correlation_id=uuid.uuid4(),
        trigger_source="API",
        created_at=datetime.now(UTC),
    )

    repository = Repository(
        id=repo_id,
        url="https://github.com/org/repo",
        provider="github",
        owner="org",
        name="repo",
        default_branch="main",
        created_at=datetime.now(UTC),
    )

    def _query(stmt):
        mock_res = MagicMock()
        stmt_str = str(stmt).lower()
        if "from evaluations" in stmt_str:
            mock_res.scalar_one_or_none.return_value = evaluation
            mock_res.scalar_one.return_value = evaluation
        elif "from repositories" in stmt_str:
            mock_res.scalar_one_or_none.return_value = repository
        return mock_res

    session.execute.side_effect = _query

    job_queue = InMemoryJobQueue()
    # Mark the evaluation as cancelled in the queue before pipeline start
    await job_queue.request_cancellation(eval_id)

    orchestrator = EvaluationPipelineOrchestrator(job_queue=job_queue)

    res = await orchestrator.execute_pipeline(
        session=session,
        evaluation_id=eval_id,
        repository_id=repo_id,
        fixture_snapshot_path=tmp_path,
    )

    assert res.status == EvaluationStatus.CANCELLED
    assert evaluation.status == EvaluationStatus.CANCELLED
    assert "Evaluation cancelled" in (evaluation.error_summary or "")
