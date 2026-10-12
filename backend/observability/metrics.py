"""
Prometheus metrics instrumentation and operational diagnostics for RepoScore.
Adheres strictly to OBSERVABILITY_ARCHITECTURE.md, ADR-001, ADR-007, and Prime Directive #5.
All recording calls are non-blocking and fault-tolerant to ensure telemetry failures never disrupt core pipelines.
"""

import logging
from typing import Optional
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

logger = logging.getLogger("reposcore.observability.metrics")

# 1. Evaluations metric by final status
EVALUATIONS_TOTAL = Counter(
    "reposcore_evaluations_total",
    "Total number of evaluations processed by final status",
    ["status"],
)

# 2. End-to-end evaluation latency histogram
EVALUATION_DURATION_SECONDS = Histogram(
    "reposcore_evaluation_duration_seconds",
    "End-to-end evaluation duration in seconds",
    ["status"],
    buckets=(1.0, 5.0, 15.0, 30.0, 60.0, 120.0, 300.0, 600.0),
)

# 3. Step execution duration histogram
STEP_DURATION_SECONDS = Histogram(
    "reposcore_step_duration_seconds",
    "Execution duration of individual evaluation pipeline steps",
    ["step_name", "status"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 15.0, 30.0, 60.0, 120.0),
)

# 4. Active running sandbox containers gauge
ACTIVE_SANDBOXES = Gauge(
    "reposcore_active_sandboxes",
    "Number of active Docker sandbox execution containers currently running",
)

# 5. Redis evaluation queue depth gauge
QUEUE_DEPTH = Gauge(
    "reposcore_queue_depth",
    "Number of evaluations currently waiting in the task queue",
    ["queue_name"],
)

# 6. AI inference duration histogram
AI_INFERENCE_DURATION_SECONDS = Histogram(
    "reposcore_ai_inference_duration_seconds",
    "Latency of AI inference requests in seconds",
    ["provider", "model"],
    buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
)

# 7. Discovered security findings counter
SECURITY_FINDINGS_TOTAL = Counter(
    "reposcore_security_findings_total",
    "Aggregate count of discovered security and quality findings",
    ["severity", "category"],
)

# 8. API HTTP requests counter
API_REQUESTS_TOTAL = Counter(
    "reposcore_api_requests_total",
    "Total API HTTP requests processed",
    ["method", "endpoint", "status_code"],
)

# 9. API HTTP request duration histogram
API_REQUEST_DURATION_SECONDS = Histogram(
    "reposcore_api_request_duration_seconds",
    "API HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
)


# =========================================================================
# Resilient Metric Recording Helpers
# (Wrapped with try/except to guarantee telemetry never corrupts evaluations)
# =========================================================================

def record_evaluation_metric(status: str, duration_seconds: float) -> None:
    """Record evaluation outcome and duration."""
    try:
        norm_status = status.lower()
        EVALUATIONS_TOTAL.labels(status=norm_status).inc()
        EVALUATION_DURATION_SECONDS.labels(status=norm_status).observe(max(0.0, float(duration_seconds)))
    except Exception as exc:
        logger.warning(f"Telemetry warning: failed to record evaluation metric: {exc}")


def record_step_metric(step_name: str, status: str, duration_seconds: float) -> None:
    """Record individual step execution latency and status."""
    try:
        norm_status = status.lower()
        STEP_DURATION_SECONDS.labels(step_name=step_name, status=norm_status).observe(max(0.0, float(duration_seconds)))
    except Exception as exc:
        logger.warning(f"Telemetry warning: failed to record step metric: {exc}")


def record_ai_inference_metric(provider: str, model: str, duration_seconds: float) -> None:
    """Record AI qualitative inference latency."""
    try:
        AI_INFERENCE_DURATION_SECONDS.labels(provider=provider, model=model).observe(max(0.0, float(duration_seconds)))
    except Exception as exc:
        logger.warning(f"Telemetry warning: failed to record AI inference metric: {exc}")


def record_finding_metric(severity: str, category: str) -> None:
    """Record finding discovery by severity and category."""
    try:
        SECURITY_FINDINGS_TOTAL.labels(severity=str(severity).upper(), category=str(category).upper()).inc()
    except Exception as exc:
        logger.warning(f"Telemetry warning: failed to record finding metric: {exc}")


def record_api_metric(method: str, endpoint: str, status_code: int, duration_seconds: float) -> None:
    """Record API HTTP request count and latency."""
    try:
        # Normalize endpoint (strip dynamic UUIDs or IDs to prevent label explosion)
        norm_endpoint = endpoint
        API_REQUESTS_TOTAL.labels(method=method.upper(), endpoint=norm_endpoint, status_code=str(status_code)).inc()
        API_REQUEST_DURATION_SECONDS.labels(method=method.upper(), endpoint=norm_endpoint).observe(max(0.0, float(duration_seconds)))
    except Exception as exc:
        logger.warning(f"Telemetry warning: failed to record API metric: {exc}")


def set_active_sandboxes(count: int) -> None:
    """Update active sandbox container gauge."""
    try:
        ACTIVE_SANDBOXES.set(max(0, count))
    except Exception as exc:
        logger.warning(f"Telemetry warning: failed to set active sandboxes: {exc}")


def set_queue_depth(queue_name: str, depth: int) -> None:
    """Update queue depth gauge."""
    try:
        QUEUE_DEPTH.labels(queue_name=queue_name).set(max(0, depth))
    except Exception as exc:
        logger.warning(f"Telemetry warning: failed to set queue depth: {exc}")


def generate_metrics_payload() -> tuple[bytes, str]:
    """Generate Prometheus metric payload and content type."""
    return generate_latest(), CONTENT_TYPE_LATEST
