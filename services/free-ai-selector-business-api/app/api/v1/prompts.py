"""
Prompt Processing API routes for AI Manager Platform - Business API Service
"""

import os

from app.utils.security import sanitize_error_message

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse

from app.api.v1.schemas import ErrorResponse, ProcessPromptRequest, ProcessPromptResponse
from app.application.use_cases.process_prompt import ProcessPromptUseCase
from app.domain.exceptions import AllProvidersRateLimited, ServiceUnavailable
from app.domain.models import PromptRequest
from app.infrastructure.http_clients.data_api_client import DataAPIClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

# F025: Rate limit для /process endpoint
PROCESS_RATE_LIMIT = os.getenv("PROCESS_RATE_LIMIT", "100/minute")

router = APIRouter(prefix="/prompts", tags=["Prompts"])


@router.post(
    "/process",
    response_model=ProcessPromptResponse,
    status_code=status.HTTP_200_OK,
    summary="Process prompt with AI",
    responses={
        429: {"model": ErrorResponse, "description": "All providers rate limited"},
        503: {"model": ErrorResponse, "description": "Service unavailable"},
    },
)
async def process_prompt(
    prompt_data: ProcessPromptRequest, request: Request
) -> ProcessPromptResponse:
    """
    Process user prompt with best available AI model.

    The platform automatically selects the most reliable AI model
    based on real-time reliability metrics (success rate + speed).

    Args:
        prompt_data: User's prompt text
        request: FastAPI request object (for request ID)

    Returns:
        ProcessPromptResponse with AI-generated text and metadata

    Raises:
        HTTPException: 500 if all AI providers fail
        HTTPException: 503 if no active models available
    """
    # Get request ID from middleware
    request_id = getattr(request.state, "request_id", None)

    # Create Data API client with request ID for tracing
    data_api_client = DataAPIClient(request_id=request_id)

    try:
        # Create use case
        use_case = ProcessPromptUseCase(data_api_client)

        # Execute prompt processing
        # Use "api_user" as default user_id for REST API requests
        # Telegram bot will provide actual user IDs
        prompt_request = PromptRequest(
            user_id="api_user",
            prompt_text=prompt_data.prompt,
            model_id=prompt_data.model_id,
            system_prompt=prompt_data.system_prompt,
            response_format=prompt_data.response_format
        )

        response = await use_case.execute(prompt_request)

        return ProcessPromptResponse(
            prompt=response.prompt_text,
            response=response.response_text,
            selected_model=response.selected_model_name,
            provider=response.selected_model_provider,
            response_time_seconds=response.response_time,
            success=response.success,
            # F023: Per-request telemetry
            attempts=response.attempts,
            fallback_used=response.fallback_used,
        )

    except AllProvidersRateLimited as e:
        # F025: Все провайдеры rate-limited → HTTP 429
        retry_after = e.retry_after_seconds
        logger.warning(
            "backpressure_applied",
            status=429,
            reason="all_rate_limited",
            retry_after=retry_after,
            attempts=e.attempts,
        )
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(retry_after)},
            content=ErrorResponse(
                error="all_rate_limited",
                message="All AI providers are rate limited. Please retry later.",
                retry_after=retry_after,
                attempts=e.attempts,
                providers_tried=e.providers_tried,
                providers_available=0,
            ).model_dump(),
        )

    except ServiceUnavailable as e:
        # F025: Сервис недоступен → HTTP 503
        retry_after = e.retry_after_seconds
        logger.warning(
            "backpressure_applied",
            status=503,
            reason=e.reason,
            retry_after=retry_after,
        )
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            headers={"Retry-After": str(retry_after)},
            content=ErrorResponse(
                error="service_unavailable",
                message=str(e),
                retry_after=retry_after,
                attempts=0,
                providers_tried=0,
                providers_available=0,
            ).model_dump(),
        )

    except Exception as e:
        # F023 FR-012: Включить error_type в detail для диагностики
        error_type = type(e).__name__
        logger.error("process_prompt_failed", error_type=error_type, error=sanitize_error_message(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process prompt [{error_type}]: {sanitize_error_message(e)}",
        )

    finally:
        # Close HTTP client
        await data_api_client.close()
