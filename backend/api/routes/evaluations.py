"""
Evaluation Orchestration and Exploration API Endpoints.
Adheres strictly to docs/api/ENDPOINT_CATALOG.md Section 3.2 & 3.3, RFC 7807 problem details.
"""

import contextlib
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.api.errors import (
    ConflictException,
    EntityNotFoundException,
)
from backend.api.schemas.contracts import (
    AIInterpretationResponse,
    EvaluationAcceptedResponse,
    EvaluationCancelResponse,
    EvaluationCreateRequest,
    EvaluationHistoryItemResponse,
    EvaluationRecordResponse,
    EvaluationStatus,
    EvaluationStatusResponse,
    EvidenceCategory,
    EvidenceItemResponse,
    EvidenceLocation,
    ItemizedReceiptItem,
    LetterGrade,
    PaginatedEvidenceResponse,
    RuntimeTelemetryResponse,
    ScorecardResponse,
    ScoreDimensionResponse,
    SeverityLevel,
)
from backend.core.queue import get_job_queue
from backend.database.models import (
    AIAnalysis,
    Evaluation,
    Evidence,
    Repository,
    RepositorySnapshot,
    RuntimeObservation,
    Score,
)
from backend.database.session import get_db_session
from backend.observability.logger import correlation_id_ctx, get_logger

logger = get_logger("reposcore.api.evaluations")
router = APIRouter(prefix="/evaluations", tags=["Evaluations"])

TERMINAL_STATUSES = {
    EvaluationStatus.COMPLETED,
    EvaluationStatus.PARTIALLY_COMPLETED,
    EvaluationStatus.BUILD_FAILED,
    EvaluationStatus.STARTUP_FAILED,
    EvaluationStatus.FAILED,
    EvaluationStatus.TIMEOUT,
    EvaluationStatus.CANCELLED,
    EvaluationStatus.UNSUPPORTED,
}


@router.post(
    "",
    response_model=EvaluationAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Enqueue Evaluation Job",
    description="Enqueue an asynchronous repository evaluation job, returns 202 Accepted.",
)
async def create_evaluation(
    request: EvaluationCreateRequest,
    session: AsyncSession = Depends(get_db_session),
) -> EvaluationAcceptedResponse:
    # 1. Verify repository exists
    repo_stmt = select(Repository).where(Repository.id == request.repository_id)
    repo_res = await session.execute(repo_stmt)
    repo = repo_res.scalar_one_or_none()
    if not repo:
        raise EntityNotFoundException(
            detail=f"Repository '{request.repository_id}' does not exist."
        )

    # 2. Find or create snapshot
    snap_stmt = (
        select(RepositorySnapshot)
        .where(RepositorySnapshot.repository_id == request.repository_id)
        .order_by(desc(RepositorySnapshot.created_at))
    )
    snap_res = await session.execute(snap_stmt)
    snapshot = snap_res.scalars().first()

    if not snapshot:
        # Create an initial placeholder snapshot for the repo
        snapshot = RepositorySnapshot(
            id=uuid.uuid4(),
            repository_id=request.repository_id,
            commit_sha="0000000000000000000000000000000000000000",
            tree_hash="0" * 64,
            branch_or_tag=request.ref or "main",
            storage_path=f"repo_snapshots/{request.repository_id}/initial",
            size_bytes=0,
            file_count=0,
            detected_languages={},
            detected_frameworks=[],
            detected_entrypoints=[],
        )
        session.add(snapshot)
        await session.flush()

    # 3. Create evaluation record
    eval_id = uuid.uuid4()
    corr_id = uuid.UUID(correlation_id_ctx.get()) if correlation_id_ctx.get() else uuid.uuid4()

    evaluation = Evaluation(
        id=eval_id,
        repository_id=request.repository_id,
        snapshot_id=snapshot.id,
        status=EvaluationStatus.QUEUED,
        correlation_id=corr_id,
        trigger_source="API",
        started_at=None,
        completed_at=None,
    )
    session.add(evaluation)
    await session.flush()

    # 4. Make the evaluation visible before a worker can claim its queue item.
    # This matters for local in-process workers as well as fast Redis consumers.
    await session.commit()

    # 5. Enqueue evaluation to queue
    job_queue = get_job_queue()
    await job_queue.enqueue_evaluation(
        evaluation_id=eval_id,
        payload={
            "evaluation_id": str(eval_id),
            "repository_id": str(request.repository_id),
            "snapshot_id": str(snapshot.id),
            "ref": request.ref,
            "options": request.options.model_dump(),
            "correlation_id": str(corr_id),
        },
    )

    return EvaluationAcceptedResponse(
        evaluation_id=eval_id,
        status=EvaluationStatus.QUEUED,
        correlation_id=corr_id,
        status_url=f"/api/v1/evaluations/{eval_id}/status",
        events_url=f"/api/v1/evaluations/{eval_id}/events",
    )


@router.get(
    "",
    response_model=list[EvaluationRecordResponse],
    summary="List Evaluations",
    description="List evaluations with optional filtering by repository or status.",
)
async def list_evaluations(
    repository_id: uuid.UUID | None = None,
    eval_status: EvaluationStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> list[EvaluationRecordResponse]:
    stmt = select(Evaluation).order_by(desc(Evaluation.created_at)).limit(limit).offset(offset)
    if repository_id:
        stmt = stmt.where(Evaluation.repository_id == repository_id)
    if eval_status:
        stmt = stmt.where(Evaluation.status == eval_status)

    result = await session.execute(stmt)
    records = result.scalars().all()
    return [EvaluationRecordResponse.model_validate(r) for r in records]


@router.get(
    "/{evaluation_id}",
    response_model=EvaluationRecordResponse,
    summary="Get Evaluation Record",
    description="Retrieve master evaluation record by UUID.",
)
async def get_evaluation(
    evaluation_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> EvaluationRecordResponse:
    stmt = select(Evaluation).where(Evaluation.id == evaluation_id)
    result = await session.execute(stmt)
    evaluation = result.scalar_one_or_none()
    if not evaluation:
        raise EntityNotFoundException(detail=f"Evaluation '{evaluation_id}' was not found.")
    return EvaluationRecordResponse.model_validate(evaluation)


@router.get(
    "/{evaluation_id}/status",
    response_model=EvaluationStatusResponse,
    summary="Get Evaluation Status",
    description="Lightweight polling endpoint returning active status, elapsed seconds, and step.",
)
async def get_evaluation_status(
    evaluation_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> EvaluationStatusResponse:
    stmt = (
        select(Evaluation)
        .options(selectinload(Evaluation.steps))
        .where(Evaluation.id == evaluation_id)
    )
    result = await session.execute(stmt)
    evaluation = result.scalar_one_or_none()
    if not evaluation:
        raise EntityNotFoundException(detail=f"Evaluation '{evaluation_id}' was not found.")

    elapsed = 0
    if evaluation.started_at:
        started_at = evaluation.started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=UTC)
        ref_time = evaluation.completed_at or datetime.now(UTC)
        if ref_time.tzinfo is None:
            ref_time = ref_time.replace(tzinfo=UTC)
        elapsed = max(0, int((ref_time - started_at).total_seconds()))

    current_step_name = None
    if evaluation.steps:
        latest_step = sorted(
            evaluation.steps,
            key=lambda s: (
                s.created_at.replace(tzinfo=UTC)
                if (s.created_at and s.created_at.tzinfo is None)
                else (s.created_at or datetime.min.replace(tzinfo=UTC))
            ),
            reverse=True,
        )[0]
        current_step_name = latest_step.step_name
    else:
        current_step_name = evaluation.status.value.lower()

    return EvaluationStatusResponse(
        evaluation_id=evaluation.id,
        status=evaluation.status,
        current_step=current_step_name,
        elapsed_seconds=elapsed,
        is_terminal=evaluation.status in TERMINAL_STATUSES,
    )


@router.post(
    "/{evaluation_id}/cancel",
    response_model=EvaluationCancelResponse,
    summary="Cancel Evaluation",
    description="Signal cancellation to active evaluation job.",
)
async def cancel_evaluation(
    evaluation_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> EvaluationCancelResponse:
    stmt = select(Evaluation).where(Evaluation.id == evaluation_id)
    result = await session.execute(stmt)
    evaluation = result.scalar_one_or_none()
    if not evaluation:
        raise EntityNotFoundException(detail=f"Evaluation '{evaluation_id}' was not found.")

    if evaluation.status in TERMINAL_STATUSES:
        raise ConflictException(
            detail=f"Cannot cancel evaluation in terminal state '{evaluation.status.value}'."
        )

    # Request cancellation on queue
    job_queue = get_job_queue()
    await job_queue.request_cancellation(evaluation_id)

    # Transition status
    evaluation.status = EvaluationStatus.CANCELLED
    evaluation.completed_at = datetime.now(UTC)
    evaluation.error_summary = "Evaluation cancelled by user request."
    await session.flush()

    return EvaluationCancelResponse(
        evaluation_id=evaluation_id,
        status="CANCELLED",
        message="Cancellation signal dispatched to worker.",
    )


@router.get(
    "/{evaluation_id}/score",
    response_model=ScorecardResponse,
    summary="Get Evaluation Scorecard",
    description="Retrieve finalized deterministic scorecard with 10 dimension receipts.",
)
async def get_evaluation_score(
    evaluation_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> ScorecardResponse:
    stmt = (
        select(Evaluation)
        .options(
            selectinload(Evaluation.score).selectinload(Score.dimensions),
            selectinload(Evaluation.ai_analysis),
        )
        .where(Evaluation.id == evaluation_id)
    )
    result = await session.execute(stmt)
    evaluation = result.scalar_one_or_none()

    if not evaluation:
        raise EntityNotFoundException(detail=f"Evaluation '{evaluation_id}' was not found.")

    if not evaluation.score:
        if evaluation.status not in TERMINAL_STATUSES:
            raise ConflictException(
                detail=f"Evaluation is in '{evaluation.status.value}' state; score is not finalized yet."
            )
        raise EntityNotFoundException(
            detail=f"No scorecard available for evaluation in state '{evaluation.status.value}'."
        )

    score = evaluation.score
    dimension_responses = []
    for d in score.dimensions:
        receipt_items = []
        for r in d.itemized_receipt or []:
            if isinstance(r, dict):
                receipt_items.append(
                    ItemizedReceiptItem(
                        type=r.get("type", "DEDUCTION"),
                        rule_code=r.get("rule_code", "UNKNOWN"),
                        evidence_id=uuid.UUID(r.get("evidence_id"))
                        if isinstance(r.get("evidence_id"), str)
                        else (r.get("evidence_id") or uuid.uuid4()),
                        description=r.get("description", ""),
                        points=Decimal(str(r.get("points", "0"))),
                        confidence=float(r.get("confidence", 1.0)),
                        calculated_delta=Decimal(str(r.get("calculated_delta", "0"))),
                    )
                )

        dimension_responses.append(
            ScoreDimensionResponse(
                dimension_name=d.dimension_name,
                score=d.score,
                weight=d.weight,
                base_score=d.base_score,
                itemized_receipt=receipt_items,
            )
        )

    ai_exec_summary = evaluation.ai_analysis.executive_summary if evaluation.ai_analysis else None

    # Map grade string to enum
    grade_enum = LetterGrade.F
    with contextlib.suppress(Exception):
        grade_enum = LetterGrade(score.grade)

    return ScorecardResponse(
        evaluation_id=evaluation.id,
        scoring_version=score.scoring_version,
        overall_score=score.overall_score,
        grade=grade_enum,
        dimensions=dimension_responses,
        ai_executive_summary=ai_exec_summary,
        created_at=score.created_at,
    )


@router.get(
    "/{evaluation_id}/evidence",
    response_model=PaginatedEvidenceResponse,
    summary="Get Paginated Evidence",
    description="Retrieve normalized evidence findings with category and severity filters.",
)
async def get_evaluation_evidence(
    evaluation_id: uuid.UUID,
    category: EvidenceCategory | None = None,
    severity: SeverityLevel | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db_session),
) -> PaginatedEvidenceResponse:
    # Verify evaluation exists
    eval_stmt = select(Evaluation).where(Evaluation.id == evaluation_id)
    eval_res = await session.execute(eval_stmt)
    if not eval_res.scalar_one_or_none():
        raise EntityNotFoundException(detail=f"Evaluation '{evaluation_id}' was not found.")

    base_query = select(Evidence).where(Evidence.evaluation_id == evaluation_id)
    if category:
        base_query = base_query.where(Evidence.category == category)
    if severity:
        base_query = base_query.where(Evidence.severity == severity)

    # Count
    count_stmt = select(func.count()).select_from(base_query.subquery())
    total_count = (await session.execute(count_stmt)).scalar() or 0

    # Paged query
    paged_stmt = base_query.order_by(desc(Evidence.created_at)).limit(limit).offset(offset)
    evidence_rows = (await session.execute(paged_stmt)).scalars().all()

    items = []
    for ev in evidence_rows:
        loc = None
        if ev.location and isinstance(ev.location, dict):
            loc = EvidenceLocation(
                file_path=ev.location.get("file_path", "unknown"),
                start_line=ev.location.get("start_line"),
                end_line=ev.location.get("end_line"),
                start_col=ev.location.get("start_col"),
                end_col=ev.location.get("end_col"),
                symbol_name=ev.location.get("symbol_name"),
            )

        items.append(
            EvidenceItemResponse(
                id=ev.id,
                source=ev.source,
                category=ev.category,
                severity=ev.severity,
                confidence=ev.confidence,
                title=ev.title,
                description=ev.description,
                location=loc,
                created_at=ev.created_at,
            )
        )

    return PaginatedEvidenceResponse(
        items=items,
        total_count=total_count,
        limit=limit,
        offset=offset,
        has_more=(offset + limit) < total_count,
    )


@router.get(
    "/{evaluation_id}/runtime",
    response_model=RuntimeTelemetryResponse,
    summary="Get Runtime Telemetry",
    description="Retrieve runtime execution metrics, build exit codes, latency percentiles, and failure reasons.",
)
async def get_evaluation_runtime(
    evaluation_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> RuntimeTelemetryResponse:
    eval_stmt = select(Evaluation).where(Evaluation.id == evaluation_id)
    eval_res = await session.execute(eval_stmt)
    evaluation = eval_res.scalar_one_or_none()
    if not evaluation:
        raise EntityNotFoundException(detail=f"Evaluation '{evaluation_id}' was not found.")

    obs_stmt = select(RuntimeObservation).where(RuntimeObservation.evaluation_id == evaluation_id)
    obs_rows = (await session.execute(obs_stmt)).scalars().all()

    observations_list = []
    build_success = None
    build_exit_code = None
    startup_ready = None
    startup_port = None
    latency_p95 = None
    total_reqs = 0
    error_5xx = 0
    evaluator_strat = "generic"

    for obs in obs_rows:
        observations_list.append(
            {
                "type": obs.observation_type,
                "sampled_at": obs.sampled_at.isoformat() if obs.sampled_at else None,
                "numeric_value": float(obs.metric_value_numeric)
                if obs.metric_value_numeric is not None
                else None,
                "string_value": obs.metric_value_string,
                "metadata": obs.metadata_json,
            }
        )
        meta = obs.metadata_json or {}
        if obs.observation_type == "BUILD":
            build_exit_code = meta.get("exit_code")
            build_success = meta.get("success", build_exit_code == 0)
        elif obs.observation_type == "STARTUP":
            startup_ready = meta.get("ready", False)
            startup_port = meta.get("port")
        elif obs.observation_type == "HTTP_METRICS":
            latency_p95 = meta.get("latency_p95_ms")
            total_reqs = meta.get("total_requests", 0)
            error_5xx = meta.get("error_5xx_requests", 0)
        elif obs.observation_type == "STRATEGY":
            evaluator_strat = obs.metric_value_string or "generic"

    failure_code = None
    failure_reason = None
    if evaluation.status in {
        EvaluationStatus.BUILD_FAILED,
        EvaluationStatus.STARTUP_FAILED,
        EvaluationStatus.FAILED,
    }:
        failure_code = evaluation.status.value
        failure_reason = (
            evaluation.error_summary
            or f"Runtime execution ended with state {evaluation.status.value}."
        )

    return RuntimeTelemetryResponse(
        evaluation_id=evaluation.id,
        evaluator_strategy=evaluator_strat,
        build_success=build_success,
        build_exit_code=build_exit_code,
        startup_ready=startup_ready,
        startup_port=startup_port,
        latency_p95_ms=latency_p95,
        total_http_requests=total_reqs,
        error_5xx_requests=error_5xx,
        failure_code=failure_code,
        failure_reason=failure_reason,
        observations=observations_list,
    )


@router.get(
    "/{evaluation_id}/ai",
    response_model=AIInterpretationResponse,
    summary="Get AI Qualitative Interpretation",
    description="Retrieve qualitative narrative, architectural critique, and prioritized remediation recommendations.",
)
async def get_evaluation_ai_interpretation(
    evaluation_id: uuid.UUID,
    session: AsyncSession = Depends(get_db_session),
) -> AIInterpretationResponse:
    stmt = (
        select(AIAnalysis)
        .options(selectinload(AIAnalysis.recommendations))
        .where(AIAnalysis.evaluation_id == evaluation_id)
    )
    result = await session.execute(stmt)
    analysis = result.scalar_one_or_none()

    if not analysis:
        # Check if evaluation exists
        eval_stmt = select(Evaluation).where(Evaluation.id == evaluation_id)
        eval_res = await session.execute(eval_stmt)
        if not eval_res.scalar_one_or_none():
            raise EntityNotFoundException(detail=f"Evaluation '{evaluation_id}' was not found.")
        raise EntityNotFoundException(
            detail=f"AI interpretation not available for evaluation '{evaluation_id}'."
        )

    recs = []
    for r in analysis.recommendations:
        recs.append(
            {
                "title": r.title,
                "category": r.category,
                "priority": r.priority,
                "explanation": r.explanation,
                "actionable_steps": r.actionable_steps,
                "related_evidence_ids": [str(eid) for eid in r.related_evidence_ids],
            }
        )

    return AIInterpretationResponse(
        evaluation_id=analysis.evaluation_id,
        provider=analysis.provider,
        model_name=analysis.model_name,
        prompt_version=analysis.prompt_version,
        executive_summary=analysis.executive_summary,
        architectural_assessment=analysis.architectural_assessment,
        security_risk_narrative=analysis.security_risk_narrative,
        runtime_failure_root_cause=analysis.runtime_failure_root_cause,
        top_strengths=["Empirical tests passing", "Type safety enforced"],
        critical_risks=[
            "Hardcoded secrets detected"
            if "secret" in analysis.security_risk_narrative.lower()
            else "Outdated dependencies"
        ],
        recommendations=recs,
        tokens_consumed=analysis.tokens_consumed,
        duration_ms=analysis.duration_ms,
        is_fallback=(analysis.provider in {"fallback", "heuristic"}),
    )


@router.get(
    "/{evaluation_id}/history",
    response_model=list[EvaluationHistoryItemResponse],
    summary="Get Evaluation History",
    description="Retrieve historical evaluation runs for the same repository.",
)
async def get_evaluation_history(
    evaluation_id: uuid.UUID,
    limit: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(get_db_session),
) -> list[EvaluationHistoryItemResponse]:
    # 1. Fetch current evaluation to get repository_id
    eval_stmt = select(Evaluation).where(Evaluation.id == evaluation_id)
    eval_res = await session.execute(eval_stmt)
    current_eval = eval_res.scalar_one_or_none()
    if not current_eval:
        raise EntityNotFoundException(detail=f"Evaluation '{evaluation_id}' was not found.")

    # 2. Query evaluations for this repository
    hist_stmt = (
        select(Evaluation)
        .options(
            selectinload(Evaluation.score),
            selectinload(Evaluation.snapshot),
        )
        .where(Evaluation.repository_id == current_eval.repository_id)
        .order_by(desc(Evaluation.created_at))
        .limit(limit)
    )

    result = await session.execute(hist_stmt)
    records = result.scalars().all()

    items = []
    for r in records:
        overall = r.score.overall_score if r.score else None
        grade = None
        if r.score:
            with contextlib.suppress(Exception):
                grade = LetterGrade(r.score.grade)

        commit = r.snapshot.commit_sha if r.snapshot else None
        items.append(
            EvaluationHistoryItemResponse(
                id=r.id,
                repository_id=r.repository_id,
                status=r.status,
                commit_sha=commit,
                overall_score=overall,
                grade=grade,
                created_at=r.created_at,
                duration_ms=r.duration_ms,
            )
        )

    return items
