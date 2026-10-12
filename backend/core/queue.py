"""
Distributed job queue abstraction and Redis implementation.
"""

from abc import abstractmethod
import json
from typing import Any, Dict, Optional, Protocol
import uuid
import redis.asyncio as aioredis

from backend.core.config import settings
from backend.observability.logger import get_logger

logger = get_logger("reposcore.queue")


class IJobQueue(Protocol):
    """Protocol for RepoScore asynchronous evaluation queue."""

    @abstractmethod
    async def enqueue_evaluation(self, evaluation_id: uuid.UUID, payload: Dict[str, Any]) -> None:
        """Enqueue an evaluation job for worker processing."""
        ...

    @abstractmethod
    async def publish_event(self, evaluation_id: uuid.UUID, event_type: str, data: Dict[str, Any]) -> None:
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
    async def check_health(self) -> str:
        """Check queue connectivity."""
        ...


class RedisJobQueue:
    """Production Redis queue implementation using streams and Pub/Sub."""

    def __init__(self, redis_url: str = settings.REDIS_URL):
        self.redis_url = redis_url
        self._client: Optional[aioredis.Redis] = None

    def _get_client(self) -> aioredis.Redis:
        if self._client is None:
            self._client = aioredis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=settings.REDIS_MAX_CONNECTIONS,
            )
        return self._client

    async def enqueue_evaluation(self, evaluation_id: uuid.UUID, payload: Dict[str, Any]) -> None:
        client = self._get_client()
        serialized = json.dumps(payload)
        await client.rpush("reposcore:queue:evaluations", serialized)
        logger.info(f"Evaluation {evaluation_id} enqueued to Redis queue.")

    async def publish_event(self, evaluation_id: uuid.UUID, event_type: str, data: Dict[str, Any]) -> None:
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
    """In-memory mock queue implementation for unit tests and local isolation."""

    def __init__(self) -> None:
        self.queue: list[Dict[str, Any]] = []
        self.cancelled_tokens: set[str] = set()
        self.published_events: list[Dict[str, Any]] = []

    async def enqueue_evaluation(self, evaluation_id: uuid.UUID, payload: Dict[str, Any]) -> None:
        self.queue.append({"id": str(evaluation_id), "payload": payload})

    async def publish_event(self, evaluation_id: uuid.UUID, event_type: str, data: Dict[str, Any]) -> None:
        self.published_events.append({"evaluation_id": str(evaluation_id), "event": event_type, "data": data})

    async def is_cancelled(self, evaluation_id: uuid.UUID) -> bool:
        return str(evaluation_id) in self.cancelled_tokens

    async def request_cancellation(self, evaluation_id: uuid.UUID) -> None:
        self.cancelled_tokens.add(str(evaluation_id))

    async def check_health(self) -> str:
        return "connected"


# Global queue singleton
_job_queue: Optional[IJobQueue] = None


def get_job_queue() -> IJobQueue:
    """Retrieve active queue instance."""
    global _job_queue
    if _job_queue is None:
        if settings.APP_ENV == "testing":
            _job_queue = InMemoryJobQueue()
        else:
            _job_queue = RedisJobQueue(settings.REDIS_URL)
    return _job_queue


def set_job_queue(queue: IJobQueue) -> None:
    """Explicitly override queue instance (e.g. for testing)."""
    global _job_queue
    _job_queue = queue
