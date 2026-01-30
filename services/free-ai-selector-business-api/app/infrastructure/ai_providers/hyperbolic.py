"""
Hyperbolic AI Provider integration

Интеграция с Hyperbolic API для генерации текста.
Бесплатный tier: $1 кредитов при регистрации, без требования кредитной карты.
OpenAI-совместимый API формат.

F013: Refactored to use OpenAICompatibleProvider base class.
"""

from app.infrastructure.ai_providers.base import OpenAICompatibleProvider


class HyperbolicProvider(OpenAICompatibleProvider):
    """
    Hyperbolic API провайдер (OpenAI-compatible).

    Использует Hyperbolic API для генерации текста.
    Бесплатно: $1 кредитов, без кредитной карты.
    """

    PROVIDER_NAME = "Hyperbolic"
    BASE_URL = "https://api.hyperbolic.xyz/v1/chat/completions"
    MODELS_URL = "https://api.hyperbolic.xyz/v1/models"
    DEFAULT_MODEL = "meta-llama/Llama-3.3-70B-Instruct"
    API_KEY_ENV = "HYPERBOLIC_API_KEY"
    SUPPORTS_RESPONSE_FORMAT = False
