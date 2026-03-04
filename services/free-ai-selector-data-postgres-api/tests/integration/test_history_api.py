"""Интеграционные тесты для app/api/v1/history.py."""
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.infrastructure.database.models import AIModelORM, PromptHistoryORM


@pytest.fixture
async def app_with_db(test_db):
    """FastAPI app с подменённой БД."""
    from app.main import app
    from app.infrastructure.database.connection import get_db

    async def override_get_db():
        yield test_db

    app.dependency_overrides[get_db] = override_get_db
    yield app
    app.dependency_overrides.clear()


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


class TestHistoryAPI:
    async def test_create_history(self, app_with_db, sample_model):
        async with AsyncClient(
            transport=ASGITransport(app=app_with_db),
            base_url="http://test",
        ) as client:
            response = await client.post(
                "/api/v1/history",
                json={
                    "user_id": "test-user",
                    "prompt_text": "Hello AI",
                    "selected_model_id": sample_model.id,
                    "response_text": "Hello human",
                    "response_time": "1.5",
                    "success": True,
                },
            )
        assert response.status_code == 201
        data = response.json()
        assert data["user_id"] == "test-user"
        assert data["success"] is True

    async def test_get_by_id(self, app_with_db, test_db, sample_model):
        # Создать запись напрямую
        history = PromptHistoryORM(
            user_id="u1",
            prompt_text="test",
            selected_model_id=sample_model.id,
            response_text="resp",
            response_time=Decimal("1.0"),
            success=True,
        )
        test_db.add(history)
        await test_db.flush()

        async with AsyncClient(
            transport=ASGITransport(app=app_with_db),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/v1/history/{history.id}")
        assert response.status_code == 200
        assert response.json()["id"] == history.id

    async def test_get_by_id_not_found(self, app_with_db):
        async with AsyncClient(
            transport=ASGITransport(app=app_with_db),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/history/99999")
        assert response.status_code == 404

    async def test_get_user_history(self, app_with_db, test_db, sample_model):
        for i in range(3):
            test_db.add(PromptHistoryORM(
                user_id="user-42",
                prompt_text=f"prompt-{i}",
                selected_model_id=sample_model.id,
                response_time=Decimal("1.0"),
                success=True,
            ))
        await test_db.flush()

        async with AsyncClient(
            transport=ASGITransport(app=app_with_db),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/history/user/user-42")
        assert response.status_code == 200
        assert len(response.json()) == 3

    async def test_get_model_history(self, app_with_db, test_db, sample_model):
        test_db.add(PromptHistoryORM(
            user_id="u1",
            prompt_text="p1",
            selected_model_id=sample_model.id,
            response_time=Decimal("1.0"),
            success=True,
        ))
        await test_db.flush()

        async with AsyncClient(
            transport=ASGITransport(app=app_with_db),
            base_url="http://test",
        ) as client:
            response = await client.get(f"/api/v1/history/model/{sample_model.id}")
        assert response.status_code == 200
        assert len(response.json()) >= 1

    async def test_get_recent_history(self, app_with_db, test_db, sample_model):
        test_db.add(PromptHistoryORM(
            user_id="u1",
            prompt_text="p1",
            selected_model_id=sample_model.id,
            response_time=Decimal("1.0"),
            success=True,
        ))
        await test_db.flush()

        async with AsyncClient(
            transport=ASGITransport(app=app_with_db),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/history", params={"limit": 10})
        assert response.status_code == 200

    async def test_get_statistics_period(self, app_with_db, test_db, sample_model):
        now = datetime.utcnow()
        test_db.add(PromptHistoryORM(
            user_id="u1",
            prompt_text="p1",
            selected_model_id=sample_model.id,
            response_time=Decimal("2.0"),
            success=True,
            created_at=now,
        ))
        await test_db.flush()

        async with AsyncClient(
            transport=ASGITransport(app=app_with_db),
            base_url="http://test",
        ) as client:
            response = await client.get(
                "/api/v1/history/statistics/period",
                params={
                    "start_date": (now - timedelta(hours=1)).isoformat(),
                    "end_date": (now + timedelta(hours=1)).isoformat(),
                },
            )
        assert response.status_code == 200
        data = response.json()
        assert "total_requests" in data
