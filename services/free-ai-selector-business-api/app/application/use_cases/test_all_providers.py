"""
Test All Providers Use Case

Tests all registered AI providers with a simple prompt,
returns results with response times or error details,
and updates database statistics for reliability tracking.

Note:
    Provider list comes from Data API (F008 SSOT).
    Provider instances are obtained from ProviderRegistry.
    Model names are fetched from database, not hardcoded.
"""

import logging
import time
from typing import Any, Optional

from app.domain.models import AIModelInfo
from app.utils.security import sanitize_error_message
from app.infrastructure.ai_providers.base import AIProviderBase
from app.infrastructure.ai_providers.registry import ProviderRegistry
from app.infrastructure.http_clients.data_api_client import DataAPIClient

logger = logging.getLogger(__name__)


class TestAllProvidersUseCase:
    """
    Use case for testing all AI providers (F008 SSOT).

    Sends a simple test prompt to each provider and collects:
    - Success/failure status
    - Response time for successful calls
    - Error type and message for failed calls

    Provider list is fetched from Data API (SSOT in database).
    Provider instances are obtained from ProviderRegistry.

    Additionally updates database statistics to improve reliability scores.
    This makes /test command the third source of reliability data alongside
    user prompts and health worker checks.
    """

    # Test prompt - simple and universal
    TEST_PROMPT = "Hello! Please respond with 'OK' if you can read this message."

    def __init__(self, data_api_client: DataAPIClient):
        """
        Initialize use case with Data API client.

        Args:
            data_api_client: Client for Data API communication and statistics updates

        Note:
            Provider list comes from Data API on execute() (F008 SSOT).
            Provider instances are obtained from ProviderRegistry on demand.
        """
        self.data_api_client = data_api_client

    async def execute(self) -> list[dict[str, Any]]:
        """
        Execute provider testing (F008 SSOT).

        Fetches provider list from Data API (SSOT), then tests each provider
        with a simple prompt and measures response time.
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

        # F008 SSOT: Fetch models from Data API (instead of hardcoded list)
        models = await self.data_api_client.get_all_models(active_only=False)
        logger.info(f"Fetched {len(models)} models from Data API")

        results = []

        for model in models:
            # Get provider instance from registry
            provider = ProviderRegistry.get_provider(model.provider)
            if provider is None:
                # Provider class not in registry - skip with warning
                logger.warning(
                    f"Provider '{model.provider}' not found in registry, skipping"
                )
                results.append({
                    "provider": model.provider,
                    "model": model.name,
                    "status": "error",
                    "response_time": None,
                    "error": f"Provider class not configured in registry",
                })
                continue

            result = await self._test_provider(model, provider)
            results.append(result)

        # Sort results: successful first (by response time), then failures
        results.sort(
            key=lambda r: (r["status"] != "success", r.get("response_time") or float("inf"))
        )

        logger.info(f"Provider testing completed: {len(results)} providers tested")
        return results

    async def _test_provider(
        self, model: AIModelInfo, provider: AIProviderBase
    ) -> dict[str, Any]:
        """
        Test a single provider and update database statistics (F008 SSOT).

        Args:
            model: AIModelInfo from database (SSOT for model name and provider)
            provider: Provider instance from ProviderRegistry

        Returns:
            Test result dictionary
        """
        logger.info(f"Testing provider: {model.provider}")

        result = {
            "provider": model.provider,
            "model": model.name,  # F008: Model name from DB, not hardcoded
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
                    f"✅ {model.provider} responded in {response_time:.2f}s: {response[:50]}..."
                )
            else:
                result["status"] = "error"
                result["error"] = "Empty response received"
                logger.warning(f"⚠️ {model.provider} returned empty response")

        except Exception as e:
            error_type = type(e).__name__
            # БЕЗОПАСНОСТЬ: Sanitize сообщения об ошибках для скрытия API ключей
            error_message = sanitize_error_message(e)

            result["status"] = "error"
            result["error"] = f"{error_type}: {error_message}"

            logger.error(f"❌ {model.provider} failed: {error_type}: {error_message}")

        # Update database statistics (F008: model already has ID from DB)
        await self._update_model_statistics(model, result)

        return result

    async def _update_model_statistics(
        self, model: AIModelInfo, test_result: dict[str, Any]
    ) -> None:
        """
        Update model statistics in database based on test result (F008 SSOT).

        Args:
            model: AIModelInfo from database (already contains model.id)
            test_result: Test result dictionary with status and response_time
        """
        try:
            if test_result["status"] == "success":
                response_time = test_result.get("response_time") or 0.0
                await self.data_api_client.increment_success(
                    model_id=model.id, response_time=response_time
                )
                logger.info(
                    f"📊 Updated statistics for {model.provider}: increment_success (time: {response_time:.2f}s)"
                )
            else:
                # For failures, use 0.0 as response time or a default timeout value
                response_time = test_result.get("response_time") or 0.0
                await self.data_api_client.increment_failure(
                    model_id=model.id, response_time=response_time
                )
                logger.info(f"📊 Updated statistics for {model.provider}: increment_failure")

        except Exception as db_error:
            # Log error but don't fail the test - statistics update is not critical
            logger.error(
                f"Failed to update statistics for {model.provider}: {sanitize_error_message(db_error)}"
            )
