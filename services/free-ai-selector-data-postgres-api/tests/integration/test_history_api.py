"""Тесты для app/api/v1/history.py — вызов endpoint-функций напрямую."""
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException

from app.api.v1.history import (
    create_history,
    get_history_by_id,
    get_model_history,
    get_period_statistics,
    get_recent_history,
    get_user_history,
)
from app.api.v1.schemas import PromptHistoryCreate
from app.infrastructure.database.models import AIModelORM


@pytest.fixture
async def sample_model(test_db) -> AIModelORM:
    """Создать тестовую модель в БД."""
    model = AIModelORM(
        name="Test Model",
        provider="TestProvider",
        api_endpoint="https://test.api/v1",
        success_count=10,
        failure_count=2,
        total_response_time=Decimal("5.0"),
        request_count=12,
        is_active=True,
        api_format="openai",
    )
    test_db.add(model)
    await test_db.flush()
    return model


def _make_history_data(
    model_id: int,
    user_id: str = "test-user",
    success: bool = True,
) -> PromptHistoryCreate:
    return PromptHistoryCreate(
        user_id=user_id,
        prompt_text="Hello AI",
        selected_model_id=model_id,
        response_text="Hello human",
        response_time=Decimal("1.5"),
        success=success,
    )


class TestCreateHistory:
    async def test_creates_record(self, test_db, sample_model):
        data = _make_history_data(sample_model.id)
        result = await create_history(data, test_db)
        assert result.user_id == "test-user"
        assert result.success is True
        assert result.id is not None

    async def test_returns_generated_id(self, test_db, sample_model):
        data = _make_history_data(sample_model.id)
        result = await create_history(data, test_db)
        assert isinstance(result.id, int)
        assert result.id > 0


class TestGetHistoryById:
    async def test_found(self, test_db, sample_model):
        data = _make_history_data(sample_model.id)
        created = await create_history(data, test_db)
        result = await get_history_by_id(created.id, test_db)
        assert result.id == created.id
        assert result.user_id == "test-user"

    async def test_not_found(self, test_db):
        with pytest.raises(HTTPException) as exc_info:
            await get_history_by_id(99999, test_db)
        assert exc_info.value.status_code == 404


class TestGetUserHistory:
    async def test_returns_user_records(self, test_db, sample_model):
        for _ in range(3):
            await create_history(
                _make_history_data(sample_model.id, user_id="user-42"), test_db
            )
        result = await get_user_history("user-42", limit=100, offset=0, db=test_db)
        assert len(result) == 3
        assert all(r.user_id == "user-42" for r in result)

    async def test_empty_for_unknown_user(self, test_db):
        result = await get_user_history("nobody", limit=100, offset=0, db=test_db)
        assert result == []


class TestGetModelHistory:
    async def test_returns_model_records(self, test_db, sample_model):
        await create_history(_make_history_data(sample_model.id), test_db)
        result = await get_model_history(sample_model.id, limit=100, offset=0, db=test_db)
        assert len(result) >= 1
        assert all(r.selected_model_id == sample_model.id for r in result)

    async def test_empty_for_unknown_model(self, test_db):
        result = await get_model_history(99999, limit=100, offset=0, db=test_db)
        assert result == []


class TestGetRecentHistory:
    async def test_returns_recent(self, test_db, sample_model):
        await create_history(_make_history_data(sample_model.id), test_db)
        result = await get_recent_history(limit=10, db=test_db)
        assert len(result) >= 1

    async def test_success_only_filter(self, test_db, sample_model):
        await create_history(
            _make_history_data(sample_model.id, success=True), test_db
        )
        await create_history(
            _make_history_data(sample_model.id, success=False), test_db
        )
        result = await get_recent_history(
            limit=100, success_only=True, db=test_db
        )
        assert all(r.success for r in result)


class TestGetPeriodStatistics:
    async def test_returns_stats(self, test_db, sample_model):
        await create_history(_make_history_data(sample_model.id), test_db)
        now = datetime.utcnow()
        result = await get_period_statistics(
            start_date=now - timedelta(hours=1),
            end_date=now + timedelta(hours=1),
            model_id=None,
            db=test_db,
        )
        assert result.total_requests >= 1
        assert result.success_rate >= 0.0

    async def test_empty_period(self, test_db):
        far_future = datetime(2099, 1, 1)
        result = await get_period_statistics(
            start_date=far_future,
            end_date=far_future + timedelta(hours=1),
            model_id=None,
            db=test_db,
        )
        assert result.total_requests == 0
