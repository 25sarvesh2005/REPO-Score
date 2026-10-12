"""
FastAPI Application Factory.
"""

import asyncio
from contextlib import asynccontextmanager, suppress
from typing import AsyncGenerator
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pathlib import Path
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.api.errors import register_error_handlers
from backend.api.rate_limiter import RateLimitingMiddleware
from backend.api.routes.evaluations import router as evaluations_router
from backend.api.routes.health import router as health_router
from backend.api.routes.repositories import router as repositories_router
from backend.core.config import settings
from backend.observability.logger import get_logger
from backend.observability.middleware import CorrelationIdMiddleware

logger = get_logger("reposcore.api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifecycle management."""
    logger.info(f"Starting {settings.APP_NAME} in '{settings.APP_ENV}' environment...")
    local_worker = None
    local_worker_task = None
    if "sqlite" in settings.DATABASE_URL:
        from backend.database.base import TimestampedBase
        from backend.database.session import engine
        import backend.database.models  # noqa: F401
        async with engine.begin() as conn:
            await conn.run_sync(TimestampedBase.metadata.create_all)
        logger.info("SQLite database tables initialized successfully.")
    if settings.REDIS_URL.startswith("memory://"):
        # An in-memory queue belongs to this process, so a separate worker process
        # cannot consume it. Local mode runs the same sandboxed orchestrator here.
        from backend.pipeline.worker import EvaluationWorker

        local_worker = EvaluationWorker(worker_id="local-api-worker")
        local_worker_task = asyncio.create_task(local_worker.run_forever())
        logger.info("Started in-process worker for local in-memory queue.")
    try:
        yield
    finally:
        if local_worker is not None:
            local_worker.request_shutdown()
        if local_worker_task is not None:
            with suppress(asyncio.CancelledError):
                await local_worker_task
        logger.info(f"Shutting down {settings.APP_NAME}...")


def create_app() -> FastAPI:
    """Create, configure, and return the FastAPI application instance."""
    app = FastAPI(
        title=f"{settings.APP_NAME} Evaluation Engine",
        version="0.1.0",
        description="Autonomous repository intelligence and software evaluation engine.",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
    )

    # 1. CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Correlation-ID", "Location", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
    )

    # 2. Rate Limiting Middleware
    app.add_middleware(RateLimitingMiddleware, requests_per_minute=settings.RATE_LIMIT_PER_MINUTE)

    # 3. Correlation ID Middleware
    app.add_middleware(CorrelationIdMiddleware)

    # 4. Register RFC 7807 Exception Handlers
    register_error_handlers(app)

    # 4. Operational Health & Metrics Routes (Root level)
    app.include_router(health_router)

    # 5. Versioned API Router (/api/v1)
    api_v1_router = APIRouter(prefix=settings.API_V1_PREFIX)
    api_v1_router.include_router(repositories_router)
    api_v1_router.include_router(evaluations_router)
    app.include_router(api_v1_router)

    # 6. Static Web Dashboard Mount
    static_dir = Path(__file__).resolve().parent.parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

        @app.get("/", include_in_schema=False)
        @app.get("/dashboard", include_in_schema=False)
        async def serve_dashboard() -> FileResponse:
            index_path = static_dir / "index.html"
            return FileResponse(str(index_path))

    return app


# Default app instance
app = create_app()
