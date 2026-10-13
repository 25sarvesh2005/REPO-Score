"""
FastAPI correlation ID and request tracing middleware.
"""

import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from backend.observability.logger import correlation_id_ctx, get_logger
from backend.observability.metrics import record_api_metric

logger = get_logger("reposcore.api.access")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware that ensures every incoming request has an X-Correlation-ID,
    binds it to the request context, and echoes it back in response headers.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Extract or generate correlation ID
        correlation_id = request.headers.get("X-Correlation-ID")
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        # Bind to contextvar for downstream loggers
        token = correlation_id_ctx.set(correlation_id)
        start_time = time.perf_counter()

        try:
            response = await call_next(request)
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Attach header to response
            response.headers["X-Correlation-ID"] = correlation_id

            # Record Prometheus operational telemetry
            record_api_metric(
                method=request.method,
                endpoint=request.url.path,
                status_code=response.status_code,
                duration_seconds=duration_ms / 1000.0,
            )

            # Log request completion (skip health probes in high-frequency access logs if needed)
            if request.url.path not in ("/health", "/metrics"):
                logger.info(
                    f"{request.method} {request.url.path} {response.status_code} - {duration_ms:.2f}ms",
                    extra={
                        "extra_data": {
                            "method": request.method,
                            "path": request.url.path,
                            "status_code": response.status_code,
                            "duration_ms": round(duration_ms, 2),
                        }
                    },
                )

            return response
        finally:
            correlation_id_ctx.reset(token)
