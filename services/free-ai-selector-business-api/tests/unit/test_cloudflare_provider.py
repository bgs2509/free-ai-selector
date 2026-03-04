"""Тесты для CloudflareProvider."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.infrastructure.ai_providers.cloudflare import CloudflareProvider


class TestCloudflareProvider:
    """Тесты для CloudflareProvider."""

    def test_get_provider_name(self):
        """Имя провайдера возвращается корректно."""
        provider = CloudflareProvider(api_token="test", account_id="acc")
        assert provider.get_provider_name() == "Cloudflare"

    def test_init_defaults(self):
        """Инициализация с явными параметрами."""
        provider = CloudflareProvider(api_token="tok", account_id="acc", model="custom-model")
        assert provider.api_token == "tok"
        assert provider.account_id == "acc"
        assert provider.model == "custom-model"

    def test_init_default_model(self):
        """Модель по умолчанию устанавливается при отсутствии параметра."""
        provider = CloudflareProvider(api_token="tok", account_id="acc")
        assert "llama" in provider.model.lower() or "cf/" in provider.model

    def test_supports_response_format(self):
        """Cloudflare поддерживает response_format."""
        provider = CloudflareProvider(api_token="tok", account_id="acc")
        assert provider._supports_response_format() is True

    async def test_missing_api_token_generate(self):
        """generate() без API token вызывает ошибку (HTTP 404)."""
        provider = CloudflareProvider(api_token="", account_id="acc")
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.is_success = False
        mock_response.has_redirect_location = False
        mock_response.reason_phrase = "Not Found"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_response.raise_for_status = MagicMock(
            side_effect=Exception("HTTP error")
        )

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(Exception):
                await provider.generate("test")

    async def test_missing_account_id_generate(self):
        """generate() без account ID вызывает ошибку (HTTP 401)."""
        provider = CloudflareProvider(api_token="token", account_id="")
        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.is_success = False
        mock_response.has_redirect_location = False
        mock_response.reason_phrase = "Unauthorized"

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_response.raise_for_status = MagicMock(
            side_effect=Exception("HTTP error")
        )

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(Exception):
                await provider.generate("test")

    async def test_successful_response_format(self):
        """Успешный ответ в формате result.response."""
        provider = CloudflareProvider(api_token="test-token", account_id="test-acc")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": {"response": "Hello from Cloudflare"}
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.generate("Hello")
        assert result == "Hello from Cloudflare"

    async def test_successful_choices_format(self):
        """Успешный ответ в формате result.choices (OpenAI-compatible)."""
        provider = CloudflareProvider(api_token="test-token", account_id="test-acc")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": {
                "choices": [{"message": {"content": "Response via choices"}}]
            }
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.generate("Hello")
        assert result == "Response via choices"

    async def test_list_response_joined(self):
        """Ответ-список в result.response соединяется через пробел."""
        provider = CloudflareProvider(api_token="test-token", account_id="test-acc")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": {"response": ["Hello", "world"]}
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.generate("Hello")
        assert result == "Hello world"

    async def test_invalid_response_format_raises(self):
        """Ответ без result.response и result.choices вызывает ValueError."""
        provider = CloudflareProvider(api_token="test-token", account_id="test-acc")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"result": {"something_else": True}}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(ValueError, match="Invalid response format"):
                await provider.generate("Hello")

    async def test_generate_with_system_prompt(self):
        """generate() с system_prompt включает system message в payload."""
        provider = CloudflareProvider(api_token="test-token", account_id="test-acc")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "result": {"response": "OK"}
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.generate("Hello", system_prompt="Be helpful")

        assert result == "OK"
        # Проверяем что system_prompt был включён в payload
        call_kwargs = mock_client.post.call_args
        payload = call_kwargs.kwargs.get("json") or call_kwargs[1].get("json")
        messages = payload["messages"]
        assert messages[0]["role"] == "system"
        assert messages[0]["content"] == "Be helpful"

    async def test_health_check_no_token(self):
        """health_check() без API token возвращает False."""
        provider = CloudflareProvider(api_token="", account_id="acc")
        result = await provider.health_check()
        assert result is False

    async def test_health_check_no_account(self):
        """health_check() без account ID возвращает False."""
        provider = CloudflareProvider(api_token="tok", account_id="")
        result = await provider.health_check()
        assert result is False

    async def test_health_check_success(self):
        """health_check() при успешном ответе API возвращает True."""
        provider = CloudflareProvider(api_token="tok", account_id="acc")
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.health_check()
        assert result is True

    async def test_health_check_non_200(self):
        """health_check() при статусе != 200 возвращает False."""
        provider = CloudflareProvider(api_token="tok", account_id="acc")
        mock_response = MagicMock()
        mock_response.status_code = 403

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.health_check()
        assert result is False

    async def test_health_check_exception(self):
        """health_check() при сетевой ошибке возвращает False."""
        provider = CloudflareProvider(api_token="tok", account_id="acc")
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=Exception("Network error"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await provider.health_check()
        assert result is False
