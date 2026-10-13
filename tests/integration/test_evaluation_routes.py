"""
Integration tests for Evaluation API endpoints (/api/v1/evaluations).
Adheres strictly to Phase 12 validation and contract requirements.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.app import create_app
from backend.api.schemas.contracts import (
    EvaluationStatus,
    EvidenceCategory,
    SeverityLevel,
)
from backend.core.queue import InMemoryJobQueue, set_job_queue
from backend.database.models import (
    AIAnalysis,
    Evaluation,
    Evidence,
    Recommendation,
    Repository,
    RuntimeObservation,
    Score,
    ScoreDimension,
)
from backend.database.session import get_db_session

app = create_app()
client = TestClient(app)


@pytest.fixture
def mock_db():
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    async def _get_db():
        yield session

    app.dependency_overrides[get_db_session] = _get_db
    yield session
    app.dependency_overrides.pop(get_db_session, None)


@pytest.fixture
def mock_queue():
    q = InMemoryJobQueue()
    set_job_queue(q)
    return q


def test_enqueue_evaluation_success(mock_db, mock_queue):
    repo_id = uuid.uuid4()
    repo = Repository(
        id=repo_id,
        url="https://github.com/fastapi/fastapi",
        provider="github",
        owner="fastapi",
        name="fastapi",
        default_branch="master",
        is_private=False,
        stars_count=75000,
        created_at=datetime.now(UTC),
    )

    # Mock DB queries: 1) find repo, 2) find snapshot
    mock_res_repo = MagicMock()
    mock_res_repo.scalar_one_or_none.return_value = repo

    mock_res_snap = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.first.return_value = None
    mock_res_snap.scalars.return_value = mock_scalars

    mock_db.execute.side_effect = [mock_res_repo, mock_res_snap]
    enqueue_evaluation = mock_queue.enqueue_evaluation

    async def enqueue_after_commit(*args, **kwargs):
        assert mock_db.commit.await_count == 1
        await enqueue_evaluation(*args, **kwargs)

    mock_queue.enqueue_evaluation = enqueue_after_commit

    response = client.post(
        "/api/v1/evaluations",
        json={
            "repository_id": str(repo_id),
            "ref": "master",
            "options": {"timeout_seconds": 600, "enable_ai_reasoning": True},
        },
    )

    assert response.status_code == 202
    data = response.json()
    assert data["status"] == "QUEUED"
    assert "evaluation_id" in data
    assert "status_url" in data
    assert len(mock_queue.queue) == 1


def test_enqueue_evaluation_repo_not_found(mock_db, mock_queue):
    mock_res_repo = MagicMock()
    mock_res_repo.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_res_repo

    unknown_id = uuid.uuid4()
    response = client.post(
        "/api/v1/evaluations",
        json={"repository_id": str(unknown_id)},
    )
    assert response.status_code == 404


def test_get_evaluation_status_polling(mock_db):
    eval_id = uuid.uuid4()
    evaluation = Evaluation(
        id=eval_id,
        repository_id=uuid.uuid4(),
        snapshot_id=uuid.uuid4(),
        status=EvaluationStatus.BUILDING,
        correlation_id=uuid.uuid4(),
        trigger_source="API",
        started_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        steps=[],
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = evaluation
    mock_db.execute.return_value = mock_result

    response = client.get(f"/api/v1/evaluations/{eval_id}/status")
    assert response.status_code == 200
    data = response.json()
    assert data["evaluation_id"] == str(eval_id)
    assert data["status"] == "BUILDING"
    assert data["is_terminal"] is False


def test_cancel_active_evaluation(mock_db, mock_queue):
    eval_id = uuid.uuid4()
    evaluation = Evaluation(
        id=eval_id,
        repository_id=uuid.uuid4(),
        snapshot_id=uuid.uuid4(),
        status=EvaluationStatus.BUILDING,
        correlation_id=uuid.uuid4(),
        trigger_source="API",
        started_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = evaluation
    mock_db.execute.return_value = mock_result

    response = client.post(f"/api/v1/evaluations/{eval_id}/cancel")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "CANCELLED"
    assert str(eval_id) in mock_queue.cancelled_tokens


def test_cancel_terminal_evaluation_conflict(mock_db):
    eval_id = uuid.uuid4()
    evaluation = Evaluation(
        id=eval_id,
        repository_id=uuid.uuid4(),
        snapshot_id=uuid.uuid4(),
        status=EvaluationStatus.COMPLETED,
        correlation_id=uuid.uuid4(),
        trigger_source="API",
        started_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = evaluation
    mock_db.execute.return_value = mock_result

    response = client.post(f"/api/v1/evaluations/{eval_id}/cancel")
    assert response.status_code == 409


def test_get_evaluation_score_finalized(mock_db):
    eval_id = uuid.uuid4()
    score_id = uuid.uuid4()
    score = Score(
        id=score_id,
        evaluation_id=eval_id,
        scoring_version="1.0.0",
        overall_score=Decimal("87.5"),
        grade="A",
        total_deductions=Decimal("12.5"),
        total_credits=Decimal("0.0"),
        created_at=datetime.now(UTC),
        dimensions=[
            ScoreDimension(
                id=uuid.uuid4(),
                score_id=score_id,
                dimension_name="Security",
                score=Decimal("80.0"),
                weight=Decimal("0.16"),
                base_score=Decimal("100.0"),
                itemized_receipt=[
                    {
                        "type": "DEDUCTION",
                        "rule_code": "SEC-001",
                        "evidence_id": str(uuid.uuid4()),
                        "description": "Hardcoded token",
                        "points": 20.0,
                        "confidence": 1.0,
                        "calculated_delta": 20.0,
                    }
                ],
                created_at=datetime.now(UTC),
            )
        ],
    )
    evaluation = Evaluation(
        id=eval_id,
        repository_id=uuid.uuid4(),
        snapshot_id=uuid.uuid4(),
        status=EvaluationStatus.COMPLETED,
        correlation_id=uuid.uuid4(),
        trigger_source="API",
        started_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        score=score,
        ai_analysis=None,
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = evaluation
    mock_db.execute.return_value = mock_result

    response = client.get(f"/api/v1/evaluations/{eval_id}/score")
    assert response.status_code == 200
    data = response.json()
    assert float(data["overall_score"]) == 87.5
    assert data["grade"] == "A"
    assert len(data["dimensions"]) == 1
    assert data["dimensions"][0]["dimension_name"] == "Security"
    assert len(data["dimensions"][0]["itemized_receipt"]) == 1


def test_get_evaluation_score_still_running_conflict(mock_db):
    eval_id = uuid.uuid4()
    evaluation = Evaluation(
        id=eval_id,
        repository_id=uuid.uuid4(),
        snapshot_id=uuid.uuid4(),
        status=EvaluationStatus.ANALYZING,
        correlation_id=uuid.uuid4(),
        trigger_source="API",
        started_at=datetime.now(UTC),
        created_at=datetime.now(UTC),
        score=None,
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = evaluation
    mock_db.execute.return_value = mock_result

    response = client.get(f"/api/v1/evaluations/{eval_id}/score")
    assert response.status_code == 409


def test_get_evaluation_evidence_paginated(mock_db):
    eval_id = uuid.uuid4()
    evaluation = Evaluation(
        id=eval_id,
        repository_id=uuid.uuid4(),
        snapshot_id=uuid.uuid4(),
        status=EvaluationStatus.COMPLETED,
        correlation_id=uuid.uuid4(),
        trigger_source="API",
    )
    ev_item = Evidence(
        id=uuid.uuid4(),
        evaluation_id=eval_id,
        source="semgrep",
        category=EvidenceCategory.SECURITY,
        severity=SeverityLevel.HIGH,
        confidence=0.9,
        fingerprint="fp12345",
        title="SQL Injection",
        description="Unsanitized parameter",
        location={"file_path": "app/db.py", "start_line": 20},
        created_at=datetime.now(UTC),
    )

    mock_res_eval = MagicMock()
    mock_res_eval.scalar_one_or_none.return_value = evaluation

    mock_res_count = MagicMock()
    mock_res_count.scalar.return_value = 1

    mock_res_items = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [ev_item]
    mock_res_items.scalars.return_value = mock_scalars

    mock_db.execute.side_effect = [mock_res_eval, mock_res_count, mock_res_items]

    response = client.get(f"/api/v1/evaluations/{eval_id}/evidence")
    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 1
    assert len(data["items"]) == 1
    assert data["items"][0]["title"] == "SQL Injection"
    assert data["items"][0]["location"]["file_path"] == "app/db.py"


def test_get_evaluation_runtime_telemetry(mock_db):
    eval_id = uuid.uuid4()
    evaluation = Evaluation(
        id=eval_id,
        repository_id=uuid.uuid4(),
        snapshot_id=uuid.uuid4(),
        status=EvaluationStatus.COMPLETED,
        correlation_id=uuid.uuid4(),
        trigger_source="API",
    )
    obs1 = RuntimeObservation(
        id=uuid.uuid4(),
        evaluation_id=eval_id,
        observation_type="BUILD",
        metadata_json={"exit_code": 0, "success": True},
    )
    obs2 = RuntimeObservation(
        id=uuid.uuid4(),
        evaluation_id=eval_id,
        observation_type="STARTUP",
        metadata_json={"ready": True, "port": 8000},
    )

    mock_res_eval = MagicMock()
    mock_res_eval.scalar_one_or_none.return_value = evaluation

    mock_res_obs = MagicMock()
    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [obs1, obs2]
    mock_res_obs.scalars.return_value = mock_scalars

    mock_db.execute.side_effect = [mock_res_eval, mock_res_obs]

    response = client.get(f"/api/v1/evaluations/{eval_id}/runtime")
    assert response.status_code == 200
    data = response.json()
    assert data["build_success"] is True
    assert data["startup_ready"] is True
    assert data["startup_port"] == 8000


def test_get_evaluation_ai_interpretation(mock_db):
    eval_id = uuid.uuid4()
    ai_id = uuid.uuid4()
    ai_analysis = AIAnalysis(
        id=ai_id,
        evaluation_id=eval_id,
        provider="ollama",
        model_name="llama3.2:3b",
        prompt_version="1.0.0",
        executive_summary="Solid Python library.",
        architectural_assessment="Well decoupled.",
        security_risk_narrative="No critical CVEs.",
        tokens_consumed=450,
        duration_ms=1200,
        recommendations=[
            Recommendation(
                id=uuid.uuid4(),
                ai_analysis_id=ai_id,
                title="Add type hints",
                category="CORRECTNESS",
                priority="LOW",
                explanation="Improves clarity",
                actionable_steps=["Run mypy"],
                related_evidence_ids=[],
            )
        ],
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = ai_analysis
    mock_db.execute.return_value = mock_result

    response = client.get(f"/api/v1/evaluations/{eval_id}/ai")
    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "ollama"
    assert data["executive_summary"] == "Solid Python library."
    assert len(data["recommendations"]) == 1
    assert data["recommendations"][0]["title"] == "Add type hints"
