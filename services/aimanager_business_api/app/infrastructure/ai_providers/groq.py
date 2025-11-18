"""
Groq AI Provider integration

Integrates with Groq API for ultra-fast AI inference on LPU (Language Processing Unit).
Free tier: Llama 3.3 70B (20 RPM, 14,400 RPD), no credit card required.
Speed: Up to 1,800 tokens/sec.
"""

import logging
import os
from typing import Optional

import httpx
from app.utils.security import sanitize_error_message

from app.infrastructure.ai_providers.base import AIProviderBase

logger = logging.getLogger(__name__)


class GroqProvider(AIProviderBase):
    """
    Groq API provider.

    Uses Groq's ultra-fast LPU for AI generation.
    OpenAI-compatible API format.
    No credit card required - fully free tier.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize Groq provider.

        Args:
            api_key: Groq API key (defaults to GROQ_API_KEY env var)
            model: Model name (defaults to llama-3.3-70b-versatile)
        """
        self.api_key = api_key or os.getenv("GROQ_API_KEY", "")
        self.model = model or "llama-3.3-70b-versatile"
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"
        self.timeout = 30.0  # seconds

    async def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate AI response using Groq API.

        Args:
            prompt: User's prompt text
            **kwargs: Additional parameters (max_tokens, temperature, etc.)

        Returns:
            Generated response text

        Raises:
            httpx.HTTPError: If API request fails
            ValueError: If API key is missing
        """
        if not self.api_key:
            raise ValueError("Groq API key is required")

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        # OpenAI-compatible format
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

                # OpenAI-compatible response format
                if "choices" in result and len(result["choices"]) > 0:
                    message = result["choices"][0].get("message", {})
                    return message.get("content", "").strip()
                else:
                    logger.error(f"Unexpected Groq response format: {result}")
                    raise ValueError("Invalid response format from Groq")

            except httpx.HTTPError as e:
                logger.error(f"Groq API error: {sanitize_error_message(e)}")
                raise

    async def health_check(self) -> bool:
        """
        Check if Groq API is responding.

        Returns:
            True if API is healthy, False otherwise
        """
        if not self.api_key:
            logger.warning("Groq API key not configured")
            return False

        headers = {"Authorization": f"Bearer {self.api_key}"}

        # Use models endpoint for health check
        models_url = "https://api.groq.com/openai/v1/models"

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(models_url, headers=headers)
                return response.status_code == 200

            except Exception as e:
                logger.error(f"Groq health check failed: {sanitize_error_message(e)}")
                return False

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "Groq"
