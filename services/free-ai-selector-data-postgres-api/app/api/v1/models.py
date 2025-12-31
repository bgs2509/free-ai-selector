"""
AI Models API routes for AI Manager Platform - Data API Service

Provides CRUD operations for AI models and statistics management.
"""

from datetime import datetime
from decimal import Decimal
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import AIModelCreate, AIModelResponse, AIModelStatsUpdate
from app.domain.models import AIModel
from app.infrastructure.database.connection import get_db
from app.infrastructure.repositories.ai_model_repository import AIModelRepository

router = APIRouter(prefix="/models", tags=["AI Models"])


@router.get("", response_model=List[AIModelResponse], summary="Get all AI models")
async def get_all_models(
    active_only: bool = True, db: AsyncSession = Depends(get_db)
) -> List[AIModelResponse]:
    """
    Get all AI models.

    Args:
        active_only: If True, return only active models (default: True)
        db: Database session dependency

    Returns:
        List of AI models with statistics
    """
    repository = AIModelRepository(db)
    models = await repository.get_all(active_only=active_only)

    return [_model_to_response(model) for model in models]


@router.get("/{model_id}", response_model=AIModelResponse, summary="Get AI model by ID")
async def get_model_by_id(model_id: int, db: AsyncSession = Depends(get_db)) -> AIModelResponse:
    """
    Get AI model by ID.

    Args:
        model_id: AI model ID
        db: Database session dependency

    Returns:
        AI model with statistics

    Raises:
        HTTPException: 404 if model not found
    """
    repository = AIModelRepository(db)
    model = await repository.get_by_id(model_id)

    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"AI model with ID {model_id} not found"
        )

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


def _model_to_response(model: AIModel) -> AIModelResponse:
    """
    Convert domain model to API response.

    Args:
        model: AIModel domain entity

    Returns:
        AIModelResponse schema
    """
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
        success_rate=model.success_rate,
        average_response_time=model.average_response_time,
        speed_score=model.speed_score,
        reliability_score=model.reliability_score,
    )
