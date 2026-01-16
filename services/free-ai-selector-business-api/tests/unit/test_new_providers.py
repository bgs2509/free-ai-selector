"""
Unit-тесты для новых AI провайдеров (F003)

Тестирование 9 новых провайдеров:
- Фаза 1: DeepSeek, OpenRouter, GitHub Models
- Фаза 2: Fireworks, Hyperbolic, Novita, Scaleway
- Фаза 3: Kluster, Nebius
"""

from unittest.mock import AsyncMock, patch, MagicMock

import httpx
import pytest


# ═══════════════════════════════════════════════════════════════════════════
# Фаза 1: Приоритетные провайдеры
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.unit
class TestDeepSeekProvider:
    """Тесты для DeepSeek провайдера."""

    def test_init_defaults(self):
        """Тест инициализации с параметрами по умолчанию."""
        from app.infrastructure.ai_providers.deepseek import DeepSeekProvider

        provider = DeepSeekProvider()
        assert provider.model == "deepseek-chat"
        assert provider.api_url == "https://api.deepseek.com/v1/chat/completions"
        assert provider.timeout == 30.0

    def test_init_custom_params(self):
        """Тест инициализации с кастомными параметрами."""
        from app.infrastructure.ai_providers.deepseek import DeepSeekProvider

        provider = DeepSeekProvider(api_key="test-key", model="deepseek-coder")
        assert provider.api_key == "test-key"
        assert provider.model == "deepseek-coder"

    def test_get_provider_name(self):
        """Тест получения имени провайдера."""
        from app.infrastructure.ai_providers.deepseek import DeepSeekProvider

        provider = DeepSeekProvider()
        assert provider.get_provider_name() == "DeepSeek"

    @pytest.mark.asyncio
    async def test_generate_without_api_key(self):
        """Тест генерации без API ключа."""
        from app.infrastructure.ai_providers.deepseek import DeepSeekProvider

        provider = DeepSeekProvider(api_key="")
        with pytest.raises(ValueError, match="API ключ обязателен"):
            await provider.generate("test prompt")

    @pytest.mark.asyncio
    async def test_health_check_without_api_key(self):
        """Тест health check без API ключа."""
        from app.infrastructure.ai_providers.deepseek import DeepSeekProvider

        provider = DeepSeekProvider(api_key="")
        result = await provider.health_check()
        assert result is False

    @pytest.mark.asyncio
    async def test_generate_success(self):
        """Тест успешной генерации."""
        from app.infrastructure.ai_providers.deepseek import DeepSeekProvider

        provider = DeepSeekProvider(api_key="test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Тестовый ответ"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )
            result = await provider.generate("Тестовый промпт")
            assert result == "Тестовый ответ"


@pytest.mark.unit
class TestOpenRouterProvider:
    """Тесты для OpenRouter провайдера."""

    def test_init_defaults(self):
        """Тест инициализации с параметрами по умолчанию."""
        from app.infrastructure.ai_providers.openrouter import OpenRouterProvider

        provider = OpenRouterProvider()
        assert provider.model == "deepseek/deepseek-r1:free"
        assert provider.api_url == "https://openrouter.ai/api/v1/chat/completions"

    def test_get_provider_name(self):
        """Тест получения имени провайдера."""
        from app.infrastructure.ai_providers.openrouter import OpenRouterProvider

        provider = OpenRouterProvider()
        assert provider.get_provider_name() == "OpenRouter"

    @pytest.mark.asyncio
    async def test_generate_without_api_key(self):
        """Тест генерации без API ключа."""
        from app.infrastructure.ai_providers.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(api_key="")
        with pytest.raises(ValueError, match="API ключ обязателен"):
            await provider.generate("test prompt")


@pytest.mark.unit
class TestGitHubModelsProvider:
    """Тесты для GitHub Models провайдера."""

    def test_init_defaults(self):
        """Тест инициализации с параметрами по умолчанию."""
        from app.infrastructure.ai_providers.github_models import GitHubModelsProvider

        provider = GitHubModelsProvider()
        assert provider.model == "gpt-4o-mini"
        assert provider.api_url == "https://models.inference.ai.azure.com/chat/completions"

    def test_get_provider_name(self):
        """Тест получения имени провайдера."""
        from app.infrastructure.ai_providers.github_models import GitHubModelsProvider

        provider = GitHubModelsProvider()
        assert provider.get_provider_name() == "GitHubModels"

    @pytest.mark.asyncio
    async def test_generate_without_api_key(self):
        """Тест генерации без API ключа."""
        from app.infrastructure.ai_providers.github_models import GitHubModelsProvider

        provider = GitHubModelsProvider(api_key="")
        with pytest.raises(ValueError, match="Token обязателен"):
            await provider.generate("test prompt")


# ═══════════════════════════════════════════════════════════════════════════
# Фаза 2: Дополнительные провайдеры
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.unit
class TestFireworksProvider:
    """Тесты для Fireworks провайдера."""

    def test_init_defaults(self):
        """Тест инициализации с параметрами по умолчанию."""
        from app.infrastructure.ai_providers.fireworks import FireworksProvider

        provider = FireworksProvider()
        assert "llama" in provider.model.lower()
        assert provider.api_url == "https://api.fireworks.ai/inference/v1/chat/completions"

    def test_get_provider_name(self):
        """Тест получения имени провайдера."""
        from app.infrastructure.ai_providers.fireworks import FireworksProvider

        provider = FireworksProvider()
        assert provider.get_provider_name() == "Fireworks"

    @pytest.mark.asyncio
    async def test_generate_without_api_key(self):
        """Тест генерации без API ключа."""
        from app.infrastructure.ai_providers.fireworks import FireworksProvider

        provider = FireworksProvider(api_key="")
        with pytest.raises(ValueError, match="API ключ обязателен"):
            await provider.generate("test prompt")


@pytest.mark.unit
class TestHyperbolicProvider:
    """Тесты для Hyperbolic провайдера."""

    def test_init_defaults(self):
        """Тест инициализации с параметрами по умолчанию."""
        from app.infrastructure.ai_providers.hyperbolic import HyperbolicProvider

        provider = HyperbolicProvider()
        assert "llama" in provider.model.lower()
        assert provider.api_url == "https://api.hyperbolic.xyz/v1/chat/completions"

    def test_get_provider_name(self):
        """Тест получения имени провайдера."""
        from app.infrastructure.ai_providers.hyperbolic import HyperbolicProvider

        provider = HyperbolicProvider()
        assert provider.get_provider_name() == "Hyperbolic"

    @pytest.mark.asyncio
    async def test_generate_without_api_key(self):
        """Тест генерации без API ключа."""
        from app.infrastructure.ai_providers.hyperbolic import HyperbolicProvider

        provider = HyperbolicProvider(api_key="")
        with pytest.raises(ValueError, match="API ключ обязателен"):
            await provider.generate("test prompt")


@pytest.mark.unit
class TestNovitaProvider:
    """Тесты для Novita провайдера."""

    def test_init_defaults(self):
        """Тест инициализации с параметрами по умолчанию."""
        from app.infrastructure.ai_providers.novita import NovitaProvider

        provider = NovitaProvider()
        assert "llama" in provider.model.lower()
        assert provider.api_url == "https://api.novita.ai/v3/openai/chat/completions"

    def test_get_provider_name(self):
        """Тест получения имени провайдера."""
        from app.infrastructure.ai_providers.novita import NovitaProvider

        provider = NovitaProvider()
        assert provider.get_provider_name() == "Novita"

    @pytest.mark.asyncio
    async def test_generate_without_api_key(self):
        """Тест генерации без API ключа."""
        from app.infrastructure.ai_providers.novita import NovitaProvider

        provider = NovitaProvider(api_key="")
        with pytest.raises(ValueError, match="API ключ обязателен"):
            await provider.generate("test prompt")


@pytest.mark.unit
class TestScalewayProvider:
    """Тесты для Scaleway провайдера."""

    def test_init_defaults(self):
        """Тест инициализации с параметрами по умолчанию."""
        from app.infrastructure.ai_providers.scaleway import ScalewayProvider

        provider = ScalewayProvider()
        assert "llama" in provider.model.lower()
        assert provider.api_url == "https://api.scaleway.ai/v1/chat/completions"

    def test_get_provider_name(self):
        """Тест получения имени провайдера."""
        from app.infrastructure.ai_providers.scaleway import ScalewayProvider

        provider = ScalewayProvider()
        assert provider.get_provider_name() == "Scaleway"

    @pytest.mark.asyncio
    async def test_generate_without_api_key(self):
        """Тест генерации без API ключа."""
        from app.infrastructure.ai_providers.scaleway import ScalewayProvider

        provider = ScalewayProvider(api_key="")
        with pytest.raises(ValueError, match="API ключ обязателен"):
            await provider.generate("test prompt")


# ═══════════════════════════════════════════════════════════════════════════
# Фаза 3: Резервные провайдеры
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.unit
class TestKlusterProvider:
    """Тесты для Kluster провайдера."""

    def test_init_defaults(self):
        """Тест инициализации с параметрами по умолчанию."""
        from app.infrastructure.ai_providers.kluster import KlusterProvider

        provider = KlusterProvider()
        assert "llama" in provider.model.lower()
        assert provider.api_url == "https://api.kluster.ai/v1/chat/completions"

    def test_get_provider_name(self):
        """Тест получения имени провайдера."""
        from app.infrastructure.ai_providers.kluster import KlusterProvider

        provider = KlusterProvider()
        assert provider.get_provider_name() == "Kluster"

    @pytest.mark.asyncio
    async def test_generate_without_api_key(self):
        """Тест генерации без API ключа."""
        from app.infrastructure.ai_providers.kluster import KlusterProvider

        provider = KlusterProvider(api_key="")
        with pytest.raises(ValueError, match="API ключ обязателен"):
            await provider.generate("test prompt")


@pytest.mark.unit
class TestNebiusProvider:
    """Тесты для Nebius провайдера."""

    def test_init_defaults(self):
        """Тест инициализации с параметрами по умолчанию."""
        from app.infrastructure.ai_providers.nebius import NebiusProvider

        provider = NebiusProvider()
        assert "llama" in provider.model.lower()
        assert provider.api_url == "https://api.studio.nebius.ai/v1/chat/completions"

    def test_get_provider_name(self):
        """Тест получения имени провайдера."""
        from app.infrastructure.ai_providers.nebius import NebiusProvider

        provider = NebiusProvider()
        assert provider.get_provider_name() == "Nebius"

    @pytest.mark.asyncio
    async def test_generate_without_api_key(self):
        """Тест генерации без API ключа."""
        from app.infrastructure.ai_providers.nebius import NebiusProvider

        provider = NebiusProvider(api_key="")
        with pytest.raises(ValueError, match="API ключ обязателен"):
            await provider.generate("test prompt")


# ═══════════════════════════════════════════════════════════════════════════
# Интеграционные тесты (проверка наследования от AIProviderBase)
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.unit
class TestProvidersInheritance:
    """Тесты проверки наследования от AIProviderBase."""

    def test_all_providers_inherit_from_base(self):
        """Проверка что все провайдеры наследуют от AIProviderBase."""
        from app.infrastructure.ai_providers.base import AIProviderBase
        from app.infrastructure.ai_providers.deepseek import DeepSeekProvider
        from app.infrastructure.ai_providers.openrouter import OpenRouterProvider
        from app.infrastructure.ai_providers.github_models import GitHubModelsProvider
        from app.infrastructure.ai_providers.fireworks import FireworksProvider
        from app.infrastructure.ai_providers.hyperbolic import HyperbolicProvider
        from app.infrastructure.ai_providers.novita import NovitaProvider
        from app.infrastructure.ai_providers.scaleway import ScalewayProvider
        from app.infrastructure.ai_providers.kluster import KlusterProvider
        from app.infrastructure.ai_providers.nebius import NebiusProvider

        providers = [
            DeepSeekProvider,
            OpenRouterProvider,
            GitHubModelsProvider,
            FireworksProvider,
            HyperbolicProvider,
            NovitaProvider,
            ScalewayProvider,
            KlusterProvider,
            NebiusProvider,
        ]

        for provider_class in providers:
            assert issubclass(
                provider_class, AIProviderBase
            ), f"{provider_class.__name__} должен наследовать от AIProviderBase"

    def test_all_providers_implement_required_methods(self):
        """Проверка что все провайдеры реализуют обязательные методы."""
        from app.infrastructure.ai_providers.deepseek import DeepSeekProvider
        from app.infrastructure.ai_providers.openrouter import OpenRouterProvider
        from app.infrastructure.ai_providers.github_models import GitHubModelsProvider
        from app.infrastructure.ai_providers.fireworks import FireworksProvider
        from app.infrastructure.ai_providers.hyperbolic import HyperbolicProvider
        from app.infrastructure.ai_providers.novita import NovitaProvider
        from app.infrastructure.ai_providers.scaleway import ScalewayProvider
        from app.infrastructure.ai_providers.kluster import KlusterProvider
        from app.infrastructure.ai_providers.nebius import NebiusProvider

        providers = [
            DeepSeekProvider(),
            OpenRouterProvider(),
            GitHubModelsProvider(),
            FireworksProvider(),
            HyperbolicProvider(),
            NovitaProvider(),
            ScalewayProvider(),
            KlusterProvider(),
            NebiusProvider(),
        ]

        required_methods = ["generate", "health_check", "get_provider_name"]

        for provider in providers:
            for method in required_methods:
                assert hasattr(
                    provider, method
                ), f"{provider.__class__.__name__} должен иметь метод {method}"
