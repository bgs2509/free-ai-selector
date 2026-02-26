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

import time
from typing import Any

from app.domain.models import AIModelInfo
from app.utils.security import sanitize_error_message
from app.infrastructure.ai_providers.base import AIProviderBase
from app.infrastructure.ai_providers.registry import ProviderRegistry
from app.infrastructure.http_clients.data_api_client import DataAPIClient
from app.utils.logger import get_logger
from app.utils.audit import audit_event

logger = get_logger(__name__)


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

        # Берём только активные модели, чтобы не тестировать выключенные записи
        models = await self.data_api_client.get_all_models(active_only=True)
        logger.info(f"Fetched {len(models)} active models from Data API")

        # Фильтрация: только провайдеры из registry и только одна модель на провайдера
        registry_providers = set(ProviderRegistry.get_all_provider_names())
        filtered_models: list[AIModelInfo] = []
        seen_providers: set[str] = set()
        skipped_unregistered = 0
        skipped_duplicates = 0

        for model in models:
            if model.provider not in registry_providers:
                skipped_unregistered += 1
                logger.info(
                    "Skipping model with unregistered provider",
                    provider=model.provider,
                    model_id=model.id,
                    model=model.name,
                )
                continue

            if model.provider in seen_providers:
                skipped_duplicates += 1
                logger.info(
                    "Skipping duplicate provider model",
                    provider=model.provider,
                    model_id=model.id,
                    model=model.name,
                )
                continue

            seen_providers.add(model.provider)
            filtered_models.append(model)

        logger.info(
            "Prepared provider test set",
            total_models=len(models),
            filtered_models=len(filtered_models),
            skipped_unregistered=skipped_unregistered,
            skipped_duplicates=skipped_duplicates,
        )

        results = []

        for model in filtered_models:
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
                    "error": "Provider class not configured in registry",
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
        logger.info(
            "model_call_start",
            model_id=model.id,
            model=model.name,
            provider=model.provider,
            source="providers_test",
        )
        audit_event(
            "model_call_start",
            {
                "model_id": model.id,
                "model": model.name,
                "provider": model.provider,
                "source": "providers_test",
            },
        )

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
                    f"✅ {model.provider} responded in {response_time:.2f}s (chars={len(response)})"
                )
                logger.info(
                    "model_call_success",
                    model_id=model.id,
                    model=model.name,
                    provider=model.provider,
                    source="providers_test",
                    duration_ms=round(response_time * 1000.0, 2),
                    response_chars=len(response),
                )
                audit_event(
                    "model_call_success",
                    {
                        "model_id": model.id,
                        "model": model.name,
                        "provider": model.provider,
                        "source": "providers_test",
                        "duration_ms": round(response_time * 1000.0, 2),
                        "response_chars": len(response),
                    },
                )
            else:
                result["status"] = "error"
                result["error"] = "Empty response received"
                logger.warning(f"⚠️ {model.provider} returned empty response")
                logger.warning(
                    "model_call_error",
                    model_id=model.id,
                    model=model.name,
                    provider=model.provider,
                    source="providers_test",
                    error_type="EmptyResponse",
                    error="Empty response received",
                )
                audit_event(
                    "model_call_error",
                    {
                        "model_id": model.id,
                        "model": model.name,
                        "provider": model.provider,
                        "source": "providers_test",
                        "error_type": "EmptyResponse",
                        "error": "Empty response received",
                    },
                )

        except Exception as e:
            error_type = type(e).__name__
            # БЕЗОПАСНОСТЬ: Sanitize сообщения об ошибках для скрытия API ключей
            error_message = sanitize_error_message(e)

            result["status"] = "error"
            result["error"] = f"{error_type}: {error_message}"

            logger.error(f"❌ {model.provider} failed: {error_type}: {error_message}")
            logger.warning(
                "model_call_error",
                model_id=model.id,
                model=model.name,
                provider=model.provider,
                source="providers_test",
                error_type=error_type,
                error=error_message,
            )
            audit_event(
                "model_call_error",
                {
                    "model_id": model.id,
                    "model": model.name,
                    "provider": model.provider,
                    "source": "providers_test",
                    "error_type": error_type,
                    "error": error_message,
                },
            )

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
