"""
Process Prompt Use Case

Core business logic for AI Manager Platform:
1. Fetch active AI models from Data API
2. Select best model based on reliability score
3. Call AI provider to generate response (with retry for 5xx/timeout)
4. Update model statistics
5. Record prompt history

F012: Rate Limit Handling
- Error Classification: classify errors by type
- Retry Mechanism: exponential backoff for 5xx/timeout (F023)
- Availability Cooldown: 429 → set_availability()
- Full Fallback: iterate through all available models
- Graceful Degradation: 429 doesn't reduce reliability_score

F023: Error Resilience and Telemetry
- Cooldown 24h for AuthenticationError (401/402/403) and ValidationError (404)
- Exponential backoff: 2s → 4s → 8s with jitter (MAX_RETRIES=3)
- Per-request telemetry: attempts, fallback_used in response

Note:
    Provider instances are obtained from ProviderRegistry (F008 SSOT).
    Provider metadata (api_format) is stored in the database.
    API key env var names are resolved via ProviderRegistry (F018 SSOT).
"""

import os
import time
from decimal import Decimal
from typing import Optional

from app.application.services.error_classifier import classify_error
from app.application.services.retry_service import retry_with_exponential_backoff
from app.domain.exceptions import (
    AuthenticationError,
    ProviderError,
    RateLimitError,
    ServerError,
    TimeoutError,
    ValidationError,
)
from app.domain.models import AIModelInfo, PromptRequest, PromptResponse
from app.infrastructure.ai_providers.base import AIProviderBase
from app.infrastructure.ai_providers.registry import ProviderRegistry
from app.infrastructure.http_clients.data_api_client import DataAPIClient
from app.utils.log_helpers import log_decision
from app.utils.logger import get_logger
from app.utils.security import sanitize_error_message

logger = get_logger(__name__)

# F012: Configuration
RATE_LIMIT_DEFAULT_COOLDOWN = int(os.getenv("RATE_LIMIT_DEFAULT_COOLDOWN", "3600"))

# F022: Payload budget — максимальный размер промпта перед отправкой провайдеру
MAX_PROMPT_CHARS = int(os.getenv("MAX_PROMPT_CHARS", "6000"))

# F023: Cooldown для постоянных ошибок (auth, validation)
AUTH_ERROR_COOLDOWN_SECONDS = int(os.getenv("AUTH_ERROR_COOLDOWN_SECONDS", "86400"))
VALIDATION_ERROR_COOLDOWN_SECONDS = int(os.getenv("VALIDATION_ERROR_COOLDOWN_SECONDS", "86400"))


class ProcessPromptUseCase:
    """
    Use case for processing user prompts with AI.

    Implements the core business logic:
    - Reliability-based model selection
    - AI generation with retry and full fallback (F012)
    - Error classification and graceful degradation
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
        Execute prompt processing with F012 rate limit handling.

        Full fallback loop:
        1. Get available models (active_only + available_only)
        2. Filter to configured providers only (has API key)
        3. Sort by effective_reliability_score
        4. Try each model with retry for 5xx/timeout
        5. On 429: set_availability() and continue to next model
        6. On success: record stats and return

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
            has_model_id=request.model_id is not None,
            requested_model_id=request.model_id,
            has_system_prompt=request.system_prompt is not None,
            has_response_format=request.response_format is not None,
        )

        # Step 1: Fetch available models from Data API (F012: available_only)
        models = await self.data_api_client.get_all_models(
            active_only=True,
            available_only=True,
            include_recent=True,
        )

        if not models:
            logger.error("no_active_models_available")
            raise Exception("No active AI models available")

        # Step 2: Filter to configured providers only (FR-8)
        configured_models = self._filter_configured_models(models)

        if not configured_models:
            logger.error(
                "no_configured_models_available",
                total_models=len(models),
            )
            raise Exception("No configured AI models available (missing API keys)")

        # Step 3: Sort by effective reliability score (F010)
        sorted_models = sorted(
            configured_models,
            key=lambda m: m.effective_reliability_score,
            reverse=True,
        )

        candidate_models, requested_model_found = self._build_candidate_models(
            sorted_models=sorted_models,
            requested_model_id=request.model_id,
        )
        first_model = candidate_models[0]
        selection_mode = "auto"
        selection_reason = "highest_effective_reliability_score"
        if request.model_id is not None:
            if requested_model_found:
                selection_mode = "forced_first"
                selection_reason = "requested_model_id"
            else:
                selection_mode = "forced_not_found"

        # Log initial selection
        log_decision(
            logger,
            decision="ACCEPT",
            reason=selection_reason,
            evaluated_conditions={
                "models_count": len(candidate_models),
                "selected_model": first_model.name,
                "selected_provider": first_model.provider,
                "effective_score": float(first_model.effective_reliability_score),
                "long_term_score": float(first_model.reliability_score),
                "decision_reason": first_model.decision_reason,
                "recent_request_count": first_model.recent_request_count,
                "requested_model_id": request.model_id,
                "requested_model_found": requested_model_found,
                "selection_mode": selection_mode,
            },
        )

        # F022: Payload budget — обрезка промпта для предотвращения HTTP 422
        if len(request.prompt_text) > MAX_PROMPT_CHARS:
            logger.warning(
                "prompt_truncated",
                original_length=len(request.prompt_text),
                max_length=MAX_PROMPT_CHARS,
            )
            request = PromptRequest(
                user_id=request.user_id,
                prompt_text=request.prompt_text[:MAX_PROMPT_CHARS],
                model_id=request.model_id,
                system_prompt=request.system_prompt,
                response_format=request.response_format,
            )

        # Step 4: Full fallback loop (F012: FR-9)
        start_time = time.time()
        last_error_message: Optional[str] = None
        successful_model: Optional[AIModelInfo] = None
        response_text: Optional[str] = None
        # F023: Telemetry counters
        attempts = 0

        for model in candidate_models:
            attempts += 1
            try:
                provider = self._get_provider_for_model(model)

                # Generate with retry for 5xx/timeout (F012: FR-2)
                response_text = await self._generate_with_retry(
                    provider=provider,
                    request=request,
                    model=model,
                )

                # Success!
                successful_model = model
                logger.info(
                    "generation_success",
                    model=model.name,
                    provider=model.provider,
                )
                break

            except RateLimitError as e:
                # F014: Rate limit - don't count as failure, set availability
                await self._handle_rate_limit(model, e)
                last_error_message = sanitize_error_message(e)

            except (
                ServerError,
                TimeoutError,
                AuthenticationError,
                ValidationError,
                ProviderError,
            ) as e:
                # F014: Transient errors - record as failure
                await self._handle_transient_error(model, e, start_time)
                last_error_message = sanitize_error_message(e)

            except Exception as e:
                # F014: Unexpected error - classify and handle
                classified = classify_error(e)
                if isinstance(classified, RateLimitError):
                    await self._handle_rate_limit(model, classified)
                else:
                    await self._handle_transient_error(model, classified, start_time)
                last_error_message = sanitize_error_message(e)

        response_time = Decimal(str(time.time() - start_time))

        # Check if any model succeeded
        if successful_model is None or response_text is None:
            # All models failed
            logger.error(
                "all_models_failed",
                models_tried=len(candidate_models),
                last_error=last_error_message,
            )

            # Record history with failure
            try:
                await self.data_api_client.create_history(
                    user_id=request.user_id,
                    prompt_text=request.prompt_text,
                    selected_model_id=candidate_models[0].id,
                    response_text=None,
                    response_time=response_time,
                    success=False,
                    error_message=last_error_message,
                )
            except Exception as history_error:
                logger.error(
                    "history_record_failed",
                    error=sanitize_error_message(history_error),
                )

            raise Exception(f"All AI providers failed. Last error: {last_error_message}")

        # Step 5: Update success statistics
        try:
            await self.data_api_client.increment_success(
                model_id=successful_model.id, response_time=float(response_time)
            )
        except Exception as stats_error:
            logger.error(
                "stats_update_failed",
                model=successful_model.name,
                error=sanitize_error_message(stats_error),
            )

        # Step 6: Record prompt history
        try:
            await self.data_api_client.create_history(
                user_id=request.user_id,
                prompt_text=request.prompt_text,
                selected_model_id=successful_model.id,
                response_text=response_text,
                response_time=response_time,
                success=True,
                error_message=None,
            )
        except Exception as history_error:
            logger.error(
                "history_record_failed",
                error=sanitize_error_message(history_error),
            )

        return PromptResponse(
            prompt_text=request.prompt_text,
            response_text=response_text,
            selected_model_name=successful_model.name,
            selected_model_provider=successful_model.provider,
            response_time=response_time,
            success=True,
            error_message=None,
            # F023: Per-request telemetry
            attempts=attempts,
            fallback_used=(successful_model.id != first_model.id),
        )

    def _build_candidate_models(
        self,
        sorted_models: list[AIModelInfo],
        requested_model_id: Optional[int],
    ) -> tuple[list[AIModelInfo], bool]:
        """
        Build model candidates for execution.

        If requested_model_id is provided and found in sorted_models,
        that model is tried first and the remaining models keep their score order.

        Returns:
            Tuple of (candidate_models, requested_model_found)
        """
        if requested_model_id is None:
            return sorted_models, False

        requested_model = next((model for model in sorted_models if model.id == requested_model_id), None)
        if requested_model is None:
            return sorted_models, False

        remaining_models = [model for model in sorted_models if model.id != requested_model.id]
        return [requested_model, *remaining_models], True

    def _filter_configured_models(self, models: list[AIModelInfo]) -> list[AIModelInfo]:
        """
        Filter models to only those with configured API keys (FR-8, F018 SSOT).

        A model is "configured" if ProviderRegistry knows its env_var name
        AND the corresponding environment variable contains a non-empty value.

        Args:
            models: List of all active models

        Returns:
            List of models with configured API keys
        """
        configured = []
        for model in models:
            env_var = ProviderRegistry.get_api_key_env(model.provider)
            if not env_var:
                continue
            api_key = os.getenv(env_var, "")
            if api_key:
                configured.append(model)
            else:
                logger.debug(
                    "model_not_configured",
                    model=model.name,
                    env_var=env_var,
                )
        return configured

    async def _generate_with_retry(
        self,
        provider: AIProviderBase,
        request: PromptRequest,
        model: AIModelInfo,
    ) -> str:
        """
        Generate response with retry for retryable errors.

        Uses retry_with_exponential_backoff for ServerError and TimeoutError (F023).
        RateLimitError and other errors are raised immediately.

        Args:
            provider: AI provider instance
            request: Prompt request
            model: Model info for logging

        Returns:
            Generated response text

        Raises:
            RateLimitError: If rate limit detected
            ServerError: If server error after all retries
            TimeoutError: If timeout after all retries
            AuthenticationError: If authentication fails
            ValidationError: If request validation fails
            ProviderError: For other provider errors
        """

        async def generate_func() -> str:
            return await provider.generate(
                request.prompt_text,
                system_prompt=request.system_prompt,
                response_format=request.response_format,
            )

        return await retry_with_exponential_backoff(
            func=generate_func,
            provider_name=model.provider,
            model_name=model.name,
        )

    def _get_provider_for_model(self, model: AIModelInfo) -> AIProviderBase:
        """
        Get AI provider instance for given model (F008 SSOT).

        Uses ProviderRegistry singleton to get cached provider instances.
        Provider class mapping is defined in registry.py (SSOT for class→implementation).
        Provider metadata (api_format) comes from database via Data API.

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

    async def _handle_rate_limit(
        self,
        model: AIModelInfo,
        error: RateLimitError,
    ) -> None:
        """
        Handle rate limit error: set availability cooldown (F012: FR-5, F014).

        Rate limit errors are NOT counted as failures to preserve
        reliability_score for graceful degradation.

        Args:
            model: Model info for logging and API calls
            error: RateLimitError with optional retry_after_seconds
        """
        retry_after = error.retry_after_seconds or RATE_LIMIT_DEFAULT_COOLDOWN
        logger.warning(
            "rate_limit_detected",
            model=model.name,
            provider=model.provider,
            retry_after_seconds=retry_after,
        )
        try:
            await self.data_api_client.set_availability(model.id, retry_after)
        except Exception as avail_error:
            logger.error(
                "set_availability_failed",
                model=model.name,
                error=sanitize_error_message(avail_error),
            )

    async def _handle_transient_error(
        self,
        model: AIModelInfo,
        error: Exception,
        start_time: float,
    ) -> None:
        """
        Handle transient error: log, optionally set cooldown, and record failure.

        F023: AuthenticationError и ValidationError получают cooldown 24ч
        в дополнение к increment_failure.

        Args:
            model: Model info for logging and API calls
            error: Exception that caused the failure
            start_time: Request start time for response_time calculation
        """
        response_time = Decimal(str(time.time() - start_time))
        logger.error(
            "generation_failed",
            model=model.name,
            provider=model.provider,
            error_type=type(error).__name__,
            error=sanitize_error_message(error),
        )

        # F023 FR-001/FR-002: Cooldown для постоянных ошибок
        if isinstance(error, AuthenticationError):
            await self._set_cooldown_safe(
                model, AUTH_ERROR_COOLDOWN_SECONDS, type(error).__name__
            )
        elif isinstance(error, ValidationError):
            await self._set_cooldown_safe(
                model, VALIDATION_ERROR_COOLDOWN_SECONDS, type(error).__name__
            )

        try:
            await self.data_api_client.increment_failure(
                model_id=model.id,
                response_time=float(response_time),
            )
        except Exception as stats_error:
            logger.error(
                "stats_update_failed",
                model=model.name,
                error=sanitize_error_message(stats_error),
            )

    async def _set_cooldown_safe(
        self,
        model: AIModelInfo,
        cooldown_seconds: int,
        error_type: str,
    ) -> None:
        """
        Set provider cooldown with graceful error handling (F023).

        Args:
            model: Model info for logging and API calls
            cooldown_seconds: Duration of cooldown in seconds
            error_type: Error type name for logging
        """
        logger.warning(
            "permanent_error_cooldown",
            model=model.name,
            provider=model.provider,
            error_type=error_type,
            cooldown_seconds=cooldown_seconds,
        )
        try:
            await self.data_api_client.set_availability(model.id, cooldown_seconds)
        except Exception as avail_error:
            logger.error(
                "set_availability_failed",
                model=model.name,
                error=sanitize_error_message(avail_error),
            )
