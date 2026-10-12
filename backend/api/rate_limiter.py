"""
Sliding-Window Rate Limiting Middleware for FastAPI.
Protects RepoScore API gateway from denial-of-service and abuse.
Adheres strictly to RFC 7807 (Problem Details for HTTP APIs) and Phase 17 security standards.
"""

from collections import defaultdict
from datetime import datetime, timezone
import time
from typing import Dict, List
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from backend.core.config import settings
from backend.observability.logger import get_logger

logger = get_logger("reposcore.api.ratelimit")

EXEMPT_PREFIXES = (
    "/health",
    "/ready",
    "/metrics",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/static",
    "/favicon.ico",
)


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """
    In-memory sliding window rate limiter per client IP.
    """

    def __init__(self, app, requests_per_minute: int = 120) -> None:
        super().__init__(app)
        self.limit = requests_per_minute
        self.window_seconds = 60.0
        self._clients: Dict[str, List[float]] = defaultdict(list)

    def _get_client_ip(self, request: Request) -> str:
        """Extract client IP, considering X-Forwarded-For if behind a reverse proxy."""
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return request.client.host if request.client else "127.0.0.1"

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip rate limiting for static assets and operational health probes
        path = request.url.path
        if path == "/" or any(path.startswith(prefix) for prefix in EXEMPT_PREFIXES):
            return await call_next(request)

        if not settings.RATE_LIMIT_ENABLED:
            return await call_next(request)

        client_ip = self._get_client_ip(request)
        now = time.monotonic()
        cutoff = now - self.window_seconds

        # Prune expired timestamps
        timestamps = [t for t in self._clients[client_ip] if t > cutoff]
        self._clients[client_ip] = timestamps

        if len(timestamps) >= self.limit:
            logger.warning(
                f"Rate limit exceeded for client {client_ip}: {len(timestamps)} requests in last 60s"
            )
            reset_time = int(time.time() + self.window_seconds)
            problem_payload = {
                "type": "https://reposcore.internal/errors/rate-limit-exceeded",
                "title": "Too Many Requests",
                "status": 429,
                "detail": f"Rate limit of {self.limit} requests per minute exceeded. Please retry later.",
                "retry_after": 60,
            }
            return JSONResponse(
                status_code=429,
                content=problem_payload,
                media_type="application/problem+json",
                headers={
                    "Retry-After": "60",
                    "X-RateLimit-Limit": str(self.limit),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_time),
                },
            )

        # Record this request timestamp
        timestamps.append(now)
        remaining = max(0, self.limit - len(timestamps))
        reset_time = int(time.time() + self.window_seconds)

        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)
        return response
