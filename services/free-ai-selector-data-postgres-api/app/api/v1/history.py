"""
Prompt History API routes for AI Manager Platform - Data API Service

Provides operations for managing prompt history records.
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.params import Query as _QueryParam
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.schemas import (
    CallerStatisticsResponse,
    ModelStatisticsResponse,
    PromptHistoryCreate,
    PromptHistoryResponse,
)
from app.domain.models import PromptHistory
from app.infrastructure.database.connection import get_db
from app.infrastructure.repositories.prompt_history_repository import PromptHistoryRepository

router = APIRouter(prefix="/history", tags=["Prompt History"])


def _unwrap_query(value, fallback=None):
    """Resolve a FastAPI ``Query(...)`` default to its scalar value.

    Route handlers in this service are unit-tested by direct invocation, where
    FastAPI does not resolve ``Query(...)`` defaults — un-passed params keep
    their ``fastapi.params.Query`` object. Over HTTP the values are already
    scalars, so this is a no-op there.
    """
    if isinstance(value, _QueryParam):
        default = value.default
        return fallback if default is ... else default
    return value


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
        caller=history_data.caller,
        http_status=history_data.http_status,
        requested_model=history_data.requested_model,
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


@router.get(
    "",
    response_model=List[PromptHistoryResponse],
    summary="Get recent history (journal, with optional filters)",
)
async def get_recent_history(
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records"),
    offset: int = Query(0, ge=0, description="Number of records to skip"),
    success_only: bool = Query(False, description="Return only successful requests"),
    caller: Optional[str] = Query(None, description="Filter by external project (caller)"),
    success: Optional[bool] = Query(
        None, description="Filter by success flag (overrides success_only when set)"
    ),
    date_from: Optional[datetime] = Query(
        None, description="Inclusive lower bound on created_at"
    ),
    date_to: Optional[datetime] = Query(None, description="Inclusive upper bound on created_at"),
    db: AsyncSession = Depends(get_db),
) -> List[PromptHistoryResponse]:
    """
    Get recent prompt history records (journal view).

    Backward compatible: with no new query params it behaves like before
    (recent records, optional success_only). When any journal filter is
    provided (caller / success / date_from / date_to / offset), the filtered
    listing is used instead.

    Args:
        limit: Maximum number of records to return (1-1000, default: 100)
        offset: Number of records to skip (default: 0)
        success_only: Legacy flag — return only successful requests (default: False)
        caller: Optional filter by external project (caller)
        success: Optional explicit success filter (takes precedence over success_only)
        date_from: Optional inclusive lower bound on created_at
        date_to: Optional inclusive upper bound on created_at
        db: Database session dependency

    Returns:
        List of prompt history records, ordered by created_at DESC
    """
    # Resolve Query() defaults for direct (non-HTTP) invocation; no-op over HTTP.
    limit = _unwrap_query(limit, 100)
    offset = _unwrap_query(offset, 0)
    success_only = _unwrap_query(success_only, False)
    caller = _unwrap_query(caller, None)
    success = _unwrap_query(success, None)
    date_from = _unwrap_query(date_from, None)
    date_to = _unwrap_query(date_to, None)

    repository = PromptHistoryRepository(db)

    # Resolve success filter: explicit `success` wins; else legacy success_only.
    success_filter: Optional[bool] = success
    if success_filter is None and success_only:
        success_filter = True

    use_filtered = (
        caller is not None
        or success_filter is not None
        or date_from is not None
        or date_to is not None
        or offset > 0
    )

    if use_filtered:
        histories = await repository.get_filtered(
            caller=caller,
            success=success_filter,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            offset=offset,
        )
    else:
        histories = await repository.get_recent(limit=limit, success_only=success_only)

    return [_history_to_response(history) for history in histories]


@router.get(
    "/statistics/by-caller",
    response_model=List[CallerStatisticsResponse],
    summary="Get per-project (caller) aggregate statistics",
)
async def get_caller_statistics(
    window_days: int = Query(7, ge=1, le=365, description="Look-back window in days"),
    db: AsyncSession = Depends(get_db),
) -> List[CallerStatisticsResponse]:
    """
    Get per-project ("caller") aggregate statistics within a time window.

    Args:
        window_days: Number of days to look back (1-365, default: 7)
        db: Database session dependency

    Returns:
        List of per-caller aggregate objects, ordered by request_count DESC
    """
    window_days = _unwrap_query(window_days, 7)

    repository = PromptHistoryRepository(db)
    stats = await repository.get_stats_grouped_by_caller(window_days=window_days)

    return [CallerStatisticsResponse(**row) for row in stats]


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
        caller=history.caller,
        http_status=history.http_status,
        requested_model=history.requested_model,
    )
