"""
Fireworks AI Provider integration

Интеграция с Fireworks API для генерации текста.
Бесплатный tier: $1 кредитов при регистрации, без требования кредитной карты.
OpenAI-совместимый API формат.

F013: Refactored to use OpenAICompatibleProvider base class.
"""

from app.infrastructure.ai_providers.base import OpenAICompatibleProvider


class FireworksProvider(OpenAICompatibleProvider):
    """
    Fireworks API провайдер (OpenAI-compatible).

    Использует Fireworks API для генерации текста.
    Бесплатно: $1 кредитов, без кредитной карты.
    """

    PROVIDER_NAME = "Fireworks"
    BASE_URL = "https://api.fireworks.ai/inference/v1/chat/completions"
    MODELS_URL = "https://api.fireworks.ai/inference/v1/models"
    DEFAULT_MODEL = "accounts/fireworks/models/gpt-oss-20b"
    API_KEY_ENV = "FIREWORKS_API_KEY"
    SUPPORTS_RESPONSE_FORMAT = False
