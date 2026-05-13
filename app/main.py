"""FastAPI application factory and entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.exceptions import AppException
from app.core.middleware import setup_exception_handlers, setup_logging_middleware
from app.core.lifecycle import init_app, shutdown_app
from app.api.v1 import health, merchants, mccs, external_merchants, auto_creation, embeddings, outbox


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle manager."""
    # Startup
    await init_app()
    yield
    # Shutdown
    await shutdown_app()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Payments Classification MCP",
        description="Merchant classification microservice",
        version="1.0.0",
        lifespan=lifespan,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
    )

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Configure trusted hosts
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.allowed_hosts,
    )

    # Setup exception handlers
    setup_exception_handlers(app)

    # Setup logging middleware
    setup_logging_middleware(app)

    # Include routers
    app.include_router(health.router, prefix="/api")
    app.include_router(merchants.router, prefix="/api/v1")
    app.include_router(mccs.router, prefix="/api/v1")
    app.include_router(external_merchants.router, prefix="/api/v1")
    app.include_router(auto_creation.router, prefix="/api/v1")
    app.include_router(embeddings.router, prefix="/api/v1")
    app.include_router(outbox.router, prefix="/api/v1")

    return app


app = create_app()
