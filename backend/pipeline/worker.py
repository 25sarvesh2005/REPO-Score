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
from backend.observability.metrics import record_evaluation_metric
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
        self._stop_event = asyncio.Event()

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
                record_evaluation_metric("timeout", timeout)
                try:
                    await self.job_queue.send_to_dlq(eval_id, payload, reason=f"Timeout exceeded ({timeout}s)")
                except Exception as dlq_err:
                    logger.warning(f"Worker [{self.worker_id}] failed to route to DLQ: {dlq_err}")
                return False

            except Exception as exc:
                logger.error(f"Worker [{self.worker_id}] evaluation {eval_id} encountered fatal error: {exc}", exc_info=True)
                await session.rollback()
                try:
                    await self.job_queue.send_to_dlq(eval_id, payload, reason=str(exc))
                except Exception as dlq_err:
                    logger.warning(f"Worker [{self.worker_id}] failed to route to DLQ: {dlq_err}")
                return False

    async def run_once(self) -> bool:
        """
        Poll and execute a single job from the queue (non-blocking or single pass).
        Useful for integration testing and deterministic test runners.
        """
        payload = await self.job_queue.dequeue_evaluation()
        if payload is None:
            return False
        return await self.process_job(payload)

    def request_shutdown(self) -> None:
        """Ask the polling loop to stop after its current job completes."""
        self._is_running = False
        self._stop_event.set()

    async def run_forever(self, poll_interval_seconds: float = 0.5) -> None:
        """Continuously process queued jobs until graceful shutdown is requested."""
        if poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be greater than zero")

        self._is_running = True
        self._stop_event.clear()
        logger.info(f"Worker [{self.worker_id}] started.")
        try:
            while self._is_running:
                processed = await self.run_once()
                if processed:
                    continue
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=poll_interval_seconds)
                except asyncio.TimeoutError:
                    pass
        finally:
            self._is_running = False
            logger.info(f"Worker [{self.worker_id}] stopped.")


async def main() -> None:
    """Run the production worker process."""
    worker = EvaluationWorker()
    await worker.run_forever()


if __name__ == "__main__":
    asyncio.run(main())
