"""
FastAPI dependencies for AI Manager Platform - Data API Service (F015).

Provides reusable dependencies for route handlers to reduce code duplication.
"""

from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import AIModel
from app.infrastructure.database.connection import get_db
from app.infrastructure.repositories.ai_model_repository import AIModelRepository


async def get_model_or_404(
    model_id: int,
    db: AsyncSession = Depends(get_db),
) -> AIModel:
    """
    FastAPI dependency: get model by ID or raise 404.

    Eliminates duplicate get+404 pattern across 6 endpoints (F015: FR-002).

    Args:
        model_id: Model ID from path parameter
        db: Database session dependency

    Returns:
        AIModel domain entity

    Raises:
        HTTPException: 404 if model not found
    """
    repository = AIModelRepository(db)
    model = await repository.get_by_id(model_id)

    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"AI model with ID {model_id} not found",
        )

    return model
