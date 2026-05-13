"""FastAPI middleware and exception handlers."""

import uuid
import time
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from app.core.exceptions import AppException
import structlog

logger = structlog.get_logger(__name__)


def setup_exception_handlers(app: FastAPI):
    """Setup custom exception handlers for FastAPI."""

    @app.exception_handler(AppException)
    async def handle_app_exception(request: Request, exc: AppException):
        """Handle application exceptions."""
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error_code": exc.error_code,
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        """Handle request validation errors."""
        return JSONResponse(
            status_code=422,
            content={
                "error_code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def handle_generic_exception(request: Request, exc: Exception):
        """Handle generic unhandled exceptions."""
        logger.error(
            "Unhandled exception",
            error=str(exc),
            error_type=type(exc).__name__,
            path=request.url.path,
            method=request.method,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error_code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred",
                "details": None,
            },
        )


def setup_logging_middleware(app: FastAPI):
    """Setup HTTP logging middleware."""

    @app.middleware("http")
    async def logging_middleware(request: Request, call_next):
        """Log incoming requests and outgoing responses."""
        request_id = str(uuid.uuid4())
        start_time = time.time()

        # Add request ID to request state
        request.state.request_id = request_id

        # Log incoming request
        logger.info(
            "incoming_request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            query_params=dict(request.query_params),
        )

        # Get response
        response = await call_next(request)

        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000

        # Log outgoing response
        logger.info(
            "outgoing_response",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )

        # Add request ID to response headers
        response.headers["X-Request-ID"] = request_id

        return response
