"""Тесты для DataAPIClient."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from decimal import Decimal

from app.infrastructure.http_clients.data_api_client import DataAPIClient


@pytest.fixture
def client():
    """Создать DataAPIClient для тестов."""
    return DataAPIClient(base_url="http://test-data:8001")


class TestDataAPIClient:
    """Тесты для DataAPIClient."""

    async def test_get_all_models(self, client):
        """get_all_models возвращает список AIModelInfo."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = [
            {
                "id": 1,
                "name": "Test Model",
                "provider": "TestProvider",
                "api_endpoint": "https://test.api",
                "reliability_score": 0.9,
                "is_active": True,
                "api_format": "openai",
                "effective_reliability_score": 0.85,
                "recent_request_count": 10,
                "decision_reason": "highest_score",
                "success_rate": 0.95,
                "average_response_time": 1.5,
                "request_count": 100,
                "available_at": None,
            }
        ]

        client.client.get = AsyncMock(return_value=mock_response)
        models = await client.get_all_models()
        assert len(models) == 1
        assert models[0].name == "Test Model"
        assert models[0].effective_reliability_score == 0.85
        assert models[0].recent_request_count == 10

    async def test_get_all_models_effective_score_none_fallback(self, client):
        """effective_reliability_score = None откатывается к reliability_score."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = [
            {
                "id": 1,
                "name": "Model",
                "provider": "Prov",
                "api_endpoint": "https://api",
                "reliability_score": 0.75,
                "is_active": True,
                "effective_reliability_score": None,
            }
        ]

        client.client.get = AsyncMock(return_value=mock_response)
        models = await client.get_all_models()
        assert models[0].effective_reliability_score == 0.75

    async def test_get_all_models_effective_score_zero_preserved(self, client):
        """effective_reliability_score = 0.0 сохраняется (не откатывается к fallback)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = [
            {
                "id": 1,
                "name": "Model",
                "provider": "Prov",
                "api_endpoint": "https://api",
                "reliability_score": 0.75,
                "is_active": True,
                "effective_reliability_score": 0.0,
            }
        ]

        client.client.get = AsyncMock(return_value=mock_response)
        models = await client.get_all_models()
        assert models[0].effective_reliability_score == 0.0

    async def test_get_model_by_id_found(self, client):
        """get_model_by_id возвращает AIModelInfo при успешном ответе."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "id": 1,
            "name": "Model",
            "provider": "Prov",
            "api_endpoint": "https://api",
            "reliability_score": 0.8,
            "is_active": True,
            "api_format": "openai",
        }

        client.client.get = AsyncMock(return_value=mock_response)
        model = await client.get_model_by_id(1)
        assert model is not None
        assert model.id == 1
        assert model.provider == "Prov"

    async def test_get_model_by_id_not_found(self, client):
        """get_model_by_id возвращает None при 404."""
        mock_response = MagicMock()
        mock_response.status_code = 404

        client.client.get = AsyncMock(return_value=mock_response)
        model = await client.get_model_by_id(999)
        assert model is None

    async def test_increment_success(self, client):
        """increment_success отправляет POST запрос."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        client.client.post = AsyncMock(return_value=mock_response)
        await client.increment_success(1, 1.5)
        client.client.post.assert_called_once()
        call_args = client.client.post.call_args
        assert "increment-success" in call_args[0][0]

    async def test_increment_failure(self, client):
        """increment_failure отправляет POST запрос."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        client.client.post = AsyncMock(return_value=mock_response)
        await client.increment_failure(1, 2.0)
        client.client.post.assert_called_once()
        call_args = client.client.post.call_args
        assert "increment-failure" in call_args[0][0]

    async def test_set_availability(self, client):
        """set_availability отправляет PATCH запрос с параметрами."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        client.client.patch = AsyncMock(return_value=mock_response)
        await client.set_availability(1, 3600, reason="rate_limit")
        client.client.patch.assert_called_once()
        call_args = client.client.patch.call_args
        assert "availability" in call_args[0][0]

    async def test_set_availability_with_all_params(self, client):
        """set_availability передаёт все опциональные параметры."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()

        client.client.patch = AsyncMock(return_value=mock_response)
        await client.set_availability(
            1, 3600,
            reason="rate_limit",
            error_type="RateLimitError",
            source="process_prompt",
        )
        client.client.patch.assert_called_once()
        call_kwargs = client.client.patch.call_args
        params = call_kwargs.kwargs.get("params") or call_kwargs[1].get("params")
        assert params["reason"] == "rate_limit"
        assert params["error_type"] == "RateLimitError"
        assert params["source"] == "process_prompt"

    async def test_create_history(self, client):
        """create_history возвращает ID созданной записи."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"id": 42}

        client.client.post = AsyncMock(return_value=mock_response)
        result = await client.create_history(
            user_id="u1",
            prompt_text="hello",
            selected_model_id=1,
            response_text="hi",
            response_time=Decimal("1.5"),
            success=True,
        )
        assert result == 42

    async def test_create_history_with_error(self, client):
        """create_history передаёт error_message в payload."""
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"id": 43}

        client.client.post = AsyncMock(return_value=mock_response)
        result = await client.create_history(
            user_id="u1",
            prompt_text="hello",
            selected_model_id=1,
            response_text=None,
            response_time=Decimal("2.0"),
            success=False,
            error_message="Provider timeout",
        )
        assert result == 43
        call_kwargs = client.client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        assert payload["error_message"] == "Provider timeout"
        assert payload["success"] is False

    async def test_close(self, client):
        """close() вызывает aclose() на внутреннем клиенте."""
        client.client.aclose = AsyncMock()
        await client.close()
        client.client.aclose.assert_called_once()

    def test_get_headers_content_type(self, client):
        """_get_headers всегда включает Content-Type."""
        headers = client._get_headers()
        assert headers["Content-Type"] == "application/json"

    def test_get_headers_with_request_id(self):
        """_get_headers включает X-Request-ID если указан request_id."""
        c = DataAPIClient(base_url="http://test", request_id="req-123")
        headers = c._get_headers()
        assert "X-Request-ID" in headers

    def test_base_url_trailing_slash_stripped(self):
        """Trailing slash в base_url обрезается."""
        c = DataAPIClient(base_url="http://test-data:8001/")
        assert c.base_url == "http://test-data:8001"
