"""
Asynchronous Evaluation Job Worker.
Processes queued evaluation tasks from Redis, executes orchestrator pipeline,
and guarantees graceful shutdown and timeout recovery.
"""

import asyncio
from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, Optional
import uuid

from sqlalchemy import select

from backend.core.config import settings
from backend.core.queue import IJobQueue, get_job_queue
from backend.database.models import Evaluation
from backend.database.session import AsyncSessionLocal
from backend.observability.logger import get_logger
from backend.pipeline.orchestrator import EvaluationPipelineOrchestrator

logger = get_logger("reposcore.pipeline.worker")


class EvaluationWorker:
    """
    Background worker that continuously pulls evaluation tasks from the queue
    and triggers pipeline orchestration.
    """

    def __init__(
        self,
        worker_id: Optional[str] = None,
        job_queue: Optional[IJobQueue] = None,
        orchestrator: Optional[EvaluationPipelineOrchestrator] = None,
        session_factory: Optional[Any] = None,
    ) -> None:
        self.worker_id = worker_id or f"worker-{uuid.uuid4().hex[:8]}"
        self.job_queue = job_queue or get_job_queue()
        self.orchestrator = orchestrator or EvaluationPipelineOrchestrator(job_queue=self.job_queue)
        self.session_factory = session_factory or AsyncSessionLocal
        self._is_running = False

    async def process_job(self, payload: Dict[str, Any]) -> bool:
        """
        Process a single evaluation job payload.
        Returns True if successful, False if failed.
        """
        raw_eval_id = payload.get("evaluation_id")
        raw_repo_id = payload.get("repository_id")
        ref = payload.get("ref", "main")
        options = payload.get("options", {})

        if not raw_eval_id or not raw_repo_id:
            logger.error(f"Malformed job payload missing IDs: {payload}")
            return False

        try:
            eval_id = uuid.UUID(str(raw_eval_id))
            repo_id = uuid.UUID(str(raw_repo_id))
        except (ValueError, TypeError, AttributeError) as exc:
            logger.error(f"Malformed job payload with invalid UUIDs: {payload} - {exc}")
            return False

        logger.info(f"Worker [{self.worker_id}] claimed evaluation {eval_id}...")

        async with self.session_factory() as session:
            try:
                # Stamp worker ID on evaluation
                stmt = select(Evaluation).where(Evaluation.id == eval_id)
                eval_rec = (await session.execute(stmt)).scalar_one_or_none()
                if eval_rec:
                    eval_rec.worker_id = self.worker_id
                    await session.flush()

                # Execute pipeline with timeout
                timeout = float(options.get("timeout_seconds", settings.EVALUATION_DEFAULT_TIMEOUT_SECONDS))
                result = await asyncio.wait_for(
                    self.orchestrator.execute_pipeline(
                        session=session,
                        evaluation_id=eval_id,
                        repository_id=repo_id,
                        ref=ref,
                        options=options,
                    ),
                    timeout=timeout,
                )

                logger.info(
                    f"Worker [{self.worker_id}] finished evaluation {eval_id} "
                    f"with status {result.status.value} (score={result.overall_score}, grade={result.grade})"
                )
                return True

            except asyncio.TimeoutError:
                logger.error(f"Worker [{self.worker_id}] evaluation {eval_id} exceeded timeout {timeout}s.")
                if eval_rec:
                    eval_rec.status = "TIMEOUT"
                    eval_rec.error_summary = f"Evaluation job exceeded timeout limit of {timeout} seconds."
                    eval_rec.completed_at = datetime.now(timezone.utc)
                    await session.commit()
                return False

            except Exception as exc:
                logger.error(f"Worker [{self.worker_id}] evaluation {eval_id} encountered fatal error: {exc}", exc_info=True)
                await session.rollback()
                return False

    async def run_once(self) -> bool:
        """
        Poll and execute a single job from the queue (non-blocking or single pass).
        Useful for integration testing and deterministic test runners.
        """
        # If using InMemoryJobQueue
        if hasattr(self.job_queue, "queue") and self.job_queue.queue:
            item = self.job_queue.queue.pop(0)
            return await self.process_job(item.get("payload", {}))
        return False
