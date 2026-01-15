"""
Process Prompt Use Case

Core business logic for AI Manager Platform:
1. Fetch active AI models from Data API
2. Select best model based on reliability score
3. Call AI provider to generate response
4. Update model statistics
5. Record prompt history

Note:
    Provider instances are obtained from ProviderRegistry (F008 SSOT).
    Provider metadata (api_format, env_var) is stored in the database.
"""

import time
from decimal import Decimal
from typing import Optional

from app.utils.logger import get_logger
from app.utils.log_helpers import log_decision
from app.utils.security import sanitize_error_message

from app.domain.models import AIModelInfo, PromptRequest, PromptResponse
from app.infrastructure.ai_providers.base import AIProviderBase
from app.infrastructure.ai_providers.registry import ProviderRegistry
from app.infrastructure.http_clients.data_api_client import DataAPIClient

logger = get_logger(__name__)


class ProcessPromptUseCase:
    """
    Use case for processing user prompts with AI.

    Implements the core business logic:
    - Reliability-based model selection
    - AI generation with fallback
    - Statistics tracking
    - History recording
    """

    def __init__(self, data_api_client: DataAPIClient):
        """
        Initialize use case with Data API client.

        Args:
            data_api_client: Client for Data API communication

        Note:
            Provider instances are obtained from ProviderRegistry on demand (F008 SSOT).
            This eliminates hardcoded provider list - providers are defined once in seed.py.
        """
        self.data_api_client = data_api_client

    async def execute(self, request: PromptRequest) -> PromptResponse:
        """
        Execute prompt processing.

        Args:
            request: PromptRequest with user_id and prompt_text

        Returns:
            PromptResponse with generated text and metadata

        Raises:
            Exception: If all providers fail
        """
        # F011-B: Log system_prompt and response_format presence
        logger.info(
            "processing_prompt",
            prompt_length=len(request.prompt_text),
            has_system_prompt=request.system_prompt is not None,
            has_response_format=request.response_format is not None,
        )

        # Step 1: Fetch active models from Data API
        models = await self.data_api_client.get_all_models(active_only=True)

        if not models:
            logger.error("no_active_models_available")
            raise Exception("No active AI models available")

        # Step 2: Select best model based on effective reliability score (F010)
        best_model = self._select_best_model(models)

        # Log the model selection decision with F010 fields
        log_decision(
            logger,
            decision="ACCEPT",
            reason="highest_effective_reliability_score",
            evaluated_conditions={
                "models_count": len(models),
                "selected_model": best_model.name,
                "selected_provider": best_model.provider,
                "effective_score": float(best_model.effective_reliability_score),
                "long_term_score": float(best_model.reliability_score),
                "decision_reason": best_model.decision_reason,
                "recent_request_count": best_model.recent_request_count,
            },
        )

        # Step 3: Try to generate with selected model
        start_time = time.time()
        response_text = None
        error_message = None
        success = False

        try:
            provider = self._get_provider_for_model(best_model)
            # F011-B: Pass system_prompt and response_format to provider
            response_text = await provider.generate(
                request.prompt_text,
                system_prompt=request.system_prompt,
                response_format=request.response_format,
            )
            success = True
            logger.info(
                "generation_success",
                model=best_model.name,
                provider=best_model.provider,
            )

        except Exception as e:
            error_message = sanitize_error_message(e)
            logger.error(
                "generation_failed",
                model=best_model.name,
                provider=best_model.provider,
                error=error_message,
            )

            # Try fallback to next best model
            fallback_model = self._select_fallback_model(models, best_model)
            if fallback_model:
                # Log fallback decision with F010 fields
                log_decision(
                    logger,
                    decision="FALLBACK",
                    reason="primary_model_failed",
                    evaluated_conditions={
                        "failed_model": best_model.name,
                        "fallback_model": fallback_model.name,
                        "fallback_effective_score": float(fallback_model.effective_reliability_score),
                        "fallback_decision_reason": fallback_model.decision_reason,
                    },
                )
                try:
                    fallback_provider = self._get_provider_for_model(fallback_model)
                    # F011-B: Pass system_prompt and response_format to fallback provider
                    response_text = await fallback_provider.generate(
                        request.prompt_text,
                        system_prompt=request.system_prompt,
                        response_format=request.response_format,
                    )
                    success = True
                    best_model = fallback_model  # Use fallback model for stats
                    error_message = None
                    logger.info(
                        "fallback_success",
                        model=best_model.name,
                        provider=best_model.provider,
                    )

                except Exception as fallback_error:
                    logger.error(
                        "fallback_failed",
                        model=fallback_model.name,
                        error=sanitize_error_message(fallback_error),
                    )

        response_time = Decimal(str(time.time() - start_time))

        # Step 4: Update model statistics
        try:
            if success:
                await self.data_api_client.increment_success(
                    model_id=best_model.id, response_time=float(response_time)
                )
            else:
                await self.data_api_client.increment_failure(
                    model_id=best_model.id, response_time=float(response_time)
                )
        except Exception as stats_error:
            logger.error(
                "stats_update_failed",
                model=best_model.name,
                error=sanitize_error_message(stats_error),
            )

        # Step 5: Record prompt history
        try:
            await self.data_api_client.create_history(
                user_id=request.user_id,
                prompt_text=request.prompt_text,
                selected_model_id=best_model.id,
                response_text=response_text,
                response_time=response_time,
                success=success,
                error_message=error_message,
            )
        except Exception as history_error:
            logger.error(
                "history_record_failed",
                error=sanitize_error_message(history_error),
            )

        # Return response
        if not success:
            raise Exception(f"All AI providers failed. Last error: {error_message}")

        return PromptResponse(
            prompt_text=request.prompt_text,
            response_text=response_text or "",
            selected_model_name=best_model.name,
            selected_model_provider=best_model.provider,
            response_time=response_time,
            success=success,
            error_message=error_message,
        )

    def _select_best_model(self, models: list[AIModelInfo]) -> AIModelInfo:
        """
        Select best model based on effective reliability score (F010).

        Uses effective_reliability_score which is either:
        - recent_reliability_score (if >= 3 requests in 7-day window)
        - reliability_score (fallback for cold start)

        Args:
            models: List of active models

        Returns:
            Model with highest effective reliability score
        """
        return max(models, key=lambda m: m.effective_reliability_score)

    def _select_fallback_model(
        self, models: list[AIModelInfo], failed_model: AIModelInfo
    ) -> Optional[AIModelInfo]:
        """
        Select fallback model (second best) based on effective reliability score (F010).

        Args:
            models: List of active models
            failed_model: Model that just failed

        Returns:
            Next best model, or None if no alternatives
        """
        available_models = [m for m in models if m.id != failed_model.id]
        if not available_models:
            return None
        return max(available_models, key=lambda m: m.effective_reliability_score)

    def _get_provider_for_model(self, model: AIModelInfo) -> AIProviderBase:
        """
        Get AI provider instance for given model (F008 SSOT).

        Uses ProviderRegistry singleton to get cached provider instances.
        Provider class mapping is defined in registry.py (SSOT for class→implementation).
        Provider metadata (api_format, env_var) comes from database via Data API.

        Args:
            model: AIModelInfo object with provider name

        Returns:
            AIProviderBase instance for the model's provider

        Raises:
            ValueError: If provider class not found in registry
        """
        provider = ProviderRegistry.get_provider(model.provider)
        if provider is None:
            raise ValueError(f"Provider '{model.provider}' not configured in registry")
        return provider
