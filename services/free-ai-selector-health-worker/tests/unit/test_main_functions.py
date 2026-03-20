"""Тесты для run_health_checks — делегирование в Business API."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import run_health_checks


class TestRunHealthChecks:
    async def test_delegates_to_business_api(self):
        """Тест: health worker вызывает POST /providers/test в business-api."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "total_providers": 2,
            "successful": 1,
            "failed": 1,
            "results": [
                {
                    "provider": "Groq",
                    "model": "llama-3.3-70b",
                    "status": "success",
                    "response_time": 1.5,
                    "error": None,
                },
                {
                    "provider": "Cerebras",
                    "model": "llama-3.3-70b",
                    "status": "error",
                    "response_time": None,
                    "error": "HTTPError: 401 Unauthorized",
                },
            ],
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            patch("app.main.audit_event"),
        ):
            await run_health_checks()

        # Проверяем, что вызван POST /providers/test
        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "/providers/test" in call_args[0][0]

    async def test_handles_business_api_error(self):
        """Тест: обработка ошибки при вызове business-api."""
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=Exception("Connection refused"))

        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            patch("app.main.audit_event"),
        ):
            # Не должно бросить исключение
            await run_health_checks()

    async def test_handles_all_healthy(self):
        """Тест: все провайдеры здоровы."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "total_providers": 2,
            "successful": 2,
            "failed": 0,
            "results": [
                {
                    "provider": "Groq",
                    "model": "llama-3.3-70b",
                    "status": "success",
                    "response_time": 1.2,
                    "error": None,
                },
                {
                    "provider": "Cerebras",
                    "model": "llama-3.3-70b",
                    "status": "success",
                    "response_time": 0.8,
                    "error": None,
                },
            ],
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            patch("app.main.audit_event"),
        ):
            await run_health_checks()

    async def test_handles_all_unhealthy(self):
        """Тест: все провайдеры нездоровы."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "total_providers": 1,
            "successful": 0,
            "failed": 1,
            "results": [
                {
                    "provider": "Groq",
                    "model": "llama-3.3-70b",
                    "status": "error",
                    "response_time": None,
                    "error": "HTTPError: 500",
                },
            ],
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            patch("app.main.audit_event"),
        ):
            await run_health_checks()

    async def test_handles_empty_results(self):
        """Тест: пустой список результатов."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "total_providers": 0,
            "successful": 0,
            "failed": 0,
            "results": [],
        }

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            patch("app.main.audit_event"),
        ):
            await run_health_checks()

    async def test_handles_http_error_status(self):
        """Тест: business-api возвращает HTTP 500."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status = MagicMock(
            side_effect=Exception("500 Internal Server Error")
        )

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            patch("app.main.audit_event"),
        ):
            # Не должно бросить исключение — ловится внутри
            await run_health_checks()
