"""
Hardening, Reliability, Rate Limiting, and DLQ Tests.
Adheres strictly to Phase 17 specifications, FAILURE_MODEL.md, and AGENTS Prime Directives.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse

from backend.api.rate_limiter import RateLimitingMiddleware
from backend.core.config import settings
from backend.core.queue import InMemoryJobQueue
from backend.database.models import Evaluation
from backend.pipeline.orchestrator import EvaluationPipelineOrchestrator
from backend.pipeline.worker import EvaluationWorker
from backend.sandbox.mock import MockSandboxManager
from backend.sandbox.models import SandboxConfig


# =========================================================================
# 1. Rate Limiting Middleware Tests
# =========================================================================

def test_rate_limiter_within_limit():
    """Verify requests within rate limit pass through with rate limit headers."""
    app = FastAPI()
    app.add_middleware(RateLimitingMiddleware, requests_per_minute=10)

    @app.get("/api/v1/test")
    def sample_endpoint():
        return {"status": "ok"}

    client = TestClient(app)
    resp = client.get("/api/v1/test")
    assert resp.status_code == 200
    assert resp.headers["X-RateLimit-Limit"] == "10"
    assert int(resp.headers["X-RateLimit-Remaining"]) == 9
    assert "X-RateLimit-Reset" in resp.headers


def test_rate_limiter_exceeded_returns_429():
    """Verify requests exceeding rate limit receive HTTP 429 with RFC 7807 Problem Details."""
    app = FastAPI()
    app.add_middleware(RateLimitingMiddleware, requests_per_minute=3)

    @app.get("/api/v1/test")
    def sample_endpoint():
        return {"status": "ok"}

    client = TestClient(app)
    # First 3 requests succeed
    for _ in range(3):
        r = client.get("/api/v1/test")
        assert r.status_code == 200

    # 4th request must be rate-limited (HTTP 429)
    blocked = client.get("/api/v1/test")
    assert blocked.status_code == 429
    assert blocked.headers["content-type"] == "application/problem+json"
    assert blocked.headers["Retry-After"] == "60"
    assert blocked.headers["X-RateLimit-Remaining"] == "0"

    problem = blocked.json()
    assert problem["status"] == 429
    assert problem["title"] == "Too Many Requests"
    assert "rate-limit-exceeded" in problem["type"]


def test_rate_limiter_exempt_paths():
    """Verify health probes and metrics endpoints bypass rate limiting."""
    app = FastAPI()
    app.add_middleware(RateLimitingMiddleware, requests_per_minute=2)

    @app.get("/health")
    def health():
        return {"status": "healthy"}

    @app.get("/metrics")
    def metrics():
        return {"metrics": "data"}

    client = TestClient(app)
    # Exceed limit on health probes
    for _ in range(10):
        resp_h = client.get("/health")
        assert resp_h.status_code == 200

        resp_m = client.get("/metrics")
        assert resp_m.status_code == 200


# =========================================================================
# 2. Dead-Letter Queue (DLQ) & Worker Recovery Tests
# =========================================================================

@pytest.mark.asyncio
async def test_dead_letter_queue_push_and_inspection():
    """Verify job queue stores failed tasks into DLQ with reason and timestamp."""
    queue = InMemoryJobQueue()
    eval_id = uuid.uuid4()
    payload = {"repository_id": str(uuid.uuid4()), "ref": "main"}

    await queue.send_to_dlq(eval_id, payload, reason="Simulated infrastructure failure")

    assert len(queue.dlq) == 1
    dlq_entry = queue.dlq[0]
    assert dlq_entry["evaluation_id"] == str(eval_id)
    assert dlq_entry["payload"] == payload
    assert dlq_entry["reason"] == "Simulated infrastructure failure"
    assert "failed_at" in dlq_entry


@pytest.mark.asyncio
async def test_worker_crash_pushes_to_dlq():
    """Verify worker routes catastrophic unhandled failures to the Dead-Letter Queue."""
    eval_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    queue = InMemoryJobQueue()

    mock_orchestrator = MagicMock(spec=EvaluationPipelineOrchestrator)
    mock_orchestrator.execute_pipeline = AsyncMock(
        side_effect=RuntimeError("Unrecoverable database corruption")
    )

    evaluation = Evaluation(
        id=eval_id,
        repository_id=repo_id,
        status="QUEUED",
        correlation_id=uuid.uuid4(),
        trigger_source="API",
        created_at=datetime.now(timezone.utc),
    )

    mock_session = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = evaluation
    mock_session.execute.return_value = mock_res
    mock_session.flush = AsyncMock()
    mock_session.commit = AsyncMock()
    mock_session.rollback = AsyncMock()

    class MockSessionFactory:
        async def __aenter__(self):
            return mock_session

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    worker = EvaluationWorker(
        worker_id="test-hardening-worker",
        job_queue=queue,
        orchestrator=mock_orchestrator,
        session_factory=lambda: MockSessionFactory(),
    )

    payload = {
        "evaluation_id": str(eval_id),
        "repository_id": str(repo_id),
        "ref": "main",
    }

    result = await worker.process_job(payload)
    assert result is False

    # Verify task was pushed to DLQ
    assert len(queue.dlq) == 1
    assert queue.dlq[0]["evaluation_id"] == str(eval_id)
    assert "Unrecoverable database corruption" in queue.dlq[0]["reason"]


# =========================================================================
# 3. Sandbox Orphan Sweeper Simulation Tests
# =========================================================================

@pytest.mark.asyncio
async def test_mock_sandbox_orphan_cleanup():
    """Verify sandbox manager orphan cleanup terminates dangling active containers."""
    manager = MockSandboxManager()
    config = SandboxConfig(
        image="reposcore/sandbox-python:3.11-slim",
        workdir="/workspace/build",
    )

    # Spawn 3 sandboxes
    sbx1 = await manager.create_sandbox(config)
    sbx2 = await manager.create_sandbox(config)
    sbx3 = await manager.create_sandbox(config)

    assert len(manager._active_sandboxes) == 3

    # Run orphan cleanup sweep
    purged = await manager.cleanup_orphans(older_than_seconds=60)
    assert purged == 3
    assert len(manager._active_sandboxes) == 0
    assert sbx1.state.value == "TERMINATED"
    assert sbx2.state.value == "TERMINATED"
    assert sbx3.state.value == "TERMINATED"
