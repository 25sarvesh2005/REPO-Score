"""
Prometheus metrics instrumentation for RepoScore.
"""

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

# Evaluations metric by final status
EVALUATIONS_TOTAL = Counter(
    "reposcore_evaluations_total",
    "Total number of evaluations processed",
    ["status"],
)

# Step execution duration histogram
STEP_DURATION_SECONDS = Histogram(
    "reposcore_step_duration_seconds",
    "Execution duration of individual evaluation pipeline steps",
    ["step_name"],
    buckets=(1.0, 5.0, 15.0, 30.0, 60.0, 120.0, 300.0, 600.0),
)

# Active running sandbox containers gauge
ACTIVE_SANDBOXES = Gauge(
    "reposcore_active_sandboxes",
    "Number of active Docker sandbox execution containers currently running",
)

# Redis evaluation queue depth gauge
QUEUE_DEPTH = Gauge(
    "reposcore_queue_depth",
    "Number of evaluations currently waiting in the Redis queue",
)


def generate_metrics_payload() -> tuple[bytes, str]:
    """Generate Prometheus metric payload and content type."""
    return generate_latest(), CONTENT_TYPE_LATEST
