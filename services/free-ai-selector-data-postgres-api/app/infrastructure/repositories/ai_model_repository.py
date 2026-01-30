"""
AI Model Repository - Data access layer for AI models

Implements repository pattern for AI model CRUD operations.
Uses SQLAlchemy 2.0 async patterns.
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import AIModel
from app.infrastructure.database.models import AIModelORM


class AIModelRepository:
    """Repository for AI Model data access operations."""

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            session: AsyncSession instance for database operations
        """
        self.session = session

    async def get_all(
        self, active_only: bool = True, available_only: bool = False
    ) -> List[AIModel]:
        """
        Get all AI models.

        Args:
            active_only: If True, return only active models (default: True)
            available_only: If True, return only currently available models (default: False)
                           A model is available if available_at is NULL or <= now()

        Returns:
            List of AIModel domain entities
        """
        query = select(AIModelORM)
        if active_only:
            query = query.where(AIModelORM.is_active)

        # F012: Filter by availability
        if available_only:
            now = datetime.utcnow()
            query = query.where(
                (AIModelORM.available_at.is_(None)) | (AIModelORM.available_at <= now)
            )

        result = await self.session.execute(query)
        orm_models = result.scalars().all()

        return [self._to_domain(orm_model) for orm_model in orm_models]

    async def get_by_id(self, model_id: int) -> Optional[AIModel]:
        """
        Get AI model by ID.

        Args:
            model_id: AI model ID

        Returns:
            AIModel domain entity if found, None otherwise
        """
        query = select(AIModelORM).where(AIModelORM.id == model_id)
        result = await self.session.execute(query)
        orm_model = result.scalar_one_or_none()

        if orm_model is None:
            return None

        return self._to_domain(orm_model)

    async def get_by_name(self, name: str) -> Optional[AIModel]:
        """
        Get AI model by name.

        Args:
            name: AI model name

        Returns:
            AIModel domain entity if found, None otherwise
        """
        query = select(AIModelORM).where(AIModelORM.name == name)
        result = await self.session.execute(query)
        orm_model = result.scalar_one_or_none()

        if orm_model is None:
            return None

        return self._to_domain(orm_model)

    async def create(self, model: AIModel) -> AIModel:
        """
        Create a new AI model.

        Args:
            model: AIModel domain entity (without ID)

        Returns:
            Created AIModel with generated ID
        """
        orm_model = AIModelORM(
            name=model.name,
            provider=model.provider,
            api_endpoint=model.api_endpoint,
            success_count=model.success_count,
            failure_count=model.failure_count,
            total_response_time=model.total_response_time,
            request_count=model.request_count,
            last_checked=model.last_checked,
            is_active=model.is_active,
        )

        self.session.add(orm_model)
        await self.session.flush()
        await self.session.refresh(orm_model)

        return self._to_domain(orm_model)

    async def update_stats(
        self,
        model_id: int,
        success_count: Optional[int] = None,
        failure_count: Optional[int] = None,
        total_response_time: Optional[Decimal] = None,
        request_count: Optional[int] = None,
        last_checked: Optional[datetime] = None,
    ) -> Optional[AIModel]:
        """
        Update AI model statistics.

        Args:
            model_id: AI model ID
            success_count: New success count (optional)
            failure_count: New failure count (optional)
            total_response_time: New total response time (optional)
            request_count: New request count (optional)
            last_checked: New last checked timestamp (optional)

        Returns:
            Updated AIModel if found, None otherwise
        """
        # Build update dict with only provided values
        update_values = {}
        if success_count is not None:
            update_values["success_count"] = success_count
        if failure_count is not None:
            update_values["failure_count"] = failure_count
        if total_response_time is not None:
            update_values["total_response_time"] = total_response_time
        if request_count is not None:
            update_values["request_count"] = request_count
        if last_checked is not None:
            update_values["last_checked"] = last_checked

        if not update_values:
            # No updates provided, just fetch and return
            return await self.get_by_id(model_id)

        # Add updated_at timestamp
        update_values["updated_at"] = datetime.utcnow()

        # Execute update
        stmt = update(AIModelORM).where(AIModelORM.id == model_id).values(**update_values)
        await self.session.execute(stmt)
        await self.session.flush()

        # Fetch and return updated model
        return await self.get_by_id(model_id)

    async def increment_success(self, model_id: int, response_time: Decimal) -> Optional[AIModel]:
        """
        Increment success count and update metrics.

        Args:
            model_id: AI model ID
            response_time: Response time in seconds

        Returns:
            Updated AIModel if found, None otherwise
        """
        model = await self.get_by_id(model_id)
        if model is None:
            return None

        return await self.update_stats(
            model_id=model_id,
            success_count=model.success_count + 1,
            request_count=model.request_count + 1,
            total_response_time=model.total_response_time + response_time,
            last_checked=datetime.utcnow(),
        )

    async def increment_failure(self, model_id: int, response_time: Decimal) -> Optional[AIModel]:
        """
        Increment failure count and update metrics.

        Args:
            model_id: AI model ID
            response_time: Response time in seconds (even for failures)

        Returns:
            Updated AIModel if found, None otherwise
        """
        model = await self.get_by_id(model_id)
        if model is None:
            return None

        return await self.update_stats(
            model_id=model_id,
            failure_count=model.failure_count + 1,
            request_count=model.request_count + 1,
            total_response_time=model.total_response_time + response_time,
            last_checked=datetime.utcnow(),
        )

    async def set_active(self, model_id: int, is_active: bool) -> Optional[AIModel]:
        """
        Set model active status.

        Args:
            model_id: AI model ID
            is_active: New active status

        Returns:
            Updated AIModel if found, None otherwise
        """
        stmt = (
            update(AIModelORM)
            .where(AIModelORM.id == model_id)
            .values(is_active=is_active, updated_at=datetime.utcnow())
        )
        await self.session.execute(stmt)
        await self.session.flush()

        return await self.get_by_id(model_id)

    async def set_availability(
        self, model_id: int, retry_after_seconds: int
    ) -> Optional[AIModel]:
        """
        Set model availability (F012: Rate Limit Handling).

        Sets available_at to now() + retry_after_seconds.
        A model with available_at in the future is temporarily unavailable.

        Args:
            model_id: AI model ID
            retry_after_seconds: Seconds until the model becomes available again

        Returns:
            Updated AIModel if found, None otherwise
        """
        available_at = datetime.utcnow()
        if retry_after_seconds > 0:
            available_at = datetime.utcnow() + timedelta(seconds=retry_after_seconds)
        else:
            # retry_after_seconds = 0 means clear the cooldown
            available_at = None

        stmt = (
            update(AIModelORM)
            .where(AIModelORM.id == model_id)
            .values(available_at=available_at, updated_at=datetime.utcnow())
        )
        await self.session.execute(stmt)
        await self.session.flush()

        return await self.get_by_id(model_id)

    def _to_domain(self, orm_model: AIModelORM) -> AIModel:
        """
        Convert ORM model to domain model.

        Args:
            orm_model: SQLAlchemy ORM instance

        Returns:
            AIModel domain entity
        """
        return AIModel(
            id=orm_model.id,
            name=orm_model.name,
            provider=orm_model.provider,
            api_endpoint=orm_model.api_endpoint,
            success_count=orm_model.success_count,
            failure_count=orm_model.failure_count,
            total_response_time=orm_model.total_response_time,
            request_count=orm_model.request_count,
            last_checked=orm_model.last_checked,
            is_active=orm_model.is_active,
            created_at=orm_model.created_at,
            updated_at=orm_model.updated_at,
            api_format=orm_model.api_format,
            env_var=orm_model.env_var,
            available_at=orm_model.available_at,
        )
