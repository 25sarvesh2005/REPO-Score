"""
Unit tests for structured logging and secret redaction.
"""

import json
import logging
from backend.observability.logger import (
    StructuredJSONFormatter,
    correlation_id_ctx,
    evaluation_id_ctx,
    redact_secrets,
)


def test_redact_github_token():
    raw = "User token is ghp_1234567890abcdef1234567890abcdef1234 and active"
    redacted = redact_secrets(raw)
    assert "ghp_1234567890abcdef" not in redacted
    assert "[REDACTED_GH_TOKEN]" in redacted


def test_redact_aws_key():
    raw = "AWS key is AKIAIOSFODNN7EXAMPLE used in deploy"
    redacted = redact_secrets(raw)
    assert "AKIAIOSFODNN7EXAMPLE" not in redacted
    assert "[REDACTED_AWS_KEY]" in redacted


def test_redact_bearer_token():
    raw = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.token"
    redacted = redact_secrets(raw)
    assert "[REDACTED_TOKEN]" in redacted


def test_redact_postgres_credentials():
    raw = "Database connection: postgresql://admin:SuperSecretPassword123@localhost:5432/db"
    redacted = redact_secrets(raw)
    assert "SuperSecretPassword123" not in redacted
    assert "postgresql://admin:[REDACTED]@localhost:5432/db" in redacted


def test_structured_json_formatter():
    formatter = StructuredJSONFormatter()
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Processing evaluation for repo",
        args=(),
        exc_info=None,
    )

    token = correlation_id_ctx.set("test-corr-123")
    eval_token = evaluation_id_ctx.set("test-eval-456")
    try:
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test_logger"
        assert parsed["message"] == "Processing evaluation for repo"
        assert parsed["correlation_id"] == "test-corr-123"
        assert parsed["evaluation_id"] == "test-eval-456"
    finally:
        correlation_id_ctx.reset(token)
        evaluation_id_ctx.reset(eval_token)
