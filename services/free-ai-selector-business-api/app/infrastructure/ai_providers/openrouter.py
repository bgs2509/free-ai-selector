"""
OpenRouter AI Provider integration

Интеграция с OpenRouter API — агрегатором AI моделей.
Бесплатный tier: 50 RPD, 20 RPM для бесплатных моделей (с суффиксом :free).
OpenAI-совместимый API формат.

F013: Refactored to use OpenAICompatibleProvider base class.
"""

from app.infrastructure.ai_providers.base import OpenAICompatibleProvider


class OpenRouterProvider(OpenAICompatibleProvider):
    """
    OpenRouter API провайдер (агрегатор, OpenAI-compatible).

    Использует OpenRouter API для доступа к 30+ бесплатным моделям.
    Бесплатно: 50 RPD, 20 RPM для :free моделей.
    """

    PROVIDER_NAME = "OpenRouter"
    BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
    MODELS_URL = "https://openrouter.ai/api/v1/models"
    DEFAULT_MODEL = "deepseek/deepseek-r1-0528"
    API_KEY_ENV = "OPENROUTER_API_KEY"
    SUPPORTS_RESPONSE_FORMAT = False
    EXTRA_HEADERS = {
        "HTTP-Referer": "https://github.com/free-ai-selector",
        "X-Title": "Free AI Selector",
    }
