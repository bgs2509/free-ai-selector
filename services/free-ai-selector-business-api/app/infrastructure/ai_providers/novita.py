"""
Novita AI Provider integration

Интеграция с Novita API для генерации текста.
Бесплатный tier: $10 кредитов + 5 полностью бесплатных моделей.
OpenAI-совместимый API формат.

F013: Refactored to use OpenAICompatibleProvider base class.
"""

from app.infrastructure.ai_providers.base import OpenAICompatibleProvider


class NovitaProvider(OpenAICompatibleProvider):
    """
    Novita API провайдер (OpenAI-compatible).

    Использует Novita API для генерации текста.
    Бесплатно: $10 кредитов + 5 полностью бесплатных моделей.
    """

    PROVIDER_NAME = "Novita"
    BASE_URL = "https://api.novita.ai/v3/openai/chat/completions"
    MODELS_URL = "https://api.novita.ai/v3/openai/models"
    DEFAULT_MODEL = "meta-llama/llama-3.1-70b-instruct"
    API_KEY_ENV = "NOVITA_API_KEY"
    SUPPORTS_RESPONSE_FORMAT = False
