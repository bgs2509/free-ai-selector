"""
Prompt History Repository - Data access layer for prompt history

Implements repository pattern for prompt history CRUD operations.
Uses SQLAlchemy 2.0 async patterns.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import case, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import PromptHistory
from app.infrastructure.database.models import PromptHistoryORM


class PromptHistoryRepository:
    """Repository for Prompt History data access operations."""

    def __init__(self, session: AsyncSession):
        """
        Initialize repository with database session.

        Args:
            session: AsyncSession instance for database operations
        """
        self.session = session

    async def create(self, history: PromptHistory) -> PromptHistory:
        """
        Create a new prompt history record.

        Args:
            history: PromptHistory domain entity (without ID)

        Returns:
            Created PromptHistory with generated ID
        """
        orm_history = PromptHistoryORM(
            user_id=history.user_id,
            prompt_text=history.prompt_text,
            selected_model_id=history.selected_model_id,
            response_text=history.response_text,
            response_time=history.response_time,
            success=history.success,
            error_message=history.error_message,
        )

        self.session.add(orm_history)
        await self.session.flush()
        await self.session.refresh(orm_history)

        return self._to_domain(orm_history)

    async def get_by_id(self, history_id: int) -> Optional[PromptHistory]:
        """
        Get prompt history by ID.

        Args:
            history_id: Prompt history ID

        Returns:
            PromptHistory domain entity if found, None otherwise
        """
        query = select(PromptHistoryORM).where(PromptHistoryORM.id == history_id)
        result = await self.session.execute(query)
        orm_history = result.scalar_one_or_none()

        if orm_history is None:
            return None

        return self._to_domain(orm_history)

    async def get_by_user(
        self, user_id: str, limit: int = 100, offset: int = 0
    ) -> List[PromptHistory]:
        """
        Get prompt history for a specific user.

        Args:
            user_id: User ID (Telegram user ID or API user ID)
            limit: Maximum number of records to return (default: 100)
            offset: Number of records to skip (default: 0)

        Returns:
            List of PromptHistory domain entities, ordered by created_at DESC
        """
        query = (
            select(PromptHistoryORM)
            .where(PromptHistoryORM.user_id == user_id)
            .order_by(desc(PromptHistoryORM.created_at))
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(query)
        orm_histories = result.scalars().all()

        return [self._to_domain(orm_history) for orm_history in orm_histories]

    async def get_by_model(
        self, model_id: int, limit: int = 100, offset: int = 0
    ) -> List[PromptHistory]:
        """
        Get prompt history for a specific model.

        Args:
            model_id: AI model ID
            limit: Maximum number of records to return (default: 100)
            offset: Number of records to skip (default: 0)

        Returns:
            List of PromptHistory domain entities, ordered by created_at DESC
        """
        query = (
            select(PromptHistoryORM)
            .where(PromptHistoryORM.selected_model_id == model_id)
            .order_by(desc(PromptHistoryORM.created_at))
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(query)
        orm_histories = result.scalars().all()

        return [self._to_domain(orm_history) for orm_history in orm_histories]

    async def get_recent(
        self, limit: int = 100, success_only: bool = False
    ) -> List[PromptHistory]:
        """
        Get recent prompt history records.

        Args:
            limit: Maximum number of records to return (default: 100)
            success_only: If True, return only successful requests (default: False)

        Returns:
            List of PromptHistory domain entities, ordered by created_at DESC
        """
        query = select(PromptHistoryORM).order_by(desc(PromptHistoryORM.created_at)).limit(limit)

        if success_only:
            query = query.where(PromptHistoryORM.success == True)

        result = await self.session.execute(query)
        orm_histories = result.scalars().all()

        return [self._to_domain(orm_history) for orm_history in orm_histories]

    async def get_recent_stats_for_all_models(
        self, window_days: int = 7
    ) -> Dict[int, Dict[str, Any]]:
        """
        Get aggregated statistics for all models within a time window.

        Uses SQL GROUP BY for efficient aggregation instead of loading all records.
        Leverages existing index ix_prompt_history_created_at.

        Args:
            window_days: Number of days to look back (default: 7)

        Returns:
            Dict mapping model_id to stats dict:
            {
                model_id: {
                    "request_count": int,
                    "success_count": int,
                    "avg_response_time": float
                }
            }
        """
        cutoff_date = datetime.utcnow() - timedelta(days=window_days)

        query = (
            select(
                PromptHistoryORM.selected_model_id,
                func.count().label("request_count"),
                func.sum(
                    case((PromptHistoryORM.success == True, 1), else_=0)  # noqa: E712
                ).label("success_count"),
                func.avg(PromptHistoryORM.response_time).label("avg_response_time"),
            )
            .where(PromptHistoryORM.created_at > cutoff_date)
            .group_by(PromptHistoryORM.selected_model_id)
        )

        result = await self.session.execute(query)
        rows = result.all()

        return {
            row.selected_model_id: {
                "request_count": row.request_count,
                "success_count": row.success_count,
                "avg_response_time": float(row.avg_response_time or 0.0),
            }
            for row in rows
        }

    async def get_statistics_for_period(
        self, start_date: datetime, end_date: datetime, model_id: Optional[int] = None
    ) -> dict:
        """
        Get statistics for a specific time period.

        Args:
            start_date: Start of period
            end_date: End of period
            model_id: Optional filter by model ID

        Returns:
            Dictionary with statistics:
            {
                "total_requests": int,
                "successful_requests": int,
                "failed_requests": int,
                "success_rate": float
            }
        """
        query = select(PromptHistoryORM).where(
            PromptHistoryORM.created_at >= start_date, PromptHistoryORM.created_at <= end_date
        )

        if model_id is not None:
            query = query.where(PromptHistoryORM.selected_model_id == model_id)

        result = await self.session.execute(query)
        histories = result.scalars().all()

        total_requests = len(histories)
        successful_requests = sum(1 for h in histories if h.success)
        failed_requests = total_requests - successful_requests
        success_rate = successful_requests / total_requests if total_requests > 0 else 0.0

        return {
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "success_rate": success_rate,
        }

    def _to_domain(self, orm_history: PromptHistoryORM) -> PromptHistory:
        """
        Convert ORM model to domain model.

        Args:
            orm_history: SQLAlchemy ORM instance

        Returns:
            PromptHistory domain entity
        """
        return PromptHistory(
            id=orm_history.id,
            user_id=orm_history.user_id,
            prompt_text=orm_history.prompt_text,
            selected_model_id=orm_history.selected_model_id,
            response_text=orm_history.response_text,
            response_time=orm_history.response_time,
            success=orm_history.success,
            error_message=orm_history.error_message,
            created_at=orm_history.created_at,
        )
