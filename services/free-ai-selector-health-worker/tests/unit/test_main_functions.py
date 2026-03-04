"""Тесты для вспомогательных функций app/main.py."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import (
    PROVIDER_ENV_VARS,
    API_FORMAT_CHECKERS,
    run_health_checks,
)


class TestProviderEnvVars:
    def test_all_12_providers(self):
        assert len(PROVIDER_ENV_VARS) == 12

    def test_groq_env_var(self):
        assert PROVIDER_ENV_VARS["Groq"] == "GROQ_API_KEY"

    def test_cloudflare_env_var(self):
        assert PROVIDER_ENV_VARS["Cloudflare"] == "CLOUDFLARE_API_TOKEN"

    def test_github_env_var(self):
        assert PROVIDER_ENV_VARS["GitHubModels"] == "GITHUB_TOKEN"


class TestApiFormatCheckers:
    def test_three_formats(self):
        assert len(API_FORMAT_CHECKERS) == 3

    def test_has_openai(self):
        assert "openai" in API_FORMAT_CHECKERS

    def test_has_huggingface(self):
        assert "huggingface" in API_FORMAT_CHECKERS

    def test_has_cloudflare(self):
        assert "cloudflare" in API_FORMAT_CHECKERS


class TestRunHealthChecks:
    async def test_fetches_and_checks_models(self):
        """Тест основного цикла: fetch моделей + проверка + обновление."""
        mock_models_response = MagicMock()
        mock_models_response.status_code = 200
        mock_models_response.raise_for_status = MagicMock()
        mock_models_response.json.return_value = [
            {
                "id": 1,
                "name": "Test Model",
                "provider": "Groq",
                "api_endpoint": "https://api.groq.com/v1/chat",
                "api_format": "openai",
            }
        ]

        mock_update_response = MagicMock()
        mock_update_response.status_code = 200
        mock_update_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_models_response)
        mock_client.post = AsyncMock(return_value=mock_update_response)

        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            patch(
                "app.main.universal_health_check",
                new_callable=AsyncMock,
                return_value=(True, 1.5),
            ),
            patch("app.main.audit_event"),
        ):
            await run_health_checks()

    async def test_handles_fetch_error(self):
        """Тест обработки ошибки при получении моделей."""
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))

        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            patch("app.main.audit_event"),
        ):
            # Не должно бросить исключение
            await run_health_checks()

    async def test_skips_unconfigured_providers(self):
        """Провайдеры без API ключей пропускаются."""
        mock_models_response = MagicMock()
        mock_models_response.status_code = 200
        mock_models_response.raise_for_status = MagicMock()
        mock_models_response.json.return_value = [
            {
                "id": 1,
                "name": "Test Model",
                "provider": "Groq",
                "api_endpoint": "https://api.groq.com/v1/chat",
                "api_format": "openai",
            }
        ]

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_models_response)

        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            patch(
                "app.main.universal_health_check",
                new_callable=AsyncMock,
                return_value=(False, 0.0),  # no api key
            ),
            patch("app.main.audit_event"),
        ):
            await run_health_checks()

    async def test_handles_unhealthy_model(self):
        """Тест обработки unhealthy модели."""
        mock_models_response = MagicMock()
        mock_models_response.status_code = 200
        mock_models_response.raise_for_status = MagicMock()
        mock_models_response.json.return_value = [
            {
                "id": 1,
                "name": "Failing Model",
                "provider": "Groq",
                "api_endpoint": "https://api.groq.com/v1/chat",
                "api_format": "openai",
            }
        ]

        mock_update_response = MagicMock()
        mock_update_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(return_value=mock_models_response)
        mock_client.post = AsyncMock(return_value=mock_update_response)

        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            patch(
                "app.main.universal_health_check",
                new_callable=AsyncMock,
                return_value=(False, 2.0),  # unhealthy but responded
            ),
            patch("app.main.audit_event"),
        ):
            await run_health_checks()
