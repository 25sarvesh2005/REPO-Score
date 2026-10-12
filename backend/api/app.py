"""
FastAPI Application Factory.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.errors import register_error_handlers
from backend.api.routes.health import router as health_router
from backend.core.config import settings
from backend.observability.logger import get_logger
from backend.observability.middleware import CorrelationIdMiddleware

logger = get_logger("reposcore.api")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifecycle management."""
    logger.info(f"Starting {settings.APP_NAME} in '{settings.APP_ENV}' environment...")
    yield
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

    # 2. Correlation ID Middleware
    app.add_middleware(CorrelationIdMiddleware)

    # 3. Register RFC 7807 Exception Handlers
    register_error_handlers(app)

    # 4. Operational Health & Metrics Routes (Root level)
    app.include_router(health_router)

    # 5. Versioned API Router (/api/v1)
    api_v1_router = APIRouter(prefix=settings.API_V1_PREFIX)
    # Placeholder for domain routes to be added in Phase 06+
    app.include_router(api_v1_router)

    return app


# Default app instance
app = create_app()
