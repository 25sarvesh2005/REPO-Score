"""
Domain exceptions and RFC 7807 Problem Details exception handlers.
"""

from datetime import datetime, timezone
import uuid
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from backend.observability.logger import correlation_id_ctx, get_logger

logger = get_logger("reposcore.api.errors")


class RepoScoreException(Exception):
    """Base exception for all RepoScore domain errors."""

    def __init__(
        self,
        detail: str,
        title: str = "Internal Application Error",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        error_type: str = "https://reposcore.internal/errors/internal-error",
    ):
        super().__init__(detail)
        self.detail = detail
        self.title = title
        self.status_code = status_code
        self.error_type = error_type


class EntityNotFoundException(RepoScoreException):
    def __init__(self, detail: str = "The requested resource was not found."):
        super().__init__(
            detail=detail,
            title="Resource Not Found",
            status_code=status.HTTP_404_NOT_FOUND,
            error_type="https://reposcore.internal/errors/not-found",
        )


class ConflictException(RepoScoreException):
    def __init__(self, detail: str = "Operation conflicts with current resource state."):
        super().__init__(
            detail=detail,
            title="Resource Conflict",
            status_code=status.HTTP_409_CONFLICT,
            error_type="https://reposcore.internal/errors/conflict",
        )


class ValidationException(RepoScoreException):
    def __init__(self, detail: str = "Invalid request input."):
        super().__init__(
            detail=detail,
            title="Validation Error",
            status_code=status.HTTP_400_BAD_REQUEST,
            error_type="https://reposcore.internal/errors/bad-request",
        )


class ServiceUnavailableException(RepoScoreException):
    def __init__(self, detail: str = "Backing service is currently unavailable."):
        super().__init__(
            detail=detail,
            title="Service Unavailable",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            error_type="https://reposcore.internal/errors/service-unavailable",
        )


def build_problem_payload(
    status_code: int,
    title: str,
    detail: str,
    instance: str,
    error_type: str = "https://reposcore.internal/errors/generic-error",
    invalid_params: list | None = None,
) -> dict:
    """Construct standard RFC 7807 Problem Details dictionary."""
    corr_id = correlation_id_ctx.get() or str(uuid.uuid4())
    payload = {
        "type": error_type,
        "title": title,
        "status": status_code,
        "detail": detail,
        "instance": instance,
        "correlation_id": corr_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "invalid_params": invalid_params or [],
    }
    return payload


def register_error_handlers(app: FastAPI) -> None:
    """Register RFC 7807 error handlers on the FastAPI application."""

    @app.exception_handler(RepoScoreException)
    async def reposcore_exception_handler(request: Request, exc: RepoScoreException) -> JSONResponse:
        logger.warning(f"Domain exception on {request.url.path}: {exc.detail}")
        payload = build_problem_payload(
            status_code=exc.status_code,
            title=exc.title,
            detail=exc.detail,
            instance=request.url.path,
            error_type=exc.error_type,
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=payload,
            media_type="application/problem+json",
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        logger.info(f"Schema validation error on {request.url.path}")
        invalid_params = []
        for err in exc.errors():
            loc = ".".join(str(x) for x in err.get("loc", []))
            invalid_params.append({"name": loc, "reason": err.get("msg", "Invalid value")})

        payload = build_problem_payload(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            title="Unprocessable Entity",
            detail="The request body or parameters failed schema validation.",
            instance=request.url.path,
            error_type="https://reposcore.internal/errors/validation-error",
            invalid_params=invalid_params,
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=payload,
            media_type="application/problem+json",
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        payload = build_problem_payload(
            status_code=exc.status_code,
            title="HTTP Error",
            detail=str(exc.detail),
            instance=request.url.path,
            error_type=f"https://reposcore.internal/errors/http-{exc.status_code}",
        )
        return JSONResponse(
            status_code=exc.status_code,
            content=payload,
            media_type="application/problem+json",
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(f"Unhandled server error on {request.url.path}: {exc}")
        payload = build_problem_payload(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Internal Server Error",
            detail="An unexpected internal server error occurred.",
            instance=request.url.path,
            error_type="https://reposcore.internal/errors/internal-error",
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=payload,
            media_type="application/problem+json",
        )
