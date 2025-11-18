"""
Providers API routes for AI Manager Platform - Business API Service

Endpoints for testing and managing AI providers.
"""

import logging
from app.utils.security import sanitize_error_message

from fastapi import APIRouter, HTTPException, Request, status

from app.application.use_cases.test_all_providers import TestAllProvidersUseCase
from app.infrastructure.http_clients.data_api_client import DataAPIClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/providers", tags=["Providers"])


@router.post(
    "/test",
    status_code=status.HTTP_200_OK,
    summary="Test all AI providers",
)
async def test_all_providers(request: Request) -> dict:
    """
    Test all registered AI providers with a simple prompt.

    Tests each provider sequentially and returns results including:
    - Provider name and model
    - Success/error status
    - Response time (for successful calls)
    - Error details (for failed calls)

    Results are sorted by response time (fastest first).

    Additionally, this endpoint updates database statistics for each provider,
    making /test command a third source of reliability data alongside
    user prompts and health worker checks.

    Args:
        request: FastAPI request object (for request ID)

    Returns:
        {
            "total_providers": 6,
            "successful": 4,
            "failed": 2,
            "results": [
                {
                    "provider": "Cerebras",
                    "model": "Llama 3.3 70B",
                    "status": "success",
                    "response_time": 0.87,
                    "error": null
                },
                {
                    "provider": "SomeProvider",
                    "model": "Model Name",
                    "status": "error",
                    "response_time": null,
                    "error": "HTTPError: 401 Unauthorized"
                }
            ]
        }

    Raises:
        HTTPException: 500 if testing fails catastrophically
    """
    # Get request ID from middleware
    request_id = getattr(request.state, "request_id", None)

    # Create Data API client with request ID for tracing
    data_api_client = DataAPIClient(request_id=request_id)

    try:
        logger.info("Received request to test all providers")

        # Create and execute use case with Data API client
        use_case = TestAllProvidersUseCase(data_api_client)
        results = await use_case.execute()

        # Count successes and failures
        successful = sum(1 for r in results if r["status"] == "success")
        failed = len(results) - successful

        response = {
            "total_providers": len(results),
            "successful": successful,
            "failed": failed,
            "results": results,
        }

        logger.info(f"Provider testing completed: {successful}/{len(results)} successful")

        return response

    except Exception as e:
        logger.error(f"Failed to test providers: {sanitize_error_message(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to test providers: {sanitize_error_message(e)}",
        )

    finally:
        # Close HTTP client
        await data_api_client.close()
