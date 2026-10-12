"""
Unit tests for queue abstraction and in-memory mock implementation.
"""

import uuid
import pytest
from backend.core.queue import InMemoryJobQueue


@pytest.mark.asyncio
async def test_in_memory_queue_operations():
    queue = InMemoryJobQueue()
    eval_id = uuid.uuid4()
    payload = {"repository_id": str(uuid.uuid4()), "ref": "main"}

    # Test enqueue
    await queue.enqueue_evaluation(eval_id, payload)
    assert len(queue.queue) == 1
    assert queue.queue[0]["id"] == str(eval_id)

    # Test event publishing
    await queue.publish_event(eval_id, "step_started", {"step": "INGESTING"})
    assert len(queue.published_events) == 1
    assert queue.published_events[0]["event"] == "step_started"

    # Test cancellation token
    assert await queue.is_cancelled(eval_id) is False
    await queue.request_cancellation(eval_id)
    assert await queue.is_cancelled(eval_id) is True

    # Test health
    assert await queue.check_health() == "connected"
