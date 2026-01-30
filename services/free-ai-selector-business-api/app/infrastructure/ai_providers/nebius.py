"""
Nebius AI Provider integration

Интеграция с Nebius Studio API для генерации текста.
Бесплатный tier: $1 кредитов при регистрации, без требования кредитной карты.
OpenAI-совместимый API формат.

F013: Refactored to use OpenAICompatibleProvider base class.
"""

from app.infrastructure.ai_providers.base import OpenAICompatibleProvider


class NebiusProvider(OpenAICompatibleProvider):
    """
    Nebius Studio API провайдер (OpenAI-compatible).

    Использует Nebius API для генерации текста.
    Бесплатно: $1 кредитов, без кредитной карты.
    """

    PROVIDER_NAME = "Nebius"
    BASE_URL = "https://api.studio.nebius.ai/v1/chat/completions"
    MODELS_URL = "https://api.studio.nebius.ai/v1/models"
    DEFAULT_MODEL = "meta-llama/Meta-Llama-3.1-70B-Instruct"
    API_KEY_ENV = "NEBIUS_API_KEY"
    SUPPORTS_RESPONSE_FORMAT = False
