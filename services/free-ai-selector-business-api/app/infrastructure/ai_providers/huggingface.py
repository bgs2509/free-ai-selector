"""
HuggingFace AI Provider integration

Integrates with HuggingFace Inference Providers API (OpenAI-compatible).
Free tier available with HuggingFace account.
"""

import logging
import os
from typing import Optional

import httpx
from app.utils.security import sanitize_error_message

from app.infrastructure.ai_providers.base import AIProviderBase

logger = logging.getLogger(__name__)


class HuggingFaceProvider(AIProviderBase):
    """
    HuggingFace Inference Providers API provider.

    Uses new router.huggingface.co OpenAI-compatible API.
    Supports multiple inference providers under unified endpoint.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize HuggingFace provider.

        Args:
            api_key: HuggingFace API token (defaults to HUGGINGFACE_API_KEY env var)
            model: Model name (defaults to meta-llama/Meta-Llama-3-8B-Instruct)
        """
        self.api_key = api_key or os.getenv("HUGGINGFACE_API_KEY", "")
        self.model = model or "meta-llama/Meta-Llama-3-8B-Instruct"
        self.api_url = "https://router.huggingface.co/v1/chat/completions"
        self.timeout = 30.0  # seconds

    async def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate AI response using HuggingFace Inference API.

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
            raise ValueError("HuggingFace API key is required")

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
                    logger.error(f"Unexpected HuggingFace response format: {sanitize_error_message(str(result))}")
                    raise ValueError("Invalid response format from HuggingFace")

            except httpx.HTTPError as e:
                logger.error(f"HuggingFace API error: {sanitize_error_message(e)}")
                raise

    async def health_check(self) -> bool:
        """
        Check if HuggingFace API is responding.

        Returns:
            True if API is healthy, False otherwise
        """
        if not self.api_key:
            logger.warning("HuggingFace API key not configured")
            return False

        headers = {"Authorization": f"Bearer {self.api_key}"}

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                # Use models endpoint for health check
                response = await client.get(
                    "https://router.huggingface.co/v1/models",
                    headers=headers,
                )
                return response.status_code == 200

            except Exception as e:
                logger.error(f"HuggingFace health check failed: {sanitize_error_message(e)}")
                return False

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "HuggingFace"

    def _supports_response_format(self) -> bool:
        """
        Check if provider supports response_format parameter.

        F011-B: HuggingFace support for response_format is TBD.
        Using graceful degradation (returns False).
        """
        return False
