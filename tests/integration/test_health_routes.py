"""
Integration tests for operational health and readiness endpoints.
"""

from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from backend.api.app import create_app
from backend.core.queue import InMemoryJobQueue, set_job_queue

client = TestClient(create_app())


def test_liveness_probe():
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@patch("backend.api.routes.health.check_database_health", new_callable=AsyncMock)
def test_readiness_probe_healthy(mock_db_health):
    mock_db_health.return_value = "connected"
    mock_queue = InMemoryJobQueue()
    set_job_queue(mock_queue)

    response = client.get("/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["database"] == "connected"
    assert data["redis"] == "connected"


@patch("backend.api.routes.health.check_database_health", new_callable=AsyncMock)
def test_readiness_probe_database_down(mock_db_health):
    mock_db_health.return_value = "disconnected"
    mock_queue = InMemoryJobQueue()
    set_job_queue(mock_queue)

    response = client.get("/ready")
    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    problem = response.json()
    assert problem["status"] == 503
    assert "Database is disconnected" in problem["detail"]
    assert "correlation_id" in problem


def test_metrics_endpoint():
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "reposcore_evaluations_total" in response.text
