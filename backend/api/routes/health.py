"""
Operational health and readiness check route handlers.
"""

from fastapi import APIRouter, Response, status

from backend.api.errors import ServiceUnavailableException
from backend.api.schemas.contracts import HealthResponse, ReadinessResponse
from backend.core.queue import get_job_queue
from backend.database.session import check_database_health
from backend.observability.metrics import generate_metrics_payload

router = APIRouter(tags=["Operational"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Gateway Liveness Probe",
)
async def get_health() -> HealthResponse:
    """Liveness probe verifying that the FastAPI gateway is alive and accepting requests."""
    return HealthResponse(status="healthy")


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    status_code=status.HTTP_200_OK,
    summary="Gateway Readiness Probe",
)
async def get_readiness() -> ReadinessResponse:
    """
    Readiness probe validating downstream connectivity to PostgreSQL and Redis.
    Returns 503 if any dependency is unreachable.
    """
    db_status = await check_database_health()
    queue = get_job_queue()
    redis_status = await queue.check_health()

    if db_status != "connected" or redis_status != "connected":
        raise ServiceUnavailableException(
            detail=f"Readiness check failed: Database is {db_status}, Redis is {redis_status}."
        )

    return ReadinessResponse(
        status="ready",
        database=db_status,
        redis=redis_status,
    )


@router.get(
    "/metrics",
    summary="Prometheus Metrics",
)
async def get_metrics() -> Response:
    """Scrape endpoint for Prometheus telemetry collector."""
    payload, content_type = generate_metrics_payload()
    return Response(content=payload, media_type=content_type)
