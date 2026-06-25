"""Тесты для DataAPIClient."""

import pytest
from unittest.mock import AsyncMock, MagicMock
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
            1,
            3600,
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


@pytest.mark.unit
class TestV2RankingContract:
    """bmm/ADR-0003: business-api consumes v2 effective scores + new decision_reason
    via the unchanged /models contract, and the sort ranks healthy > broken."""

    async def test_v2_effective_scores_rank_healthy_above_broken(self, client):
        # Representative v2 effective scores produced by data-api rating_v2 for the
        # live model set (Ollama/OpenRouter healthy, SambaNova broken-but-fast).
        rows = [
            ("SambaNova", 0.020, 0.39),
            ("Groq", 0.195, 0.5),
            ("Fireworks", 0.584, 9.9),
            ("OpenRouter", 0.702, 12.1),
            ("Ollama", 0.828, 7.6),
        ]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = [
            {
                "id": i,
                "name": name,
                "provider": name,
                "api_endpoint": "https://test.api",
                "reliability_score": 0.5,
                "is_active": True,
                "api_format": "openai",
                "effective_reliability_score": eff,
                "recent_request_count": 100,
                "decision_reason": "laplace_ucb",  # new v2 value flows through unchanged
                "success_rate": 0.5,
                "average_response_time": lat,
                "request_count": 100,
                "available_at": None,
            }
            for i, (name, eff, lat) in enumerate(rows, start=1)
        ]
        client.client.get = AsyncMock(return_value=mock_response)

        models = await client.get_all_models()
        # Apply the business-api selection sort key (process_prompt.py Step 3).
        ranked = sorted(
            models,
            key=lambda m: (m.effective_reliability_score, -m.average_response_time),
            reverse=True,
        )
        assert [m.name for m in ranked] == [
            "Ollama",
            "OpenRouter",
            "Fireworks",
            "Groq",
            "SambaNova",
        ]
        # New decision_reason mapped through the unchanged contract (not "fallback").
        assert all(m.decision_reason == "laplace_ucb" for m in models)

    def test_base_url_trailing_slash_stripped(self):
        """Trailing slash в base_url обрезается."""
        c = DataAPIClient(base_url="http://test-data:8001/")
        assert c.base_url == "http://test-data:8001"


class TestDataAPIClientCallerAnalytics:
    """fm6: caller fields in create_history + journal/analytics GET helpers."""

    @pytest.fixture
    def client(self):
        return DataAPIClient(base_url="http://test-data:8001")

    async def test_create_history_sends_caller_fields(self, client):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"id": 50}
        client.client.post = AsyncMock(return_value=mock_response)

        result = await client.create_history(
            user_id="api_user",
            prompt_text="hello",
            selected_model_id=1,
            response_text=None,
            response_time=Decimal("2.0"),
            success=False,
            error_message="503",
            caller="sensedar",
            http_status=503,
            requested_model="gpt-x",
        )

        assert result == 50
        payload = client.client.post.call_args.kwargs["json"]
        assert payload["caller"] == "sensedar"
        assert payload["http_status"] == 503
        assert payload["requested_model"] == "gpt-x"

    async def test_get_caller_statistics(self, client):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = [{"caller": "taro", "request_count": 3}]
        client.client.get = AsyncMock(return_value=mock_response)

        result = await client.get_caller_statistics(window_days=30)

        assert result[0]["caller"] == "taro"
        assert client.client.get.call_args.kwargs["params"]["window_days"] == 30

    async def test_get_history_builds_filter_params(self, client):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = [{"id": 1}]
        client.client.get = AsyncMock(return_value=mock_response)

        await client.get_history(caller="sensedar", success=True, limit=5, offset=2)

        params = client.client.get.call_args.kwargs["params"]
        assert params["caller"] == "sensedar"
        assert params["success"] is True
        assert params["limit"] == 5
        assert params["offset"] == 2

    async def test_get_history_by_id_found(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"id": 7, "caller": "taro"}
        client.client.get = AsyncMock(return_value=mock_response)

        result = await client.get_history_by_id(7)
        assert result["caller"] == "taro"

    async def test_get_history_by_id_returns_none_on_404(self, client):
        mock_response = MagicMock()
        mock_response.status_code = 404
        client.client.get = AsyncMock(return_value=mock_response)

        result = await client.get_history_by_id(999)
        assert result is None
