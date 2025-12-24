"""
Prompt History API routes for AI Manager Platform - Data API Service

Provides operations for managing prompt history records.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import (
    ModelStatisticsResponse,
    PromptHistoryCreate,
    PromptHistoryResponse,
)
from app.domain.models import PromptHistory
from app.infrastructure.database.connection import get_db
from app.infrastructure.repositories.prompt_history_repository import PromptHistoryRepository

router = APIRouter(prefix="/history", tags=["Prompt History"])


@router.post(
    "",
    response_model=PromptHistoryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create prompt history record",
)
async def create_history(
    history_data: PromptHistoryCreate, db: AsyncSession = Depends(get_db)
) -> PromptHistoryResponse:
    """
    Create a new prompt history record.

    Args:
        history_data: Prompt history creation data
        db: Database session dependency

    Returns:
        Created prompt history record
    """
    repository = PromptHistoryRepository(db)

    new_history = PromptHistory(
        id=None,
        user_id=history_data.user_id,
        prompt_text=history_data.prompt_text,
        selected_model_id=history_data.selected_model_id,
        response_text=history_data.response_text,
        response_time=history_data.response_time,
        success=history_data.success,
        error_message=history_data.error_message,
        created_at=datetime.utcnow(),
    )

    created_history = await repository.create(new_history)
    await db.commit()

    return _history_to_response(created_history)


@router.get("/{history_id}", response_model=PromptHistoryResponse, summary="Get history record by ID")
async def get_history_by_id(
    history_id: int, db: AsyncSession = Depends(get_db)
) -> PromptHistoryResponse:
    """
    Get prompt history record by ID.

    Args:
        history_id: History record ID
        db: Database session dependency

    Returns:
        Prompt history record

    Raises:
        HTTPException: 404 if record not found
    """
    repository = PromptHistoryRepository(db)
    history = await repository.get_by_id(history_id)

    if history is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"History record with ID {history_id} not found",
        )

    return _history_to_response(history)


@router.get("/user/{user_id}", response_model=List[PromptHistoryResponse], summary="Get user history")
async def get_user_history(
    user_id: str,
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    db: AsyncSession = Depends(get_db),
) -> List[PromptHistoryResponse]:
    """
    Get prompt history for a specific user.

    Args:
        user_id: User ID (Telegram user ID or API user ID)
        limit: Maximum number of records to return (1-1000, default: 100)
        offset: Number of records to skip (default: 0)
        db: Database session dependency

    Returns:
        List of prompt history records, ordered by created_at DESC
    """
    repository = PromptHistoryRepository(db)
    histories = await repository.get_by_user(user_id=user_id, limit=limit, offset=offset)

    return [_history_to_response(history) for history in histories]


@router.get(
    "/model/{model_id}", response_model=List[PromptHistoryResponse], summary="Get model history"
)
async def get_model_history(
    model_id: int,
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    db: AsyncSession = Depends(get_db),
) -> List[PromptHistoryResponse]:
    """
    Get prompt history for a specific AI model.

    Args:
        model_id: AI model ID
        limit: Maximum number of records to return (1-1000, default: 100)
        offset: Number of records to skip (default: 0)
        db: Database session dependency

    Returns:
        List of prompt history records, ordered by created_at DESC
    """
    repository = PromptHistoryRepository(db)
    histories = await repository.get_by_model(model_id=model_id, limit=limit, offset=offset)

    return [_history_to_response(history) for history in histories]


@router.get("", response_model=List[PromptHistoryResponse], summary="Get recent history")
async def get_recent_history(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records"),
    success_only: bool = Query(False, description="Return only successful requests"),
    db: AsyncSession = Depends(get_db),
) -> List[PromptHistoryResponse]:
    """
    Get recent prompt history records.

    Args:
        limit: Maximum number of records to return (1-1000, default: 100)
        success_only: If True, return only successful requests (default: False)
        db: Database session dependency

    Returns:
        List of prompt history records, ordered by created_at DESC
    """
    repository = PromptHistoryRepository(db)
    histories = await repository.get_recent(limit=limit, success_only=success_only)

    return [_history_to_response(history) for history in histories]


@router.get(
    "/statistics/period",
    response_model=ModelStatisticsResponse,
    summary="Get statistics for period",
)
async def get_period_statistics(
    start_date: datetime = Query(..., description="Start of period"),
    end_date: datetime = Query(..., description="End of period"),
    model_id: Optional[int] = Query(None, description="Optional filter by model ID"),
    db: AsyncSession = Depends(get_db),
) -> ModelStatisticsResponse:
    """
    Get statistics for a specific time period.

    Args:
        start_date: Start of period
        end_date: End of period
        model_id: Optional filter by model ID
        db: Database session dependency

    Returns:
        Statistics for the period
    """
    repository = PromptHistoryRepository(db)
    stats = await repository.get_statistics_for_period(
        start_date=start_date, end_date=end_date, model_id=model_id
    )

    return ModelStatisticsResponse(**stats)


def _history_to_response(history: PromptHistory) -> PromptHistoryResponse:
    """
    Convert domain model to API response.

    Args:
        history: PromptHistory domain entity

    Returns:
        PromptHistoryResponse schema
    """
    return PromptHistoryResponse(
        id=history.id,
        user_id=history.user_id,
        prompt_text=history.prompt_text,
        selected_model_id=history.selected_model_id,
        response_text=history.response_text,
        response_time=history.response_time,
        success=history.success,
        error_message=history.error_message,
        created_at=history.created_at,
    )
