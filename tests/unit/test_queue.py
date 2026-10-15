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
    assert await queue.dequeue_evaluation() == payload
    assert await queue.dequeue_evaluation() is None

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


@pytest.mark.asyncio
async def test_in_memory_queue_subscribe_events():
    queue = InMemoryJobQueue()
    eval_id = uuid.uuid4()

    await queue.publish_event(eval_id, "step_started", {"step": "INGESTING"})
    await queue.publish_event(eval_id, "evaluation_finished", {"status": "COMPLETED"})

    events = []
    gen = queue.subscribe_events(eval_id, timeout=0.01)
    try:
        async for item in gen:
            if not item:
                break
            events.append(item)
            if item.get("event") == "evaluation_finished":
                break
    finally:
        await gen.aclose()

    assert len(events) == 2
    assert events[0]["event"] == "step_started"
    assert events[1]["event"] == "evaluation_finished"
