"""
Evaluation Pipeline Orchestrator.
Connects ingestion, queue, static analyzers, runtime sandbox, evidence normalizer,
deterministic scoring engine, and local-first AI interpretation into a unified,
resilient, auditable lifecycle.

Adheres strictly to EVALUATION_LIFECYCLE.md, Prime Directives #1-#6, and ADR-001 through ADR-010.
"""

import contextlib
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.ai.service import AIInterpretationService
from backend.analyzers.models import NormalizedFinding
from backend.analyzers.registry import AnalyzerRegistry
from backend.api.schemas.contracts import (
    EvaluationStatus,
)
from backend.core.queue import IJobQueue, get_job_queue
from backend.database.models import (
    Evaluation,
    EvaluationStep,
    Evidence,
    Repository,
    RepositorySnapshot,
)
from backend.database.models import (
    RuntimeObservation as RuntimeObservationModel,
)
from backend.observability.logger import (
    correlation_id_ctx,
    evaluation_id_ctx,
    get_logger,
)
from backend.observability.metrics import (
    record_ai_inference_metric,
    record_evaluation_metric,
    record_finding_metric,
    record_step_metric,
)
from backend.pipeline.models import PipelineExecutionResult, StepExecutionLog, StepStatus
from backend.repository.detector import detect_technologies_and_category
from backend.repository.models import TechnologyDetectionResult
from backend.repository.service import RepositoryIngestionService
from backend.runtime.dispatcher import RuntimeDispatcher
from backend.runtime.models import RuntimeFailureCode, RuntimeObservation
from backend.sandbox.docker import DockerSandboxManager
from backend.sandbox.interface import ISandboxManager
from backend.scoring.calculator import DeterministicScoringEngine
from backend.scoring.models import ScorecardResult

logger = get_logger("reposcore.pipeline.orchestrator")


class EvaluationPipelineOrchestrator:
    """
    Autonomous coordinator executing repository evaluation lifecycle end-to-end.
    """

    @staticmethod
    def _resolve_sandbox_manager() -> ISandboxManager:
        return DockerSandboxManager()

    def __init__(
        self,
        ingestion_service: RepositoryIngestionService | None = None,
        analyzer_registry: AnalyzerRegistry | None = None,
        runtime_dispatcher: RuntimeDispatcher | None = None,
        sandbox_manager: ISandboxManager | None = None,
        scoring_engine: DeterministicScoringEngine | None = None,
        ai_service: AIInterpretationService | None = None,
        job_queue: IJobQueue | None = None,
    ) -> None:
        self.ingestion_service = ingestion_service or RepositoryIngestionService()
        self.analyzer_registry = analyzer_registry or AnalyzerRegistry()
        self.runtime_dispatcher = runtime_dispatcher or RuntimeDispatcher()
        self.sandbox_manager = sandbox_manager or self._resolve_sandbox_manager()
        self.scoring_engine = scoring_engine or DeterministicScoringEngine()
        self.ai_service = ai_service or AIInterpretationService()
        self.job_queue = job_queue or get_job_queue()

    async def execute_pipeline(
        self,
        session: AsyncSession,
        evaluation_id: uuid.UUID,
        repository_id: uuid.UUID,
        ref: str = "main",
        options: dict[str, Any] | None = None,
        fixture_snapshot_path: Path | None = None,
    ) -> PipelineExecutionResult:
        """
        Execute full end-to-end evaluation flow.
        """
        opts = options or {}
        enable_ai = opts.get("enable_ai_reasoning", True)
        steps_executed: list[StepExecutionLog] = []
        t0 = time.monotonic()

        # 1. Fetch evaluation & repository records
        eval_stmt = select(Evaluation).where(Evaluation.id == evaluation_id)
        evaluation = (await session.execute(eval_stmt)).scalar_one_or_none()
        if not evaluation:
            raise ValueError(f"Evaluation record '{evaluation_id}' not found in database.")

        repo_stmt = select(Repository).where(Repository.id == repository_id)
        repository = (await session.execute(repo_stmt)).scalar_one_or_none()
        if not repository:
            raise ValueError(f"Repository record '{repository_id}' not found in database.")

        # Bind tracing contexts
        evaluation_id_ctx.set(str(evaluation_id))
        correlation_id_ctx.set(str(evaluation.correlation_id))

        evaluation.started_at = datetime.now(UTC)
        await self._publish_event(
            evaluation_id, "evaluation.lifecycle.started", {"status": "INGESTING"}
        )
        await session.commit()

        snapshot_path: Path | None = fixture_snapshot_path
        detection: TechnologyDetectionResult | None = None
        all_evidence: list[NormalizedFinding] = []
        runtime_obs: RuntimeObservation | None = None
        partial_status: str | None = None
        scorecard: ScorecardResult | None = None

        try:
            # -------------------------------------------------------------
            # STAGE 1: INGESTING
            # -------------------------------------------------------------
            if await self._check_cancellation(evaluation_id, session, evaluation, steps_executed):
                return self._build_result(evaluation, steps_executed, is_cancelled=True)

            step_log = await self._start_step(
                session, evaluation_id, EvaluationStatus.INGESTING, "INGESTING"
            )
            try:
                if not snapshot_path or not snapshot_path.exists():
                    ingest_result = await self.ingestion_service.ingest_repository(
                        repository.url, ref=ref
                    )
                    if not ingest_result.success or not ingest_result.snapshot_path:
                        raise RuntimeError(
                            f"Repository ingestion failed: {ingest_result.error_message}"
                        )
                    snapshot_path = Path(ingest_result.snapshot_path)
                    detection = ingest_result.technologies or detect_technologies_and_category(
                        snapshot_path
                    )
                else:
                    detection = detect_technologies_and_category(snapshot_path)

                # Update snapshot DB record
                snap_stmt = select(RepositorySnapshot).where(
                    RepositorySnapshot.id == evaluation.snapshot_id
                )
                snapshot_rec = (await session.execute(snap_stmt)).scalar_one_or_none()
                if snapshot_rec:
                    snapshot_rec.detected_languages = (
                        {detection.primary_language: 100} if detection.primary_language else {}
                    )
                    snapshot_rec.detected_frameworks = detection.detected_frameworks
                    snapshot_rec.detected_entrypoints = detection.detected_entrypoints
                    snapshot_rec.storage_path = str(snapshot_path)

                await self._complete_step(session, step_log, StepStatus.SUCCESS)
                steps_executed.append(step_log)
            except Exception as exc:
                await self._complete_step(
                    session, step_log, StepStatus.FAILURE, error_message=str(exc)
                )
                steps_executed.append(step_log)
                evaluation.status = EvaluationStatus.FAILED
                evaluation.error_summary = f"Ingestion error: {exc}"
                await session.flush()
                return self._build_result(evaluation, steps_executed)

            # -------------------------------------------------------------
            # STAGE 2: ANALYZING (Static & Security Analyzers)
            # -------------------------------------------------------------
            if await self._check_cancellation(evaluation_id, session, evaluation, steps_executed):
                return self._build_result(evaluation, steps_executed, is_cancelled=True)

            step_log = await self._start_step(
                session, evaluation_id, EvaluationStatus.ANALYZING, "ANALYZING"
            )
            try:
                tech_stack = {
                    "primary_language": detection.primary_language,
                    "frameworks": detection.detected_frameworks,
                    "archetype": detection.evaluator_category.value,
                }
                findings = await self.analyzer_registry.execute_all(
                    snapshot_path, tech_stack=tech_stack
                )
                all_evidence.extend(findings)

                # Record metrics for discovered findings
                for f in findings:
                    record_finding_metric(
                        severity=f.severity.value
                        if hasattr(f.severity, "value")
                        else str(f.severity),
                        category=f.category.value
                        if hasattr(f.category, "value")
                        else str(f.category),
                    )

                # Persist evidence records to database
                for f in findings:
                    loc_dict = (
                        f.location.model_dump()
                        if f.location is not None and hasattr(f.location, "model_dump")
                        else (f.location if isinstance(f.location, dict) else None)
                    )
                    ev_row = Evidence(
                        id=uuid.uuid4(),
                        evaluation_id=evaluation_id,
                        source=f.analyzer_id,
                        category=f.category,
                        severity=f.severity,
                        confidence=f.confidence,
                        fingerprint=f.fingerprint,
                        title=f.title,
                        description=f.description,
                        location=loc_dict,
                        raw_payload=f.raw_evidence,
                        normalized_attributes={},
                        related_evidence_ids=[],
                    )
                    session.add(ev_row)

                await self._complete_step(
                    session,
                    step_log,
                    StepStatus.SUCCESS,
                    metadata={"findings_count": len(findings)},
                )
                steps_executed.append(step_log)
            except Exception as exc:
                await self._complete_step(
                    session, step_log, StepStatus.FAILURE, error_message=str(exc)
                )
                steps_executed.append(step_log)
                evaluation.status = EvaluationStatus.FAILED
                evaluation.error_summary = f"Static analysis error: {exc}"
                await session.flush()
                return self._build_result(evaluation, steps_executed)

            # -------------------------------------------------------------
            # STAGE 3: RUNTIME EVALUATION (BUILDING -> STARTING -> TESTING)
            # -------------------------------------------------------------
            if await self._check_cancellation(evaluation_id, session, evaluation, steps_executed):
                return self._build_result(evaluation, steps_executed, is_cancelled=True)

            step_build = await self._start_step(
                session, evaluation_id, EvaluationStatus.BUILDING, "BUILDING"
            )
            runtime_obs = await self.runtime_dispatcher.execute_evaluation(
                snapshot_path=snapshot_path,
                detection=detection,
                sandbox_manager=self.sandbox_manager,
                context={"evaluation_id": str(evaluation_id)},
            )

            # Persist observations to DB
            self._persist_runtime_observations(session, evaluation_id, runtime_obs)

            if runtime_obs.failure_code in {
                RuntimeFailureCode.BUILD_FAILURE,
                RuntimeFailureCode.DEPENDENCY_INSTALL_FAILED,
            }:
                await self._complete_step(
                    session,
                    step_build,
                    StepStatus.FAILURE,
                    error_message=runtime_obs.failure_reason,
                    exit_code=1,
                )
                steps_executed.append(step_build)
                partial_status = "BUILD_FAILED"
            else:
                await self._complete_step(session, step_build, StepStatus.SUCCESS, exit_code=0)
                steps_executed.append(step_build)

                # STARTING & TESTING steps
                step_start = await self._start_step(
                    session, evaluation_id, EvaluationStatus.STARTING, "STARTING"
                )
                if runtime_obs.failure_code in {
                    RuntimeFailureCode.STARTUP_TIMEOUT,
                    RuntimeFailureCode.CRASH_ON_BOOT,
                }:
                    await self._complete_step(
                        session,
                        step_start,
                        StepStatus.FAILURE,
                        error_message=runtime_obs.failure_reason,
                    )
                    steps_executed.append(step_start)
                    partial_status = "STARTUP_FAILED"
                else:
                    await self._complete_step(session, step_start, StepStatus.SUCCESS)
                    steps_executed.append(step_start)

                    step_test = await self._start_step(
                        session, evaluation_id, EvaluationStatus.TESTING, "TESTING"
                    )
                    await self._complete_step(session, step_test, StepStatus.SUCCESS)
                    steps_executed.append(step_test)

            # -------------------------------------------------------------
            # STAGE 4: SCORING (Deterministic Core)
            # -------------------------------------------------------------
            if await self._check_cancellation(evaluation_id, session, evaluation, steps_executed):
                return self._build_result(evaluation, steps_executed, is_cancelled=True)

            step_score = await self._start_step(
                session, evaluation_id, EvaluationStatus.SCORING, "SCORING"
            )
            try:
                scorecard = self.scoring_engine.compute_scorecard(
                    evaluation_id=evaluation_id,
                    evidence_records=all_evidence,
                    partial_status=partial_status,
                )
                await self.scoring_engine.persist_scorecard(session, scorecard)
                await self._complete_step(
                    session,
                    step_score,
                    StepStatus.SUCCESS,
                    metadata={
                        "overall_score": float(scorecard.overall_score),
                        "grade": scorecard.grade.value,
                    },
                )
                steps_executed.append(step_score)
            except Exception as exc:
                await self._complete_step(
                    session, step_score, StepStatus.FAILURE, error_message=str(exc)
                )
                steps_executed.append(step_score)
                evaluation.status = EvaluationStatus.FAILED
                evaluation.error_summary = f"Scoring engine error: {exc}"
                await session.flush()
                return self._build_result(evaluation, steps_executed)

            # -------------------------------------------------------------
            # STAGE 5: AI INTERPRETATION (Advisory Qualitative Synthesis)
            # -------------------------------------------------------------
            if enable_ai and scorecard:
                if await self._check_cancellation(
                    evaluation_id, session, evaluation, steps_executed
                ):
                    return self._build_result(evaluation, steps_executed, is_cancelled=True)

                step_ai = await self._start_step(
                    session, evaluation_id, EvaluationStatus.AI_INTERPRETATION, "AI_INTERPRETATION"
                )
                ai_t0 = time.monotonic()
                try:
                    ai_result = await self.ai_service.interpret_evaluation(
                        scorecard=scorecard,
                        evidence_records=all_evidence,
                        detection=detection,
                        runtime=runtime_obs,
                    )
                    ai_duration_s = time.monotonic() - ai_t0
                    record_ai_inference_metric(
                        provider=getattr(self.ai_service.provider, "provider_name", "local"),
                        model=getattr(self.ai_service.provider, "model_name", "default"),
                        duration_seconds=ai_duration_s,
                    )
                    await self.ai_service.persist_analysis(session, evaluation_id, ai_result)
                    await self._complete_step(
                        session,
                        step_ai,
                        StepStatus.SUCCESS,
                        metadata={"is_fallback": ai_result.is_fallback},
                    )
                    steps_executed.append(step_ai)
                except Exception as exc:
                    logger.warning(f"AI Interpretation failed, degrading gracefully: {exc}")
                    await self._complete_step(
                        session, step_ai, StepStatus.FAILURE, error_message=str(exc)
                    )
                    steps_executed.append(step_ai)

            # -------------------------------------------------------------
            # FINALIZATION: Terminal State Transition
            # -------------------------------------------------------------
            total_duration_ms = int((time.monotonic() - t0) * 1000)
            evaluation.completed_at = datetime.now(UTC)
            evaluation.duration_ms = total_duration_ms

            if partial_status:
                evaluation.status = EvaluationStatus.PARTIALLY_COMPLETED
                evaluation.error_summary = f"Completed with partial evaluation: {partial_status}"
            else:
                evaluation.status = EvaluationStatus.COMPLETED

            # Record final evaluation metric
            record_evaluation_metric(
                status=evaluation.status.value,
                duration_seconds=total_duration_ms / 1000.0,
            )

            await self._publish_event(
                evaluation_id,
                "evaluation.lifecycle.completed",
                {
                    "status": evaluation.status.value,
                    "overall_score": float(scorecard.overall_score) if scorecard else 0.0,
                },
            )
            await session.commit()

            return PipelineExecutionResult(
                evaluation_id=evaluation_id,
                repository_id=repository_id,
                status=evaluation.status,
                overall_score=scorecard.overall_score if scorecard else None,
                grade=scorecard.grade if scorecard else None,
                evidence_count=len(all_evidence),
                duration_ms=total_duration_ms,
                steps_executed=steps_executed,
                is_partial=bool(partial_status),
            )

        except Exception as unhandled_exc:
            logger.error(f"Catastrophic pipeline execution failure: {unhandled_exc}", exc_info=True)
            evaluation.status = EvaluationStatus.FAILED
            evaluation.completed_at = datetime.now(UTC)
            evaluation.duration_ms = int((time.monotonic() - t0) * 1000)
            evaluation.error_summary = f"Catastrophic failure: {unhandled_exc}"
            record_evaluation_metric(
                status=EvaluationStatus.FAILED.value,
                duration_seconds=evaluation.duration_ms / 1000.0,
            )
            await session.commit()
            return self._build_result(evaluation, steps_executed, error_summary=str(unhandled_exc))

    async def _start_step(
        self,
        session: AsyncSession,
        evaluation_id: uuid.UUID,
        status_enum: EvaluationStatus,
        step_name: str,
    ) -> StepExecutionLog:
        evaluation = (
            await session.execute(select(Evaluation).where(Evaluation.id == evaluation_id))
        ).scalar_one()
        evaluation.status = status_enum
        await self._publish_event(evaluation_id, "evaluation.step.started", {"step": step_name})
        await session.flush()

        step_db = EvaluationStep(
            id=uuid.uuid4(),
            evaluation_id=evaluation_id,
            step_name=step_name,
            status="RUNNING",
            started_at=datetime.now(UTC),
        )
        session.add(step_db)
        await session.commit()

        return StepExecutionLog(
            step_name=step_name,
            status=StepStatus.RUNNING,
            started_at=step_db.started_at,
            step_id=step_db.id,
            evaluation_id=evaluation_id,
        )

    async def _complete_step(
        self,
        session: AsyncSession,
        log: StepExecutionLog,
        status: StepStatus,
        exit_code: int | None = None,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        log.status = status
        log.completed_at = datetime.now(UTC)
        start_ts = log.started_at
        if start_ts and start_ts.tzinfo is None:
            start_ts = start_ts.replace(tzinfo=UTC)
        completed_ts = log.completed_at
        if completed_ts and completed_ts.tzinfo is None:
            completed_ts = completed_ts.replace(tzinfo=UTC)
        log.duration_ms = int((completed_ts - start_ts).total_seconds() * 1000) if start_ts else 0
        log.exit_code = exit_code
        log.error_message = error_message
        log.metadata = metadata or {}

        # Update step in DB - match by exact step_id, or scope to evaluation_id
        step_id = getattr(log, "step_id", None)
        eval_id = getattr(log, "evaluation_id", None)
        if step_id:
            stmt = select(EvaluationStep).where(EvaluationStep.id == step_id)
        elif eval_id:
            stmt = (
                select(EvaluationStep)
                .where(
                    EvaluationStep.evaluation_id == eval_id,
                    EvaluationStep.step_name == log.step_name,
                    EvaluationStep.status == "RUNNING",
                )
                .order_by(EvaluationStep.created_at.desc())
            )
        else:
            stmt = (
                select(EvaluationStep)
                .where(
                    EvaluationStep.step_name == log.step_name,
                    EvaluationStep.status == "RUNNING",
                )
                .order_by(EvaluationStep.created_at.desc())
            )

        step_db = (await session.execute(stmt)).scalars().first()
        if step_db:
            step_db.status = status.value
            step_db.completed_at = log.completed_at
            step_db.duration_ms = log.duration_ms
            step_db.exit_code = exit_code
            step_db.error_message = error_message
            step_db.step_metadata = log.metadata
        await session.commit()

        # Record operational step metric and structured telemetry log
        record_step_metric(
            step_name=log.step_name,
            status=status.value,
            duration_seconds=log.duration_ms / 1000.0,
        )
        logger.info(
            f"Step '{log.step_name}' finished with status '{status.value}' ({log.duration_ms}ms)",
            extra={
                "extra_data": {
                    "step": log.step_name,
                    "status": status.value,
                    "duration_ms": log.duration_ms,
                    "exit_code": exit_code,
                    "error_message": error_message,
                }
            },
        )

    async def _check_cancellation(
        self,
        evaluation_id: uuid.UUID,
        session: AsyncSession,
        evaluation: Evaluation,
        steps: list[StepExecutionLog],
    ) -> bool:
        if await self.job_queue.is_cancelled(evaluation_id):
            evaluation.status = EvaluationStatus.CANCELLED
            evaluation.completed_at = datetime.now(UTC)
            evaluation.error_summary = "Evaluation cancelled by user request."
            await session.commit()
            return True
        return False

    def _persist_runtime_observations(
        self,
        session: AsyncSession,
        evaluation_id: uuid.UUID,
        obs: RuntimeObservation,
    ) -> None:
        if obs.build_result:
            session.add(
                RuntimeObservationModel(
                    id=uuid.uuid4(),
                    evaluation_id=evaluation_id,
                    observation_type="BUILD",
                    metadata_json={
                        "exit_code": obs.build_result.exit_code,
                        "success": obs.build_result.success,
                        "duration_ms": obs.build_result.duration_ms,
                    },
                )
            )
        if obs.startup_result:
            session.add(
                RuntimeObservationModel(
                    id=uuid.uuid4(),
                    evaluation_id=evaluation_id,
                    observation_type="STARTUP",
                    metadata_json={
                        "ready": obs.startup_result.ready,
                        "port": obs.startup_result.port,
                        "duration_ms": obs.startup_result.duration_ms,
                    },
                )
            )
        if obs.http_metrics:
            session.add(
                RuntimeObservationModel(
                    id=uuid.uuid4(),
                    evaluation_id=evaluation_id,
                    observation_type="HTTP_METRICS",
                    metadata_json={
                        "latency_p95_ms": obs.http_metrics.latency_p95_ms,
                        "total_requests": obs.http_metrics.total_requests,
                        "error_5xx_requests": obs.http_metrics.error_5xx_requests,
                    },
                )
            )
        session.add(
            RuntimeObservationModel(
                id=uuid.uuid4(),
                evaluation_id=evaluation_id,
                observation_type="STRATEGY",
                metric_value_string=obs.evaluator_type.value,
                metadata_json={"primary_language": obs.primary_language},
            )
        )

    async def _publish_event(
        self, evaluation_id: uuid.UUID, event_type: str, data: dict[str, Any]
    ) -> None:
        with contextlib.suppress(Exception):
            await self.job_queue.publish_event(evaluation_id, event_type, data)

    def _build_result(
        self,
        evaluation: Evaluation,
        steps: list[StepExecutionLog],
        is_cancelled: bool = False,
        error_summary: str | None = None,
    ) -> PipelineExecutionResult:
        return PipelineExecutionResult(
            evaluation_id=evaluation.id,
            repository_id=evaluation.repository_id,
            status=evaluation.status,
            steps_executed=steps,
            error_summary=error_summary or evaluation.error_summary,
            is_cancelled=is_cancelled,
        )
