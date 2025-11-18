"""
Test All Providers Use Case

Tests all registered AI providers with a simple prompt
and returns results with response times or error details.
"""

import logging
import time
from typing import Any

from app.infrastructure.ai_providers.base import AIProviderBase
from app.infrastructure.ai_providers.cerebras import CerebrasProvider
from app.infrastructure.ai_providers.cloudflare import CloudflareProvider
from app.infrastructure.ai_providers.google_gemini import GoogleGeminiProvider
from app.infrastructure.ai_providers.groq import GroqProvider
from app.infrastructure.ai_providers.huggingface import HuggingFaceProvider
from app.infrastructure.ai_providers.sambanova import SambanovaProvider

logger = logging.getLogger(__name__)


class TestAllProvidersUseCase:
    """
    Use case for testing all AI providers.

    Sends a simple test prompt to each provider and collects:
    - Success/failure status
    - Response time for successful calls
    - Error type and message for failed calls
    """

    # Test prompt - simple and universal
    TEST_PROMPT = "Hello! Please respond with 'OK' if you can read this message."

    def __init__(self):
        """Initialize use case with all registered providers."""
        # Initialize AI providers (6 verified free-tier providers, no credit card required)
        self.providers = {
            "GoogleGemini": GoogleGeminiProvider(),
            "Groq": GroqProvider(),
            "Cerebras": CerebrasProvider(),
            "SambaNova": SambanovaProvider(),
            "HuggingFace": HuggingFaceProvider(),
            "Cloudflare": CloudflareProvider(),
        }

    async def execute(self) -> list[dict[str, Any]]:
        """
        Execute provider testing.

        Tests each provider with a simple prompt and measures response time.

        Returns:
            List of test results, one per provider:
            [
                {
                    "provider": "GoogleGemini",
                    "model": "Gemini 2.5 Flash",
                    "status": "success",
                    "response_time": 1.234,
                    "error": None
                },
                {
                    "provider": "SomeProvider",
                    "model": "Model Name",
                    "status": "error",
                    "response_time": None,
                    "error": "Connection timeout"
                }
            ]
        """
        logger.info("Starting provider testing...")

        results = []

        for provider_name, provider_instance in self.providers.items():
            result = await self._test_provider(provider_name, provider_instance)
            results.append(result)

        # Sort results: successful first (by response time), then failures
        results.sort(
            key=lambda r: (r["status"] != "success", r.get("response_time") or float("inf"))
        )

        logger.info(f"Provider testing completed: {len(results)} providers tested")
        return results

    async def _test_provider(
        self, provider_name: str, provider: AIProviderBase
    ) -> dict[str, Any]:
        """
        Test a single provider.

        Args:
            provider_name: Name of the provider (e.g., "Groq")
            provider: Provider instance

        Returns:
            Test result dictionary
        """
        logger.info(f"Testing provider: {provider_name}")

        # Get provider-specific model name
        model_name = self._get_model_name(provider_name)

        result = {
            "provider": provider_name,
            "model": model_name,
            "status": "unknown",
            "response_time": None,
            "error": None,
        }

        try:
            start_time = time.time()

            # Call provider with test prompt
            response = await provider.generate(self.TEST_PROMPT)

            end_time = time.time()
            response_time = end_time - start_time

            # Verify we got a response
            if response and len(response.strip()) > 0:
                result["status"] = "success"
                result["response_time"] = round(response_time, 2)
                logger.info(
                    f"✅ {provider_name} responded in {response_time:.2f}s: {response[:50]}..."
                )
            else:
                result["status"] = "error"
                result["error"] = "Empty response received"
                logger.warning(f"⚠️ {provider_name} returned empty response")

        except Exception as e:
            error_type = type(e).__name__
            error_message = str(e)

            result["status"] = "error"
            result["error"] = f"{error_type}: {error_message}"

            logger.error(f"❌ {provider_name} failed: {error_type}: {error_message}")

        return result

    def _get_model_name(self, provider_name: str) -> str:
        """
        Get friendly model name for provider.

        Args:
            provider_name: Provider name

        Returns:
            Human-readable model name
        """
        model_names = {
            "GoogleGemini": "Gemini 2.5 Flash",
            "Groq": "Llama 3.3 70B Versatile",
            "Cerebras": "Llama 3.3 70B",
            "SambaNova": "Meta-Llama-3.3-70B-Instruct",
            "HuggingFace": "Meta-Llama-3-8B-Instruct",
            "Cloudflare": "Llama 3.3 70B FP8 Fast",
        }
        return model_names.get(provider_name, "Unknown Model")
