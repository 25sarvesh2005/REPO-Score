"""
Integration tests for the RuntimeDispatcher and isolated execution engine.
"""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from backend.repository.models import EvaluatorCategory, TechnologyDetectionResult
from backend.runtime.dispatcher import RuntimeDispatcher
from backend.runtime.models import EvaluatorType, RuntimeFailureCode
from backend.sandbox.interface import ISandbox, ISandboxManager
from backend.sandbox.models import NetworkPolicy, SandboxExecutionResult, SandboxState


def test_dispatcher_resolves_evaluators():
    disp = RuntimeDispatcher()

    # Web API
    det_web = TechnologyDetectionResult(evaluator_category=EvaluatorCategory.WEB_API)
    ev_web = disp.resolve_evaluator(det_web)
    assert ev_web.evaluator_type == EvaluatorType.HTTP_API

    # CLI Tool
    det_cli = TechnologyDetectionResult(evaluator_category=EvaluatorCategory.CLI_TOOL)
    ev_cli = disp.resolve_evaluator(det_cli)
    assert ev_cli.evaluator_type == EvaluatorType.CLI_TOOL

    # Library
    det_lib = TechnologyDetectionResult(evaluator_category=EvaluatorCategory.LIBRARY)
    ev_lib = disp.resolve_evaluator(det_lib)
    assert ev_lib.evaluator_type == EvaluatorType.LIBRARY

    # Background Worker
    det_wrk = TechnologyDetectionResult(evaluator_category=EvaluatorCategory.BACKGROUND_WORKER)
    ev_wrk = disp.resolve_evaluator(det_wrk)
    assert ev_wrk.evaluator_type == EvaluatorType.BACKGROUND_WORKER

    # Unsupported / Generic
    det_unsup = TechnologyDetectionResult(evaluator_category=EvaluatorCategory.UNSUPPORTED)
    ev_unsup = disp.resolve_evaluator(det_unsup)
    assert ev_unsup.evaluator_type == EvaluatorType.GENERIC_RUNNER


def test_dispatcher_resolve_sandbox_config_security_invariants(tmp_path: Path):
    disp = RuntimeDispatcher()
    det = TechnologyDetectionResult(
        primary_language="Python",
        evaluator_category=EvaluatorCategory.WEB_API,
    )
    cfg = disp.resolve_sandbox_config(tmp_path, det)

    # Security Invariants
    assert cfg.user == "10001:10001"
    assert cfg.read_only_rootfs is True
    assert cfg.cap_drop == ["ALL"]
    assert cfg.security_opt == ["no-new-privileges:true"]
    assert cfg.network_mode == NetworkPolicy.NONE
    assert cfg.memory_limit == "2048m"
    assert cfg.cpu_quota == 2.0
    assert cfg.pids_limit == 128
    assert cfg.image == "reposcore/sandbox-python:3.11-slim"


@pytest.mark.asyncio
async def test_dispatcher_executes_evaluation_end_to_end(tmp_path: Path):
    (tmp_path / "main.py").write_text("print('hello')\n")
    det = TechnologyDetectionResult(
        primary_language="Python",
        evaluator_category=EvaluatorCategory.CLI_TOOL,
    )

    sbx = AsyncMock(spec=ISandbox)
    sbx.state = SandboxState.RUNNING
    sbx.execute = AsyncMock(
        return_value=SandboxExecutionResult(
            exit_code=0, stdout="build ok\nmytool version 1.0", stderr=""
        )
    )
    sbx.get_stats = AsyncMock(return_value={"memory_usage": 1024, "memory_limit": 2048})

    async def _term():
        sbx.state = SandboxState.TERMINATED

    sbx.terminate = AsyncMock(side_effect=_term)

    mgr = AsyncMock(spec=ISandboxManager)
    mgr.is_available = AsyncMock(return_value=True)
    mgr.create_sandbox = AsyncMock(return_value=sbx)
    disp = RuntimeDispatcher()

    obs = await disp.execute_evaluation(
        snapshot_path=tmp_path,
        detection=det,
        sandbox_manager=mgr,
        context={"evaluation_id": "disp-eval-1"},
    )

    assert obs.evaluation_id == "disp-eval-1"
    assert obs.evaluator_type == EvaluatorType.CLI_TOOL
    assert obs.cli_metrics is not None
    assert obs.resource_metrics is not None
    assert sbx.state == SandboxState.TERMINATED


@pytest.mark.asyncio
async def test_dispatcher_refuses_execution_when_sandbox_unavailable(tmp_path: Path):
    det = TechnologyDetectionResult(
        primary_language="Python",
        evaluator_category=EvaluatorCategory.WEB_API,
    )
    mgr = AsyncMock(spec=ISandboxManager)
    mgr.is_available = AsyncMock(return_value=False)
    disp = RuntimeDispatcher()

    obs = await disp.execute_evaluation(
        snapshot_path=tmp_path,
        detection=det,
        sandbox_manager=mgr,
    )

    assert obs.failure_code == RuntimeFailureCode.SANDBOX_ERROR
    assert "unavailable on host" in (obs.failure_reason or "")
    assert "Prime Directive #4" in obs.critical_logs[0]


@pytest.mark.asyncio
async def test_dispatcher_handles_unsupported_archetype(tmp_path: Path):
    det = TechnologyDetectionResult(
        primary_language=None,
        evaluator_category=EvaluatorCategory.UNSUPPORTED,
    )
    sbx = AsyncMock(spec=ISandbox)
    sbx.state = SandboxState.RUNNING
    sbx.execute = AsyncMock(
        return_value=SandboxExecutionResult(exit_code=0, stdout="noop", stderr="")
    )
    sbx.get_stats = AsyncMock(return_value={"memory_usage": 1024, "memory_limit": 2048})
    sbx.terminate = AsyncMock()

    mgr = AsyncMock(spec=ISandboxManager)
    mgr.is_available = AsyncMock(return_value=True)
    mgr.create_sandbox = AsyncMock(return_value=sbx)
    disp = RuntimeDispatcher()

    obs = await disp.execute_evaluation(
        snapshot_path=tmp_path,
        detection=det,
        sandbox_manager=mgr,
    )

    assert obs.evaluator_type == EvaluatorType.GENERIC_RUNNER
    assert obs.failure_code == RuntimeFailureCode.UNSUPPORTED_TECH
