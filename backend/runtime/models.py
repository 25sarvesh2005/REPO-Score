"""
Domain models and schema definitions for the isolated runtime evaluation engine.
Adheres strictly to EVIDENCE_ARCHITECTURE.md, RUNTIME_ARCHITECTURE.md, and ADR-009.
"""

from enum import Enum
import hashlib
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from backend.analyzers.models import FindingLocation, NormalizedFinding
from backend.api.schemas.contracts import EvidenceCategory, SeverityLevel


class EvaluatorType(str, Enum):
    """Categorical runtime evaluation strategy."""
    HTTP_API = "HTTP_API"
    CLI_TOOL = "CLI_TOOL"
    LIBRARY = "LIBRARY"
    BACKGROUND_WORKER = "BACKGROUND_WORKER"
    GENERIC_RUNNER = "GENERIC_RUNNER"
    UNSUPPORTED = "UNSUPPORTED"


class TestOrigin(str, Enum):
    """Origin and provenance classification for executed tests (EVAL-029)."""
    __test__ = False
    REPOSITORY_PROVIDED = "REPOSITORY_PROVIDED"
    PLATFORM_DETERMINISTIC = "PLATFORM_DETERMINISTIC"
    AI_GENERATED = "AI_GENERATED"
    RUNTIME_SCENARIO = "RUNTIME_SCENARIO"
    SECURITY = "SECURITY"


class RuntimeFailureCode(str, Enum):
    """Structured failure categories for build, startup, and execution."""
    BUILD_FAILURE = "BUILD_FAILURE"
    STARTUP_TIMEOUT = "STARTUP_TIMEOUT"
    CRASH_ON_BOOT = "CRASH_ON_BOOT"
    OOM_KILLED = "OOM_KILLED"
    HIGH_ERROR_RATE = "HIGH_ERROR_RATE"
    ZOMBIE_ON_SHUTDOWN = "ZOMBIE_ON_SHUTDOWN"
    TEST_EXECUTION_FAILURE = "TEST_EXECUTION_FAILURE"
    DEPENDENCY_INSTALL_FAILED = "DEPENDENCY_INSTALL_FAILED"
    SANDBOX_ERROR = "SANDBOX_ERROR"
    TIMEOUT = "TIMEOUT"
    UNSUPPORTED_TECH = "UNSUPPORTED_TECH"


class BuildResult(BaseModel):
    """Outcome of dependency installation and compilation inside the sandbox (EVAL-021 to EVAL-024)."""
    success: bool = Field(..., description="Whether build completed with zero exit code")
    duration_ms: int = Field(default=0, ge=0, description="Build execution time in milliseconds")
    exit_code: int = Field(default=0, description="Process exit code")
    stdout: str = Field(default="", description="Sanitized standard output from build")
    stderr: str = Field(default="", description="Sanitized standard error from build")
    command: List[str] = Field(default_factory=list, description="Build command executed")
    timed_out: bool = Field(default=False, description="Whether build exceeded timeout ceiling")
    oom_killed: bool = Field(default=False, description="Whether build was terminated by OOM killer")
    artifacts: Dict[str, Any] = Field(default_factory=dict, description="Build metadata and diagnostic markers")


class StartupResult(BaseModel):
    """Outcome of application bootstrapping and readiness probing (EVAL-025 to EVAL-028)."""
    success: bool = Field(..., description="Whether application successfully started and responded")
    duration_ms: int = Field(default=0, ge=0, description="Startup bootstrapping latency in milliseconds")
    exit_code: Optional[int] = Field(default=None, description="Exit code if process terminated prematurely")
    ready: bool = Field(default=False, description="Whether listening socket or ready endpoint was verified")
    ready_endpoint: Optional[str] = Field(default=None, description="Discovered healthy readiness endpoint")
    port: Optional[int] = Field(default=None, description="Detected loopback listening port")
    stdout: str = Field(default="", description="Sanitized standard output captured during startup")
    stderr: str = Field(default="", description="Sanitized standard error captured during startup")
    timed_out: bool = Field(default=False, description="Whether startup polling exceeded readiness timeout")
    failure_message: Optional[str] = Field(default=None, description="Diagnostic error explanation if failed")


class ResourceMetrics(BaseModel):
    """Cgroups resource telemetry observed during sandboxed execution (EVAL-032)."""
    cpu_peak_percent: float = Field(default=0.0, ge=0.0, description="Peak CPU utilization percentage")
    cpu_avg_percent: float = Field(default=0.0, ge=0.0, description="Average CPU utilization percentage")
    memory_peak_mb: int = Field(default=0, ge=0, description="Peak memory consumption in megabytes")
    memory_steady_mb: int = Field(default=0, ge=0, description="Steady-state memory consumption in megabytes")
    pids_peak: int = Field(default=0, ge=0, description="Peak concurrent process/thread count")
    disk_bytes_written: int = Field(default=0, ge=0, description="Total scratchpad disk bytes written")


class HttpMetrics(BaseModel):
    """Synthetic HTTP load probing and latency metrics (EVAL-031)."""
    total_requests: int = Field(default=0, ge=0, description="Total synthetic HTTP requests executed")
    successful_requests: int = Field(default=0, ge=0, description="Total HTTP 2xx responses received")
    error_5xx_requests: int = Field(default=0, ge=0, description="Total HTTP 5xx server error responses")
    error_4xx_requests: int = Field(default=0, ge=0, description="Total HTTP 4xx client error responses")
    latency_p50_ms: float = Field(default=0.0, ge=0.0, description="50th percentile response latency in ms")
    latency_p95_ms: float = Field(default=0.0, ge=0.0, description="95th percentile response latency in ms")
    latency_p99_ms: float = Field(default=0.0, ge=0.0, description="99th percentile response latency in ms")
    endpoints_tested: List[str] = Field(default_factory=list, description="List of URL paths probed")

    @property
    def error_rate(self) -> float:
        """Fraction of total requests resulting in server errors (5xx)."""
        if self.total_requests == 0:
            return 0.0
        return self.error_5xx_requests / self.total_requests


class TestCaseResult(BaseModel):
    """Individual test execution outcome record with provenance tracking (EVAL-029)."""
    __test__ = False
    name: str = Field(..., description="Identifier or name of test case")
    origin: TestOrigin = Field(default=TestOrigin.REPOSITORY_PROVIDED, description="Provenance origin of test")
    passed: bool = Field(default=True, description="Whether test case passed")
    skipped: bool = Field(default=False, description="Whether test case was ignored or skipped")
    duration_ms: int = Field(default=0, ge=0, description="Execution duration in milliseconds")
    failure_message: Optional[str] = Field(default=None, description="Assertion failure message or traceback")
    stdout: Optional[str] = Field(default=None, description="Test-specific standard output")


class TestMetrics(BaseModel):
    """Aggregated test suite execution metrics (EVAL-030)."""
    __test__ = False
    tests_total: int = Field(default=0, ge=0, description="Total test cases executed")
    tests_passed: int = Field(default=0, ge=0, description="Total passing tests")
    tests_failed: int = Field(default=0, ge=0, description="Total failing tests")
    tests_skipped: int = Field(default=0, ge=0, description="Total skipped tests")
    duration_ms: int = Field(default=0, ge=0, description="Total test execution duration in ms")
    line_coverage_percent: Optional[float] = Field(
        default=None, ge=0.0, le=100.0, description="Line test coverage percentage"
    )
    branch_coverage_percent: Optional[float] = Field(
        default=None, ge=0.0, le=100.0, description="Branch test coverage percentage"
    )
    test_runner: Optional[str] = Field(default=None, description="Test runner tool executed (e.g. pytest, npm test)")
    test_cases: List[TestCaseResult] = Field(default_factory=list, description="Granular individual test results")


class CliMetrics(BaseModel):
    """Evaluation metrics for command-line tool resilience and conformance."""
    help_tested: bool = Field(default=False, description="Whether --help and -h flags were tested")
    help_exit_code: Optional[int] = Field(default=None, description="Exit code for --help invocation")
    help_output_length: int = Field(default=0, ge=0, description="Character count of returned help documentation")
    version_tested: bool = Field(default=False, description="Whether --version flag was tested")
    version_exit_code: Optional[int] = Field(default=None, description="Exit code for --version invocation")
    version_output: Optional[str] = Field(default=None, description="Captured version string")
    invalid_args_tested: bool = Field(default=False, description="Whether invalid argument resilience was tested")
    invalid_args_exit_code: Optional[int] = Field(
        default=None, description="Exit code on invalid arguments (expected non-zero)"
    )
    invalid_args_clean_error: bool = Field(
        default=False, description="True if invalid arguments produced clean error without unhandled traceback"
    )
    json_output_supported: bool = Field(default=False, description="True if --json produces valid JSON")


class WorkerMetrics(BaseModel):
    """Evaluation metrics for daemon and background queue worker processes."""
    stable_running_duration_ms: int = Field(default=0, ge=0, description="Stable execution window in milliseconds")
    heartbeat_detected: bool = Field(default=False, description="Whether periodic readiness logs were detected")
    clean_sigterm_exit: bool = Field(default=False, description="Whether worker exited cleanly on SIGTERM within 5s")
    termination_duration_ms: int = Field(default=0, ge=0, description="Time taken to terminate upon receiving SIGTERM")
    unhandled_exceptions_count: int = Field(default=0, ge=0, description="Count of caught traceback logs")


class RuntimeObservation(BaseModel):
    """
    Complete empirical runtime observation record produced by sandboxed execution.
    Converts directly into verifiable, immutable EvidenceRecords for downstream scoring.
    """
    evaluation_id: str = Field(..., description="Evaluation job UUID")
    evaluator_type: EvaluatorType = Field(..., description="Operational evaluator strategy used")
    primary_language: Optional[str] = Field(default=None, description="Detected repository language")
    build_result: Optional[BuildResult] = Field(default=None, description="Build step results")
    startup_result: Optional[StartupResult] = Field(default=None, description="Startup and readiness results")
    resource_metrics: Optional[ResourceMetrics] = Field(default=None, description="Observed cgroups telemetry")
    http_metrics: Optional[HttpMetrics] = Field(default=None, description="HTTP synthetic probing metrics")
    cli_metrics: Optional[CliMetrics] = Field(default=None, description="CLI invocation metrics")
    worker_metrics: Optional[WorkerMetrics] = Field(default=None, description="Worker daemon metrics")
    test_metrics: Optional[TestMetrics] = Field(default=None, description="Native test suite metrics")
    exit_code: Optional[int] = Field(default=None, description="Primary process terminal exit code")
    duration_ms: int = Field(default=0, ge=0, description="Total runtime evaluation duration in milliseconds")
    failure_code: Optional[RuntimeFailureCode] = Field(
        default=None, description="Structured failure category if execution was unsuccessful"
    )
    failure_reason: Optional[str] = Field(default=None, description="Human-readable failure diagnostic message")
    unhandled_exceptions: List[str] = Field(default_factory=list, description="Captured tracebacks and unhandled panics")
    critical_logs: List[str] = Field(default_factory=list, description="Notable diagnostic or error log lines")
    raw_stdout: str = Field(default="", description="Sanitized and bounded overall standard output")
    raw_stderr: str = Field(default="", description="Sanitized and bounded overall standard error")

    def to_evidence_items(self) -> List[NormalizedFinding]:
        """
        Convert empirical runtime observations into canonical normalized findings
        traceable to specific score dimensions (CORRECTNESS, RELIABILITY, PERFORMANCE, TESTING).
        """
        findings: List[NormalizedFinding] = []

        # 1. Build Failure Evidence
        if self.build_result and not self.build_result.success:
            err_snippet = (self.build_result.stderr or self.build_result.stdout or "Build failed")[:300]
            findings.append(
                NormalizedFinding(
                    analyzer_id="runtime-engine",
                    tool_version="1.0.0",
                    rule_id="RUN-BUILD-001-FAILURE",
                    category=EvidenceCategory.CORRECTNESS,
                    severity=SeverityLevel.CRITICAL,
                    confidence=1.0,
                    title="Repository Build Failed in Isolated Sandbox",
                    description=f"Build command failed with exit code {self.build_result.exit_code}. Error: {err_snippet}",
                    recommendation="Ensure dependencies are declared in manifest files and code compiles cleanly.",
                    raw_evidence={
                        "exit_code": self.build_result.exit_code,
                        "command": self.build_result.command,
                        "timed_out": self.build_result.timed_out,
                        "oom_killed": self.build_result.oom_killed,
                    },
                )
            )

        # 2. Startup Failure / Crash on Boot
        if self.startup_result and not self.startup_result.success:
            severity = SeverityLevel.CRITICAL if self.failure_code == RuntimeFailureCode.CRASH_ON_BOOT else SeverityLevel.HIGH
            findings.append(
                NormalizedFinding(
                    analyzer_id="runtime-engine",
                    tool_version="1.0.0",
                    rule_id="RUN-BOOT-001-STARTUP-FAILED",
                    category=EvidenceCategory.RELIABILITY,
                    severity=severity,
                    confidence=1.0,
                    title="Application Failed to Bootstrap or Become Ready",
                    description=(
                        f"Startup failed: {self.startup_result.failure_message or 'Service failed to respond on loopback port'}. "
                        f"Exit code: {self.startup_result.exit_code}"
                    ),
                    recommendation="Verify standalone development mode configuration and ensure default ports are configurable.",
                    raw_evidence={
                        "exit_code": self.startup_result.exit_code,
                        "timed_out": self.startup_result.timed_out,
                        "ready": self.startup_result.ready,
                    },
                )
            )

        # 3. OOM Killed Evidence
        if self.failure_code == RuntimeFailureCode.OOM_KILLED or (
            self.build_result and self.build_result.oom_killed
        ):
            findings.append(
                NormalizedFinding(
                    analyzer_id="runtime-engine",
                    tool_version="1.0.0",
                    rule_id="RUN-RES-001-OOM-KILLED",
                    category=EvidenceCategory.PERFORMANCE,
                    severity=SeverityLevel.CRITICAL,
                    confidence=1.0,
                    title="Process Terminated by Linux OOM Killer",
                    description="The container process exceeded the 2048MB memory quota and was killed by cgroups.",
                    recommendation="Optimize memory utilization and inspect data structures for memory leaks.",
                    raw_evidence={
                        "memory_limit": "2048m",
                        "failure_code": "OOM_KILLED",
                    },
                )
            )

        # 4. HTTP Metrics Evidence
        if self.http_metrics and self.http_metrics.total_requests > 0:
            if self.http_metrics.error_rate > 0.10:
                findings.append(
                    NormalizedFinding(
                        analyzer_id="runtime-http",
                        tool_version="1.0.0",
                        rule_id="RUN-HTTP-001-HIGH-ERROR-RATE",
                        category=EvidenceCategory.RELIABILITY,
                        severity=SeverityLevel.HIGH,
                        confidence=1.0,
                        title="High HTTP Server Error Rate Under Synthetic Load",
                        description=(
                            f"{self.http_metrics.error_5xx_requests} out of {self.http_metrics.total_requests} "
                            f"requests returned HTTP 5xx ({self.http_metrics.error_rate * 100:.1f}% failure rate)."
                        ),
                        recommendation="Review server logs and address unhandled exceptions occurring in request handlers.",
                        raw_evidence={
                            "total_requests": self.http_metrics.total_requests,
                            "error_5xx": self.http_metrics.error_5xx_requests,
                            "error_rate": self.http_metrics.error_rate,
                        },
                    )
                )

            if self.http_metrics.latency_p95_ms > 2000.0:
                findings.append(
                    NormalizedFinding(
                        analyzer_id="runtime-http",
                        tool_version="1.0.0",
                        rule_id="RUN-HTTP-002-HIGH-LATENCY",
                        category=EvidenceCategory.PERFORMANCE,
                        severity=SeverityLevel.MEDIUM,
                        confidence=0.9,
                        title="Elevated HTTP Response Latency Observed",
                        description=f"Synthetic probe observed 95th percentile latency of {self.http_metrics.latency_p95_ms:.1f}ms (>2000ms threshold).",
                        recommendation="Profile request handlers and optimize blocking synchronous operations.",
                        raw_evidence={
                            "latency_p50_ms": self.http_metrics.latency_p50_ms,
                            "latency_p95_ms": self.http_metrics.latency_p95_ms,
                            "latency_p99_ms": self.http_metrics.latency_p99_ms,
                        },
                    )
                )

        # 5. Native Test Suite Evidence
        if self.test_metrics and self.test_metrics.tests_total > 0:
            if self.test_metrics.tests_failed > 0:
                findings.append(
                    NormalizedFinding(
                        analyzer_id="runtime-test",
                        tool_version="1.0.0",
                        rule_id="RUN-TEST-001-FAILURES",
                        category=EvidenceCategory.TESTING,
                        severity=SeverityLevel.HIGH,
                        confidence=1.0,
                        title=f"{self.test_metrics.tests_failed} Tests Failed in Repository Test Suite",
                        description=(
                            f"Test runner {self.test_metrics.test_runner or 'native'} reported "
                            f"{self.test_metrics.tests_failed} failed tests out of {self.test_metrics.tests_total} total."
                        ),
                        recommendation="Fix failing test assertions and maintain clean CI pipeline tests.",
                        raw_evidence={
                            "total": self.test_metrics.tests_total,
                            "failed": self.test_metrics.tests_failed,
                            "passed": self.test_metrics.tests_passed,
                            "runner": self.test_metrics.test_runner,
                        },
                    )
                )
            elif self.test_metrics.tests_passed > 0 and self.test_metrics.tests_failed == 0:
                findings.append(
                    NormalizedFinding(
                        analyzer_id="runtime-test",
                        tool_version="1.0.0",
                        rule_id="RUN-TEST-002-ALL-PASSED",
                        category=EvidenceCategory.TESTING,
                        severity=SeverityLevel.INFO,
                        confidence=1.0,
                        title=f"All {self.test_metrics.tests_passed} Tests Passed Successfully",
                        description=(
                            f"Repository test runner {self.test_metrics.test_runner or 'native'} executed "
                            f"{self.test_metrics.tests_passed} passing tests with 0 failures."
                        ),
                        recommendation="Maintain comprehensive unit and integration test coverage.",
                        raw_evidence={
                            "total": self.test_metrics.tests_total,
                            "passed": self.test_metrics.tests_passed,
                            "runner": self.test_metrics.test_runner,
                        },
                    )
                )

        # 6. CLI Resilience Evidence
        if self.cli_metrics and self.cli_metrics.invalid_args_tested:
            if not self.cli_metrics.invalid_args_clean_error:
                findings.append(
                    NormalizedFinding(
                        analyzer_id="runtime-cli",
                        tool_version="1.0.0",
                        rule_id="RUN-CLI-001-UNCLEAN-ERROR",
                        category=EvidenceCategory.RELIABILITY,
                        severity=SeverityLevel.LOW,
                        confidence=0.85,
                        title="CLI Tool Panicked or Dumped Traceback on Invalid Arguments",
                        description="Passing unrecognized CLI flags produced an unhandled stack trace or unexpected zero exit code.",
                        recommendation="Implement proper argument parsing with clean error messages and non-zero exit codes.",
                        raw_evidence={
                            "exit_code": self.cli_metrics.invalid_args_exit_code,
                            "clean_error": self.cli_metrics.invalid_args_clean_error,
                        },
                    )
                )

        # 7. Worker Clean Shutdown Evidence
        if self.worker_metrics and not self.worker_metrics.clean_sigterm_exit:
            findings.append(
                NormalizedFinding(
                    analyzer_id="runtime-worker",
                    tool_version="1.0.0",
                    rule_id="RUN-WRK-001-ZOMBIE-SHUTDOWN",
                    category=EvidenceCategory.RELIABILITY,
                    severity=SeverityLevel.MEDIUM,
                    confidence=0.9,
                    title="Background Worker Failed Clean Termination on SIGTERM",
                    description="Worker process did not exit within 5 seconds of receiving SIGTERM signal.",
                    recommendation="Handle SIGTERM gracefully and ensure background thread pools and socket listeners are closed.",
                    raw_evidence={
                        "clean_sigterm_exit": self.worker_metrics.clean_sigterm_exit,
                        "termination_duration_ms": self.worker_metrics.termination_duration_ms,
                    },
                )
            )

        # 8. Unhandled Exceptions / Crash Traces
        for idx, exc in enumerate(self.unhandled_exceptions[:5]):
            findings.append(
                NormalizedFinding(
                    analyzer_id="runtime-engine",
                    tool_version="1.0.0",
                    rule_id=f"RUN-EXC-{idx + 1:03d}-UNHANDLED",
                    category=EvidenceCategory.RELIABILITY,
                    severity=SeverityLevel.HIGH,
                    confidence=1.0,
                    title="Unhandled Exception Detected in Runtime Output",
                    description=f"Caught runtime unhandled exception: {exc[:250]}",
                    recommendation="Add error handling around crashing code paths and catch exceptions cleanly.",
                    raw_evidence={"exception": exc[:500]},
                )
            )

        return findings
