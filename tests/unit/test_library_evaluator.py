"""
Unit tests for LibraryEvaluator and native test parsers.
"""

from pathlib import Path
import pytest

from backend.repository.models import EvaluatorCategory, TechnologyDetectionResult
from backend.runtime.library_evaluator import (
    LibraryEvaluator,
    parse_cargo_output,
    parse_go_output,
    parse_jest_output,
    parse_pytest_output,
)
from backend.runtime.models import EvaluatorType, RuntimeFailureCode, TestOrigin
from backend.sandbox.mock import MockSandbox
from backend.sandbox.models import SandboxConfig, SandboxExecutionResult


def test_parse_pytest_output():
    raw = """
tests/test_math.py::test_add PASSED
tests/test_math.py::test_sub PASSED
tests/test_math.py::test_div FAILED
tests/test_math.py::test_skip SKIPPED
TOTAL                                         100     15    85%
================= 2 passed, 1 failed, 1 skipped in 0.45s =================
"""
    total, passed, failed, skipped, cases, cov = parse_pytest_output(raw)
    assert total == 4
    assert passed == 2
    assert failed == 1
    assert skipped == 1
    assert cov == 85.0
    assert len(cases) == 4
    assert cases[0].origin == TestOrigin.REPOSITORY_PROVIDED
    assert cases[0].passed is True
    assert cases[2].passed is False


def test_parse_jest_output():
    raw = """
Tests:       1 failed, 2 skipped, 10 passed, 13 total
Snapshots:   0 total
Time:        1.234 s
"""
    total, passed, failed, skipped, cases, cov = parse_jest_output(raw)
    assert total == 13
    assert passed == 10
    assert failed == 1
    assert skipped == 2


def test_parse_cargo_output():
    raw = "test result: ok. 15 passed; 0 failed; 2 ignored; 0 measured; 0 filtered out"
    total, passed, failed, skipped, cases, cov = parse_cargo_output(raw)
    assert total == 17
    assert passed == 15
    assert failed == 0
    assert skipped == 2


def test_parse_go_output():
    raw = """
=== RUN   TestAdd
--- PASS: TestAdd (0.00s)
=== RUN   TestSubtract
--- FAIL: TestSubtract (0.00s)
FAIL
"""
    total, passed, failed, skipped, cases, cov = parse_go_output(raw)
    assert total == 2
    assert passed == 1
    assert failed == 1


@pytest.mark.asyncio
async def test_library_evaluator_execution(tmp_path: Path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_sample.py").write_text("def test_ok(): pass\n")

    det = TechnologyDetectionResult(
        primary_language="Python",
        detected_test_runners=["pytest"],
        evaluator_category=EvaluatorCategory.LIBRARY,
    )
    cfg = SandboxConfig(image="reposcore/sandbox-python:3.11-slim")

    def test_handler(cmd):
        cmd_str = " ".join(cmd)
        if "pytest" in cmd_str:
            return SandboxExecutionResult(
                exit_code=0,
                stdout="tests/test_sample.py::test_ok PASSED\n=== 1 passed in 0.12s ===",
                stderr="",
                duration_ms=120,
            )
        return SandboxExecutionResult(exit_code=0, stdout="ok", stderr="")

    sbx = MockSandbox("sbx-lib-1", cfg, command_handler=test_handler)
    ev = LibraryEvaluator()
    obs = await ev.evaluate(sbx, tmp_path, det, context={"evaluation_id": "test-lib"})

    assert obs.evaluation_id == "test-lib"
    assert obs.evaluator_type == EvaluatorType.LIBRARY
    assert obs.test_metrics is not None
    assert obs.test_metrics.tests_total == 1
    assert obs.test_metrics.tests_passed == 1
    assert obs.test_metrics.tests_failed == 0
    assert obs.failure_code is None


@pytest.mark.asyncio
async def test_library_evaluator_test_failure(tmp_path: Path):
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()

    det = TechnologyDetectionResult(
        primary_language="Python",
        detected_test_runners=["pytest"],
        evaluator_category=EvaluatorCategory.LIBRARY,
    )
    cfg = SandboxConfig(image="reposcore/sandbox-python:3.11-slim")

    def fail_handler(cmd):
        cmd_str = " ".join(cmd)
        if "pytest" in cmd_str:
            return SandboxExecutionResult(
                exit_code=1,
                stdout="tests/test_sample.py::test_fail FAILED\n=== 1 failed in 0.12s ===",
                stderr="",
                duration_ms=120,
            )
        return SandboxExecutionResult(exit_code=0, stdout="ok", stderr="")

    sbx = MockSandbox("sbx-lib-fail", cfg, command_handler=fail_handler)
    ev = LibraryEvaluator()
    obs = await ev.evaluate(sbx, tmp_path, det)

    assert obs.test_metrics is not None
    assert obs.test_metrics.tests_failed == 1
    assert obs.failure_code == RuntimeFailureCode.TEST_EXECUTION_FAILURE
