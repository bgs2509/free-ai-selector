"""
Google AI Studio (Gemini) AI Provider integration

Integrates with Google Generative AI API for free AI model access.
Free tier: Gemini 2.5 Flash (10 RPM, 250 RPD), no credit card required.
"""

import logging
import os
from typing import Optional

import httpx
from app.utils.security import sanitize_error_message

from app.infrastructure.ai_providers.base import AIProviderBase

logger = logging.getLogger(__name__)


class GoogleGeminiProvider(AIProviderBase):
    """
    Google AI Studio (Gemini) API provider.

    Uses free Gemini API for AI generation.
    No credit card required - fully free tier.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize Google Gemini provider.

        Args:
            api_key: Google AI Studio API key (defaults to GOOGLE_AI_STUDIO_API_KEY env var)
            model: Model name (defaults to gemini-2.5-flash)
        """
        self.api_key = api_key or os.getenv("GOOGLE_AI_STUDIO_API_KEY", "")
        self.model = model or "gemini-2.5-flash"
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"
        self.timeout = 30.0  # seconds

    async def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate AI response using Google Gemini API.

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
            raise ValueError("Google AI Studio API key is required")

        # Construct endpoint URL
        endpoint = f"{self.base_url}/models/{self.model}:generateContent"

        # Build request payload (Gemini format)
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "maxOutputTokens": kwargs.get("max_tokens", 512),
                "temperature": kwargs.get("temperature", 0.7),
                "topP": kwargs.get("top_p", 0.9),
            },
        }

        # Set API key in query params (Gemini uses x-goog-api-key header or query param)
        params = {"key": self.api_key}

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(endpoint, json=payload, params=params)
                response.raise_for_status()

                result = response.json()

                # Extract text from Gemini response format
                if "candidates" in result and len(result["candidates"]) > 0:
                    candidate = result["candidates"][0]
                    if "content" in candidate and "parts" in candidate["content"]:
                        parts = candidate["content"]["parts"]
                        if len(parts) > 0 and "text" in parts[0]:
                            return parts[0]["text"].strip()

                logger.error(f"Unexpected Google Gemini response format: {result}")
                raise ValueError("Invalid response format from Google Gemini")

            except httpx.HTTPError as e:
                logger.error(f"Google Gemini API error: {sanitize_error_message(e)}")
                raise

    async def health_check(self) -> bool:
        """
        Check if Google Gemini API is responding.

        Returns:
            True if API is healthy, False otherwise
        """
        if not self.api_key:
            logger.warning("Google AI Studio API key not configured")
            return False

        # Use models.list endpoint for health check
        endpoint = f"{self.base_url}/models"
        params = {"key": self.api_key}

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(endpoint, params=params)
                return response.status_code == 200

            except Exception as e:
                logger.error(f"Google Gemini health check failed: {sanitize_error_message(e)}")
                return False

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "GoogleGemini"
