"""
Runtime Evaluation Dispatcher and Orchestration Engine.
Adheres strictly to RUNTIME_ARCHITECTURE.md, ADR-002, ADR-009, and Prime Directive #4.
Ensures ZERO execution on host; routes evaluation strictly through isolated ISandbox instances.
"""

from pathlib import Path
import time
from typing import Any, Dict, List, Optional
import uuid

from backend.repository.models import EvaluatorCategory, TechnologyDetectionResult
from backend.runtime.cli_evaluator import CliEvaluator
from backend.runtime.generic_evaluator import GenericEvaluator
from backend.runtime.http_evaluator import HttpApiEvaluator
from backend.runtime.interface import BaseRuntimeEvaluator
from backend.runtime.library_evaluator import LibraryEvaluator
from backend.runtime.models import (
    EvaluatorType,
    RuntimeFailureCode,
    RuntimeObservation,
)
from backend.runtime.worker_evaluator import WorkerEvaluator
from backend.sandbox.exceptions import SandboxError, SandboxTimeoutError, SandboxUnavailableError
from backend.sandbox.interface import ISandboxManager
from backend.sandbox.models import NetworkPolicy, SandboxConfig


LANGUAGE_IMAGE_MAP: Dict[str, str] = {
    "Python": "reposcore/sandbox-python:3.11-slim",
    "Node.js": "reposcore/sandbox-node:20-slim",
    "Go": "reposcore/sandbox-go:1.22-alpine",
    "Rust": "reposcore/sandbox-rust:1.77-slim",
    "Java": "reposcore/sandbox-java:21-temurin",
}


class RuntimeDispatcher:
    """
    Central coordinator that resolves evaluation strategies, configures
    hardened sandboxes, dispatches evaluation runs, and guarantees cleanup.
    """

    def __init__(self, evaluators: Optional[List[BaseRuntimeEvaluator]] = None) -> None:
        self._evaluators: List[BaseRuntimeEvaluator] = evaluators or [
            HttpApiEvaluator(),
            CliEvaluator(),
            LibraryEvaluator(),
            WorkerEvaluator(),
            GenericEvaluator(),
        ]

    def resolve_evaluator(self, detection: TechnologyDetectionResult) -> BaseRuntimeEvaluator:
        """Resolve the most specialized evaluator matching the detected repository archetype."""
        category = detection.evaluator_category

        if category == EvaluatorCategory.WEB_API:
            for ev in self._evaluators:
                if ev.evaluator_type == EvaluatorType.HTTP_API:
                    return ev

        if category == EvaluatorCategory.CLI_TOOL:
            for ev in self._evaluators:
                if ev.evaluator_type == EvaluatorType.CLI_TOOL:
                    return ev

        if category == EvaluatorCategory.LIBRARY:
            for ev in self._evaluators:
                if ev.evaluator_type == EvaluatorType.LIBRARY:
                    return ev

        if category == EvaluatorCategory.BACKGROUND_WORKER:
            for ev in self._evaluators:
                if ev.evaluator_type == EvaluatorType.BACKGROUND_WORKER:
                    return ev

        # Fallback to can_evaluate match
        for ev in self._evaluators:
            if ev.can_evaluate(detection) and ev.evaluator_type != EvaluatorType.GENERIC_RUNNER:
                return ev

        # Default fallback
        for ev in self._evaluators:
            if isinstance(ev, GenericEvaluator):
                return ev

        return GenericEvaluator()

    def resolve_sandbox_config(
        self,
        snapshot_path: Path,
        detection: TechnologyDetectionResult,
        timeout_seconds: int = 120,
    ) -> SandboxConfig:
        """
        Derive hardened, non-root SandboxConfig adhering to Phase 07 security invariants.
        """
        primary = detection.primary_language or "Generic"
        image = LANGUAGE_IMAGE_MAP.get(primary, "reposcore/sandbox-base:latest")

        resolved_path = str(snapshot_path.resolve())

        return SandboxConfig(
            image=image,
            workdir="/workspace/build",
            user="10001:10001",
            read_only_rootfs=True,
            cap_drop=["ALL"],
            security_opt=["no-new-privileges:true"],
            network_mode=NetworkPolicy.NONE,
            memory_limit="2048m",
            memory_swap="2048m",
            cpu_quota=2.0,
            pids_limit=128,
            timeout_seconds=timeout_seconds,
            bind_mounts={
                resolved_path: {"bind": "/workspace/src", "mode": "ro"},
            },
            tmpfs_mounts={
                "/workspace/build": "rw,nosuid,nodev,size=1024m",
                "/tmp": "rw,nosuid,nodev,size=256m",
            },
        )

    async def execute_evaluation(
        self,
        snapshot_path: Path,
        detection: TechnologyDetectionResult,
        sandbox_manager: ISandboxManager,
        context: Optional[Dict[str, Any]] = None,
    ) -> RuntimeObservation:
        """
        Orchestrate end-to-end sandboxed runtime evaluation.
        Enforces strict lifecycle guarantees: sandboxes are ALWAYS terminated upon exit.
        """
        ctx = context or {}
        evaluation_id = ctx.get("evaluation_id", str(uuid.uuid4()))
        t0 = time.monotonic()

        evaluator = self.resolve_evaluator(detection)

        # Step 1: Verify sandbox runtime availability
        if not await sandbox_manager.is_available():
            duration_ms = int((time.monotonic() - t0) * 1000)
            return RuntimeObservation(
                evaluation_id=evaluation_id,
                evaluator_type=evaluator.evaluator_type,
                primary_language=detection.primary_language,
                duration_ms=duration_ms,
                failure_code=RuntimeFailureCode.SANDBOX_ERROR,
                failure_reason="Sandbox execution manager is unavailable on host. Refusing host execution.",
                critical_logs=["Sandbox runtime unreachable; Prime Directive #4 strictly observed."],
            )

        # Step 2: Configure hardened sandbox
        config = self.resolve_sandbox_config(snapshot_path, detection)

        # Step 3: Spawn sandbox and execute within safe boundary
        sandbox = None
        try:
            sandbox = await sandbox_manager.create_sandbox(config)
            observation = await evaluator.evaluate(
                sandbox=sandbox,
                snapshot_path=snapshot_path,
                detection=detection,
                context={**ctx, "evaluation_id": evaluation_id},
            )
            return observation
        except SandboxTimeoutError as exc:
            duration_ms = int((time.monotonic() - t0) * 1000)
            return RuntimeObservation(
                evaluation_id=evaluation_id,
                evaluator_type=evaluator.evaluator_type,
                primary_language=detection.primary_language,
                duration_ms=duration_ms,
                failure_code=RuntimeFailureCode.TIMEOUT,
                failure_reason=f"Sandbox execution timed out: {exc}",
                raw_stderr=str(exc),
            )
        except SandboxError as exc:
            duration_ms = int((time.monotonic() - t0) * 1000)
            return RuntimeObservation(
                evaluation_id=evaluation_id,
                evaluator_type=evaluator.evaluator_type,
                primary_language=detection.primary_language,
                duration_ms=duration_ms,
                failure_code=RuntimeFailureCode.SANDBOX_ERROR,
                failure_reason=f"Sandbox execution error: {exc}",
                raw_stderr=str(exc),
            )
        finally:
            if sandbox is not None:
                try:
                    await sandbox.terminate()
                except Exception:
                    pass
