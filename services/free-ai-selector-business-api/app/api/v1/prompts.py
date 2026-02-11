"""
Prompt Processing API routes for AI Manager Platform - Business API Service
"""

import logging
from app.utils.security import sanitize_error_message

from fastapi import APIRouter, HTTPException, Request, status

from app.api.v1.schemas import ProcessPromptRequest, ProcessPromptResponse
from app.application.use_cases.process_prompt import ProcessPromptUseCase
from app.domain.models import PromptRequest
from app.infrastructure.http_clients.data_api_client import DataAPIClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prompts", tags=["Prompts"])


@router.post(
    "/process",
    response_model=ProcessPromptResponse,
    status_code=status.HTTP_200_OK,
    summary="Process prompt with AI",
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
        )

    except Exception as e:
        logger.error(f"Failed to process prompt: {sanitize_error_message(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process prompt: {sanitize_error_message(e)}",
        )

    finally:
        # Close HTTP client
        await data_api_client.close()
