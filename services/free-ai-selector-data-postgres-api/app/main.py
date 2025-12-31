"""
AI Manager Platform - Data API Service (PostgreSQL)

FastAPI application providing data layer access to AI models and prompt history.
Level 2 (Development Ready) maturity.
"""

import os
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status

from app.utils.logger import setup_logging, get_logger
from app.utils.request_id import (
    setup_tracing_context,
    clear_tracing_context,
    generate_id,
    REQUEST_ID_HEADER,
    CORRELATION_ID_HEADER,
)
from app.utils.security import sanitize_error_message
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1 import history, models
from app.api.v1.schemas import HealthCheckResponse
from app.infrastructure.database.connection import AsyncSessionLocal, engine

# =============================================================================
# Configuration
# =============================================================================

SERVICE_NAME = "free-ai-selector-data-postgres-api"
SERVICE_VERSION = "1.0.0"
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# =============================================================================
# Logging Configuration (AIDD Framework: structlog)
# =============================================================================

setup_logging(SERVICE_NAME)
logger = get_logger(__name__)


# =============================================================================
# Lifespan Events
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Lifespan context manager for startup and shutdown events.

    Startup:
        - Log service initialization
        - Verify database connection

    Shutdown:
        - Close database connections
        - Log service shutdown
    """
    # Startup
    logger.info(
        "service_starting",
        version=SERVICE_VERSION,
        environment=ENVIRONMENT,
    )

    # Verify database connection
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        logger.info("database_connected", status="healthy")
    except Exception as e:
        logger.error(
            "database_connection_failed",
            error=sanitize_error_message(e),
        )
        raise

    yield

    # Shutdown
    logger.info("service_stopping")
    await engine.dispose()


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="AI Manager Platform - Data API",
    description="Data layer service providing PostgreSQL access for AI models and prompt history",
    version=SERVICE_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# =============================================================================
# Middleware
# =============================================================================


@app.middleware("http")
async def add_request_id_middleware(request: Request, call_next):
    """
    Middleware to add request ID and correlation ID to all requests.

    AIDD Framework: ContextVars-based tracing with structlog.
    """
    # Get or generate IDs
    request_id = request.headers.get(REQUEST_ID_HEADER, generate_id())
    correlation_id = request.headers.get(CORRELATION_ID_HEADER, request_id)

    # Setup tracing context (ContextVars + structlog binding)
    setup_tracing_context(request_id=request_id, correlation_id=correlation_id)

    # Add request ID to request state (for backwards compatibility)
    request.state.request_id = request_id

    # Log incoming request with duration tracking
    start_time = time.perf_counter()
    logger.info("request_started", method=request.method, path=request.url.path)

    try:
        # Process request
        response = await call_next(request)

        # Add IDs to response headers
        response.headers[REQUEST_ID_HEADER] = request_id

        # Log response with duration_ms
        duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info(
            "request_completed",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )

        return response
    finally:
        # Clear context after request
        clear_tracing_context()


@app.middleware("http")
async def error_handling_middleware(request: Request, call_next):
    """
    Global error handling middleware.

    Catches unhandled exceptions and returns structured error responses.
    """
    try:
        return await call_next(request)
    except Exception as e:
        request_id = getattr(request.state, "request_id", "unknown")
        logger.error(
            "unhandled_exception",
            error=sanitize_error_message(e),
            error_type=type(e).__name__,
        )

        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": "Internal server error",
                "request_id": request_id,
                "error_type": type(e).__name__,
            },
        )


# =============================================================================
# Health Check Endpoint
# =============================================================================


@app.get(
    "/health",
    response_model=HealthCheckResponse,
    status_code=status.HTTP_200_OK,
    tags=["Health"],
    summary="Health check endpoint",
)
async def health_check() -> HealthCheckResponse:
    """
    Health check endpoint.

    Verifies:
    - Service is running
    - Database connection is healthy

    Returns:
        HealthCheckResponse with service status
    """
    # Check database connection
    db_status = "healthy"
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {sanitize_error_message(e)}"
        logger.error(
            "health_check_failed",
            error=sanitize_error_message(e),
            component="database",
        )

    return HealthCheckResponse(
        status="healthy" if db_status == "healthy" else "unhealthy",
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
        database=db_status,
    )


# =============================================================================
# API Routes
# =============================================================================

# Include v1 API routes
app.include_router(models.router, prefix="/api/v1")
app.include_router(history.router, prefix="/api/v1")


# =============================================================================
# Root Endpoint
# =============================================================================


@app.get("/", tags=["Root"], summary="Root endpoint")
async def root():
    """
    Root endpoint providing service information.

    Returns:
        Service name, version, and documentation links
    """
    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "environment": ENVIRONMENT,
        "docs": "/docs",
        "health": "/health",
    }
