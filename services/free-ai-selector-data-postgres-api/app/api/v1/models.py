"""
AI Models API routes for AI Manager Platform - Data API Service

Provides CRUD operations for AI models and statistics management.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_model_or_404
from app.api.v1.schemas import AIModelCreate, AIModelResponse, AIModelStatsUpdate
from app.domain.models import AIModel
from app.infrastructure.database.connection import get_db
from app.infrastructure.repositories.ai_model_repository import AIModelRepository
from app.infrastructure.repositories.prompt_history_repository import PromptHistoryRepository

router = APIRouter(prefix="/models", tags=["AI Models"])

# F010: Minimum requests required to use recent score
MIN_REQUESTS_FOR_RECENT = 3


@router.get("", response_model=List[AIModelResponse], summary="Get all AI models")
async def get_all_models(
    active_only: bool = True,
    available_only: bool = Query(
        False, description="Exclude models with available_at > now() (F012)"
    ),
    include_recent: bool = Query(
        False, description="Include recent metrics calculated from prompt_history (F010)"
    ),
    window_days: int = Query(
        7, ge=1, le=30, description="Window size in days for recent metrics"
    ),
    db: AsyncSession = Depends(get_db),
) -> List[AIModelResponse]:
    """
    Get all AI models.

    Args:
        active_only: If True, return only active models (default: True)
        available_only: If True, exclude models with available_at > now() (default: False)
        include_recent: If True, include recent metrics from prompt_history (F010)
        window_days: Window size in days for recent metrics (1-30, default: 7)
        db: Database session dependency

    Returns:
        List of AI models with statistics (and optional recent metrics)
    """
    repository = AIModelRepository(db)
    models = await repository.get_all(active_only=active_only, available_only=available_only)

    if not include_recent:
        return [_model_to_response(model) for model in models]

    # F010: Get recent stats for all models
    history_repository = PromptHistoryRepository(db)
    recent_stats = await history_repository.get_recent_stats_for_all_models(window_days)

    return [
        _model_to_response(model, recent_stats)
        for model in models
    ]


@router.get("/{model_id}", response_model=AIModelResponse, summary="Get AI model by ID")
async def get_model_by_id(
    model: AIModel = Depends(get_model_or_404),
) -> AIModelResponse:
    """
    Get AI model by ID.

    Args:
        model: AIModel from get_model_or_404 dependency (F015)

    Returns:
        AI model with statistics

    Raises:
        HTTPException: 404 if model not found
    """
    return _model_to_response(model)


@router.post(
    "",
    response_model=AIModelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create new AI model",
)
async def create_model(
    model_data: AIModelCreate, db: AsyncSession = Depends(get_db)
) -> AIModelResponse:
    """
    Create a new AI model.

    Args:
        model_data: AI model creation data
        db: Database session dependency

    Returns:
        Created AI model

    Raises:
        HTTPException: 409 if model with same name already exists
    """
    repository = AIModelRepository(db)

    # Check if model with same name already exists
    existing_model = await repository.get_by_name(model_data.name)
    if existing_model is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"AI model with name '{model_data.name}' already exists",
        )

    # Create new model
    new_model = AIModel(
        id=None,
        name=model_data.name,
        provider=model_data.provider,
        api_endpoint=model_data.api_endpoint,
        success_count=0,
        failure_count=0,
        total_response_time=Decimal("0.0"),
        request_count=0,
        last_checked=None,
        is_active=model_data.is_active,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    created_model = await repository.create(new_model)
    await db.commit()

    return _model_to_response(created_model)


@router.put("/{model_id}/stats", response_model=AIModelResponse, summary="Update model statistics")
async def update_model_stats(
    model_id: int, stats_update: AIModelStatsUpdate, db: AsyncSession = Depends(get_db)
) -> AIModelResponse:
    """
    Update AI model statistics.

    Args:
        model_id: AI model ID
        stats_update: Statistics update data
        db: Database session dependency

    Returns:
        Updated AI model

    Raises:
        HTTPException: 404 if model not found
    """
    repository = AIModelRepository(db)

    updated_model = await repository.update_stats(
        model_id=model_id,
        success_count=stats_update.success_count,
        failure_count=stats_update.failure_count,
        total_response_time=stats_update.total_response_time,
        request_count=stats_update.request_count,
    )

    if updated_model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"AI model with ID {model_id} not found"
        )

    await db.commit()

    return _model_to_response(updated_model)


@router.post(
    "/{model_id}/increment-success", response_model=AIModelResponse, summary="Increment success count"
)
async def increment_success(
    model_id: int, response_time: float, db: AsyncSession = Depends(get_db)
) -> AIModelResponse:
    """
    Increment success count for a model.

    Args:
        model_id: AI model ID
        response_time: Response time in seconds
        db: Database session dependency

    Returns:
        Updated AI model

    Raises:
        HTTPException: 404 if model not found
    """
    repository = AIModelRepository(db)

    updated_model = await repository.increment_success(
        model_id=model_id, response_time=Decimal(str(response_time))
    )

    if updated_model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"AI model with ID {model_id} not found"
        )

    await db.commit()

    return _model_to_response(updated_model)


@router.post(
    "/{model_id}/increment-failure", response_model=AIModelResponse, summary="Increment failure count"
)
async def increment_failure(
    model_id: int, response_time: float, db: AsyncSession = Depends(get_db)
) -> AIModelResponse:
    """
    Increment failure count for a model.

    Args:
        model_id: AI model ID
        response_time: Response time in seconds
        db: Database session dependency

    Returns:
        Updated AI model

    Raises:
        HTTPException: 404 if model not found
    """
    repository = AIModelRepository(db)

    updated_model = await repository.increment_failure(
        model_id=model_id, response_time=Decimal(str(response_time))
    )

    if updated_model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"AI model with ID {model_id} not found"
        )

    await db.commit()

    return _model_to_response(updated_model)


@router.patch("/{model_id}/active", response_model=AIModelResponse, summary="Set model active status")
async def set_model_active(
    model_id: int, is_active: bool, db: AsyncSession = Depends(get_db)
) -> AIModelResponse:
    """
    Set model active status.

    Args:
        model_id: AI model ID
        is_active: New active status
        db: Database session dependency

    Returns:
        Updated AI model

    Raises:
        HTTPException: 404 if model not found
    """
    repository = AIModelRepository(db)

    updated_model = await repository.set_active(model_id=model_id, is_active=is_active)

    if updated_model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"AI model with ID {model_id} not found"
        )

    await db.commit()

    return _model_to_response(updated_model)


@router.patch(
    "/{model_id}/availability", response_model=AIModelResponse, summary="Set model availability cooldown"
)
async def set_model_availability(
    model_id: int,
    retry_after_seconds: int = Query(
        ..., ge=0, description="Seconds until model becomes available (0 = clear cooldown)"
    ),
    db: AsyncSession = Depends(get_db),
) -> AIModelResponse:
    """
    Set model availability cooldown (F012: Rate Limit Handling).

    When a provider returns 429 rate limit, set available_at to now() + retry_after_seconds.
    The model will be excluded from selection until available_at is reached.

    Args:
        model_id: AI model ID
        retry_after_seconds: Seconds until model becomes available (0 = clear cooldown)
        db: Database session dependency

    Returns:
        Updated AI model with new available_at timestamp

    Raises:
        HTTPException: 404 if model not found
    """
    repository = AIModelRepository(db)

    updated_model = await repository.set_availability(
        model_id=model_id, retry_after_seconds=retry_after_seconds
    )

    if updated_model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"AI model with ID {model_id} not found"
        )

    await db.commit()

    return _model_to_response(updated_model)


def _model_to_response(
    model: AIModel,
    recent_stats: Dict[int, Dict[str, Any]] | None = None,
) -> AIModelResponse:
    """
    Convert domain model to API response (F015: FR-001 unified function).

    Args:
        model: AIModel domain entity
        recent_stats: Optional dict from get_recent_stats_for_all_models() (F010)

    Returns:
        AIModelResponse schema with or without recent metrics
    """
    # F010: Calculate recent metrics only if recent_stats provided
    if recent_stats is not None:
        recent_metrics = _calculate_recent_metrics(model, recent_stats)
    else:
        recent_metrics = {
            "recent_success_rate": None,
            "recent_request_count": None,
            "recent_reliability_score": None,
            "effective_reliability_score": None,
            "decision_reason": None,
        }

    return AIModelResponse(
        id=model.id,
        name=model.name,
        provider=model.provider,
        api_endpoint=model.api_endpoint,
        success_count=model.success_count,
        failure_count=model.failure_count,
        total_response_time=model.total_response_time,
        request_count=model.request_count,
        last_checked=model.last_checked,
        is_active=model.is_active,
        created_at=model.created_at,
        updated_at=model.updated_at,
        api_format=model.api_format,
        env_var=model.env_var,
        available_at=model.available_at,
        success_rate=model.success_rate,
        average_response_time=model.average_response_time,
        speed_score=model.speed_score,
        reliability_score=model.reliability_score,
        # F010: Recent metrics
        recent_success_rate=recent_metrics["recent_success_rate"],
        recent_request_count=recent_metrics["recent_request_count"],
        recent_reliability_score=recent_metrics["recent_reliability_score"],
        effective_reliability_score=recent_metrics["effective_reliability_score"],
        decision_reason=recent_metrics["decision_reason"],
    )


def _calculate_recent_metrics(
    model: AIModel, recent_stats: Dict[int, Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Calculate recent metrics for a model (F010).

    If model has >= MIN_REQUESTS_FOR_RECENT requests in window,
    uses recent_reliability_score. Otherwise falls back to long-term score.

    Args:
        model: AIModel domain entity
        recent_stats: Dict from get_recent_stats_for_all_models()

    Returns:
        Dict with recent_*, effective_*, and decision_reason fields
    """
    stats = recent_stats.get(model.id, {})
    request_count = stats.get("request_count", 0)
    success_count = stats.get("success_count", 0)
    avg_response_time = stats.get("avg_response_time", 0.0)

    if request_count >= MIN_REQUESTS_FOR_RECENT:
        recent_success_rate = success_count / request_count

        # F016: Использование ReliabilityService (Single Source of Truth)
        from app.domain.services.reliability_service import ReliabilityService

        recent_reliability = ReliabilityService.calculate(
            success_rate=recent_success_rate, avg_response_time=avg_response_time
        )

        return {
            "recent_success_rate": round(recent_success_rate, 4),
            "recent_request_count": request_count,
            "recent_reliability_score": round(recent_reliability, 4),
            "effective_reliability_score": round(recent_reliability, 4),
            "decision_reason": "recent_score",
        }
    else:
        return {
            "recent_success_rate": None,
            "recent_request_count": request_count,
            "recent_reliability_score": None,
            "effective_reliability_score": round(model.reliability_score, 4),
            "decision_reason": "fallback",
        }


