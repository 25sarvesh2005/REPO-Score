"""
Unit tests for CliEvaluator.
"""

from pathlib import Path

import pytest

from backend.repository.models import EvaluatorCategory, TechnologyDetectionResult
from backend.runtime.cli_evaluator import CliEvaluator
from backend.runtime.models import EvaluatorType
from backend.sandbox.models import SandboxExecutionResult


def test_cli_evaluator_can_evaluate():
    ev = CliEvaluator()
    assert ev.evaluator_type == EvaluatorType.CLI_TOOL

    det_cli = TechnologyDetectionResult(evaluator_category=EvaluatorCategory.CLI_TOOL)
    assert ev.can_evaluate(det_cli) is True

    det_web = TechnologyDetectionResult(evaluator_category=EvaluatorCategory.WEB_API)
    assert ev.can_evaluate(det_web) is False


def test_cli_evaluator_resolve_cli_command(tmp_path: Path):
    ev = CliEvaluator()
    (tmp_path / "cli.py").write_text("import click\n")
    det = TechnologyDetectionResult(
        primary_language="Python",
        detected_frameworks=["Click"],
        evaluator_category=EvaluatorCategory.CLI_TOOL,
    )
    cmd = ev.resolve_cli_command(tmp_path, det)
    assert cmd == ["python", "cli.py"]


@pytest.mark.asyncio
async def test_cli_evaluator_success_and_resilience(tmp_path: Path, make_mock_sandbox):
    (tmp_path / "main.py").write_text("print('hello')")
    det = TechnologyDetectionResult(
        primary_language="Python",
        evaluator_category=EvaluatorCategory.CLI_TOOL,
    )

    def cli_handler(cmd, *args, **kwargs):
        cmd_str = " ".join(cmd)
        if "--help" in cmd_str:
            return SandboxExecutionResult(
                exit_code=0,
                stdout="Usage: mytool [OPTIONS]\nOptions:\n  --help Show this message",
                stderr="",
                duration_ms=10,
            )
        if "--version" in cmd_str:
            return SandboxExecutionResult(
                exit_code=0,
                stdout="mytool version 1.2.3",
                stderr="",
                duration_ms=10,
            )
        if "--invalid-flag" in cmd_str:
            return SandboxExecutionResult(
                exit_code=2,
                stdout="",
                stderr="Error: No such option: --invalid-flag-reposcore-probe",
                duration_ms=10,
            )
        return SandboxExecutionResult(exit_code=0, stdout="build ok", stderr="", duration_ms=10)

    sbx = make_mock_sandbox(cli_handler)
    ev = CliEvaluator()
    obs = await ev.evaluate(sbx, tmp_path, det, context={"evaluation_id": "test-cli"})

    assert obs.evaluation_id == "test-cli"
    assert obs.evaluator_type == EvaluatorType.CLI_TOOL
    assert obs.cli_metrics is not None
    assert obs.cli_metrics.help_tested is True
    assert obs.cli_metrics.help_exit_code == 0
    assert obs.cli_metrics.version_tested is True
    assert obs.cli_metrics.version_output == "mytool version 1.2.3"
    assert obs.cli_metrics.invalid_args_tested is True
    assert obs.cli_metrics.invalid_args_exit_code == 2
    assert obs.cli_metrics.invalid_args_clean_error is True


@pytest.mark.asyncio
async def test_cli_evaluator_unhandled_crash_on_invalid_args(tmp_path: Path, make_mock_sandbox):
    (tmp_path / "main.py").write_text("print('hello')")
    det = TechnologyDetectionResult(
        primary_language="Python",
        evaluator_category=EvaluatorCategory.CLI_TOOL,
    )

    def crashing_cli_handler(cmd, *args, **kwargs):
        cmd_str = " ".join(cmd)
        if "--invalid-flag" in cmd_str:
            return SandboxExecutionResult(
                exit_code=1,
                stdout="",
                stderr="Traceback (most recent call last):\n  File 'main.py', line 12, in <module>\nIndexError: list index out of range",
                duration_ms=10,
            )
        return SandboxExecutionResult(exit_code=0, stdout="ok", stderr="")

    sbx = make_mock_sandbox(crashing_cli_handler)
    ev = CliEvaluator()
    obs = await ev.evaluate(sbx, tmp_path, det)

    assert obs.cli_metrics is not None
    assert obs.cli_metrics.invalid_args_clean_error is False
    assert len(obs.unhandled_exceptions) > 0
