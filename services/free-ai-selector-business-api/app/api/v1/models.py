"""
Model Statistics API routes for AI Manager Platform - Business API Service
"""

from app.utils.security import sanitize_error_message

from fastapi import APIRouter, HTTPException, Request, status

from app.api.v1.schemas import AIModelStatsResponse, ModelsStatsResponse
from app.infrastructure.http_clients.data_api_client import DataAPIClient
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/models", tags=["Models"])


@router.get(
    "/stats", response_model=ModelsStatsResponse, summary="Get all models statistics"
)
async def get_models_stats(request: Request) -> ModelsStatsResponse:
    """
    Get statistics for all AI models.

    Returns reliability scores, success rates, and performance metrics
    for all active models.

    Args:
        request: FastAPI request object (for request ID)

    Returns:
        ModelsStatsResponse with all models statistics

    Raises:
        HTTPException: 500 if Data API request fails
    """
    # Get request ID from middleware
    request_id = getattr(request.state, "request_id", None)

    # Create Data API client
    data_api_client = DataAPIClient(request_id=request_id)

    try:
        # Fetch all models (including inactive for stats)
        models = await data_api_client.get_all_models(active_only=False)

        # Convert to response schema (используем реальные метрики из Data API)
        model_stats = [
            AIModelStatsResponse(
                id=model.id,
                name=model.name,
                provider=model.provider,
                reliability_score=model.reliability_score,
                success_rate=model.success_rate,
                average_response_time=model.average_response_time,
                total_requests=model.request_count,
                is_active=model.is_active,
            )
            for model in models
        ]

        return ModelsStatsResponse(models=model_stats, total_models=len(model_stats))

    except Exception as e:
        logger.error("fetch_models_statistics_failed", error=sanitize_error_message(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch models statistics: {sanitize_error_message(e)}",
        )

    finally:
        # Close HTTP client
        await data_api_client.close()
