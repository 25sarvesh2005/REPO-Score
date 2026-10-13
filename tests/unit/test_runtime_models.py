"""
Unit tests for runtime domain models, metrics, and evidence derivation.
"""

from backend.api.schemas.contracts import EvidenceCategory, SeverityLevel
from backend.runtime.models import (
    BuildResult,
    CliMetrics,
    EvaluatorType,
    HttpMetrics,
    RuntimeFailureCode,
    RuntimeObservation,
    StartupResult,
    TestMetrics,
    TestOrigin,
    WorkerMetrics,
)


def test_evaluator_type_and_test_origin_enums():
    assert EvaluatorType.HTTP_API == "HTTP_API"
    assert EvaluatorType.CLI_TOOL == "CLI_TOOL"
    assert EvaluatorType.LIBRARY == "LIBRARY"
    assert EvaluatorType.BACKGROUND_WORKER == "BACKGROUND_WORKER"
    assert EvaluatorType.GENERIC_RUNNER == "GENERIC_RUNNER"
    assert EvaluatorType.UNSUPPORTED == "UNSUPPORTED"

    assert TestOrigin.REPOSITORY_PROVIDED == "REPOSITORY_PROVIDED"
    assert TestOrigin.PLATFORM_DETERMINISTIC == "PLATFORM_DETERMINISTIC"
    assert TestOrigin.AI_GENERATED == "AI_GENERATED"
    assert TestOrigin.RUNTIME_SCENARIO == "RUNTIME_SCENARIO"
    assert TestOrigin.SECURITY == "SECURITY"


def test_runtime_failure_codes():
    assert RuntimeFailureCode.BUILD_FAILURE == "BUILD_FAILURE"
    assert RuntimeFailureCode.STARTUP_TIMEOUT == "STARTUP_TIMEOUT"
    assert RuntimeFailureCode.CRASH_ON_BOOT == "CRASH_ON_BOOT"
    assert RuntimeFailureCode.OOM_KILLED == "OOM_KILLED"
    assert RuntimeFailureCode.HIGH_ERROR_RATE == "HIGH_ERROR_RATE"
    assert RuntimeFailureCode.ZOMBIE_ON_SHUTDOWN == "ZOMBIE_ON_SHUTDOWN"
    assert RuntimeFailureCode.TEST_EXECUTION_FAILURE == "TEST_EXECUTION_FAILURE"
    assert RuntimeFailureCode.SANDBOX_ERROR == "SANDBOX_ERROR"


def test_http_metrics_error_rate():
    metrics = HttpMetrics(
        total_requests=100,
        successful_requests=90,
        error_5xx_requests=10,
        error_4xx_requests=0,
    )
    assert metrics.error_rate == 0.10

    empty_metrics = HttpMetrics(total_requests=0)
    assert empty_metrics.error_rate == 0.0


def test_to_evidence_items_build_failure():
    obs = RuntimeObservation(
        evaluation_id="eval-123",
        evaluator_type=EvaluatorType.HTTP_API,
        build_result=BuildResult(
            success=False,
            exit_code=1,
            stderr="pip: command not found or dependency unresolvable",
            command=["pip", "install", "-r", "requirements.txt"],
        ),
        failure_code=RuntimeFailureCode.BUILD_FAILURE,
    )

    findings = obs.to_evidence_items()
    assert len(findings) == 1
    f = findings[0]
    assert f.rule_id == "RUN-BUILD-001-FAILURE"
    assert f.category == EvidenceCategory.CORRECTNESS
    assert f.severity == SeverityLevel.CRITICAL
    assert f.confidence == 1.0
    assert "Build Failed" in f.title
    assert f.raw_evidence["exit_code"] == 1


def test_to_evidence_items_crash_on_boot_and_oom():
    obs = RuntimeObservation(
        evaluation_id="eval-123",
        evaluator_type=EvaluatorType.HTTP_API,
        startup_result=StartupResult(
            success=False,
            exit_code=137,
            failure_message="Killed by SIGKILL",
        ),
        failure_code=RuntimeFailureCode.OOM_KILLED,
        unhandled_exceptions=["MemoryError: Out of memory"],
    )

    findings = obs.to_evidence_items()
    rule_ids = {f.rule_id for f in findings}
    assert "RUN-BOOT-001-STARTUP-FAILED" in rule_ids
    assert "RUN-RES-001-OOM-KILLED" in rule_ids
    assert "RUN-EXC-001-UNHANDLED" in rule_ids


def test_to_evidence_items_http_metrics():
    obs = RuntimeObservation(
        evaluation_id="eval-123",
        evaluator_type=EvaluatorType.HTTP_API,
        http_metrics=HttpMetrics(
            total_requests=50,
            successful_requests=40,
            error_5xx_requests=10,
            latency_p95_ms=2500.0,
            endpoints_tested=["/health"],
        ),
    )

    findings = obs.to_evidence_items()
    rule_ids = {f.rule_id for f in findings}
    assert "RUN-HTTP-001-HIGH-ERROR-RATE" in rule_ids
    assert "RUN-HTTP-002-HIGH-LATENCY" in rule_ids


def test_to_evidence_items_test_metrics_passed_and_failed():
    # Failing tests
    obs_fail = RuntimeObservation(
        evaluation_id="eval-123",
        evaluator_type=EvaluatorType.LIBRARY,
        test_metrics=TestMetrics(
            tests_total=10,
            tests_passed=8,
            tests_failed=2,
            test_runner="pytest",
        ),
    )
    findings_fail = obs_fail.to_evidence_items()
    assert len(findings_fail) == 1
    assert findings_fail[0].rule_id == "RUN-TEST-001-FAILURES"
    assert findings_fail[0].severity == SeverityLevel.HIGH

    # Passing tests
    obs_pass = RuntimeObservation(
        evaluation_id="eval-123",
        evaluator_type=EvaluatorType.LIBRARY,
        test_metrics=TestMetrics(
            tests_total=15,
            tests_passed=15,
            tests_failed=0,
            test_runner="pytest",
        ),
    )
    findings_pass = obs_pass.to_evidence_items()
    assert len(findings_pass) == 1
    assert findings_pass[0].rule_id == "RUN-TEST-002-ALL-PASSED"
    assert findings_pass[0].severity == SeverityLevel.INFO


def test_to_evidence_items_cli_and_worker_resilience():
    obs = RuntimeObservation(
        evaluation_id="eval-123",
        evaluator_type=EvaluatorType.CLI_TOOL,
        cli_metrics=CliMetrics(
            invalid_args_tested=True,
            invalid_args_clean_error=False,
            invalid_args_exit_code=1,
        ),
        worker_metrics=WorkerMetrics(
            clean_sigterm_exit=False,
            termination_duration_ms=6000,
        ),
    )
    findings = obs.to_evidence_items()
    rule_ids = {f.rule_id for f in findings}
    assert "RUN-CLI-001-UNCLEAN-ERROR" in rule_ids
    assert "RUN-WRK-001-ZOMBIE-SHUTDOWN" in rule_ids
