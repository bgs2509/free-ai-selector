"""
DeepSeek AI Provider integration

Интеграция с DeepSeek API для генерации текста.
Бесплатный tier: 5M токенов, без требования кредитной карты.
OpenAI-совместимый API формат.

F013: Refactored to use OpenAICompatibleProvider base class.
"""

from app.infrastructure.ai_providers.base import OpenAICompatibleProvider


class DeepSeekProvider(OpenAICompatibleProvider):
    """
    DeepSeek API провайдер (OpenAI-compatible).

    Использует DeepSeek API для генерации текста.
    Бесплатно: 5M токенов, без кредитной карты.
    """

    PROVIDER_NAME = "DeepSeek"
    BASE_URL = "https://api.deepseek.com/v1/chat/completions"
    MODELS_URL = "https://api.deepseek.com/v1/models"
    DEFAULT_MODEL = "deepseek-chat"
    API_KEY_ENV = "DEEPSEEK_API_KEY"
    SUPPORTS_RESPONSE_FORMAT = False
