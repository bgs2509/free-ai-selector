"""
GitHub Models AI Provider integration

Интеграция с GitHub Models API через Azure AI.
Бесплатный tier: 50 RPD, 10 RPM через Personal Access Token.
OpenAI-совместимый API формат.

F013: Refactored to use OpenAICompatibleProvider base class.
"""

import httpx

from app.infrastructure.ai_providers.base import OpenAICompatibleProvider


class GitHubModelsProvider(OpenAICompatibleProvider):
    """
    GitHub Models API провайдер (OpenAI-compatible).

    Использует GitHub Models API (Azure AI Inference) для генерации текста.
    Бесплатно: 50 RPD, 10 RPM через GitHub PAT токен.
    Supports response_format (F011-B).
    """

    PROVIDER_NAME = "GitHubModels"
    BASE_URL = "https://models.inference.ai.azure.com/chat/completions"
    MODELS_URL = "https://models.inference.ai.azure.com/"
    DEFAULT_MODEL = "gpt-4o-mini"
    API_KEY_ENV = "GITHUB_TOKEN"
    SUPPORTS_RESPONSE_FORMAT = True  # F011-B: Supports json_schema format

    def _is_health_check_success(self, response: httpx.Response) -> bool:
        """GitHub Models возвращает < 500 при успехе."""
        return response.status_code < 500
