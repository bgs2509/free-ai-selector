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

    async def test_statistics_for_period_with_mixed_results(self, test_db: AsyncSession):
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

    async def test_statistics_excludes_records_outside_period(self, test_db: AsyncSession):
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
