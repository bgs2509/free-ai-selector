"""
Test All Providers Use Case

Tests all registered AI providers with a simple prompt,
returns results with response times or error details,
and updates database statistics for reliability tracking.
"""

import logging
import time
from typing import Any, Optional

from app.domain.models import AIModelInfo
from app.utils.security import sanitize_error_message
from app.infrastructure.ai_providers.base import AIProviderBase
from app.infrastructure.ai_providers.cerebras import CerebrasProvider
from app.infrastructure.ai_providers.cloudflare import CloudflareProvider
from app.infrastructure.ai_providers.cohere import CohereProvider
from app.infrastructure.ai_providers.deepseek import DeepSeekProvider
from app.infrastructure.ai_providers.fireworks import FireworksProvider
from app.infrastructure.ai_providers.github_models import GitHubModelsProvider
from app.infrastructure.ai_providers.google_gemini import GoogleGeminiProvider
from app.infrastructure.ai_providers.groq import GroqProvider
from app.infrastructure.ai_providers.huggingface import HuggingFaceProvider
from app.infrastructure.ai_providers.hyperbolic import HyperbolicProvider
from app.infrastructure.ai_providers.kluster import KlusterProvider
from app.infrastructure.ai_providers.nebius import NebiusProvider
from app.infrastructure.ai_providers.novita import NovitaProvider
from app.infrastructure.ai_providers.openrouter import OpenRouterProvider
from app.infrastructure.ai_providers.sambanova import SambanovaProvider
from app.infrastructure.ai_providers.scaleway import ScalewayProvider
from app.infrastructure.http_clients.data_api_client import DataAPIClient

logger = logging.getLogger(__name__)


class TestAllProvidersUseCase:
    """
    Use case for testing all AI providers.

    Sends a simple test prompt to each provider and collects:
    - Success/failure status
    - Response time for successful calls
    - Error type and message for failed calls

    Additionally updates database statistics to improve reliability scores.
    This makes /test command the third source of reliability data alongside
    user prompts and health worker checks.
    """

    # Test prompt - simple and universal
    TEST_PROMPT = "Hello! Please respond with 'OK' if you can read this message."

    def __init__(self, data_api_client: DataAPIClient):
        """
        Initialize use case with Data API client and all registered providers.

        Args:
            data_api_client: Client for Data API communication and statistics updates
        """
        self.data_api_client = data_api_client

        # Initialize AI providers (16 verified free-tier providers, no credit card required)
        self.providers = {
            # Существующие провайдеры (6 шт.)
            "GoogleGemini": GoogleGeminiProvider(),
            "Groq": GroqProvider(),
            "Cerebras": CerebrasProvider(),
            "SambaNova": SambanovaProvider(),
            "HuggingFace": HuggingFaceProvider(),
            "Cloudflare": CloudflareProvider(),
            # Новые провайдеры F003 — Фаза 1: Приоритетные (4 шт.)
            "DeepSeek": DeepSeekProvider(),
            "Cohere": CohereProvider(),
            "OpenRouter": OpenRouterProvider(),
            "GitHubModels": GitHubModelsProvider(),
            # Новые провайдеры F003 — Фаза 2: Дополнительные (4 шт.)
            "Fireworks": FireworksProvider(),
            "Hyperbolic": HyperbolicProvider(),
            "Novita": NovitaProvider(),
            "Scaleway": ScalewayProvider(),
            # Новые провайдеры F003 — Фаза 3: Резервные (2 шт.)
            "Kluster": KlusterProvider(),
            "Nebius": NebiusProvider(),
        }

    async def execute(self) -> list[dict[str, Any]]:
        """
        Execute provider testing.

        Tests each provider with a simple prompt and measures response time.
        Updates database statistics for each test to improve reliability scores.

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

    async def _get_model_for_provider(self, provider_name: str) -> Optional[AIModelInfo]:
        """
        Get model from database by provider name.

        Args:
            provider_name: Provider name (e.g., "GoogleGemini")

        Returns:
            AIModelInfo if found, None otherwise
        """
        try:
            models = await self.data_api_client.get_all_models(active_only=False)
            for model in models:
                if model.provider == provider_name:
                    return model
            logger.warning(f"No model found in database for provider: {provider_name}")
            return None
        except Exception as e:
            logger.error(f"Failed to get model for provider {provider_name}: {sanitize_error_message(e)}")
            return None

    async def _test_provider(
        self, provider_name: str, provider: AIProviderBase
    ) -> dict[str, Any]:
        """
        Test a single provider and update database statistics.

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
            # БЕЗОПАСНОСТЬ: Sanitize сообщения об ошибках для скрытия API ключей
            error_message = sanitize_error_message(e)

            result["status"] = "error"
            result["error"] = f"{error_type}: {error_message}"

            logger.error(f"❌ {provider_name} failed: {error_type}: {error_message}")

        # Update database statistics
        await self._update_model_statistics(provider_name, result)

        return result

    async def _update_model_statistics(
        self, provider_name: str, test_result: dict[str, Any]
    ) -> None:
        """
        Update model statistics in database based on test result.

        Args:
            provider_name: Provider name (e.g., "GoogleGemini")
            test_result: Test result dictionary with status and response_time
        """
        # Get model from database
        model = await self._get_model_for_provider(provider_name)
        if not model:
            logger.warning(
                f"Cannot update statistics for {provider_name}: model not found in database"
            )
            return

        try:
            if test_result["status"] == "success":
                response_time = test_result.get("response_time") or 0.0
                await self.data_api_client.increment_success(
                    model_id=model.id, response_time=response_time
                )
                logger.info(
                    f"📊 Updated statistics for {provider_name}: increment_success (time: {response_time:.2f}s)"
                )
            else:
                # For failures, use 0.0 as response time or a default timeout value
                response_time = test_result.get("response_time") or 0.0
                await self.data_api_client.increment_failure(
                    model_id=model.id, response_time=response_time
                )
                logger.info(f"📊 Updated statistics for {provider_name}: increment_failure")

        except Exception as db_error:
            # Log error but don't fail the test - statistics update is not critical
            logger.error(
                f"Failed to update statistics for {provider_name}: {str(db_error)}"
            )

    def _get_model_name(self, provider_name: str) -> str:
        """
        Get friendly model name for provider.

        Args:
            provider_name: Provider name

        Returns:
            Human-readable model name
        """
        model_names = {
            # Существующие (6)
            "GoogleGemini": "Gemini 2.5 Flash",
            "Groq": "Llama 3.3 70B Versatile",
            "Cerebras": "Llama 3.3 70B",
            "SambaNova": "Meta-Llama-3.3-70B-Instruct",
            "HuggingFace": "Meta-Llama-3-8B-Instruct",
            "Cloudflare": "Llama 3.3 70B FP8 Fast",
            # F003 Фаза 1 (4)
            "DeepSeek": "DeepSeek-V3",
            "Cohere": "Command-R",
            "OpenRouter": "DeepSeek-R1 (free)",
            "GitHubModels": "GPT-4o-mini",
            # F003 Фаза 2 (4)
            "Fireworks": "Llama 3.3 70B",
            "Hyperbolic": "Llama 3.3 70B",
            "Novita": "Llama 3.3 70B",
            "Scaleway": "Llama 3.3 70B",
            # F003 Фаза 3 (2)
            "Kluster": "Llama-3.3-70B",
            "Nebius": "Llama-3.3-70B-Instruct",
        }
        return model_names.get(provider_name, "Unknown Model")
