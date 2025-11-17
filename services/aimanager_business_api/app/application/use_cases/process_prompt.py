"""
Process Prompt Use Case

Core business logic for AI Manager Platform:
1. Fetch active AI models from Data API
2. Select best model based on reliability score
3. Call AI provider to generate response
4. Update model statistics
5. Record prompt history
"""

import logging
import time
from decimal import Decimal
from typing import Optional

from app.domain.models import AIModelInfo, PromptRequest, PromptResponse
from app.infrastructure.ai_providers.base import AIProviderBase
from app.infrastructure.ai_providers.huggingface import HuggingFaceProvider
from app.infrastructure.ai_providers.replicate import ReplicateProvider
from app.infrastructure.ai_providers.together import TogetherProvider
from app.infrastructure.http_clients.data_api_client import DataAPIClient

logger = logging.getLogger(__name__)


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
        """
        self.data_api_client = data_api_client

        # Initialize AI providers
        self.providers = {
            "HuggingFace": HuggingFaceProvider(),
            "Replicate": ReplicateProvider(),
            "Together.ai": TogetherProvider(),
        }

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
        logger.info(f"Processing prompt for user {request.user_id}")

        # Step 1: Fetch active models from Data API
        models = await self.data_api_client.get_all_models(active_only=True)

        if not models:
            logger.error("No active AI models available")
            raise Exception("No active AI models available")

        # Step 2: Select best model based on reliability score
        best_model = self._select_best_model(models)
        logger.info(
            f"Selected model: {best_model.name} (reliability: {best_model.reliability_score:.3f})"
        )

        # Step 3: Try to generate with selected model
        start_time = time.time()
        response_text = None
        error_message = None
        success = False

        try:
            provider = self._get_provider_for_model(best_model)
            response_text = await provider.generate(request.prompt_text)
            success = True
            logger.info(f"Successfully generated response with {best_model.name}")

        except Exception as e:
            error_message = str(e)
            logger.error(f"Failed to generate with {best_model.name}: {error_message}")

            # Try fallback to next best model
            fallback_model = self._select_fallback_model(models, best_model)
            if fallback_model:
                logger.info(f"Trying fallback model: {fallback_model.name}")
                try:
                    fallback_provider = self._get_provider_for_model(fallback_model)
                    response_text = await fallback_provider.generate(request.prompt_text)
                    success = True
                    best_model = fallback_model  # Use fallback model for stats
                    error_message = None
                    logger.info(f"Fallback successful with {best_model.name}")

                except Exception as fallback_error:
                    logger.error(f"Fallback also failed: {str(fallback_error)}")

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
            logger.error(f"Failed to update model statistics: {str(stats_error)}")

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
            logger.error(f"Failed to record history: {str(history_error)}")

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
        Select best model based on reliability score.

        Args:
            models: List of active models

        Returns:
            Model with highest reliability score
        """
        return max(models, key=lambda m: m.reliability_score)

    def _select_fallback_model(
        self, models: list[AIModelInfo], failed_model: AIModelInfo
    ) -> Optional[AIModelInfo]:
        """
        Select fallback model (second best).

        Args:
            models: List of active models
            failed_model: Model that just failed

        Returns:
            Next best model, or None if no alternatives
        """
        available_models = [m for m in models if m.id != failed_model.id]
        if not available_models:
            return None
        return max(available_models, key=lambda m: m.reliability_score)

    def _get_provider_for_model(self, model: AIModelInfo) -> AIProviderBase:
        """
        Get AI provider instance for given model.

        Args:
            model: AIModelInfo object

        Returns:
            AIProviderBase instance for the model's provider

        Raises:
            ValueError: If provider not found
        """
        provider = self.providers.get(model.provider)
        if provider is None:
            raise ValueError(f"No provider implementation for: {model.provider}")
        return provider
