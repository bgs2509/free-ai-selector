"""
AI Manager Platform - Business API Service

FastAPI application providing business logic and AI provider integration.
Level 2 (Development Ready) maturity.
"""

import logging
from app.utils.security import sanitize_error_message
import os
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import httpx
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.v1 import models, prompts, providers
from app.api.v1.schemas import HealthCheckResponse

# =============================================================================
# Configuration
# =============================================================================

SERVICE_NAME = "free-ai-selector-business-api"
SERVICE_VERSION = "1.0.0"
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
LOG_LEVEL = os.getenv("BUSINESS_API_LOG_LEVEL", "INFO")
REQUEST_ID_HEADER = os.getenv("REQUEST_ID_HEADER", "X-Request-ID")

# Data API configuration
DATA_API_URL = os.getenv("DATA_API_URL", "http://localhost:8001")

# CORS configuration
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")

# Rate limiting configuration (Level 2 requirement)
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
RATE_LIMIT_PERIOD = int(os.getenv("RATE_LIMIT_PERIOD", "60"))

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
# Rate Limiter
# =============================================================================

limiter = Limiter(key_func=get_remote_address)


# =============================================================================
# Lifespan Events
# =============================================================================


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Lifespan context manager for startup and shutdown events.

    Startup:
        - Log service initialization
        - Verify Data API connection

    Shutdown:
        - Log service shutdown
    """
    # Startup
    logger.info(f"Starting {SERVICE_NAME} v{SERVICE_VERSION} (Environment: {ENVIRONMENT})")

    # Verify Data API connection
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{DATA_API_URL}/health")
            if response.status_code == 200:
                logger.info("Data API connection verified successfully")
            else:
                logger.warning(f"Data API health check returned status {response.status_code}")
    except Exception as e:
        logger.error(f"Data API connection failed: {sanitize_error_message(e)}")
        logger.warning("Service will start but may encounter errors")

    yield

    # Shutdown
    logger.info(f"Shutting down {SERVICE_NAME}")


# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="AI Manager Platform - Business API",
    description="Business logic service providing AI prompt processing and model selection",
    version=SERVICE_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# =============================================================================
# Middleware
# =============================================================================

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
            f'{{"request_id": "{request_id}", "error": "{sanitize_error_message(e)}", '
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
    - Data API connection is healthy

    Returns:
        HealthCheckResponse with service status
    """
    # Check Data API connection
    data_api_status = "healthy"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{DATA_API_URL}/health")
            if response.status_code != 200:
                data_api_status = f"unhealthy: status {response.status_code}"
    except Exception as e:
        data_api_status = f"unhealthy: {sanitize_error_message(e)}"
        logger.error(f"Health check failed: Data API connection error - {sanitize_error_message(e)}")

    return HealthCheckResponse(
        status="healthy" if data_api_status == "healthy" else "unhealthy",
        service=SERVICE_NAME,
        version=SERVICE_VERSION,
        data_api_connection=data_api_status,
    )


# =============================================================================
# API Routes
# =============================================================================

# Include v1 API routes
app.include_router(prompts.router, prefix="/api/v1")
app.include_router(models.router, prefix="/api/v1")
app.include_router(providers.router, prefix="/api/v1")


# =============================================================================
# Root Endpoint
# =============================================================================


@app.get("/", tags=["Root"], summary="Root endpoint")
@limiter.limit(f"{RATE_LIMIT_REQUESTS}/{RATE_LIMIT_PERIOD}second")
async def root(request: Request):
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
