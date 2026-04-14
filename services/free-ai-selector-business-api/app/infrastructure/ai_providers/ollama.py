"""
Ollama AI Provider integration (local LLM)

Integrates with Ollama server for local LLM inference.
Ollama exposes an OpenAI-compatible API at /v1/chat/completions.

Uses OLLAMA_BASE_URL env var for server address (default: http://localhost:11434).
API key is a dummy value — Ollama ignores the Authorization header.
"""

import os
from typing import ClassVar

from app.infrastructure.ai_providers.base import OpenAICompatibleProvider


class OllamaProvider(OpenAICompatibleProvider):
    """
    Base class for Ollama-hosted models.

    All Ollama models share the same server URL and dummy API key.
    Subclasses only set PROVIDER_NAME and DEFAULT_MODEL.
    """

    API_KEY_ENV = "OLLAMA_API_KEY"
    SUPPORTS_RESPONSE_FORMAT = True
    TIMEOUT: ClassVar[float] = 120.0
    TAGS: ClassVar[set[str]] = {"local"}
    MAX_OUTPUT_TOKENS: ClassVar[int] = 4096

    def _get_base_url(self) -> str:
        """Get Ollama server base URL from environment."""
        return os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

    def _build_url(self) -> str:
        """Build chat completions URL from OLLAMA_BASE_URL."""
        return f"{self._get_base_url()}/v1/chat/completions"

    def _get_models_url(self) -> str:
        """Build models URL from OLLAMA_BASE_URL."""
        return f"{self._get_base_url()}/v1/models"

    async def health_check(self) -> bool:
        """Health check using dynamic MODELS_URL."""
        import httpx

        from app.utils.logger import get_logger
        from app.utils.security import sanitize_error_message

        logger = get_logger(__name__)
        headers = {"Authorization": f"Bearer {self.api_key}"}
        models_url = self._get_models_url()

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(models_url, headers=headers)
                return self._is_health_check_success(response)
            except Exception as e:
                err_msg = sanitize_error_message(e)
                logger.error(
                    "health_check_failed", provider=self.PROVIDER_NAME, error=err_msg
                )
                return False


class OllamaGemma4E2B(OllamaProvider):
    """Ollama Gemma 4 E2B (5.1B params, Q4_K_M, vision+audio+tools+thinking)."""

    PROVIDER_NAME = "Ollama-Gemma4-E2B"
    DEFAULT_MODEL = "gemma4:e2b"


# Dict for easy registration in registry.py
OLLAMA_PROVIDERS: dict[str, type[OllamaProvider]] = {
    "Ollama-Gemma4-E2B": OllamaGemma4E2B,
}
