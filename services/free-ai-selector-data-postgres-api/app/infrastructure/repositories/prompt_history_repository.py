"""
Prompt History Repository - Data access layer for prompt history

Implements repository pattern for prompt history CRUD operations.
Uses SQLAlchemy 2.0 async patterns.
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import case, desc, func, literal, select
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
            caller=history.caller,
            http_status=history.http_status,
            requested_model=history.requested_model,
        )

        self.session.add(orm_history)
        await self.session.flush()
        await self.session.refresh(orm_history)

        # Автоматически удаляем старые записи, оставляем только 5000 последних
        # (увеличено с 1000 для учёта записей health worker)
        await self._cleanup_old_records(keep_count=5000)

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
        query = (
            select(PromptHistoryORM)
            .order_by(desc(PromptHistoryORM.created_at))
            .limit(limit)
        )

        if success_only:
            query = query.where(PromptHistoryORM.success)

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

    async def get_recent_weighted_stats_for_all_models(
        self, window_days: int = 7, decay_per_hour: Optional[float] = None
    ) -> Dict[int, Dict[str, Any]]:
        """
        Decay-взвешенная агрегация статистики моделей за окно (bmm v2 / ADR-0003).

        Свежие записи весят больше: weight = decay_per_hour ^ hours_ago.
        decay_per_hour по умолчанию выводится из RATING_HALF_LIFE_HOURS (~0.98 при 34ч).

        Возвращает decay-взвешенные суммы успехов и ЖЁСТКИХ сбоев
        (success=false AND http_status != 429; NULL http_status трактуется как hard),
        чтобы 429-rate-limit не топили quality. Плюс медиану латентности.

        Args:
            window_days: Размер окна в днях (default: 7)
            decay_per_hour: Коэффициент затухания за 1 час (default: из half-life)

        Returns:
            Dict {model_id: {request_count, weighted_success_rate,
            weighted_avg_response_time, w_success, w_fail_hard, median_response_time}}
        """
        from app.domain.services import rating_params

        if decay_per_hour is None:
            decay_per_hour = rating_params.decay_per_hour()

        cutoff_date = datetime.utcnow() - timedelta(days=window_days)

        # hours_ago = EXTRACT(EPOCH FROM (NOW() - created_at)) / 3600
        hours_ago = func.extract(
            "epoch", func.now() - PromptHistoryORM.created_at
        ) / literal(3600.0)

        # weight = POW(decay_per_hour, hours_ago)
        weight = func.pow(literal(decay_per_hour), hours_ago)

        # bmm: a row is a HARD failure when it failed AND was not a 429 rate-limit.
        # NULL http_status (rows before migration 0005) is treated as hard (conservative).
        hard_fail = (PromptHistoryORM.success == False) & (  # noqa: E712
            PromptHistoryORM.http_status.is_(None)
            | (PromptHistoryORM.http_status != literal(429))
        )

        query = (
            select(
                PromptHistoryORM.selected_model_id,
                func.count().label("request_count"),
                # weighted success rate
                func.sum(
                    case((PromptHistoryORM.success == True, weight), else_=literal(0.0))  # noqa: E712
                ).label("weighted_successes"),
                # bmm: weighted HARD failures only (429 excluded) for Laplace quality
                func.sum(case((hard_fail, weight), else_=literal(0.0))).label(
                    "weighted_hard_failures"
                ),
                func.sum(weight).label("total_weight"),
                # weighted average response time
                func.sum(PromptHistoryORM.response_time * weight).label(
                    "weighted_time_sum"
                ),
                # bmm: median latency (robust vs mean for speed scoring)
                func.percentile_cont(0.5)
                .within_group(PromptHistoryORM.response_time.asc())
                .label("median_response_time"),
            )
            .where(PromptHistoryORM.created_at > cutoff_date)
            .group_by(PromptHistoryORM.selected_model_id)
        )

        result = await self.session.execute(query)
        rows = result.all()

        stats: Dict[int, Dict[str, Any]] = {}
        for row in rows:
            total_w = float(row.total_weight or 0.0)
            if total_w > 0:
                w_success_rate = float(row.weighted_successes or 0.0) / total_w
                w_avg_time = float(row.weighted_time_sum or 0.0) / total_w
            else:
                w_success_rate = 0.0
                w_avg_time = 0.0

            stats[row.selected_model_id] = {
                "request_count": row.request_count,
                "weighted_success_rate": round(w_success_rate, 4),
                "weighted_avg_response_time": round(w_avg_time, 4),
                # bmm v2 (ADR-0003) fields
                "w_success": round(float(row.weighted_successes or 0.0), 6),
                "w_fail_hard": round(float(row.weighted_hard_failures or 0.0), 6),
                "median_response_time": round(
                    float(row.median_response_time or 0.0), 4
                ),
            }

        return stats

    async def get_statistics_for_period(
        self, start_date: datetime, end_date: datetime, model_id: Optional[int] = None
    ) -> dict:
        """
        Get statistics for a specific time period using SQL aggregation.

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
        # Используем SQL aggregation вместо загрузки всех записей (F017)
        query = select(
            func.count().label("total"),
            func.sum(case((PromptHistoryORM.success == True, 1), else_=0)).label(
                "success"
            ),  # noqa: E712
        ).where(
            PromptHistoryORM.created_at >= start_date,
            PromptHistoryORM.created_at <= end_date,
        )

        if model_id is not None:
            query = query.where(PromptHistoryORM.selected_model_id == model_id)

        result = await self.session.execute(query)
        row = result.one()

        total_requests = row.total or 0
        successful_requests = row.success or 0
        failed_requests = total_requests - successful_requests
        success_rate = (
            successful_requests / total_requests if total_requests > 0 else 0.0
        )

        return {
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "failed_requests": failed_requests,
            "success_rate": success_rate,
        }

    async def get_stats_grouped_by_caller(
        self, window_days: int = 7
    ) -> List[Dict[str, Any]]:
        """
        Get per-caller (per-project) aggregate statistics within a time window (oxl).

        Mirrors the GROUP BY aggregation style of get_recent_stats_for_all_models,
        but groups by `caller`. For each caller it also resolves the most-frequently
        selected model via a second grouped query.

        Args:
            window_days: Number of days to look back (default: 7)

        Returns:
            List of per-caller aggregate dicts, ordered by request_count DESC:
            {
                "caller": Optional[str],
                "request_count": int,
                "success_count": int,
                "success_rate": float,
                "avg_response_time": float,
                "top_model_id": Optional[int],
            }
        """
        cutoff_date = datetime.utcnow() - timedelta(days=window_days)

        # Primary aggregation: counts + success + avg response time grouped by caller.
        agg_query = (
            select(
                PromptHistoryORM.caller,
                func.count().label("request_count"),
                func.sum(
                    case((PromptHistoryORM.success == True, 1), else_=0)  # noqa: E712
                ).label("success_count"),
                func.avg(PromptHistoryORM.response_time).label("avg_response_time"),
                func.sum(
                    case((PromptHistoryORM.requested_model.is_(None), 1), else_=0)
                ).label("auto_count"),
                func.sum(
                    case((PromptHistoryORM.requested_model.is_not(None), 1), else_=0)
                ).label("pinned_count"),
            )
            .where(PromptHistoryORM.created_at > cutoff_date)
            .group_by(PromptHistoryORM.caller)
            .order_by(desc(func.count()))
        )

        agg_result = await self.session.execute(agg_query)
        agg_rows = agg_result.all()

        # Secondary aggregation: most-frequent selected_model_id per caller.
        model_query = (
            select(
                PromptHistoryORM.caller,
                PromptHistoryORM.selected_model_id,
                func.count().label("model_count"),
            )
            .where(PromptHistoryORM.created_at > cutoff_date)
            .group_by(PromptHistoryORM.caller, PromptHistoryORM.selected_model_id)
            .order_by(PromptHistoryORM.caller, desc(func.count()))
        )

        model_result = await self.session.execute(model_query)

        # Keep the first (highest-count) model row per caller.
        top_model_by_caller: Dict[Optional[str], int] = {}
        for row in model_result.all():
            if row.caller not in top_model_by_caller:
                top_model_by_caller[row.caller] = row.selected_model_id

        stats: List[Dict[str, Any]] = []
        for row in agg_rows:
            request_count = row.request_count or 0
            success_count = row.success_count or 0
            success_rate = success_count / request_count if request_count > 0 else 0.0
            stats.append(
                {
                    "caller": row.caller,
                    "request_count": request_count,
                    "success_count": success_count,
                    "success_rate": success_rate,
                    "avg_response_time": float(row.avg_response_time or 0.0),
                    "top_model_id": top_model_by_caller.get(row.caller),
                    "auto_count": row.auto_count or 0,
                    "pinned_count": row.pinned_count or 0,
                }
            )

        return stats

    async def get_filtered(
        self,
        caller: Optional[str] = None,
        success: Optional[bool] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[PromptHistory]:
        """
        Filtered journal listing of prompt history records (oxl).

        All filters are optional and combined with AND. Results are ordered by
        created_at DESC for journal-style display.

        Args:
            caller: Optional filter by external project name
            success: Optional filter by success flag
            date_from: Optional inclusive lower bound on created_at
            date_to: Optional inclusive upper bound on created_at
            limit: Maximum number of records to return (default: 100)
            offset: Number of records to skip (default: 0)

        Returns:
            List of PromptHistory domain entities, ordered by created_at DESC
        """
        query = select(PromptHistoryORM)

        if caller is not None:
            query = query.where(PromptHistoryORM.caller == caller)
        if success is not None:
            query = query.where(PromptHistoryORM.success == success)
        if date_from is not None:
            query = query.where(PromptHistoryORM.created_at >= date_from)
        if date_to is not None:
            query = query.where(PromptHistoryORM.created_at <= date_to)

        query = (
            query.order_by(desc(PromptHistoryORM.created_at))
            .limit(limit)
            .offset(offset)
        )

        result = await self.session.execute(query)
        orm_histories = result.scalars().all()

        return [self._to_domain(orm_history) for orm_history in orm_histories]

    async def _cleanup_old_records(self, keep_count: int = 1000) -> None:
        """
        Удаляет старые записи, оставляя только keep_count последних.

        Args:
            keep_count: Количество записей для сохранения (default: 1000)
        """
        # Подзапрос: получить ID последних keep_count записей
        subquery = (
            select(PromptHistoryORM.id)
            .order_by(desc(PromptHistoryORM.created_at))
            .limit(keep_count)
            .scalar_subquery()
        )

        # Удалить все записи, которые не входят в топ keep_count
        from sqlalchemy import delete

        delete_query = delete(PromptHistoryORM).where(
            PromptHistoryORM.id.notin_(subquery)
        )

        await self.session.execute(delete_query)

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
            caller=orm_history.caller,
            http_status=orm_history.http_status,
            requested_model=orm_history.requested_model,
        )
