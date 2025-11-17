"""
Model Statistics API routes for AI Manager Platform - Business API Service
"""

import logging

from fastapi import APIRouter, HTTPException, Request, status

from app.api.v1.schemas import AIModelStatsResponse, ModelsStatsResponse
from app.infrastructure.http_clients.data_api_client import DataAPIClient

logger = logging.getLogger(__name__)

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

        # Convert to response schema
        model_stats = [
            AIModelStatsResponse(
                id=model.id,
                name=model.name,
                provider=model.provider,
                reliability_score=model.reliability_score,
                success_rate=model.reliability_score / 0.6 if model.reliability_score > 0 else 0.0,  # Approximate
                average_response_time=0.0,  # Will be computed by Data API
                total_requests=0,  # Will be fetched from Data API model details
                is_active=model.is_active,
            )
            for model in models
        ]

        return ModelsStatsResponse(models=model_stats, total_models=len(model_stats))

    except Exception as e:
        logger.error(f"Failed to fetch models statistics: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch models statistics: {str(e)}",
        )

    finally:
        # Close HTTP client
        await data_api_client.close()
