"""
Unit tests for production-grade hardening:
1. Dynamic sandbox provider resolution (mock vs docker vs auto)
2. Sandbox image resolution and fallback
3. Concurrency safety in orchestrator step completion
4. Worker fatal error status persistence to FAILED
"""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.api.schemas.contracts import EvaluationStatus
from backend.core.config import Settings
from backend.database.models import Evaluation, EvaluationStep
from backend.pipeline.models import StepExecutionLog, StepStatus
from backend.pipeline.orchestrator import EvaluationPipelineOrchestrator
from backend.pipeline.worker import EvaluationWorker
from backend.sandbox.docker import DockerSandboxManager


def test_sandbox_provider_setting_validation():
    """Verify SANDBOX_PROVIDER strictly accepts docker and rejects mock or unhardened providers."""
    s1 = Settings(SANDBOX_PROVIDER="docker")
    assert s1.SANDBOX_PROVIDER == "docker"

    s2 = Settings(SANDBOX_PROVIDER="DOCKER")
    assert s2.SANDBOX_PROVIDER == "docker"

    with pytest.raises(ValueError):
        Settings(SANDBOX_PROVIDER="mock")

    with pytest.raises(ValueError):
        Settings(SANDBOX_PROVIDER="auto")

    with pytest.raises(ValueError):
        Settings(SANDBOX_PROVIDER="invalid-provider")


def test_resolve_sandbox_manager_modes():
    """Verify orchestrator strictly resolves DockerSandboxManager in production."""
    mgr = EvaluationPipelineOrchestrator._resolve_sandbox_manager()
    assert isinstance(mgr, DockerSandboxManager)


@pytest.mark.asyncio
async def test_docker_sandbox_manager_image_fallback():
    """Verify DockerSandboxManager gracefully resolves to official base image when custom image is absent."""
    mgr = DockerSandboxManager()
    with patch.object(mgr, "_image_exists_locally", AsyncMock(return_value=False)):
        resolved = await mgr._resolve_image("reposcore/sandbox-python:3.11-slim")
        assert resolved == "python:3.11-slim"

        resolved_node = await mgr._resolve_image("reposcore/sandbox-node:20-slim")
        assert resolved_node == "node:20-slim"

    with patch.object(mgr, "_image_exists_locally", AsyncMock(return_value=True)):
        resolved_custom = await mgr._resolve_image("reposcore/sandbox-python:3.11-slim")
        assert resolved_custom == "reposcore/sandbox-python:3.11-slim"


@pytest.mark.asyncio
async def test_complete_step_disambiguates_by_step_id():
    """Verify _complete_step updates the exact step targeted by step_id, avoiding cross-evaluation races."""
    orch = EvaluationPipelineOrchestrator(sandbox_manager=AsyncMock())

    eval_a_id = uuid.uuid4()
    step_a_id = uuid.uuid4()

    step_a = EvaluationStep(
        id=step_a_id,
        evaluation_id=eval_a_id,
        step_name="ANALYZING",
        status="RUNNING",
        started_at=datetime.now(UTC),
    )

    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.first.return_value = step_a
    session.execute = AsyncMock(return_value=mock_result)

    log_a = StepExecutionLog(
        step_name="ANALYZING",
        status=StepStatus.RUNNING,
        started_at=datetime.now(UTC),
        step_id=step_a_id,
        evaluation_id=eval_a_id,
    )

    await orch._complete_step(session, log_a, StepStatus.SUCCESS)

    assert step_a.status == "SUCCESS"
    session.commit.assert_awaited()
    call_args = session.execute.call_args[0][0]
    compiled_stmt = str(call_args.compile())
    assert "evaluation_steps.id =" in compiled_stmt


@pytest.mark.asyncio
async def test_worker_persists_failed_status_on_fatal_exception():
    """Verify that if an unhandled pipeline error occurs, worker marks evaluation as FAILED in DB."""
    eval_id = uuid.uuid4()
    repo_id = uuid.uuid4()

    mock_queue = AsyncMock()
    mock_orch = MagicMock(spec=EvaluationPipelineOrchestrator)
    mock_orch.execute_pipeline = AsyncMock(
        side_effect=RuntimeError("Simulated infrastructure crash")
    )

    eval_row = Evaluation(
        id=eval_id,
        repository_id=repo_id,
        status=EvaluationStatus.QUEUED,
        correlation_id=uuid.uuid4(),
    )

    session = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = eval_row
    session.execute = AsyncMock(return_value=mock_res)

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def mock_session_factory():
        yield session

    worker = EvaluationWorker(
        worker_id="test-resilience-worker",
        job_queue=mock_queue,
        orchestrator=mock_orch,
        session_factory=mock_session_factory,
    )

    success = await worker.process_job(
        {
            "evaluation_id": str(eval_id),
            "repository_id": str(repo_id),
        }
    )

    assert success is False
    assert eval_row.status == EvaluationStatus.FAILED
    assert "Simulated infrastructure crash" in eval_row.error_summary
    mock_queue.send_to_dlq.assert_awaited_once()
