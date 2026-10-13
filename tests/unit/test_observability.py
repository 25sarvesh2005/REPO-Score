"""
Unit and integration tests for Observability, Metrics, and Operational Diagnostics.
Adheres strictly to Phase 16 specifications and OBSERVABILITY_ARCHITECTURE.md.
"""

import json
import logging

from backend.observability.logger import (
    StructuredJSONFormatter,
    correlation_id_ctx,
    evaluation_id_ctx,
    redact_secrets,
)
from backend.observability.metrics import (
    generate_metrics_payload,
    record_ai_inference_metric,
    record_api_metric,
    record_evaluation_metric,
    record_finding_metric,
    record_step_metric,
    set_active_sandboxes,
    set_queue_depth,
)

# =========================================================================
# 1. Secret Redaction Tests
# =========================================================================


def test_redact_redis_and_webhook_credentials():
    """Verify Redis passwords and Slack webhook URLs are sanitized."""
    redis_raw = "Connecting to redis://:mypassword123@localhost:6379/0"
    redacted_redis = redact_secrets(redis_raw)
    assert "mypassword123" not in redacted_redis
    assert "redis://:[REDACTED]@localhost:6379/0" in redacted_redis

    webhook_raw = "Notification sent to https://hooks.slack.com/services/T00/B00/SECRET123"
    redacted_webhook = redact_secrets(webhook_raw)
    assert "SECRET123" not in redacted_webhook
    assert "[REDACTED_WEBHOOK_URL]" in redacted_webhook


def test_redact_private_key_blocks():
    """Verify private key blocks are completely redacted."""
    key_block = (
        "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA0Y1m...\n-----END RSA PRIVATE KEY-----"
    )
    redacted_key = redact_secrets(f"Loaded certificate:\n{key_block}\nReady.")
    assert "MIIEowIBAAKCAQEA" not in redacted_key
    assert "[REDACTED_PRIVATE_KEY]" in redacted_key


# =========================================================================
# 2. Structured JSON Logger Tests
# =========================================================================


def test_structured_logger_extra_data_redaction():
    """Verify structured logger formats fields and redacts secrets within extra_data."""
    formatter = StructuredJSONFormatter()
    record = logging.LogRecord(
        name="reposcore.test",
        level=logging.INFO,
        pathname="test.py",
        lineno=42,
        msg="Container step executed",
        args=(),
        exc_info=None,
    )
    record.extra_data = {
        "step": "BUILDING",
        "command": "npm install --token=ghp_1234567890abcdef1234567890abcdef1234",
        "duration_ms": 3500,
    }

    token = correlation_id_ctx.set("corr-uuid-789")
    eval_token = evaluation_id_ctx.set("eval-uuid-012")
    try:
        raw_json = formatter.format(record)
        data = json.loads(raw_json)

        assert data["level"] == "INFO"
        assert data["correlation_id"] == "corr-uuid-789"
        assert data["evaluation_id"] == "eval-uuid-012"
        assert data["step"] == "BUILDING"
        assert data["duration_ms"] == 3500
        # Secret in extra_data string must be redacted:
        assert "ghp_1234567890abcdef" not in data["command"]
        assert "[REDACTED_GH_TOKEN]" in data["command"]
    finally:
        correlation_id_ctx.reset(token)
        evaluation_id_ctx.reset(eval_token)


def test_structured_logger_exception_formatting():
    """Verify exception stack traces serialize cleanly into JSON."""
    formatter = StructuredJSONFormatter()
    try:
        raise ValueError("Simulated operational failure")
    except ValueError:
        exc_info = __import__("sys").exc_info()

    record = logging.LogRecord(
        name="reposcore.test",
        level=logging.ERROR,
        pathname="test.py",
        lineno=88,
        msg="Catastrophic stage failure",
        args=(),
        exc_info=exc_info,
    )

    raw_json = formatter.format(record)
    data = json.loads(raw_json)

    assert data["level"] == "ERROR"
    assert "exception" in data
    assert "ValueError: Simulated operational failure" in data["exception"]


# =========================================================================
# 3. Prometheus Metrics & Scrape Endpoint Tests
# =========================================================================


def test_metrics_recording_helpers():
    """Verify all metric recording helper functions observe and increment Prometheus collectors."""
    # 1. Evaluation metric
    record_evaluation_metric("COMPLETED", 45.2)
    record_evaluation_metric("FAILED", 12.0)

    # 2. Step metric
    record_step_metric("BUILDING", "SUCCESS", 14.5)
    record_step_metric("TESTING", "FAILURE", 8.2)

    # 3. AI inference metric
    record_ai_inference_metric("ollama", "qwen2.5-coder", 3.4)

    # 4. Security finding metric
    record_finding_metric("CRITICAL", "SECURITY")
    record_finding_metric("HIGH", "DEPENDENCY_HEALTH")

    # 5. API metric
    record_api_metric("GET", "/evaluations", 200, 0.045)
    record_api_metric("POST", "/evaluations", 202, 0.120)

    # 6. Gauges
    set_active_sandboxes(3)
    set_queue_depth("default", 5)

    # 7. Generate Prometheus payload
    payload_bytes, content_type = generate_metrics_payload()
    payload_text = payload_bytes.decode("utf-8")

    assert "reposcore_evaluations_total" in payload_text
    assert "reposcore_evaluation_duration_seconds" in payload_text
    assert "reposcore_step_duration_seconds" in payload_text
    assert "reposcore_ai_inference_duration_seconds" in payload_text
    assert "reposcore_security_findings_total" in payload_text
    assert "reposcore_api_requests_total" in payload_text
    assert "reposcore_api_request_duration_seconds" in payload_text
    assert "reposcore_active_sandboxes" in payload_text
    assert "reposcore_queue_depth" in payload_text


def test_metric_failure_resilience():
    """
    Verify Prime Directive & Phase 16 acceptance criterion:
    Observability/telemetry failures must NEVER raise uncaught exceptions or corrupt evaluation pipelines.
    """
    # Passing invalid non-numeric duration
    record_evaluation_metric("COMPLETED", "invalid_duration")  # type: ignore
    record_step_metric("BUILDING", "SUCCESS", None)  # type: ignore
    record_ai_inference_metric("ollama", "model", object())  # type: ignore
    record_api_metric("GET", "/test", "not_a_status", "not_a_num")  # type: ignore
    set_active_sandboxes(-10)  # Handles negative values gracefully
    set_queue_depth("queue", -5)
    # Execution completes cleanly without throwing exceptions
