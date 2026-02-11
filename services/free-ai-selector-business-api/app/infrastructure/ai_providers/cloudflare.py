"""
Cloudflare Workers AI Provider integration

Integrates with Cloudflare Workers AI for serverless GPU-powered inference.
Free tier: 10,000 Neurons/day, no credit card required.
Supports multiple models for text, image, and speech tasks.
"""

import logging
import os
from typing import Optional

import httpx
from app.utils.security import sanitize_error_message

from app.infrastructure.ai_providers.base import AIProviderBase

logger = logging.getLogger(__name__)


class CloudflareProvider(AIProviderBase):
    """
    Cloudflare Workers AI API provider.

    Uses Cloudflare's serverless GPU infrastructure for AI generation.
    No credit card required - fully free tier with 10k Neurons/day.
    """

    API_KEY_ENV = "CLOUDFLARE_API_TOKEN"

    def __init__(
        self,
        api_token: Optional[str] = None,
        account_id: Optional[str] = None,
        model: Optional[str] = None,
    ):
        """
        Initialize Cloudflare provider.

        Args:
            api_token: Cloudflare API token (defaults to CLOUDFLARE_API_TOKEN env var)
            account_id: Cloudflare account ID (defaults to CLOUDFLARE_ACCOUNT_ID env var)
            model: Model name (defaults to @cf/meta/llama-3.3-70b-instruct-fp8-fast)
        """
        self.api_token = api_token or os.getenv("CLOUDFLARE_API_TOKEN", "")
        self.account_id = account_id or os.getenv("CLOUDFLARE_ACCOUNT_ID", "")
        self.model = model or "@cf/meta/llama-3.3-70b-instruct-fp8-fast"
        self.base_url = "https://api.cloudflare.com/client/v4"
        self.timeout = 30.0  # seconds

    async def generate(self, prompt: str, **kwargs) -> str:
        """
        Generate AI response using Cloudflare Workers AI API.

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
            ValueError: If API token or account ID is missing
        """
        if not self.api_token:
            raise ValueError("Cloudflare API token is required")
        if not self.account_id:
            raise ValueError("Cloudflare account ID is required")

        # F011-B: Extract new kwargs
        system_prompt = kwargs.get("system_prompt")
        response_format = kwargs.get("response_format")

        headers = {"Authorization": f"Bearer {self.api_token}", "Content-Type": "application/json"}

        # Construct endpoint URL with account ID and model
        endpoint = f"{self.base_url}/accounts/{self.account_id}/ai/run/{self.model}"

        # F011-B: Build messages array (OpenAI format)
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Cloudflare uses messages format (similar to OpenAI)
        payload = {
            "messages": messages,
            "max_tokens": kwargs.get("max_tokens", 512),
            "temperature": kwargs.get("temperature", 0.7),
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
                response = await client.post(endpoint, headers=headers, json=payload)
                response.raise_for_status()

                result = response.json()

                # Cloudflare response format
                if "result" in result:
                    result_data = result["result"]

                    # Handle response field (text generation models)
                    if "response" in result_data:
                        response = result_data["response"]
                        # Handle both string and list responses
                        if isinstance(response, list):
                            response = " ".join(str(item) for item in response)
                        return str(response).strip()

                    # Handle choices format (OpenAI-compatible)
                    if "choices" in result_data and len(result_data["choices"]) > 0:
                        message = result_data["choices"][0].get("message", {})
                        content = message.get("content", "")
                        # Handle both string and list content
                        if isinstance(content, list):
                            content = " ".join(str(item) for item in content)
                        return str(content).strip()

                logger.error(f"Unexpected Cloudflare response format: {sanitize_error_message(str(result))}")
                raise ValueError("Invalid response format from Cloudflare Workers AI")

            except httpx.HTTPError as e:
                logger.error(f"Cloudflare Workers AI API error: {sanitize_error_message(e)}")
                raise

    async def health_check(self) -> bool:
        """
        Check if Cloudflare Workers AI API is responding.

        Returns:
            True if API is healthy, False otherwise
        """
        if not self.api_token:
            logger.warning("Cloudflare API token not configured")
            return False
        if not self.account_id:
            logger.warning("Cloudflare account ID not configured")
            return False

        headers = {"Authorization": f"Bearer {self.api_token}"}

        # Use account verification endpoint for health check
        endpoint = f"{self.base_url}/accounts/{self.account_id}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(endpoint, headers=headers)
                return response.status_code == 200

            except Exception as e:
                logger.error(f"Cloudflare Workers AI health check failed: {sanitize_error_message(e)}")
                return False

    def get_provider_name(self) -> str:
        """Get provider name."""
        return "Cloudflare"

    def _supports_response_format(self) -> bool:
        """
        Check if provider supports response_format parameter.

        F011-B: Cloudflare supports both json_object and json_schema formats.
        """
        return True
