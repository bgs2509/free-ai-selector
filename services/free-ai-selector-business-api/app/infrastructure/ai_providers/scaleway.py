"""
Scaleway AI Provider integration

Интеграция с Scaleway Generative APIs для генерации текста.
Бесплатный tier: 1M токенов в месяц, EU-based, GDPR compliant.
OpenAI-совместимый API формат.

F013: Refactored to use OpenAICompatibleProvider base class.
"""

from app.infrastructure.ai_providers.base import OpenAICompatibleProvider


class ScalewayProvider(OpenAICompatibleProvider):
    """
    Scaleway Generative APIs провайдер (OpenAI-compatible).

    Использует Scaleway API для генерации текста.
    Бесплатно: 1M токенов/месяц, EU-based, GDPR compliant.
    """

    PROVIDER_NAME = "Scaleway"
    BASE_URL = "https://api.scaleway.ai/v1/chat/completions"
    MODELS_URL = "https://api.scaleway.ai/v1/models"
    DEFAULT_MODEL = "llama-3.1-70b-instruct"
    API_KEY_ENV = "SCALEWAY_API_KEY"
    SUPPORTS_RESPONSE_FORMAT = False
