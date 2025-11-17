"""
AI Manager Platform - Data API Service (PostgreSQL)

FastAPI application providing data layer access to AI models and prompt history.
Level 2 (Development Ready) maturity.
"""

import logging
import os
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1 import history, models
from app.api.v1.schemas import HealthCheckResponse
from app.infrastructure.database.connection import AsyncSessionLocal, engine

# =============================================================================
# Configuration
# =============================================================================

SERVICE_NAME = "aimanager_data_postgres_api"
SERVICE_VERSION = "1.0.0"
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
LOG_LEVEL = os.getenv("DATA_API_LOG_LEVEL", "INFO")
REQUEST_ID_HEADER = os.getenv("REQUEST_ID_HEADER", "X-Request-ID")

# =============================================================================
# Logging Configuration (Level 2: JSON logging)
# =============================================================================

logging.basicConfig(
    level=LOG_LEVEL,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "service": "'
    + SERVICE_NAME
    + '", "message": "%(message)s"}',
    datefmt="%Y-%m-%d %H:%M:%S",
)

logger = logging.getLogger(__name__)


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
    logger.info(f"Starting {SERVICE_NAME} v{SERVICE_VERSION} (Environment: {ENVIRONMENT})")

    # Verify database connection
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        logger.info("Database connection verified successfully")
    except Exception as e:
        logger.error(f"Database connection failed: {str(e)}")
        raise

    yield

    # Shutdown
    logger.info(f"Shutting down {SERVICE_NAME}")
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
    Middleware to add request ID to all requests.

    Level 2 requirement: Request ID tracking for observability.
    """
    # Get or generate request ID
    request_id = request.headers.get(REQUEST_ID_HEADER, str(uuid.uuid4()))

    # Add request ID to request state
    request.state.request_id = request_id

    # Log incoming request
    logger.info(
        f'{{"request_id": "{request_id}", "method": "{request.method}", '
        f'"path": "{request.url.path}", "event": "request_started"}}'
    )

    # Process request
    response = await call_next(request)

    # Add request ID to response headers
    response.headers[REQUEST_ID_HEADER] = request_id

    # Log response
    logger.info(
        f'{{"request_id": "{request_id}", "status_code": {response.status_code}, '
        f'"event": "request_completed"}}'
    )

    return response


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
            f'{{"request_id": "{request_id}", "error": "{str(e)}", '
            f'"error_type": "{type(e).__name__}", "event": "unhandled_exception"}}'
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
        db_status = f"unhealthy: {str(e)}"
        logger.error(f"Health check failed: database connection error - {str(e)}")

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
