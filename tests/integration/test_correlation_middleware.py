"""
Integration tests for correlation ID propagation and header handling.
"""

import uuid

from fastapi.testclient import TestClient

from backend.api.app import create_app

client = TestClient(create_app())


def test_correlation_id_echo():
    custom_id = str(uuid.uuid4())
    response = client.get("/health", headers={"X-Correlation-ID": custom_id})
    assert response.status_code == 200
    assert response.headers.get("X-Correlation-ID") == custom_id


def test_correlation_id_auto_generation():
    response = client.get("/health")
    assert response.status_code == 200
    generated_id = response.headers.get("X-Correlation-ID")
    assert generated_id is not None
    # Validate it parses as UUID
    parsed = uuid.UUID(generated_id)
    assert str(parsed) == generated_id
