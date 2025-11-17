"""
Together.ai AI Provider integration

Integrates with Together.ai API for free AI model access.
"""

import logging
import os
from typing import Optional

import httpx

from app.infrastructure.ai_providers.base import AIProviderBase

logger = logging.getLogger(__name__)


class TogetherProvider(AIProviderBase):
    """
    Together.ai API provider.

    Uses Together.ai's API for AI generation.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Together.ai provider.

        Args:
            api_key: Together.ai API key (defaults to TOGETHER_AI_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("TOGETHER_AI_API_KEY", "")
        self.api_url = "https://api.together.xyz/v1/chat/completions"
        self.model = "meta-llama/Meta-Llama-3-8B-Instruct"
        self.timeout = 30.0  # seconds

    async def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate AI response using Together.ai API.

        Args:
            prompt: User's prompt text
            **kwargs: Additional parameters

        Returns:
            Generated response text

        Raises:
            httpx.HTTPError: If API request fails
            ValueError: If API key is missing
        """
        if not self.api_key:
            raise ValueError("Together.ai API key is required")

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": kwargs.get("max_tokens", 512),
            "temperature": kwargs.get("temperature", 0.7),
            "top_p": kwargs.get("top_p", 0.9),
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(self.api_url, headers=headers, json=payload)
                response.raise_for_status()

                result = response.json()

                # Together.ai uses OpenAI-compatible format
                if "choices" in result and len(result["choices"]) > 0:
                    message = result["choices"][0].get("message", {})
                    return message.get("content", "").strip()
                else:
                    logger.error(f"Unexpected Together.ai response format: {result}")
                    raise ValueError("Invalid response format from Together.ai")

            except httpx.HTTPError as e:
                logger.error(f"Together.ai API error: {str(e)}")
                raise

    async def health_check(self) -> bool:
        """
        Check if Together.ai API is responding.

        Returns:
            True if API is healthy, False otherwise
        """
        if not self.api_key:
            logger.warning("Together.ai API key not configured")
            return False

        headers = {"Authorization": f"Bearer {self.api_key}"}

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                # Send minimal request to check API availability
                response = await client.post(
                    self.api_url,
                    headers=headers,
                    json={
                        "model": self.model,
                        "messages": [{"role": "user", "content": "test"}],
                        "max_tokens": 10,
                    },
                )

                return response.status_code == 200

            except Exception as e:
                logger.error(f"Together.ai health check failed: {str(e)}")
                return False

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "Together.ai"
