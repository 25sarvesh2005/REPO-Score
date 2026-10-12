"""
Generic and Fallback Runtime Evaluator.
Adheres strictly to RUNTIME_ARCHITECTURE.md Section 1 and ADR-009.
Handles generic builds and unclassified or unsupported repository architectures gracefully.
"""

from pathlib import Path
import time
from typing import Any, Dict, Optional
import uuid

from backend.repository.models import EvaluatorCategory, TechnologyDetectionResult
from backend.runtime.builder import execute_build
from backend.runtime.interface import BaseRuntimeEvaluator
from backend.runtime.models import (
    EvaluatorType,
    ResourceMetrics,
    RuntimeFailureCode,
    RuntimeObservation,
)
from backend.sandbox.interface import ISandbox


class GenericEvaluator(BaseRuntimeEvaluator):
    """
    Fallback evaluator for projects without specific framework signatures or unsupported stacks.
    """

    @property
    def evaluator_type(self) -> EvaluatorType:
        return EvaluatorType.GENERIC_RUNNER

    def can_evaluate(self, detection: TechnologyDetectionResult) -> bool:
        # Fallback catches all remaining cases
        return True

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

        # Step 1: Sandboxed Build Execution
        build_result = await execute_build(sandbox, snapshot_path, detection)

        stats = await sandbox.get_stats()
        mem_mb = int(stats.get("memory_usage", 52428800) / (1024 * 1024))
        resource_metrics = ResourceMetrics(
            cpu_peak_percent=float(stats.get("cpu_percent", 5.0)),
            cpu_avg_percent=float(stats.get("cpu_percent", 5.0)),
            memory_peak_mb=mem_mb,
            memory_steady_mb=mem_mb,
            pids_peak=int(stats.get("pids", 1)),
            disk_bytes_written=0,
        )

        duration_ms = int((time.monotonic() - start_time) * 1000)

        is_unsupported = detection.evaluator_category == EvaluatorCategory.UNSUPPORTED
        failure_code = (
            RuntimeFailureCode.UNSUPPORTED_TECH
            if is_unsupported
            else (None if build_result.success else RuntimeFailureCode.BUILD_FAILURE)
        )
        failure_reason = (
            "Repository technology stack is unsupported for automated runtime execution"
            if is_unsupported
            else (None if build_result.success else f"Build failed with exit code {build_result.exit_code}")
        )

        return RuntimeObservation(
            evaluation_id=evaluation_id,
            evaluator_type=self.evaluator_type,
            primary_language=detection.primary_language,
            build_result=build_result,
            resource_metrics=resource_metrics,
            exit_code=build_result.exit_code,
            duration_ms=duration_ms,
            failure_code=failure_code,
            failure_reason=failure_reason,
            raw_stdout=build_result.stdout,
            raw_stderr=build_result.stderr,
        )
