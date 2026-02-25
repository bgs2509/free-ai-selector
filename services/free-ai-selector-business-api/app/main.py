"""
AI Manager Platform - Business API Service

FastAPI application providing business logic and AI provider integration.
Level 2 (Development Ready) maturity.
"""

import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import httpx
from fastapi import FastAPI, Request, Response, status

from app.utils.logger import setup_logging, get_logger
from app.utils.request_id import (
    setup_tracing_context,
    clear_tracing_context,
    generate_id,
    REQUEST_ID_HEADER,
    CORRELATION_ID_HEADER,
)
from app.utils.log_helpers import log_request_started, log_request_completed
from app.utils.security import sanitize_error_message
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter
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

# Data API configuration
DATA_API_URL = os.getenv("DATA_API_URL", "http://localhost:8001")

# CORS configuration
CORS_ORIGINS = os.getenv(
    "CORS_ORIGINS", "http://localhost:3000,http://localhost:8000"
).split(",")

# Rate limiting configuration (Level 2 requirement)
RATE_LIMIT_REQUESTS = int(os.getenv("RATE_LIMIT_REQUESTS", "100"))
RATE_LIMIT_PERIOD = int(os.getenv("RATE_LIMIT_PERIOD", "60"))

# Root path for reverse proxy (для работы за nginx-proxy)
ROOT_PATH = os.getenv("ROOT_PATH", "")

# =============================================================================
# Logging Configuration (AIDD Framework: structlog)
# =============================================================================

setup_logging(SERVICE_NAME)
logger = get_logger(__name__)

# =============================================================================
# Rate Limiter
# =============================================================================

limiter = Limiter(key_func=get_remote_address, headers_enabled=True)


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
    logger.info(
        "service_starting",
        version=SERVICE_VERSION,
        environment=ENVIRONMENT,
    )

    # Verify Data API connection
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{DATA_API_URL}/health")
            if response.status_code == 200:
                logger.info("data_api_connected", status="healthy")
            else:
                logger.warning(
                    "data_api_connected",
                    status="unhealthy",
                    status_code=response.status_code,
                )
    except Exception as e:
        logger.error(
            "data_api_connection_failed",
            error=sanitize_error_message(e),
        )
        logger.warning("service_starting_with_errors")

    yield

    # Shutdown
    logger.info("service_stopping")


# =============================================================================
# FastAPI Application
# =============================================================================

# Динамический OpenAPI URL для работы за reverse proxy (nginx-proxy)
# При пустом ROOT_PATH используется стандартный путь /openapi.json
# При ROOT_PATH="/free-ai-selector" путь станет /free-ai-selector/openapi.json
_openapi_url = f"{ROOT_PATH}/openapi.json" if ROOT_PATH else "/openapi.json"

app = FastAPI(
    title="Free AI Selector - Business API",
    description="Бизнес-логика и интеграция с AI-провайдерами",
    version=SERVICE_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url=_openapi_url,
    root_path=ROOT_PATH,
    lifespan=lifespan,
)

# Add rate limiter to app state
app.state.limiter = limiter


async def rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """F025: Кастомный обработчик slowapi rate limit в формате ErrorResponse."""
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "error": "client_rate_limited",
            "message": f"Rate limit exceeded: {exc.detail}",
            "retry_after": 60,
            "attempts": 0,
            "providers_tried": 0,
            "providers_available": 0,
        },
    )


app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

# =============================================================================
# Static Files для веб-интерфейса
# =============================================================================

# Монтируем статические файлы для веб-интерфейса
# ROOT_PATH в FastAPI автоматически обрабатывает prefix для nginx reverse proxy
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

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
    start_time = log_request_started(
        logger, method=request.method, path=request.url.path
    )

    try:
        # Process request
        response = await call_next(request)

        # Add IDs to response headers
        response.headers[REQUEST_ID_HEADER] = request_id

        # Log response with duration_ms
        log_request_completed(
            logger,
            method=request.method,
            path=request.url.path,
            start_time=start_time,
            status_code=response.status_code,
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
        logger.error(
            "health_check_failed",
            error=sanitize_error_message(e),
            external_service="data_api",
        )

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


@app.get("/", include_in_schema=False)
async def root():
    """
    Перенаправление на веб-интерфейс.

    Returns:
        RedirectResponse на static/index.html
    """
    return RedirectResponse(url="/static/index.html")


@app.get("/api", tags=["Root"], summary="API информация")
@limiter.limit(f"{RATE_LIMIT_REQUESTS}/{RATE_LIMIT_PERIOD}second")
async def api_info(request: Request, response: Response):
    """
    Информация об API.

    Returns:
        Название сервиса, версия и ссылки на документацию
    """
    # Параметр response нужен slowapi для корректной установки rate-limit заголовков.
    _ = response
    return {
        "service": SERVICE_NAME,
        "version": SERVICE_VERSION,
        "environment": ENVIRONMENT,
        "docs": "/docs",
        "health": "/health",
    }
