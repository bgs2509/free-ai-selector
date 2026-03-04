"""Тесты для HTTP-функций Telegram Bot."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import httpx


class TestCallBusinessApi:
    async def test_success(self):
        from app.main import call_business_api

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "response": "AI response",
            "selected_model": "Model",
            "provider": "Prov",
            "response_time_seconds": 1.0,
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await call_business_api("Hello")

        assert result is not None
        assert result["response"] == "AI response"

    async def test_http_error(self):
        from app.main import call_business_api

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=httpx.HTTPError("500"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await call_business_api("Hello")

        assert result is None

    async def test_timeout(self):
        from app.main import call_business_api

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=httpx.ReadTimeout("timeout"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await call_business_api("Hello")

        assert result is None


class TestGetModelsStats:
    async def test_success(self):
        from app.main import get_models_stats

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"models": [], "total_models": 0}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await get_models_stats()

        assert result is not None

    async def test_error(self):
        from app.main import get_models_stats

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=httpx.HTTPError("err"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await get_models_stats()

        assert result is None


class TestTestAllProviders:
    async def test_success(self):
        from app.main import test_all_providers

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"results": [], "total_providers": 0}

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await test_all_providers()

        assert result is not None

    async def test_error(self):
        from app.main import test_all_providers

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=httpx.HTTPError("err"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            result = await test_all_providers()

        assert result is None
