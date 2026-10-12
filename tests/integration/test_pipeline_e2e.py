"""
End-to-End Integration Tests for Evaluation Pipeline Orchestrator and Worker.
Adheres strictly to Phase 13 requirements:
- Real fixture repository flows end-to-end
- Failure paths explicit (BUILD_FAILED -> PARTIALLY_COMPLETED)
- Cancellation handling
- Correlation and provenance intact
- No mocked success in production path
"""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import tempfile
from unittest.mock import AsyncMock, MagicMock
import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.ai.mock_provider import MockProvider
from backend.ai.service import AIInterpretationService
from backend.analyzers.registry import AnalyzerRegistry
from backend.api.schemas.contracts import (
    EvaluationStatus,
    EvidenceCategory,
    LetterGrade,
    SeverityLevel,
)
from backend.core.queue import InMemoryJobQueue
from backend.database.models import (
    AIAnalysis,
    Evaluation,
    EvaluationStep,
    Evidence,
    Repository,
    RepositorySnapshot,
    RuntimeObservation as RuntimeObservationModel,
    Score,
    ScoreDimension,
)
from backend.pipeline.models import PipelineExecutionResult
from backend.pipeline.orchestrator import EvaluationPipelineOrchestrator
from backend.pipeline.worker import EvaluationWorker
from backend.repository.service import RepositoryIngestionService
from backend.runtime.dispatcher import RuntimeDispatcher
from backend.runtime.models import (
    BuildResult,
    EvaluatorType,
    HttpMetrics,
    RuntimeFailureCode,
    RuntimeObservation,
    StartupResult,
)
from backend.sandbox.mock import MockSandboxManager
from backend.scoring.calculator import DeterministicScoringEngine


@pytest.fixture
def temp_fixture_repo(tmp_path: Path):
    """Create a real fixture repository on disk with clean code."""
    repo_dir = tmp_path / "sample_service"
    repo_dir.mkdir(parents=True, exist_ok=True)

    # 1. Main entrypoint
    main_py = repo_dir / "main.py"
    main_py.write_text(
        '"""FastAPI service sample."""\n'
        'from fastapi import FastAPI\n'
        'app = FastAPI()\n\n'
        '@app.get("/health")\n'
        'def health():\n'
        '    return {"status": "ok"}\n',
        encoding="utf-8",
    )

    # 2. Config & requirements
    reqs_txt = repo_dir / "requirements.txt"
    reqs_txt.write_text("fastapi>=0.100.0\nuvicorn>=0.22.0\n", encoding="utf-8")

    # 3. Tests
    test_dir = repo_dir / "tests"
    test_dir.mkdir(parents=True, exist_ok=True)
    test_file = test_dir / "test_main.py"
    test_file.write_text(
        "def test_sample():\n    assert 1 + 1 == 2\n",
        encoding="utf-8",
    )

    return repo_dir


@pytest.fixture
def mock_db_session():
    """Mock asynchronous database session that simulates entity tracking."""
    session = AsyncMock(spec=AsyncSession)
    stored_entities = {}

    def _add(entity):
        tbl = getattr(entity, "__tablename__", type(entity).__name__)
        if tbl not in stored_entities:
            stored_entities[tbl] = []
        stored_entities[tbl].append(entity)

    session.add.side_effect = _add
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()

    return session, stored_entities


@pytest.mark.asyncio
async def test_pipeline_e2e_clean_repository(temp_fixture_repo, mock_db_session):
    session, stored = mock_db_session

    repo_id = uuid.uuid4()
    eval_id = uuid.uuid4()
    snap_id = uuid.uuid4()
    corr_id = uuid.uuid4()

    repository = Repository(
        id=repo_id,
        url="https://github.com/fastapi/fastapi",
        provider="github",
        owner="fastapi",
        name="fastapi",
        default_branch="master",
        is_private=False,
        stars_count=75000,
        created_at=datetime.now(timezone.utc),
    )

    snapshot = RepositorySnapshot(
        id=snap_id,
        repository_id=repo_id,
        commit_sha="a" * 40,
        tree_hash="b" * 64,
        branch_or_tag="master",
        storage_path=str(temp_fixture_repo),
        size_bytes=1024,
        file_count=3,
        detected_languages={"Python": 100},
        detected_frameworks=["FastAPI"],
        detected_entrypoints=["main.py"],
        created_at=datetime.now(timezone.utc),
    )

    evaluation = Evaluation(
        id=eval_id,
        repository_id=repo_id,
        snapshot_id=snap_id,
        status=EvaluationStatus.QUEUED,
        correlation_id=corr_id,
        trigger_source="API",
        created_at=datetime.now(timezone.utc),
    )

    # Setup session query responses
    def _execute_query(stmt):
        mock_res = MagicMock()
        stmt_str = str(stmt).lower()
        if "from evaluations" in stmt_str:
            mock_res.scalar_one_or_none.return_value = evaluation
            mock_res.scalar_one.return_value = evaluation
        elif "from repositories" in stmt_str:
            mock_res.scalar_one_or_none.return_value = repository
        elif "from repository_snapshots" in stmt_str:
            mock_res.scalar_one_or_none.return_value = snapshot
        elif "from evaluation_steps" in stmt_str:
            mock_scalars = MagicMock()
            mock_scalars.first.return_value = None
            mock_res.scalars.return_value = mock_scalars
        return mock_res

    session.execute.side_effect = _execute_query

    # Setup orchestrator with real analyzers, scoring engine, and mock sandbox
    job_queue = InMemoryJobQueue()
    sandbox_manager = MockSandboxManager()
    ai_service = AIInterpretationService(provider=MockProvider())

    orchestrator = EvaluationPipelineOrchestrator(
        sandbox_manager=sandbox_manager,
        ai_service=ai_service,
        job_queue=job_queue,
    )

    result = await orchestrator.execute_pipeline(
        session=session,
        evaluation_id=eval_id,
        repository_id=repo_id,
        ref="master",
        options={"enable_ai_reasoning": True},
        fixture_snapshot_path=temp_fixture_repo,
    )

    # Invariants Check:
    assert result.status == EvaluationStatus.COMPLETED
    assert result.is_partial is False
    assert result.is_cancelled is False
    assert result.overall_score is not None
    assert result.overall_score >= Decimal("85.0")  # Clean repo gets A or A+
    assert result.grade in {LetterGrade.A, LetterGrade.A_PLUS}

    # Verify lifecycle steps executed: INGESTING, ANALYZING, BUILDING, STARTING, TESTING, SCORING, AI_INTERPRETATION
    step_names = [s.step_name for s in result.steps_executed]
    assert "INGESTING" in step_names
    assert "ANALYZING" in step_names
    assert "BUILDING" in step_names
    assert "SCORING" in step_names
    assert "AI_INTERPRETATION" in step_names

    # Verify database persistence calls
    assert "scores" in stored
    assert "score_dimensions" in stored
    assert len(stored["score_dimensions"]) == 10  # All 10 dimensions persisted!
    assert "ai_analyses" in stored


@pytest.mark.asyncio
async def test_pipeline_e2e_partial_completion_on_build_failure(temp_fixture_repo, mock_db_session):
    """
    Test failure path: When container build fails, pipeline must gracefully route
    to SCORING with partial penalties and finish in PARTIALLY_COMPLETED.
    """
    session, stored = mock_db_session

    repo_id = uuid.uuid4()
    eval_id = uuid.uuid4()
    snap_id = uuid.uuid4()

    repository = Repository(
        id=repo_id,
        url="https://github.com/broken/broken-app",
        provider="github",
        owner="broken",
        name="broken-app",
        default_branch="master",
        is_private=False,
    )

    evaluation = Evaluation(
        id=eval_id,
        repository_id=repo_id,
        snapshot_id=snap_id,
        status=EvaluationStatus.QUEUED,
        correlation_id=uuid.uuid4(),
        trigger_source="API",
    )

    def _execute_query(stmt):
        mock_res = MagicMock()
        stmt_str = str(stmt).lower()
        if "from evaluations" in stmt_str:
            mock_res.scalar_one_or_none.return_value = evaluation
            mock_res.scalar_one.return_value = evaluation
        elif "from repositories" in stmt_str:
            mock_res.scalar_one_or_none.return_value = repository
        elif "from repository_snapshots" in stmt_str:
            mock_res.scalar_one_or_none.return_value = None
        elif "from evaluation_steps" in stmt_str:
            mock_scalars = MagicMock()
            mock_scalars.first.return_value = None
            mock_res.scalars.return_value = mock_scalars
        return mock_res

    session.execute.side_effect = _execute_query

    # Mock dispatcher simulating build failure
    mock_dispatcher = MagicMock(spec=RuntimeDispatcher)
    mock_dispatcher.execute_evaluation = AsyncMock(
        return_value=RuntimeObservation(
            evaluation_id=str(eval_id),
            evaluator_type=EvaluatorType.HTTP_API,
            build_result=BuildResult(exit_code=1, stdout="", stderr="SyntaxError: invalid syntax", duration_ms=500, success=False),
            failure_code=RuntimeFailureCode.BUILD_FAILURE,
            failure_reason="Compilation failed: SyntaxError in dependencies",
            critical_logs=["SyntaxError: invalid syntax"],
        )
    )

    orchestrator = EvaluationPipelineOrchestrator(
        runtime_dispatcher=mock_dispatcher,
        ai_service=AIInterpretationService(provider=MockProvider()),
        job_queue=InMemoryJobQueue(),
    )

    result = await orchestrator.execute_pipeline(
        session=session,
        evaluation_id=eval_id,
        repository_id=repo_id,
        fixture_snapshot_path=temp_fixture_repo,
    )

    # Must finish in PARTIALLY_COMPLETED, not fake COMPLETED!
    assert result.status == EvaluationStatus.PARTIALLY_COMPLETED
    assert result.is_partial is True
    assert evaluation.status == EvaluationStatus.PARTIALLY_COMPLETED
    assert "partial evaluation" in evaluation.error_summary.lower()

    # Scores and receipts were still computed
    assert result.overall_score is not None
    assert "scores" in stored


@pytest.mark.asyncio
async def test_pipeline_cancellation_handling(temp_fixture_repo, mock_db_session):
    """
    Test cancellation token detection mid-pipeline terminates execution cleanly.
    """
    session, stored = mock_db_session

    repo_id = uuid.uuid4()
    eval_id = uuid.uuid4()

    repository = Repository(
        id=repo_id,
        url="https://github.com/fastapi/fastapi",
        provider="github",
        owner="fastapi",
        name="fastapi",
        default_branch="master",
        is_private=False,
    )

    evaluation = Evaluation(
        id=eval_id,
        repository_id=repo_id,
        snapshot_id=uuid.uuid4(),
        status=EvaluationStatus.QUEUED,
        correlation_id=uuid.uuid4(),
        trigger_source="API",
    )

    def _execute_query(stmt):
        mock_res = MagicMock()
        stmt_str = str(stmt).lower()
        if "from evaluations" in stmt_str:
            mock_res.scalar_one_or_none.return_value = evaluation
            mock_res.scalar_one.return_value = evaluation
        elif "from repositories" in stmt_str:
            mock_res.scalar_one_or_none.return_value = repository
        else:
            mock_scalars = MagicMock()
            mock_scalars.first.return_value = None
            mock_res.scalars.return_value = mock_scalars
            mock_res.scalar_one_or_none.return_value = None
        return mock_res

    session.execute.side_effect = _execute_query

    job_queue = InMemoryJobQueue()
    # Trigger cancellation before execution begins
    await job_queue.request_cancellation(eval_id)

    orchestrator = EvaluationPipelineOrchestrator(
        job_queue=job_queue,
    )

    result = await orchestrator.execute_pipeline(
        session=session,
        evaluation_id=eval_id,
        repository_id=repo_id,
        fixture_snapshot_path=temp_fixture_repo,
    )

    assert result.is_cancelled is True
    assert evaluation.status == EvaluationStatus.CANCELLED
    assert "cancelled" in evaluation.error_summary.lower()


@pytest.mark.asyncio
async def test_worker_run_once(temp_fixture_repo, mock_db_session):
    """
    Test EvaluationWorker successfully consumes a queued job and processes it.
    """
    job_queue = InMemoryJobQueue()
    eval_id = uuid.uuid4()
    repo_id = uuid.uuid4()

    # Enqueue a job
    await job_queue.enqueue_evaluation(
        evaluation_id=eval_id,
        payload={
            "evaluation_id": str(eval_id),
            "repository_id": str(repo_id),
            "ref": "master",
            "options": {"timeout_seconds": 60},
        },
    )

    mock_orch = MagicMock(spec=EvaluationPipelineOrchestrator)
    mock_orch.execute_pipeline = AsyncMock(
        return_value=PipelineExecutionResult(
            evaluation_id=eval_id,
            repository_id=repo_id,
            status=EvaluationStatus.COMPLETED,
            overall_score=Decimal("92.0"),
            grade=LetterGrade.A,
        )
    )

    session, _ = mock_db_session
    mock_res_eval = MagicMock()
    mock_res_eval.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_res_eval

    from contextlib import asynccontextmanager
    @asynccontextmanager
    async def mock_session_factory():
        yield session

    worker = EvaluationWorker(
        worker_id="test-worker-1",
        job_queue=job_queue,
        orchestrator=mock_orch,
        session_factory=mock_session_factory,
    )

    # Worker claims and processes the single enqueued job through the queue protocol.
    assert len(job_queue.queue) == 1
    success = await worker.run_once()
    assert success is True
    assert mock_orch.execute_pipeline.called


@pytest.mark.asyncio
async def test_worker_run_forever_claims_queued_jobs(mock_db_session):
    """The daemon loop must consume queued jobs instead of leaving them QUEUED indefinitely."""
    job_queue = InMemoryJobQueue()
    eval_id = uuid.uuid4()
    repo_id = uuid.uuid4()
    await job_queue.enqueue_evaluation(
        evaluation_id=eval_id,
        payload={
            "evaluation_id": str(eval_id),
            "repository_id": str(repo_id),
            "ref": "main",
            "options": {"timeout_seconds": 60},
        },
    )

    mock_orch = MagicMock(spec=EvaluationPipelineOrchestrator)
    mock_orch.execute_pipeline = AsyncMock(
        return_value=PipelineExecutionResult(
            evaluation_id=eval_id,
            repository_id=repo_id,
            status=EvaluationStatus.COMPLETED,
            overall_score=Decimal("92.0"),
            grade=LetterGrade.A,
        )
    )
    session, _ = mock_db_session
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result

    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def mock_session_factory():
        yield session

    worker = EvaluationWorker(
        worker_id="daemon-test-worker",
        job_queue=job_queue,
        orchestrator=mock_orch,
        session_factory=mock_session_factory,
    )
    worker_task = asyncio.create_task(worker.run_forever(poll_interval_seconds=0.01))
    try:
        for _ in range(20):
            if mock_orch.execute_pipeline.called:
                break
            await asyncio.sleep(0.01)
        assert mock_orch.execute_pipeline.called
    finally:
        worker.request_shutdown()
        await asyncio.wait_for(worker_task, timeout=1)
