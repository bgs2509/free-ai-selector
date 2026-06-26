"""
Unit tests for PromptHistoryRepository (F017)
"""

from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import PromptHistory
from app.infrastructure.database.models import PromptHistoryORM
from app.infrastructure.repositories.prompt_history_repository import (
    PromptHistoryRepository,
)


@pytest.mark.unit
class TestF017GetStatisticsForPeriod:
    """Test get_statistics_for_period() SQL aggregation optimization (F017)."""

    async def test_empty_period_returns_zero_statistics(self, test_db: AsyncSession):
        """Test statistics for period with no records (F017)."""
        repository = PromptHistoryRepository(test_db)

        start = datetime.utcnow() - timedelta(days=7)
        end = datetime.utcnow()

        stats = await repository.get_statistics_for_period(start, end)

        assert stats["total_requests"] == 0
        assert stats["successful_requests"] == 0
        assert stats["failed_requests"] == 0
        assert stats["success_rate"] == 0.0

    async def test_statistics_for_period_with_mixed_results(
        self, test_db: AsyncSession
    ):
        """Test statistics calculation with mixed success/failure records (F017)."""
        repository = PromptHistoryRepository(test_db)

        now = datetime.utcnow()

        # Create 10 records: 7 success, 3 failure
        for i in range(10):
            history = PromptHistory(
                id=None,
                user_id="test_user",
                prompt_text="test prompt",
                selected_model_id=1,
                response_text="response" if i < 7 else None,
                response_time=Decimal("1.5"),
                success=(i < 7),  # First 7 are success
                error_message=None if i < 7 else "error",
                created_at=now - timedelta(hours=i),
            )
            await repository.create(history)

        await test_db.commit()

        # Get statistics for period covering all records
        start = now - timedelta(days=1)
        end = now + timedelta(hours=1)

        stats = await repository.get_statistics_for_period(start, end)

        assert stats["total_requests"] == 10
        assert stats["successful_requests"] == 7
        assert stats["failed_requests"] == 3
        assert stats["success_rate"] == 0.7

    async def test_statistics_for_period_all_success(self, test_db: AsyncSession):
        """Test statistics with all successful records (F017)."""
        repository = PromptHistoryRepository(test_db)

        now = datetime.utcnow()

        # Create 5 successful records
        for i in range(5):
            history = PromptHistory(
                id=None,
                user_id="test_user",
                prompt_text="test prompt",
                selected_model_id=1,
                response_text="response",
                response_time=Decimal("1.0"),
                success=True,
                error_message=None,
                created_at=now - timedelta(hours=i),
            )
            await repository.create(history)

        await test_db.commit()

        start = now - timedelta(days=1)
        end = now + timedelta(hours=1)

        stats = await repository.get_statistics_for_period(start, end)

        assert stats["total_requests"] == 5
        assert stats["successful_requests"] == 5
        assert stats["failed_requests"] == 0
        assert stats["success_rate"] == 1.0

    async def test_statistics_for_period_all_failures(self, test_db: AsyncSession):
        """Test statistics with all failed records (F017)."""
        repository = PromptHistoryRepository(test_db)

        now = datetime.utcnow()

        # Create 3 failed records
        for i in range(3):
            history = PromptHistory(
                id=None,
                user_id="test_user",
                prompt_text="test prompt",
                selected_model_id=1,
                response_text=None,
                response_time=Decimal("0.5"),
                success=False,
                error_message="error",
                created_at=now - timedelta(hours=i),
            )
            await repository.create(history)

        await test_db.commit()

        start = now - timedelta(days=1)
        end = now + timedelta(hours=1)

        stats = await repository.get_statistics_for_period(start, end)

        assert stats["total_requests"] == 3
        assert stats["successful_requests"] == 0
        assert stats["failed_requests"] == 3
        assert stats["success_rate"] == 0.0

    async def test_statistics_filtered_by_model_id(self, test_db: AsyncSession):
        """Test statistics filtering by specific model_id (F017)."""
        repository = PromptHistoryRepository(test_db)

        now = datetime.utcnow()

        # Create records for model_id=1 (3 success, 1 failure)
        for i in range(4):
            history = PromptHistory(
                id=None,
                user_id="test_user",
                prompt_text="test prompt",
                selected_model_id=1,
                response_text="response" if i < 3 else None,
                response_time=Decimal("1.0"),
                success=(i < 3),
                error_message=None if i < 3 else "error",
                created_at=now - timedelta(hours=i),
            )
            await repository.create(history)

        # Create records for model_id=2 (2 success)
        for i in range(2):
            history = PromptHistory(
                id=None,
                user_id="test_user",
                prompt_text="test prompt",
                selected_model_id=2,
                response_text="response",
                response_time=Decimal("1.0"),
                success=True,
                error_message=None,
                created_at=now - timedelta(hours=i + 10),
            )
            await repository.create(history)

        await test_db.commit()

        start = now - timedelta(days=1)
        end = now + timedelta(hours=1)

        # Filter by model_id=1
        stats = await repository.get_statistics_for_period(start, end, model_id=1)

        assert stats["total_requests"] == 4
        assert stats["successful_requests"] == 3
        assert stats["failed_requests"] == 1
        assert stats["success_rate"] == 0.75

    async def test_statistics_excludes_records_outside_period(
        self, test_db: AsyncSession
    ):
        """Test that statistics only include records within the specified period (F017)."""
        repository = PromptHistoryRepository(test_db)

        now = datetime.utcnow()

        # Create records directly via ORM to control created_at (bypass repository.create())
        # This allows us to set custom timestamps for testing period filtering

        # BEFORE period (8 days ago)
        old_orm = PromptHistoryORM(
            user_id="test_user",
            prompt_text="old prompt",
            selected_model_id=1,
            response_text="response",
            response_time=Decimal("1.0"),
            success=True,
            error_message=None,
            created_at=now - timedelta(days=8),
        )
        test_db.add(old_orm)

        # WITHIN period (12 hours ago)
        current_orm = PromptHistoryORM(
            user_id="test_user",
            prompt_text="current prompt",
            selected_model_id=1,
            response_text="response",
            response_time=Decimal("1.0"),
            success=True,
            error_message=None,
            created_at=now - timedelta(hours=12),
        )
        test_db.add(current_orm)

        # AFTER period (in future - 2 hours ahead)
        future_orm = PromptHistoryORM(
            user_id="test_user",
            prompt_text="future prompt",
            selected_model_id=1,
            response_text="response",
            response_time=Decimal("1.0"),
            success=True,
            error_message=None,
            created_at=now + timedelta(hours=2),
        )
        test_db.add(future_orm)

        await test_db.commit()

        # Period: last 24 hours (from 1 day ago to 1 hour in future)
        start = now - timedelta(days=1)
        end = now + timedelta(hours=1)

        stats = await repository.get_statistics_for_period(start, end)

        # Only the current record (12h ago) should be counted
        # Old record (8 days ago) is before start
        # Future record (2h ahead) is after end
        assert stats["total_requests"] == 1
        assert stats["successful_requests"] == 1
        assert stats["failed_requests"] == 0
        assert stats["success_rate"] == 1.0


def _make_history(
    *,
    caller=None,
    success=True,
    model_id=1,
    http_status=None,
    requested_model=None,
    created_at=None,
):
    """Helper building a PromptHistory domain entity for caller tests (oxl)."""
    return PromptHistory(
        id=None,
        user_id="test_user",
        prompt_text="test prompt",
        selected_model_id=model_id,
        response_text="response" if success else None,
        response_time=Decimal("1.5"),
        success=success,
        error_message=None if success else "error",
        created_at=created_at or datetime.utcnow(),
        caller=caller,
        http_status=http_status,
        requested_model=requested_model,
    )


@pytest.mark.unit
class TestCallerPersistence:
    """create() persists the new caller/http_status/requested_model fields (oxl)."""

    async def test_create_persists_caller_fields(self, test_db: AsyncSession):
        repository = PromptHistoryRepository(test_db)

        created = await repository.create(
            _make_history(
                caller="health-worker", http_status=200, requested_model="qwen"
            )
        )
        await test_db.commit()

        fetched = await repository.get_by_id(created.id)
        assert fetched is not None
        assert fetched.caller == "health-worker"
        assert fetched.http_status == 200
        assert fetched.requested_model == "qwen"

    async def test_create_caller_fields_default_null(self, test_db: AsyncSession):
        repository = PromptHistoryRepository(test_db)

        created = await repository.create(_make_history())
        await test_db.commit()

        fetched = await repository.get_by_id(created.id)
        assert fetched is not None
        assert fetched.caller is None
        assert fetched.http_status is None
        assert fetched.requested_model is None


@pytest.mark.unit
class TestGetStatsGroupedByCaller:
    """get_stats_grouped_by_caller() per-project aggregation (oxl)."""

    async def test_empty_returns_empty_list(self, test_db: AsyncSession):
        repository = PromptHistoryRepository(test_db)
        result = await repository.get_stats_grouped_by_caller(window_days=7)
        assert result == []

    async def test_groups_by_caller_with_success_rate(self, test_db: AsyncSession):
        repository = PromptHistoryRepository(test_db)

        # caller A: 3 success, 1 failure (model 1 dominant)
        for i in range(4):
            await repository.create(
                _make_history(caller="A", success=(i < 3), model_id=1)
            )
        # caller B: 1 success (model 2)
        await repository.create(_make_history(caller="B", success=True, model_id=2))

        await test_db.commit()

        result = await repository.get_stats_grouped_by_caller(window_days=7)
        by_caller = {row["caller"]: row for row in result}

        assert by_caller["A"]["request_count"] == 4
        assert by_caller["A"]["success_count"] == 3
        assert by_caller["A"]["success_rate"] == 0.75
        assert by_caller["A"]["top_model_id"] == 1
        assert by_caller["A"]["avg_response_time"] == pytest.approx(1.5)

        assert by_caller["B"]["request_count"] == 1
        assert by_caller["B"]["success_rate"] == 1.0
        assert by_caller["B"]["top_model_id"] == 2

    async def test_ordered_by_request_count_desc(self, test_db: AsyncSession):
        repository = PromptHistoryRepository(test_db)

        for _ in range(1):
            await repository.create(_make_history(caller="small"))
        for _ in range(3):
            await repository.create(_make_history(caller="big"))

        await test_db.commit()

        result = await repository.get_stats_grouped_by_caller(window_days=7)
        assert result[0]["caller"] == "big"
        assert result[0]["request_count"] == 3

    async def test_auto_vs_pinned_requested_model_breakdown(
        self, test_db: AsyncSession
    ):
        """vop: auto_count (requested_model NULL) vs pinned_count (NOT NULL)."""
        repository = PromptHistoryRepository(test_db)

        # caller P: 2 auto (no requested_model) + 3 pinned (requested_model set)
        for _ in range(2):
            await repository.create(_make_history(caller="P", requested_model=None))
        for _ in range(3):
            await repository.create(_make_history(caller="P", requested_model="gpt-x"))
        await test_db.commit()

        row = next(
            r
            for r in await repository.get_stats_grouped_by_caller(window_days=7)
            if r["caller"] == "P"
        )
        assert row["request_count"] == 5
        assert row["auto_count"] == 2
        assert row["pinned_count"] == 3

    async def test_excludes_records_outside_window(self, test_db: AsyncSession):
        repository = PromptHistoryRepository(test_db)

        now = datetime.utcnow()
        # Inside window
        await repository.create(
            _make_history(caller="A", created_at=now - timedelta(days=1))
        )
        # Outside window (created via ORM to keep custom timestamp)
        old = PromptHistoryORM(
            user_id="test_user",
            prompt_text="old",
            selected_model_id=1,
            response_text="r",
            response_time=Decimal("1.0"),
            success=True,
            error_message=None,
            created_at=now - timedelta(days=30),
            caller="A",
        )
        test_db.add(old)
        await test_db.commit()

        result = await repository.get_stats_grouped_by_caller(window_days=7)
        by_caller = {row["caller"]: row for row in result}
        assert by_caller["A"]["request_count"] == 1

    async def test_null_caller_bucket(self, test_db: AsyncSession):
        repository = PromptHistoryRepository(test_db)

        await repository.create(_make_history(caller=None))
        await test_db.commit()

        result = await repository.get_stats_grouped_by_caller(window_days=7)
        assert any(row["caller"] is None for row in result)


@pytest.mark.unit
class TestGetFiltered:
    """get_filtered() journal listing (oxl)."""

    async def test_no_filters_returns_all_desc(self, test_db: AsyncSession):
        repository = PromptHistoryRepository(test_db)

        now = datetime.utcnow()
        await repository.create(
            _make_history(caller="A", created_at=now - timedelta(hours=2))
        )
        await repository.create(
            _make_history(caller="B", created_at=now - timedelta(hours=1))
        )
        await test_db.commit()

        result = await repository.get_filtered()
        assert len(result) == 2
        # ordered created_at DESC -> most recent (B) first
        assert result[0].caller == "B"

    async def test_filter_by_caller(self, test_db: AsyncSession):
        repository = PromptHistoryRepository(test_db)

        await repository.create(_make_history(caller="A"))
        await repository.create(_make_history(caller="B"))
        await test_db.commit()

        result = await repository.get_filtered(caller="A")
        assert len(result) == 1
        assert result[0].caller == "A"

    async def test_filter_by_success(self, test_db: AsyncSession):
        repository = PromptHistoryRepository(test_db)

        await repository.create(_make_history(caller="A", success=True))
        await repository.create(_make_history(caller="A", success=False))
        await test_db.commit()

        only_failed = await repository.get_filtered(success=False)
        assert len(only_failed) == 1
        assert only_failed[0].success is False

    async def test_filter_by_date_range(self, test_db: AsyncSession):
        repository = PromptHistoryRepository(test_db)

        now = datetime.utcnow()
        # Insert via ORM directly to control created_at: repository.create() lets the
        # server_default now() fill created_at, so two rows would share a timestamp
        # and the date-range filter could not separate them.
        test_db.add(
            PromptHistoryORM(
                user_id="test_user",
                prompt_text="old prompt",
                selected_model_id=1,
                response_text="response",
                response_time=Decimal("1.0"),
                success=True,
                error_message=None,
                caller="old",
                created_at=now - timedelta(days=10),
            )
        )
        test_db.add(
            PromptHistoryORM(
                user_id="test_user",
                prompt_text="new prompt",
                selected_model_id=1,
                response_text="response",
                response_time=Decimal("1.0"),
                success=True,
                error_message=None,
                caller="new",
                created_at=now - timedelta(hours=1),
            )
        )
        await test_db.commit()

        result = await repository.get_filtered(
            date_from=now - timedelta(days=1), date_to=now + timedelta(hours=1)
        )
        assert len(result) == 1
        assert result[0].caller == "new"

    async def test_limit_and_offset(self, test_db: AsyncSession):
        repository = PromptHistoryRepository(test_db)

        now = datetime.utcnow()
        for i in range(5):
            await repository.create(
                _make_history(caller="A", created_at=now - timedelta(minutes=i))
            )
        await test_db.commit()

        page = await repository.get_filtered(limit=2, offset=2)
        assert len(page) == 2


@pytest.mark.unit
class TestRecentWeightedStatsV2:
    """bmm/ADR-0003 (j4v): exercise the v2 weighted-stats SQL on a REAL Postgres —
    hard/soft split (429 excluded), NULL http_status treated as hard, median latency.
    This is the test that was missing: prior tests only fed mock stat-dicts into
    _calculate_recent_metrics; the SQL itself was never executed against a DB."""

    async def test_hard_soft_split_and_median(self, test_db: AsyncSession):
        repository = PromptHistoryRepository(test_db)
        now = datetime.utcnow()

        # model 1 rows: 3 success, 1 hard-fail(500), 1 rate-limit(429), 1 NULL-status fail
        rows = [
            (True, 200, "1.0"),
            (True, 200, "2.0"),
            (True, 200, "3.0"),
            (False, 500, "4.0"),  # hard fail
            (False, 429, "0.5"),  # soft (rate limit) — MUST be excluded from quality
            (False, None, "5.0"),  # NULL status fail — treated as hard (conservative)
        ]
        for ok, status, rt in rows:
            await repository.create(
                PromptHistory(
                    id=None,
                    user_id="u",
                    prompt_text="p",
                    selected_model_id=1,
                    response_text="r" if ok else None,
                    response_time=Decimal(rt),
                    success=ok,
                    error_message=None if ok else "e",
                    http_status=status,
                    created_at=now,
                )
            )
        await test_db.commit()

        stats = await repository.get_recent_weighted_stats_for_all_models(window_days=7)

        assert 1 in stats
        s = stats[1]
        # All 6 rows counted in the raw count (used for UCB recent_n).
        assert s["request_count"] == 6
        # Rows are ~now → decay weight ≈ 1, so weighted sums ≈ raw counts.
        # 3 successes, 2 hard fails (500 + NULL); the 429 is in NEITHER.
        assert s["w_success"] == pytest.approx(3.0, abs=0.1)
        assert s["w_fail_hard"] == pytest.approx(2.0, abs=0.1)
        # 429 excluded from both numerator and hard-denominator → sum ≈ 5, not 6.
        assert s["w_success"] + s["w_fail_hard"] == pytest.approx(5.0, abs=0.2)
        # Median latency computed over all 6 response_times [0.5,1,2,3,4,5] → 2.5.
        assert s["median_response_time"] == pytest.approx(2.5, abs=0.6)
