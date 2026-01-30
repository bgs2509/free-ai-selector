"""
Unit-тесты для новых AI провайдеров (F003)

Тестирование 9 новых провайдеров:
- Фаза 1: DeepSeek, OpenRouter, GitHub Models
- Фаза 2: Fireworks, Hyperbolic, Novita, Scaleway
- Фаза 3: Kluster, Nebius

F013: Обновлены тесты для OpenAICompatibleProvider.
Валидация API key теперь в __init__, не в generate().
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

        # F013: API key обязателен в __init__
        provider = DeepSeekProvider(api_key="test-key")
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

        provider = DeepSeekProvider(api_key="test-key")
        assert provider.get_provider_name() == "DeepSeek"

    def test_init_without_api_key_raises(self, monkeypatch):
        """Тест: создание провайдера без API ключа вызывает ValueError."""
        from app.infrastructure.ai_providers.deepseek import DeepSeekProvider

        # F013: Валидация в __init__, нужно очистить env
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        with pytest.raises(ValueError, match="DEEPSEEK_API_KEY is required"):
            DeepSeekProvider()

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

        # F013: API key обязателен в __init__
        provider = OpenRouterProvider(api_key="test-key")
        # F013: Обновлён DEFAULT_MODEL
        assert provider.model == "deepseek/deepseek-r1-0528:free"
        assert provider.api_url == "https://openrouter.ai/api/v1/chat/completions"

    def test_get_provider_name(self):
        """Тест получения имени провайдера."""
        from app.infrastructure.ai_providers.openrouter import OpenRouterProvider

        provider = OpenRouterProvider(api_key="test-key")
        assert provider.get_provider_name() == "OpenRouter"

    def test_init_without_api_key_raises(self, monkeypatch):
        """Тест: создание провайдера без API ключа вызывает ValueError."""
        from app.infrastructure.ai_providers.openrouter import OpenRouterProvider

        # F013: Валидация в __init__, нужно очистить env
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        with pytest.raises(ValueError, match="OPENROUTER_API_KEY is required"):
            OpenRouterProvider()


@pytest.mark.unit
class TestGitHubModelsProvider:
    """Тесты для GitHub Models провайдера."""

    def test_init_defaults(self):
        """Тест инициализации с параметрами по умолчанию."""
        from app.infrastructure.ai_providers.github_models import GitHubModelsProvider

        # F013: API key обязателен в __init__
        provider = GitHubModelsProvider(api_key="test-key")
        assert provider.model == "gpt-4o-mini"
        assert provider.api_url == "https://models.inference.ai.azure.com/chat/completions"

    def test_get_provider_name(self):
        """Тест получения имени провайдера."""
        from app.infrastructure.ai_providers.github_models import GitHubModelsProvider

        provider = GitHubModelsProvider(api_key="test-key")
        assert provider.get_provider_name() == "GitHubModels"

    def test_init_without_api_key_raises(self, monkeypatch):
        """Тест: создание провайдера без API ключа вызывает ValueError."""
        from app.infrastructure.ai_providers.github_models import GitHubModelsProvider

        # F013: Валидация в __init__, нужно очистить env
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with pytest.raises(ValueError, match="GITHUB_TOKEN is required"):
            GitHubModelsProvider()


# ═══════════════════════════════════════════════════════════════════════════
# Фаза 2: Дополнительные провайдеры
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.unit
class TestFireworksProvider:
    """Тесты для Fireworks провайдера."""

    def test_init_defaults(self):
        """Тест инициализации с параметрами по умолчанию."""
        from app.infrastructure.ai_providers.fireworks import FireworksProvider

        # F013: API key обязателен в __init__
        provider = FireworksProvider(api_key="test-key")
        assert "llama" in provider.model.lower()
        assert provider.api_url == "https://api.fireworks.ai/inference/v1/chat/completions"

    def test_get_provider_name(self):
        """Тест получения имени провайдера."""
        from app.infrastructure.ai_providers.fireworks import FireworksProvider

        provider = FireworksProvider(api_key="test-key")
        assert provider.get_provider_name() == "Fireworks"

    def test_init_without_api_key_raises(self, monkeypatch):
        """Тест: создание провайдера без API ключа вызывает ValueError."""
        from app.infrastructure.ai_providers.fireworks import FireworksProvider

        # F013: Валидация в __init__, нужно очистить env
        monkeypatch.delenv("FIREWORKS_API_KEY", raising=False)
        with pytest.raises(ValueError, match="FIREWORKS_API_KEY is required"):
            FireworksProvider()


@pytest.mark.unit
class TestHyperbolicProvider:
    """Тесты для Hyperbolic провайдера."""

    def test_init_defaults(self):
        """Тест инициализации с параметрами по умолчанию."""
        from app.infrastructure.ai_providers.hyperbolic import HyperbolicProvider

        # F013: API key обязателен в __init__
        provider = HyperbolicProvider(api_key="test-key")
        assert "llama" in provider.model.lower()
        assert provider.api_url == "https://api.hyperbolic.xyz/v1/chat/completions"

    def test_get_provider_name(self):
        """Тест получения имени провайдера."""
        from app.infrastructure.ai_providers.hyperbolic import HyperbolicProvider

        provider = HyperbolicProvider(api_key="test-key")
        assert provider.get_provider_name() == "Hyperbolic"

    def test_init_without_api_key_raises(self, monkeypatch):
        """Тест: создание провайдера без API ключа вызывает ValueError."""
        from app.infrastructure.ai_providers.hyperbolic import HyperbolicProvider

        # F013: Валидация в __init__, нужно очистить env
        monkeypatch.delenv("HYPERBOLIC_API_KEY", raising=False)
        with pytest.raises(ValueError, match="HYPERBOLIC_API_KEY is required"):
            HyperbolicProvider()


@pytest.mark.unit
class TestNovitaProvider:
    """Тесты для Novita провайдера."""

    def test_init_defaults(self):
        """Тест инициализации с параметрами по умолчанию."""
        from app.infrastructure.ai_providers.novita import NovitaProvider

        # F013: API key обязателен в __init__
        provider = NovitaProvider(api_key="test-key")
        assert "llama" in provider.model.lower()
        assert provider.api_url == "https://api.novita.ai/v3/openai/chat/completions"

    def test_get_provider_name(self):
        """Тест получения имени провайдера."""
        from app.infrastructure.ai_providers.novita import NovitaProvider

        provider = NovitaProvider(api_key="test-key")
        assert provider.get_provider_name() == "Novita"

    def test_init_without_api_key_raises(self, monkeypatch):
        """Тест: создание провайдера без API ключа вызывает ValueError."""
        from app.infrastructure.ai_providers.novita import NovitaProvider

        # F013: Валидация в __init__, нужно очистить env
        monkeypatch.delenv("NOVITA_API_KEY", raising=False)
        with pytest.raises(ValueError, match="NOVITA_API_KEY is required"):
            NovitaProvider()


@pytest.mark.unit
class TestScalewayProvider:
    """Тесты для Scaleway провайдера."""

    def test_init_defaults(self):
        """Тест инициализации с параметрами по умолчанию."""
        from app.infrastructure.ai_providers.scaleway import ScalewayProvider

        # F013: API key обязателен в __init__
        provider = ScalewayProvider(api_key="test-key")
        assert "llama" in provider.model.lower()
        assert provider.api_url == "https://api.scaleway.ai/v1/chat/completions"

    def test_get_provider_name(self):
        """Тест получения имени провайдера."""
        from app.infrastructure.ai_providers.scaleway import ScalewayProvider

        provider = ScalewayProvider(api_key="test-key")
        assert provider.get_provider_name() == "Scaleway"

    def test_init_without_api_key_raises(self, monkeypatch):
        """Тест: создание провайдера без API ключа вызывает ValueError."""
        from app.infrastructure.ai_providers.scaleway import ScalewayProvider

        # F013: Валидация в __init__, нужно очистить env
        monkeypatch.delenv("SCALEWAY_API_KEY", raising=False)
        with pytest.raises(ValueError, match="SCALEWAY_API_KEY is required"):
            ScalewayProvider()


# ═══════════════════════════════════════════════════════════════════════════
# Фаза 3: Резервные провайдеры
# ═══════════════════════════════════════════════════════════════════════════


@pytest.mark.unit
class TestKlusterProvider:
    """Тесты для Kluster провайдера."""

    def test_init_defaults(self):
        """Тест инициализации с параметрами по умолчанию."""
        from app.infrastructure.ai_providers.kluster import KlusterProvider

        # F013: API key обязателен в __init__
        provider = KlusterProvider(api_key="test-key")
        assert "llama" in provider.model.lower()
        assert provider.api_url == "https://api.kluster.ai/v1/chat/completions"

    def test_get_provider_name(self):
        """Тест получения имени провайдера."""
        from app.infrastructure.ai_providers.kluster import KlusterProvider

        provider = KlusterProvider(api_key="test-key")
        assert provider.get_provider_name() == "Kluster"

    def test_init_without_api_key_raises(self, monkeypatch):
        """Тест: создание провайдера без API ключа вызывает ValueError."""
        from app.infrastructure.ai_providers.kluster import KlusterProvider

        # F013: Валидация в __init__, нужно очистить env
        monkeypatch.delenv("KLUSTER_API_KEY", raising=False)
        with pytest.raises(ValueError, match="KLUSTER_API_KEY is required"):
            KlusterProvider()


@pytest.mark.unit
class TestNebiusProvider:
    """Тесты для Nebius провайдера."""

    def test_init_defaults(self):
        """Тест инициализации с параметрами по умолчанию."""
        from app.infrastructure.ai_providers.nebius import NebiusProvider

        # F013: API key обязателен в __init__
        provider = NebiusProvider(api_key="test-key")
        assert "llama" in provider.model.lower()
        assert provider.api_url == "https://api.studio.nebius.ai/v1/chat/completions"

    def test_get_provider_name(self):
        """Тест получения имени провайдера."""
        from app.infrastructure.ai_providers.nebius import NebiusProvider

        provider = NebiusProvider(api_key="test-key")
        assert provider.get_provider_name() == "Nebius"

    def test_init_without_api_key_raises(self, monkeypatch):
        """Тест: создание провайдера без API ключа вызывает ValueError."""
        from app.infrastructure.ai_providers.nebius import NebiusProvider

        # F013: Валидация в __init__, нужно очистить env
        monkeypatch.delenv("NEBIUS_API_KEY", raising=False)
        with pytest.raises(ValueError, match="NEBIUS_API_KEY is required"):
            NebiusProvider()


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

        # F013: Теперь все провайдеры требуют API key в __init__
        providers = [
            DeepSeekProvider(api_key="test-key"),
            OpenRouterProvider(api_key="test-key"),
            GitHubModelsProvider(api_key="test-key"),
            FireworksProvider(api_key="test-key"),
            HyperbolicProvider(api_key="test-key"),
            NovitaProvider(api_key="test-key"),
            ScalewayProvider(api_key="test-key"),
            KlusterProvider(api_key="test-key"),
            NebiusProvider(api_key="test-key"),
        ]

        required_methods = ["generate", "health_check", "get_provider_name"]

        for provider in providers:
            for method in required_methods:
                assert hasattr(
                    provider, method
                ), f"{provider.__class__.__name__} должен иметь метод {method}"
