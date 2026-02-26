"""
Provider Registry — Single source of class mapping for AI providers (F008 SSOT).

This module provides:
- PROVIDER_CLASSES: Static mapping from provider name to class
- ProviderRegistry: Singleton factory with lazy initialization

Usage:
    provider = ProviderRegistry.get_provider("GoogleGemini")
    if provider:
        response = await provider.generate(prompt)

Note:
    Provider metadata (api_format) is stored in the database (seed.py).
    This registry maps provider names to their implementation classes
    and provides API key env var names (F018 SSOT).
"""

from typing import Optional

from app.infrastructure.ai_providers.base import AIProviderBase
from app.infrastructure.ai_providers.cerebras import CerebrasProvider
from app.infrastructure.ai_providers.cloudflare import CloudflareProvider
from app.infrastructure.ai_providers.deepseek import DeepSeekProvider
from app.infrastructure.ai_providers.fireworks import FireworksProvider
from app.infrastructure.ai_providers.github_models import GitHubModelsProvider
from app.infrastructure.ai_providers.groq import GroqProvider
from app.infrastructure.ai_providers.huggingface import HuggingFaceProvider
from app.infrastructure.ai_providers.hyperbolic import HyperbolicProvider
from app.infrastructure.ai_providers.novita import NovitaProvider
from app.infrastructure.ai_providers.openrouter import OpenRouterProvider
from app.infrastructure.ai_providers.sambanova import SambanovaProvider
from app.infrastructure.ai_providers.scaleway import ScalewayProvider


# Единственное место с маппингом provider_name → ProviderClass
PROVIDER_CLASSES: dict[str, type[AIProviderBase]] = {
    # Существующие провайдеры (4 шт.)
    "Groq": GroqProvider,
    "Cerebras": CerebrasProvider,
    "SambaNova": SambanovaProvider,
    "HuggingFace": HuggingFaceProvider,
    "Cloudflare": CloudflareProvider,
    # Новые провайдеры F003 — Фаза 1: Приоритетные (2 шт.)
    "DeepSeek": DeepSeekProvider,
    "OpenRouter": OpenRouterProvider,
    "GitHubModels": GitHubModelsProvider,
    # Новые провайдеры F003 — Фаза 2: Дополнительные (4 шт.)
    "Fireworks": FireworksProvider,
    "Hyperbolic": HyperbolicProvider,
    "Novita": NovitaProvider,
    "Scaleway": ScalewayProvider,
    # Новые провайдеры F003 — Фаза 3: Резервные (0 шт.)
}


class ProviderRegistry:
    """
    Фабрика для получения AI провайдеров (Singleton с lazy initialization).

    Кэширует экземпляры провайдеров для повторного использования.
    """

    _instances: dict[str, AIProviderBase] = {}

    @classmethod
    def get_provider(cls, name: str) -> Optional[AIProviderBase]:
        """
        Получить provider instance (ленивая инициализация).

        Args:
            name: Имя провайдера (например, "GoogleGemini")

        Returns:
            Инициализированный провайдер или None если не найден
        """
        if name not in cls._instances:
            provider_class = PROVIDER_CLASSES.get(name)
            if provider_class:
                cls._instances[name] = provider_class()
        return cls._instances.get(name)

    @classmethod
    def get_all_provider_names(cls) -> list[str]:
        """Получить список всех зарегистрированных имён провайдеров."""
        return list(PROVIDER_CLASSES.keys())

    @classmethod
    def has_provider(cls, name: str) -> bool:
        """Проверить наличие класса провайдера в registry."""
        return name in PROVIDER_CLASSES

    @classmethod
    def get_api_key_env(cls, name: str) -> str:
        """
        Получить имя env переменной API ключа без создания экземпляра (F018 SSOT).

        Args:
            name: Имя провайдера (например, "Groq")

        Returns:
            Имя env переменной (например, "GROQ_API_KEY") или "" если не найден
        """
        provider_class = PROVIDER_CLASSES.get(name)
        if provider_class and hasattr(provider_class, "API_KEY_ENV"):
            return provider_class.API_KEY_ENV
        return ""

    @classmethod
    def reset(cls) -> None:
        """Сбросить кэш instances (для тестов)."""
        cls._instances.clear()
