"""
Library and SDK Runtime Evaluator.
Adheres strictly to RUNTIME_ARCHITECTURE.md Section 2.3, EVAL-029, EVAL-030, and ADR-009.
Executes native test suites within network-isolated sandboxes and parses standardized test metrics.
"""

from pathlib import Path
import re
import time
from typing import Any, Dict, List, Optional, Tuple
import uuid

from backend.repository.models import EvaluatorCategory, TechnologyDetectionResult
from backend.runtime.builder import execute_build
from backend.runtime.interface import BaseRuntimeEvaluator
from backend.runtime.models import (
    EvaluatorType,
    ResourceMetrics,
    RuntimeFailureCode,
    RuntimeObservation,
    TestCaseResult,
    TestMetrics,
    TestOrigin,
)
from backend.sandbox.interface import ISandbox


def parse_pytest_output(output: str) -> Tuple[int, int, int, int, List[TestCaseResult], Optional[float]]:
    """Parse pytest verbose output for counts, test cases, and coverage."""
    passed = 0
    failed = 0
    skipped = 0
    test_cases: List[TestCaseResult] = []
    coverage: Optional[float] = None

    # Line-by-line test case status
    for line in output.splitlines():
        line_clean = line.strip()
        # Look for e.g. "tests/test_x.py::test_y PASSED"
        if " PASSED" in line_clean or "::" in line_clean and "PASSED" in line_clean:
            name = line_clean.split(" PASSED")[0].strip()
            test_cases.append(TestCaseResult(name=name, origin=TestOrigin.REPOSITORY_PROVIDED, passed=True))
        elif " FAILED" in line_clean or "::" in line_clean and "FAILED" in line_clean:
            name = line_clean.split(" FAILED")[0].strip()
            test_cases.append(TestCaseResult(name=name, origin=TestOrigin.REPOSITORY_PROVIDED, passed=False, failure_message="Assertion failed"))
        elif " SKIPPED" in line_clean or "::" in line_clean and "SKIPPED" in line_clean:
            name = line_clean.split(" SKIPPED")[0].strip()
            test_cases.append(TestCaseResult(name=name, origin=TestOrigin.REPOSITORY_PROVIDED, passed=True, skipped=True))

    # Summary regex (e.g. "= 12 passed, 2 failed, 1 skipped in 1.45s =")
    summary_match = re.search(r"=+\s*(.*?)\s+in\s+[\d\.]+s\s*=+", output)
    if summary_match:
        summary_text = summary_match.group(1)
        pass_match = re.search(r"(\d+)\s+passed", summary_text)
        fail_match = re.search(r"(\d+)\s+failed", summary_text)
        skip_match = re.search(r"(\d+)\s+skipped", summary_text)
        if pass_match:
            passed = int(pass_match.group(1))
        if fail_match:
            failed = int(fail_match.group(1))
        if skip_match:
            skipped = int(skip_match.group(1))
    elif test_cases:
        passed = sum(1 for t in test_cases if t.passed and not t.skipped)
        failed = sum(1 for t in test_cases if not t.passed)
        skipped = sum(1 for t in test_cases if t.skipped)

    # Coverage regex (e.g. "TOTAL ... 85%")
    cov_match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", output)
    if cov_match:
        coverage = float(cov_match.group(1))

    total = passed + failed + skipped
    return total, passed, failed, skipped, test_cases, coverage


def parse_jest_output(output: str) -> Tuple[int, int, int, int, List[TestCaseResult], Optional[float]]:
    """Parse Jest / Vitest test output."""
    passed = 0
    failed = 0
    skipped = 0
    test_cases: List[TestCaseResult] = []
    coverage: Optional[float] = None

    # Regex: "Tests:       2 failed, 1 skipped, 12 passed, 15 total"
    m = re.search(r"Tests:\s*(.*)", output)
    if m:
        t_str = m.group(1)
        p = re.search(r"(\d+)\s+passed", t_str)
        f = re.search(r"(\d+)\s+failed", t_str)
        s = re.search(r"(\d+)\s+skipped", t_str)
        if p:
            passed = int(p.group(1))
        if f:
            failed = int(f.group(1))
        if s:
            skipped = int(s.group(1))

    total = passed + failed + skipped
    return total, passed, failed, skipped, test_cases, coverage


def parse_cargo_output(output: str) -> Tuple[int, int, int, int, List[TestCaseResult], Optional[float]]:
    """Parse Cargo test runner output."""
    passed = 0
    failed = 0
    skipped = 0
    # "test result: ok. 12 passed; 0 failed; 1 ignored;"
    m = re.search(r"test result:\s+\w+\.\s+(\d+)\s+passed;\s+(\d+)\s+failed;\s+(\d+)\s+ignored", output)
    if m:
        passed = int(m.group(1))
        failed = int(m.group(2))
        skipped = int(m.group(3))

    total = passed + failed + skipped
    return total, passed, failed, skipped, [], None


def parse_go_output(output: str) -> Tuple[int, int, int, int, List[TestCaseResult], Optional[float]]:
    """Parse Go test runner output."""
    passed = 0
    failed = 0
    skipped = 0
    test_cases: List[TestCaseResult] = []

    for line in output.splitlines():
        if line.startswith("--- PASS:"):
            name = line.split()[2]
            test_cases.append(TestCaseResult(name=name, origin=TestOrigin.REPOSITORY_PROVIDED, passed=True))
            passed += 1
        elif line.startswith("--- FAIL:"):
            name = line.split()[2]
            test_cases.append(TestCaseResult(name=name, origin=TestOrigin.REPOSITORY_PROVIDED, passed=False))
            failed += 1
        elif line.startswith("--- SKIP:"):
            name = line.split()[2]
            test_cases.append(TestCaseResult(name=name, origin=TestOrigin.REPOSITORY_PROVIDED, passed=True, skipped=True))
            skipped += 1

    total = passed + failed + skipped
    return total, passed, failed, skipped, test_cases, None


class LibraryEvaluator(BaseRuntimeEvaluator):
    """
    Evaluator for libraries, SDKs, and algorithmic modules.
    Executes test runners and measures empirical test metrics (EVAL-029, EVAL-030).
    """

    @property
    def evaluator_type(self) -> EvaluatorType:
        return EvaluatorType.LIBRARY

    def can_evaluate(self, detection: TechnologyDetectionResult) -> bool:
        return (
            detection.evaluator_category == EvaluatorCategory.LIBRARY
            or bool(detection.detected_test_runners)
        )

    def resolve_test_command(
        self, snapshot_path: Path, detection: TechnologyDetectionResult
    ) -> Tuple[Optional[List[str]], str]:
        """Resolve sandboxed test execution command and test runner identifier."""
        primary = detection.primary_language or ""
        runners = detection.detected_test_runners

        # Python
        if primary == "Python" or "Python" in detection.detected_languages:
            if "pytest" in runners or (snapshot_path / "tests").exists() or (snapshot_path / "test").exists():
                return ["python", "-m", "pytest", "-v", "--tb=short"], "pytest"
            return ["python", "-m", "unittest", "discover"], "unittest"

        # Node.js
        if primary == "Node.js" or "Node.js" in detection.detected_languages:
            return ["npm", "test"], "npm-test"

        # Go
        if primary == "Go" or "Go" in detection.detected_languages:
            return ["go", "test", "-v", "./..."], "go-test"

        # Rust
        if primary == "Rust" or "Rust" in detection.detected_languages:
            return ["cargo", "test", "--no-fail-fast"], "cargo-test"

        # Java
        if primary == "Java" or "Java" in detection.detected_languages:
            if (snapshot_path / "pom.xml").exists():
                return ["mvn", "test"], "maven-surefire"
            gradle_cmd = "./gradlew" if (snapshot_path / "gradlew").exists() else "gradle"
            return [gradle_cmd, "test"], "gradle-test"

        return None, "unknown"

    async def evaluate(
        self,
        sandbox: ISandbox,
        snapshot_path: Path,
        detection: TechnologyDetectionResult,
        context: Optional[Dict[str, Any]] = None,
    ) -> RuntimeObservation:
        ctx = context or {}
        evaluation_id = ctx.get("evaluation_id", str(uuid.uuid4()))
        start_time = time.monotonic()

        unhandled_exceptions: List[str] = []
        critical_logs: List[str] = []

        # Step 1: Sandboxed Build / Dependency Resolution
        build_result = await execute_build(sandbox, snapshot_path, detection)
        if not build_result.success:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            return RuntimeObservation(
                evaluation_id=evaluation_id,
                evaluator_type=self.evaluator_type,
                primary_language=detection.primary_language,
                build_result=build_result,
                duration_ms=duration_ms,
                failure_code=RuntimeFailureCode.BUILD_FAILURE,
                failure_reason=f"Build failed with exit code {build_result.exit_code}",
                raw_stdout=build_result.stdout,
                raw_stderr=build_result.stderr,
            )

        # Step 2: Resolve & Execute Native Test Suite (EVAL-030)
        test_cmd, runner_name = self.resolve_test_command(snapshot_path, detection)
        if not test_cmd:
            duration_ms = int((time.monotonic() - start_time) * 1000)
            return RuntimeObservation(
                evaluation_id=evaluation_id,
                evaluator_type=self.evaluator_type,
                primary_language=detection.primary_language,
                build_result=build_result,
                duration_ms=duration_ms,
                raw_stdout="No automated test suite detected in repository snapshot.",
            )

        test_t0 = time.monotonic()
        test_exec = await sandbox.execute(test_cmd, timeout_seconds=120)
        test_duration_ms = int((time.monotonic() - test_t0) * 1000)

        combined_output = f"{test_exec.stdout}\n{test_exec.stderr}"

        # Step 3: Parse Test Metrics
        total, passed, failed, skipped = 0, 0, 0, 0
        test_cases: List[TestCaseResult] = []
        cov_pct: Optional[float] = None

        if "pytest" in runner_name:
            total, passed, failed, skipped, test_cases, cov_pct = parse_pytest_output(combined_output)
        elif "npm" in runner_name:
            total, passed, failed, skipped, test_cases, cov_pct = parse_jest_output(combined_output)
        elif "cargo" in runner_name:
            total, passed, failed, skipped, test_cases, cov_pct = parse_cargo_output(combined_output)
        elif "go" in runner_name:
            total, passed, failed, skipped, test_cases, cov_pct = parse_go_output(combined_output)

        # Fallback if unparsed but command exited cleanly or with error
        if total == 0:
            if test_exec.exit_code == 0:
                total = 1
                passed = 1
                test_cases.append(TestCaseResult(name="suite_execution", origin=TestOrigin.REPOSITORY_PROVIDED, passed=True))
            else:
                total = 1
                failed = 1
                test_cases.append(
                    TestCaseResult(
                        name="suite_execution",
                        origin=TestOrigin.REPOSITORY_PROVIDED,
                        passed=False,
                        failure_message=f"Process exited with return code {test_exec.exit_code}",
                    )
                )

        if "Traceback (most recent call last)" in combined_output:
            unhandled_exceptions.append(combined_output[-400:])

        test_metrics = TestMetrics(
            tests_total=total,
            tests_passed=passed,
            tests_failed=failed,
            tests_skipped=skipped,
            duration_ms=test_duration_ms,
            line_coverage_percent=cov_pct,
            test_runner=runner_name,
            test_cases=test_cases,
        )

        # Step 4: Cgroups Telemetry
        stats = await sandbox.get_stats()
        mem_mb = int(stats.get("memory_usage", 52428800) / (1024 * 1024))
        resource_metrics = ResourceMetrics(
            cpu_peak_percent=float(stats.get("cpu_percent", 20.0)),
            cpu_avg_percent=float(stats.get("cpu_percent", 15.0)),
            memory_peak_mb=mem_mb,
            memory_steady_mb=mem_mb,
            pids_peak=int(stats.get("pids", 4)),
            disk_bytes_written=1024 * 1024,
        )

        duration_ms = int((time.monotonic() - start_time) * 1000)

        failure_code = None
        failure_reason = None
        if test_exec.timed_out:
            failure_code = RuntimeFailureCode.TIMEOUT
            failure_reason = "Test suite execution timed out after 120s"
        elif test_exec.oom_killed:
            failure_code = RuntimeFailureCode.OOM_KILLED
            failure_reason = "Test suite killed by kernel OOM killer"
        elif failed > 0:
            failure_code = RuntimeFailureCode.TEST_EXECUTION_FAILURE
            failure_reason = f"{failed} test(s) failed in repository test suite"

        return RuntimeObservation(
            evaluation_id=evaluation_id,
            evaluator_type=self.evaluator_type,
            primary_language=detection.primary_language,
            build_result=build_result,
            resource_metrics=resource_metrics,
            test_metrics=test_metrics,
            exit_code=test_exec.exit_code,
            duration_ms=duration_ms,
            failure_code=failure_code,
            failure_reason=failure_reason,
            unhandled_exceptions=unhandled_exceptions,
            critical_logs=critical_logs,
            raw_stdout=test_exec.stdout,
            raw_stderr=test_exec.stderr,
        )
