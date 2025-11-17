"""
Replicate AI Provider integration

Integrates with Replicate API for free AI model access.
"""

import logging
import os
from typing import Optional

import httpx

from app.infrastructure.ai_providers.base import AIProviderBase

logger = logging.getLogger(__name__)


class ReplicateProvider(AIProviderBase):
    """
    Replicate API provider.

    Uses Replicate's API for AI generation.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Replicate provider.

        Args:
            api_key: Replicate API token (defaults to REPLICATE_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("REPLICATE_API_KEY", "")
        self.api_url = "https://api.replicate.com/v1/predictions"
        self.timeout = 30.0  # seconds

    async def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate AI response using Replicate API.

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
            raise ValueError("Replicate API key is required")

        headers = {"Authorization": f"Token {self.api_key}", "Content-Type": "application/json"}

        payload = {
            "version": "meta/meta-llama-3-8b-instruct",
            "input": {
                "prompt": prompt,
                "max_new_tokens": kwargs.get("max_tokens", 512),
                "temperature": kwargs.get("temperature", 0.7),
                "top_p": kwargs.get("top_p", 0.9),
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(self.api_url, headers=headers, json=payload)
                response.raise_for_status()

                result = response.json()

                # Replicate returns prediction with output array
                if "output" in result and isinstance(result["output"], list):
                    return "".join(result["output"]).strip()
                else:
                    logger.error(f"Unexpected Replicate response format: {result}")
                    raise ValueError("Invalid response format from Replicate")

            except httpx.HTTPError as e:
                logger.error(f"Replicate API error: {str(e)}")
                raise

    async def health_check(self) -> bool:
        """
        Check if Replicate API is responding.

        Returns:
            True if API is healthy, False otherwise
        """
        if not self.api_key:
            logger.warning("Replicate API key not configured")
            return False

        headers = {"Authorization": f"Token {self.api_key}"}

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                # Check API availability with minimal request
                response = await client.get("https://api.replicate.com/v1/models", headers=headers)
                return response.status_code == 200

            except Exception as e:
                logger.error(f"Replicate health check failed: {str(e)}")
                return False

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "Replicate"
