"""
SambaNova Cloud AI Provider integration

Integrates with SambaNova Cloud API for fast AI inference.
Free tier: Llama 3.3 70B (20 RPM), Llama 405B (10 RPM), no credit card required.
Speed: 430+ tokens/sec.
Bonus: $5 credits = 30M+ tokens on Llama 8B.
"""

import logging
import os
from typing import Optional

import httpx
from app.utils.security import sanitize_error_message

from app.infrastructure.ai_providers.base import AIProviderBase

logger = logging.getLogger(__name__)


class SambanovaProvider(AIProviderBase):
    """
    SambaNova Cloud API provider.

    Uses SambaNova's optimized RDU hardware for fast AI generation.
    OpenAI-compatible API format.
    No credit card required - fully free tier.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize SambaNova provider.

        Args:
            api_key: SambaNova API key (defaults to SAMBANOVA_API_KEY env var)
            model: Model name (defaults to Meta-Llama-3.3-70B-Instruct)
        """
        self.api_key = api_key or os.getenv("SAMBANOVA_API_KEY", "")
        self.model = model or "Meta-Llama-3.3-70B-Instruct"
        self.api_url = "https://api.sambanova.ai/v1/chat/completions"
        self.timeout = 30.0  # seconds

    async def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate AI response using SambaNova API.

        Args:
            prompt: User's prompt text
            **kwargs: Additional parameters
                - system_prompt (str, optional): System prompt for AI guidance (F011-B)
                - response_format (dict, optional): Response format specification (F011-B)
                - max_tokens (int, optional): Maximum tokens to generate
                - temperature (float, optional): Sampling temperature

        Returns:
            Generated response text

        Raises:
            httpx.HTTPError: If API request fails
            ValueError: If API key is missing
        """
        if not self.api_key:
            raise ValueError("SambaNova API key is required")

        # F011-B: Extract new kwargs
        system_prompt = kwargs.get("system_prompt")
        response_format = kwargs.get("response_format")

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        # F011-B: Build messages array (OpenAI format)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # OpenAI-compatible format
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", 512),
            "temperature": kwargs.get("temperature", 0.7),
            "top_p": kwargs.get("top_p", 0.9),
        }

        # F011-B: Add response_format if supported and provided
        if response_format:
            if self._supports_response_format():
                payload["response_format"] = response_format
            else:
                logger.warning(
                    "response_format_not_supported",
                    provider=self.get_provider_name(),
                    requested_format=response_format,
                )

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(self.api_url, headers=headers, json=payload)
                response.raise_for_status()

                result = response.json()

                # OpenAI-compatible response format
                if "choices" in result and len(result["choices"]) > 0:
                    message = result["choices"][0].get("message", {})
                    return message.get("content", "").strip()
                else:
                    logger.error(f"Unexpected SambaNova response format: {sanitize_error_message(str(result))}")
                    raise ValueError("Invalid response format from SambaNova")

            except httpx.HTTPError as e:
                logger.error(f"SambaNova API error: {sanitize_error_message(e)}")
                raise

    async def health_check(self) -> bool:
        """
        Check if SambaNova API is responding.

        Returns:
            True if API is healthy, False otherwise
        """
        if not self.api_key:
            logger.warning("SambaNova API key not configured")
            return False

        headers = {"Authorization": f"Bearer {self.api_key}"}

        # Use models endpoint for health check
        models_url = "https://api.sambanova.ai/v1/models"

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(models_url, headers=headers)
                return response.status_code == 200

            except Exception as e:
                logger.error(f"SambaNova health check failed: {sanitize_error_message(e)}")
                return False

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "SambaNova"

    def _supports_response_format(self) -> bool:
        """
        Check if provider supports response_format parameter.

        F011-B: SambaNova supports {"type": "json_object"} format.
        """
        return True
