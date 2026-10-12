"""
Unit tests for HttpApiEvaluator.
"""

from pathlib import Path
import pytest

from backend.repository.models import EvaluatorCategory, TechnologyDetectionResult
from backend.runtime.http_evaluator import HttpApiEvaluator
from backend.runtime.models import EvaluatorType, RuntimeFailureCode
from backend.sandbox.mock import MockSandbox
from backend.sandbox.models import SandboxConfig, SandboxExecutionResult


def test_http_evaluator_can_evaluate():
    ev = HttpApiEvaluator()
    assert ev.evaluator_type == EvaluatorType.HTTP_API

    det_web = TechnologyDetectionResult(evaluator_category=EvaluatorCategory.WEB_API)
    assert ev.can_evaluate(det_web) is True

    det_cli = TechnologyDetectionResult(evaluator_category=EvaluatorCategory.CLI_TOOL)
    assert ev.can_evaluate(det_cli) is False


def test_http_evaluator_resolve_startup_command(tmp_path: Path):
    ev = HttpApiEvaluator()
    (tmp_path / "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()\n")
    det = TechnologyDetectionResult(
        primary_language="Python",
        detected_frameworks=["FastAPI"],
        evaluator_category=EvaluatorCategory.WEB_API,
    )
    cmd = ev.resolve_startup_command(tmp_path, det, port=8000)
    assert cmd == ["uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000"]


@pytest.mark.asyncio
async def test_http_evaluator_success(tmp_path: Path):
    (tmp_path / "main.py").write_text("app = 1")
    det = TechnologyDetectionResult(
        primary_language="Python",
        detected_frameworks=["FastAPI"],
        evaluator_category=EvaluatorCategory.WEB_API,
    )
    cfg = SandboxConfig(image="reposcore/sandbox-python:3.11-slim")
    sbx = MockSandbox("sbx-http-1", cfg)

    ev = HttpApiEvaluator()
    obs = await ev.evaluate(sbx, tmp_path, det, context={"evaluation_id": "test-http"})

    assert obs.evaluation_id == "test-http"
    assert obs.evaluator_type == EvaluatorType.HTTP_API
    assert obs.startup_result is not None
    assert obs.startup_result.success is True
    assert obs.startup_result.ready is True
    assert obs.http_metrics is not None
    assert obs.http_metrics.total_requests == 50
    assert obs.failure_code is None


@pytest.mark.asyncio
async def test_http_evaluator_boot_crash(tmp_path: Path):
    (tmp_path / "main.py").write_text("app = 1")
    det = TechnologyDetectionResult(
        primary_language="Python",
        detected_frameworks=["FastAPI"],
        evaluator_category=EvaluatorCategory.WEB_API,
    )
    cfg = SandboxConfig(image="reposcore/sandbox-python:3.11-slim")

    def crash_handler(cmd):
        cmd_str = " ".join(cmd)
        if "urllib.request" in cmd_str:
            return SandboxExecutionResult(
                exit_code=1,
                stdout="{}",
                stderr="Traceback (most recent call last):\n  File 'main.py', line 1, in <module>\n    import nonexistent\nModuleNotFoundError: No module named 'nonexistent'",
                duration_ms=50,
            )
        return SandboxExecutionResult(exit_code=0, stdout="build ok", stderr="", duration_ms=10)

    sbx = MockSandbox("sbx-http-crash", cfg, command_handler=crash_handler)
    ev = HttpApiEvaluator()
    obs = await ev.evaluate(sbx, tmp_path, det)

    assert obs.startup_result is not None
    assert obs.startup_result.success is False
    assert obs.failure_code == RuntimeFailureCode.CRASH_ON_BOOT
    assert len(obs.unhandled_exceptions) > 0


@pytest.mark.asyncio
async def test_http_evaluator_startup_timeout(tmp_path: Path):
    (tmp_path / "main.py").write_text("app = 1")
    det = TechnologyDetectionResult(
        primary_language="Python",
        detected_frameworks=["FastAPI"],
        evaluator_category=EvaluatorCategory.WEB_API,
    )
    cfg = SandboxConfig(image="reposcore/sandbox-python:3.11-slim")

    def timeout_handler(cmd):
        cmd_str = " ".join(cmd)
        if "urllib.request" in cmd_str:
            return SandboxExecutionResult(
                exit_code=124,
                stdout="",
                stderr="Polling timed out",
                timed_out=True,
                duration_ms=30000,
            )
        return SandboxExecutionResult(exit_code=0, stdout="ok", stderr="")

    sbx = MockSandbox("sbx-http-timeout", cfg, command_handler=timeout_handler)
    ev = HttpApiEvaluator()
    obs = await ev.evaluate(sbx, tmp_path, det)

    assert obs.startup_result is not None
    assert obs.startup_result.timed_out is True
    assert obs.failure_code == RuntimeFailureCode.STARTUP_TIMEOUT
