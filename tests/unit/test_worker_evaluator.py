"""
Unit tests for WorkerEvaluator.
"""

from pathlib import Path
import pytest

from backend.repository.models import EvaluatorCategory, TechnologyDetectionResult
from backend.runtime.models import EvaluatorType, RuntimeFailureCode
from backend.runtime.worker_evaluator import WorkerEvaluator
from backend.sandbox.mock import MockSandbox
from backend.sandbox.models import SandboxConfig, SandboxExecutionResult


def test_worker_evaluator_can_evaluate():
    ev = WorkerEvaluator()
    assert ev.evaluator_type == EvaluatorType.BACKGROUND_WORKER

    det_worker = TechnologyDetectionResult(evaluator_category=EvaluatorCategory.BACKGROUND_WORKER)
    assert ev.can_evaluate(det_worker) is True

    det_web = TechnologyDetectionResult(evaluator_category=EvaluatorCategory.WEB_API)
    assert ev.can_evaluate(det_web) is False


@pytest.mark.asyncio
async def test_worker_evaluator_stability(tmp_path: Path):
    (tmp_path / "worker.py").write_text("import time\nprint('starting worker: ready')\n")
    det = TechnologyDetectionResult(
        primary_language="Python",
        evaluator_category=EvaluatorCategory.BACKGROUND_WORKER,
    )
    cfg = SandboxConfig(image="reposcore/sandbox-python:3.11-slim")

    def worker_handler(cmd):
        cmd_str = " ".join(cmd)
        if "worker.py" in cmd_str:
            return SandboxExecutionResult(
                exit_code=0,
                stdout="starting worker: ready\nheartbeat ok\n",
                stderr="",
                timed_out=True,
                duration_ms=10000,
            )
        return SandboxExecutionResult(exit_code=0, stdout="ok", stderr="")

    sbx = MockSandbox("sbx-worker-1", cfg, command_handler=worker_handler)
    ev = WorkerEvaluator()
    obs = await ev.evaluate(sbx, tmp_path, det, context={"evaluation_id": "test-worker"})

    assert obs.evaluation_id == "test-worker"
    assert obs.evaluator_type == EvaluatorType.BACKGROUND_WORKER
    assert obs.worker_metrics is not None
    assert obs.worker_metrics.heartbeat_detected is True
    assert obs.worker_metrics.clean_sigterm_exit is True
    assert obs.failure_code is None


@pytest.mark.asyncio
async def test_worker_evaluator_premature_crash(tmp_path: Path):
    (tmp_path / "worker.py").write_text("raise RuntimeError('broker unreachable')\n")
    det = TechnologyDetectionResult(
        primary_language="Python",
        evaluator_category=EvaluatorCategory.BACKGROUND_WORKER,
    )
    cfg = SandboxConfig(image="reposcore/sandbox-python:3.11-slim")

    def crash_handler(cmd):
        cmd_str = " ".join(cmd)
        if "worker.py" in cmd_str:
            return SandboxExecutionResult(
                exit_code=1,
                stdout="",
                stderr="Traceback (most recent call last):\nRuntimeError: broker unreachable",
                timed_out=False,
                duration_ms=200,
            )
        return SandboxExecutionResult(exit_code=0, stdout="ok", stderr="")

    sbx = MockSandbox("sbx-worker-crash", cfg, command_handler=crash_handler)
    ev = WorkerEvaluator()
    obs = await ev.evaluate(sbx, tmp_path, det)

    assert obs.worker_metrics is not None
    assert obs.worker_metrics.clean_sigterm_exit is False
    assert obs.failure_code == RuntimeFailureCode.CRASH_ON_BOOT
    assert len(obs.unhandled_exceptions) > 0
