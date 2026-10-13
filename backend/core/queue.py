"""
Distributed job queue abstraction, Redis implementation, and Dead-Letter Queue (DLQ).
Adheres strictly to FAILURE_MODEL.md, ADR-007, and Phase 17 resilience standards.
"""

import json
import uuid
from abc import abstractmethod
from datetime import UTC, datetime
from typing import Any, Protocol, cast

import redis.asyncio as aioredis

from backend.core.config import settings
from backend.observability.logger import get_logger

logger = get_logger("reposcore.queue")


class IJobQueue(Protocol):
    """Protocol for RepoScore asynchronous evaluation queue and DLQ."""

    @abstractmethod
    async def enqueue_evaluation(self, evaluation_id: uuid.UUID, payload: dict[str, Any]) -> None:
        """Enqueue an evaluation job for worker processing."""
        ...

    @abstractmethod
    async def dequeue_evaluation(self) -> dict[str, Any] | None:
        """Claim the next evaluation payload, or return ``None`` when the queue is empty."""
        ...

    @abstractmethod
    async def publish_event(
        self, evaluation_id: uuid.UUID, event_type: str, data: dict[str, Any]
    ) -> None:
        """Publish real-time event to SSE channel."""
        ...

    @abstractmethod
    async def is_cancelled(self, evaluation_id: uuid.UUID) -> bool:
        """Check if an abort token has been set for this evaluation."""
        ...

    @abstractmethod
    async def request_cancellation(self, evaluation_id: uuid.UUID) -> None:
        """Set an abort token to request job cancellation."""
        ...

    @abstractmethod
    async def send_to_dlq(
        self, evaluation_id: uuid.UUID, payload: dict[str, Any], reason: str
    ) -> None:
        """Move an unrecoverable or failed task to the dead-letter queue."""
        ...

    @abstractmethod
    async def check_health(self) -> str:
        """Check queue connectivity."""
        ...


class RedisJobQueue:
    """Production Redis queue implementation using streams, Pub/Sub, and DLQ."""

    def __init__(self, redis_url: str = settings.REDIS_URL):
        self.redis_url = redis_url
        self._client: aioredis.Redis | None = None

    def _get_client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=settings.REDIS_MAX_CONNECTIONS,
            )
        return self._client

    async def enqueue_evaluation(self, evaluation_id: uuid.UUID, payload: dict[str, Any]) -> None:
        client = self._get_client()
        serialized = json.dumps(payload)
        await client.rpush("reposcore:queue:evaluations", serialized)
        logger.info(f"Evaluation {evaluation_id} enqueued to Redis queue.")

    async def dequeue_evaluation(self) -> dict[str, Any] | None:
        """Claim one queued payload without exposing Redis details to workers."""
        client = self._get_client()
        serialized = await client.lpop("reposcore:queue:evaluations")
        if serialized is None:
            return None
        if not isinstance(serialized, (str, bytes, bytearray)):
            logger.error("Discarding Redis evaluation payload with an invalid response type.")
            return None

        try:
            payload = json.loads(serialized)
        except (TypeError, json.JSONDecodeError) as exc:
            logger.error(f"Discarding malformed Redis evaluation payload: {exc}")
            return None

        if not isinstance(payload, dict):
            logger.error("Discarding Redis evaluation payload that is not a JSON object.")
            return None
        return cast(dict[str, Any], payload)

    async def publish_event(
        self, evaluation_id: uuid.UUID, event_type: str, data: dict[str, Any]
    ) -> None:
        client = self._get_client()
        message = json.dumps({"event": event_type, "data": data})
        channel = f"reposcore:events:{evaluation_id}"
        await client.publish(channel, message)

    async def is_cancelled(self, evaluation_id: uuid.UUID) -> bool:
        client = self._get_client()
        key = f"reposcore:cancel:{evaluation_id}"
        exists = await client.exists(key)
        return bool(exists)

    async def request_cancellation(self, evaluation_id: uuid.UUID) -> None:
        client = self._get_client()
        key = f"reposcore:cancel:{evaluation_id}"
        await client.set(key, "1", ex=600)  # 10 minute TTL
        logger.info(f"Cancellation requested for evaluation {evaluation_id}.")

    async def send_to_dlq(
        self, evaluation_id: uuid.UUID, payload: dict[str, Any], reason: str
    ) -> None:
        client = self._get_client()
        dlq_entry = {
            "evaluation_id": str(evaluation_id),
            "payload": payload,
            "reason": reason,
            "failed_at": datetime.now(UTC).isoformat(),
        }
        await client.rpush("reposcore:dlq:evaluations", json.dumps(dlq_entry))
        logger.warning(f"Evaluation {evaluation_id} moved to DLQ: {reason}")

    async def check_health(self) -> str:
        try:
            client = self._get_client()
            pong = await client.ping()
            if pong:
                return "connected"
            return "disconnected"
        except Exception as exc:
            logger.warning(f"Redis health check failed: {exc}")
            return "disconnected"


class InMemoryJobQueue:
    """In-memory queue implementation for standalone local testing and DLQ tracking."""

    def __init__(self) -> None:
        self.queue: list[dict[str, Any]] = []
        self.cancelled_tokens: set[str] = set()
        self.published_events: list[dict[str, Any]] = []
        self.dlq: list[dict[str, Any]] = []

    async def enqueue_evaluation(self, evaluation_id: uuid.UUID, payload: dict[str, Any]) -> None:
        self.queue.append({"id": str(evaluation_id), "payload": payload})

    async def dequeue_evaluation(self) -> dict[str, Any] | None:
        """Claim the oldest queued payload using the same FIFO semantics as Redis."""
        if not self.queue:
            return None
        item = self.queue.pop(0)
        payload = item.get("payload")
        return dict(payload) if isinstance(payload, dict) else None

    async def publish_event(
        self, evaluation_id: uuid.UUID, event_type: str, data: dict[str, Any]
    ) -> None:
        self.published_events.append(
            {"evaluation_id": str(evaluation_id), "event": event_type, "data": data}
        )

    async def is_cancelled(self, evaluation_id: uuid.UUID) -> bool:
        return str(evaluation_id) in self.cancelled_tokens

    async def request_cancellation(self, evaluation_id: uuid.UUID) -> None:
        self.cancelled_tokens.add(str(evaluation_id))

    async def send_to_dlq(
        self, evaluation_id: uuid.UUID, payload: dict[str, Any], reason: str
    ) -> None:
        self.dlq.append(
            {
                "evaluation_id": str(evaluation_id),
                "payload": payload,
                "reason": reason,
                "failed_at": datetime.now(UTC).isoformat(),
            }
        )

    async def check_health(self) -> str:
        return "connected"


# Global queue singleton
_job_queue: IJobQueue | None = None


def get_job_queue() -> IJobQueue:
    """Retrieve active queue instance."""
    global _job_queue
    if _job_queue is None:
        if settings.APP_ENV == "testing" or settings.REDIS_URL.startswith("memory://"):
            _job_queue = InMemoryJobQueue()
        else:
            _job_queue = RedisJobQueue(settings.REDIS_URL)
    return _job_queue


def set_job_queue(queue: IJobQueue) -> None:
    """Explicitly override queue instance (e.g. for testing)."""
    global _job_queue
    _job_queue = queue
