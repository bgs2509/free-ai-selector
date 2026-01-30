"""
Kluster AI Provider integration

Интеграция с Kluster AI API для генерации текста.
Бесплатный tier: $5 кредитов при регистрации, без требования кредитной карты.
OpenAI-совместимый API формат.

F013: Refactored to use OpenAICompatibleProvider base class.
"""

from app.infrastructure.ai_providers.base import OpenAICompatibleProvider


class KlusterProvider(OpenAICompatibleProvider):
    """
    Kluster AI провайдер (OpenAI-compatible).

    Использует Kluster AI API для генерации текста.
    Бесплатно: $5 кредитов, без кредитной карты.
    """

    PROVIDER_NAME = "Kluster"
    BASE_URL = "https://api.kluster.ai/v1/chat/completions"
    MODELS_URL = "https://api.kluster.ai/v1/models"
    DEFAULT_MODEL = "klusterai/Meta-Llama-3.3-70B-Instruct-Turbo"
    API_KEY_ENV = "KLUSTER_API_KEY"
    SUPPORTS_RESPONSE_FORMAT = False
