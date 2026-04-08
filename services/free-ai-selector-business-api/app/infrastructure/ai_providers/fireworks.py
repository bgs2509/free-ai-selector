"""
Fireworks AI Provider integration

Интеграция с Fireworks API для генерации текста.
Бесплатный tier: $1 кредитов при регистрации, без требования кредитной карты.
OpenAI-совместимый API формат.

F013: Refactored to use OpenAICompatibleProvider base class.
"""

import re
from typing import Any

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
    SUPPORTS_RESPONSE_FORMAT = True  # Supports {"type": "json_object"}

    def _parse_response(self, result: dict[str, Any]) -> str:
        """Strip proprietary reasoning tags from gpt-oss-20b responses."""
        content = super()._parse_response(result)
        if "<|channel|>" in content:
            # Extract text after last <|start|>assistant
            match = re.search(
                r"<\|end\|><\|start\|>assistant\s*(.*)", content, re.DOTALL
            )
            if match and match.group(1).strip():
                return match.group(1).strip()
            # Fallback: extract text between <|message|> and <|end|>
            match = re.search(r"<\|message\|>(.*?)<\|end\|>", content, re.DOTALL)
            if match:
                return match.group(1).strip()
        return content
