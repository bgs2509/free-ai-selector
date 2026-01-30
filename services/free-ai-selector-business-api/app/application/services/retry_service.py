"""
Retry Service for AI Provider Calls

F012: Rate Limit Handling
Реализует механизм retry с фиксированной задержкой для 5xx/timeout ошибок.

Configuration:
- MAX_RETRIES: Maximum number of retry attempts (default: 10)
- RETRY_DELAY_SECONDS: Fixed delay between retries (default: 10)
"""

import asyncio
import os
from typing import Awaitable, Callable, TypeVar

from app.application.services.error_classifier import classify_error, is_retryable
from app.domain.exceptions import ProviderError
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Configuration from environment
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "10"))
RETRY_DELAY_SECONDS = int(os.getenv("RETRY_DELAY_SECONDS", "10"))

T = TypeVar("T")


async def retry_with_fixed_delay(
    func: Callable[[], Awaitable[T]],
    max_retries: int = MAX_RETRIES,
    delay_seconds: int = RETRY_DELAY_SECONDS,
    provider_name: str = "unknown",
    model_name: str = "unknown",
) -> T:
    """
    Execute async function with retry on retryable errors.

    Retries only for ServerError and TimeoutError.
    RateLimitError, AuthenticationError, ValidationError are NOT retried.

    Args:
        func: Async function to execute (should raise on error)
        max_retries: Maximum number of retry attempts
        delay_seconds: Fixed delay between retries in seconds
        provider_name: Provider name for logging
        model_name: Model name for logging

    Returns:
        Result of successful function call

    Raises:
        ProviderError: Classified error after all retries exhausted or non-retryable error
    """
    last_error: ProviderError | None = None

    for attempt in range(max_retries + 1):
        try:
            return await func()

        except Exception as e:
            # Classify the error
            classified_error = classify_error(e)

            # Check if error is retryable
            if not is_retryable(classified_error):
                # Non-retryable errors (RateLimitError, AuthenticationError, etc.)
                # raise immediately without retry
                logger.warning(
                    "non_retryable_error",
                    provider=provider_name,
                    model=model_name,
                    error_type=type(classified_error).__name__,
                    attempt=attempt + 1,
                )
                raise classified_error

            last_error = classified_error

            # Check if we have retries left
            if attempt < max_retries:
                logger.warning(
                    "retry_attempt",
                    provider=provider_name,
                    model=model_name,
                    error_type=type(classified_error).__name__,
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    delay_seconds=delay_seconds,
                )
                await asyncio.sleep(delay_seconds)
            else:
                # All retries exhausted
                logger.error(
                    "all_retries_exhausted",
                    provider=provider_name,
                    model=model_name,
                    error_type=type(classified_error).__name__,
                    total_attempts=max_retries + 1,
                )

    # Should not reach here, but just in case
    if last_error:
        raise last_error
    raise RuntimeError("Unexpected state in retry loop")
