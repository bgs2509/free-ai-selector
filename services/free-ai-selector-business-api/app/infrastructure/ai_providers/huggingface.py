"""
HuggingFace AI Provider integration

Integrates with HuggingFace Inference API for free AI model access.
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
    HuggingFace Inference API provider.

    Uses free HuggingFace Inference API for AI generation.
    """

    def __init__(self, api_key: Optional[str] = None, model_endpoint: Optional[str] = None):
        """
        Initialize HuggingFace provider.

        Args:
            api_key: HuggingFace API token (defaults to HUGGINGFACE_API_KEY env var)
            model_endpoint: Model API endpoint (optional)
        """
        self.api_key = api_key or os.getenv("HUGGINGFACE_API_KEY", "")
        self.model_endpoint = (
            model_endpoint
            or "https://api-inference.huggingface.co/models/meta-llama/Meta-Llama-3-8B-Instruct"
        )
        self.timeout = 30.0  # seconds

    async def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate AI response using HuggingFace Inference API.

        Args:
            prompt: User's prompt text
            **kwargs: Additional parameters (max_length, temperature, etc.)

        Returns:
            Generated response text

        Raises:
            httpx.HTTPError: If API request fails
            ValueError: If API key is missing
        """
        if not self.api_key:
            raise ValueError("HuggingFace API key is required")

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        payload = {
            "inputs": prompt,
            "parameters": {
                "max_new_tokens": kwargs.get("max_tokens", 512),
                "temperature": kwargs.get("temperature", 0.7),
                "top_p": kwargs.get("top_p", 0.9),
                "do_sample": True,
                "return_full_text": False,
            },
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(self.model_endpoint, headers=headers, json=payload)
                response.raise_for_status()

                result = response.json()

                # HuggingFace returns array of results
                if isinstance(result, list) and len(result) > 0:
                    generated_text = result[0].get("generated_text", "")
                    return generated_text.strip()
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
                # Send minimal request to check API availability
                response = await client.post(
                    self.model_endpoint,
                    headers=headers,
                    json={"inputs": "test", "parameters": {"max_new_tokens": 10}},
                )

                # Accept both 200 OK and 503 (model loading) as healthy
                return response.status_code in [200, 503]

            except Exception as e:
                logger.error(f"HuggingFace health check failed: {sanitize_error_message(e)}")
                return False

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "HuggingFace"
