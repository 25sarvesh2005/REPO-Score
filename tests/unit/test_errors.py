"""
Unit tests for domain exceptions and RFC 7807 Problem Details.
"""

from backend.api.errors import (
    EntityNotFoundException,
    RepoScoreException,
    build_problem_payload,
)


def test_domain_exception_defaults():
    exc = EntityNotFoundException("Snapshot not found")
    assert exc.status_code == 404
    assert exc.title == "Resource Not Found"
    assert exc.detail == "Snapshot not found"


def test_build_problem_payload():
    payload = build_problem_payload(
        status_code=404,
        title="Resource Not Found",
        detail="Repository not found",
        instance="/api/v1/repositories/123",
        error_type="https://reposcore.internal/errors/not-found",
    )

    assert payload["status"] == 404
    assert payload["title"] == "Resource Not Found"
    assert payload["detail"] == "Repository not found"
    assert payload["instance"] == "/api/v1/repositories/123"
    assert "correlation_id" in payload
    assert "timestamp" in payload
