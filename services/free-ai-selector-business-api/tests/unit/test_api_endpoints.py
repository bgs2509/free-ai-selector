"""Тесты для API endpoints Business API."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.domain.models import AIModelInfo


@pytest.fixture
async def async_client():
    """Асинхронный HTTP клиент для тестов."""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


@pytest.fixture
def mock_models():
    """Тестовые модели для API тестов."""
    return [
        AIModelInfo(
            id=1,
            name="Test Model",
            provider="TestProv",
            api_endpoint="https://api.test",
            reliability_score=0.9,
            is_active=True,
            effective_reliability_score=0.9,
            recent_request_count=10,
            decision_reason="highest",
            success_rate=0.95,
            average_response_time=1.0,
            request_count=50,
        ),
    ]


class TestModelsStats:
    """Тесты для GET /api/v1/models/stats."""

    async def test_get_stats_success(self, async_client, mock_models):
        """Успешное получение статистики моделей."""
        with patch(
            "app.api.v1.models.DataAPIClient"
        ) as MockClient:
            instance = AsyncMock()
            instance.get_all_models = AsyncMock(return_value=mock_models)
            instance.close = AsyncMock()
            MockClient.return_value = instance

            response = await async_client.get("/api/v1/models/stats")

        assert response.status_code == 200
        data = response.json()
        assert "models" in data
        assert data["total_models"] == 1
        assert data["models"][0]["name"] == "Test Model"
        assert data["models"][0]["reliability_score"] == 0.9

    async def test_get_stats_empty(self, async_client):
        """Статистика при пустом списке моделей."""
        with patch(
            "app.api.v1.models.DataAPIClient"
        ) as MockClient:
            instance = AsyncMock()
            instance.get_all_models = AsyncMock(return_value=[])
            instance.close = AsyncMock()
            MockClient.return_value = instance

            response = await async_client.get("/api/v1/models/stats")

        assert response.status_code == 200
        data = response.json()
        assert data["total_models"] == 0
        assert data["models"] == []

    async def test_get_stats_data_api_error(self, async_client):
        """Ошибка Data API возвращает 500."""
        with patch(
            "app.api.v1.models.DataAPIClient"
        ) as MockClient:
            instance = AsyncMock()
            instance.get_all_models = AsyncMock(side_effect=Exception("API down"))
            instance.close = AsyncMock()
            MockClient.return_value = instance

            response = await async_client.get("/api/v1/models/stats")

        assert response.status_code == 500


class TestProvidersTest:
    """Тесты для POST /api/v1/providers/test."""

    async def test_test_providers_success(self, async_client):
        """Успешное тестирование провайдеров."""
        with patch(
            "app.api.v1.providers.DataAPIClient"
        ) as MockClient:
            instance = AsyncMock()
            instance.close = AsyncMock()
            MockClient.return_value = instance

            with patch(
                "app.api.v1.providers.TestAllProvidersUseCase"
            ) as MockUC:
                uc_instance = AsyncMock()
                uc_instance.execute = AsyncMock(return_value=[
                    {
                        "provider": "Test",
                        "model": "M1",
                        "status": "success",
                        "response_time": 1.0,
                        "error": None,
                    }
                ])
                MockUC.return_value = uc_instance

                response = await async_client.post("/api/v1/providers/test")

        assert response.status_code == 200
        data = response.json()
        assert data["successful"] == 1
        assert data["failed"] == 0
        assert data["total_providers"] == 1

    async def test_test_providers_mixed_results(self, async_client):
        """Тестирование с успешными и неуспешными провайдерами."""
        with patch(
            "app.api.v1.providers.DataAPIClient"
        ) as MockClient:
            instance = AsyncMock()
            instance.close = AsyncMock()
            MockClient.return_value = instance

            with patch(
                "app.api.v1.providers.TestAllProvidersUseCase"
            ) as MockUC:
                uc_instance = AsyncMock()
                uc_instance.execute = AsyncMock(return_value=[
                    {
                        "provider": "Good",
                        "model": "M1",
                        "status": "success",
                        "response_time": 0.5,
                        "error": None,
                    },
                    {
                        "provider": "Bad",
                        "model": "M2",
                        "status": "error",
                        "response_time": None,
                        "error": "Timeout",
                    },
                ])
                MockUC.return_value = uc_instance

                response = await async_client.post("/api/v1/providers/test")

        assert response.status_code == 200
        data = response.json()
        assert data["successful"] == 1
        assert data["failed"] == 1
        assert data["total_providers"] == 2

    async def test_test_providers_error(self, async_client):
        """Катастрофическая ошибка при тестировании возвращает 500."""
        with patch(
            "app.api.v1.providers.DataAPIClient"
        ) as MockClient:
            instance = AsyncMock()
            instance.close = AsyncMock()
            MockClient.return_value = instance

            with patch(
                "app.api.v1.providers.TestAllProvidersUseCase"
            ) as MockUC:
                uc_instance = AsyncMock()
                uc_instance.execute = AsyncMock(side_effect=Exception("fail"))
                MockUC.return_value = uc_instance

                response = await async_client.post("/api/v1/providers/test")

        assert response.status_code == 500


class TestProcessPrompt:
    """Тесты для POST /api/v1/prompts/process."""

    async def test_process_success(self, async_client):
        """Успешная обработка промпта."""
        mock_response = MagicMock()
        mock_response.prompt_text = "hello"
        mock_response.response_text = "hi"
        mock_response.selected_model_name = "Model"
        mock_response.selected_model_provider = "Prov"
        mock_response.response_time = 1.5
        mock_response.success = True
        mock_response.attempts = 1
        mock_response.fallback_used = False

        with patch("app.api.v1.prompts.DataAPIClient") as MockClient:
            instance = AsyncMock()
            instance.close = AsyncMock()
            MockClient.return_value = instance

            with patch("app.api.v1.prompts.ProcessPromptUseCase") as MockUC:
                uc_instance = AsyncMock()
                uc_instance.execute = AsyncMock(return_value=mock_response)
                MockUC.return_value = uc_instance

                response = await async_client.post(
                    "/api/v1/prompts/process",
                    json={"prompt": "hello"},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["response"] == "hi"
        assert data["selected_model"] == "Model"
        assert data["provider"] == "Prov"
        assert data["attempts"] == 1
        assert data["fallback_used"] is False

    async def test_process_with_model_id(self, async_client):
        """Обработка промпта с указанием model_id."""
        mock_response = MagicMock()
        mock_response.prompt_text = "hello"
        mock_response.response_text = "forced response"
        mock_response.selected_model_name = "Forced Model"
        mock_response.selected_model_provider = "ForcedProv"
        mock_response.response_time = 0.8
        mock_response.success = True
        mock_response.attempts = 1
        mock_response.fallback_used = False

        with patch("app.api.v1.prompts.DataAPIClient") as MockClient:
            instance = AsyncMock()
            instance.close = AsyncMock()
            MockClient.return_value = instance

            with patch("app.api.v1.prompts.ProcessPromptUseCase") as MockUC:
                uc_instance = AsyncMock()
                uc_instance.execute = AsyncMock(return_value=mock_response)
                MockUC.return_value = uc_instance

                response = await async_client.post(
                    "/api/v1/prompts/process",
                    json={"prompt": "hello", "model_id": 1},
                )

        assert response.status_code == 200

    async def test_process_all_rate_limited(self, async_client):
        """Все провайдеры rate-limited возвращает 429."""
        from app.domain.exceptions import AllProvidersRateLimited

        with patch("app.api.v1.prompts.DataAPIClient") as MockClient:
            instance = AsyncMock()
            instance.close = AsyncMock()
            MockClient.return_value = instance

            with patch("app.api.v1.prompts.ProcessPromptUseCase") as MockUC:
                uc_instance = AsyncMock()
                uc_instance.execute = AsyncMock(
                    side_effect=AllProvidersRateLimited(
                        retry_after_seconds=60,
                        attempts=3,
                        providers_tried=3,
                    )
                )
                MockUC.return_value = uc_instance

                response = await async_client.post(
                    "/api/v1/prompts/process",
                    json={"prompt": "hello"},
                )

        assert response.status_code == 429
        data = response.json()
        assert data["error"] == "all_rate_limited"
        assert "Retry-After" in response.headers

    async def test_process_service_unavailable(self, async_client):
        """Сервис недоступен возвращает 503."""
        from app.domain.exceptions import ServiceUnavailable

        with patch("app.api.v1.prompts.DataAPIClient") as MockClient:
            instance = AsyncMock()
            instance.close = AsyncMock()
            MockClient.return_value = instance

            with patch("app.api.v1.prompts.ProcessPromptUseCase") as MockUC:
                uc_instance = AsyncMock()
                uc_instance.execute = AsyncMock(
                    side_effect=ServiceUnavailable(reason="no_models")
                )
                MockUC.return_value = uc_instance

                response = await async_client.post(
                    "/api/v1/prompts/process",
                    json={"prompt": "hello"},
                )

        assert response.status_code == 503
        data = response.json()
        assert data["error"] == "service_unavailable"
        assert "Retry-After" in response.headers

    async def test_process_internal_error(self, async_client):
        """Внутренняя ошибка возвращает 500."""
        with patch("app.api.v1.prompts.DataAPIClient") as MockClient:
            instance = AsyncMock()
            instance.close = AsyncMock()
            MockClient.return_value = instance

            with patch("app.api.v1.prompts.ProcessPromptUseCase") as MockUC:
                uc_instance = AsyncMock()
                uc_instance.execute = AsyncMock(side_effect=RuntimeError("boom"))
                MockUC.return_value = uc_instance

                response = await async_client.post(
                    "/api/v1/prompts/process",
                    json={"prompt": "hello"},
                )

        assert response.status_code == 500

    async def test_process_empty_prompt_rejected(self, async_client):
        """Пустой промпт отклоняется валидацией (422)."""
        response = await async_client.post(
            "/api/v1/prompts/process",
            json={"prompt": ""},
        )
        assert response.status_code == 422

    async def test_process_missing_prompt_rejected(self, async_client):
        """Отсутствие поля prompt отклоняется валидацией (422)."""
        response = await async_client.post(
            "/api/v1/prompts/process",
            json={},
        )
        assert response.status_code == 422

    async def test_process_invalid_response_format_rejected(self, async_client):
        """Невалидный response_format отклоняется валидацией (422)."""
        response = await async_client.post(
            "/api/v1/prompts/process",
            json={
                "prompt": "hello",
                "response_format": {"type": "invalid_type"},
            },
        )
        assert response.status_code == 422
