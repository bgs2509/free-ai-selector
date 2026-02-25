"""
Retry Service for AI Provider Calls

F012: Rate Limit Handling
F023: Exponential backoff с jitter

Configuration:
- MAX_RETRIES: Maximum number of retry attempts (default: 3)
- RETRY_BASE_DELAY: Base delay for exponential backoff in seconds (default: 2.0)
- RETRY_MAX_DELAY: Maximum delay cap in seconds (default: 30.0)
- RETRY_JITTER: Maximum random jitter in seconds (default: 1.0)
"""

import asyncio
import os
import random
from typing import Awaitable, Callable, TypeVar

from app.application.services.error_classifier import classify_error, is_retryable
from app.domain.exceptions import ProviderError
from app.utils.logger import get_logger

logger = get_logger(__name__)

# F023: Configuration from environment
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_BASE_DELAY = float(os.getenv("RETRY_BASE_DELAY", "2.0"))
RETRY_MAX_DELAY = float(os.getenv("RETRY_MAX_DELAY", "30.0"))
RETRY_JITTER = float(os.getenv("RETRY_JITTER", "1.0"))

# Deprecated: сохранено для обратной совместимости env и тестов
RETRY_DELAY_SECONDS = int(os.getenv("RETRY_DELAY_SECONDS", "10"))

T = TypeVar("T")


async def retry_with_exponential_backoff(
    func: Callable[[], Awaitable[T]],
    max_retries: int = MAX_RETRIES,
    base_delay: float = RETRY_BASE_DELAY,
    max_delay: float = RETRY_MAX_DELAY,
    jitter: float = RETRY_JITTER,
    provider_name: str = "unknown",
    model_name: str = "unknown",
) -> T:
    """
    Execute async function with retry and exponential backoff (F023).

    Delay formula: min(base_delay * 2^attempt, max_delay) + random.uniform(0, jitter)

    Retries only for ServerError and TimeoutError.
    RateLimitError, AuthenticationError, ValidationError are NOT retried.

    Args:
        func: Async function to execute (should raise on error)
        max_retries: Maximum number of retry attempts
        base_delay: Base delay for exponential backoff (seconds)
        max_delay: Maximum delay cap (seconds)
        jitter: Maximum random jitter (seconds)
        provider_name: Provider name for logging
        model_name: Model name for logging

    Returns:
        Result of successful function call

    Raises:
        ProviderError: Classified error after all retries exhausted
                       or non-retryable error
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
                delay = min(base_delay * (2 ** attempt), max_delay)
                actual_delay = delay + random.uniform(0, jitter)
                logger.warning(
                    "retry_attempt",
                    provider=provider_name,
                    model=model_name,
                    error_type=type(classified_error).__name__,
                    attempt=attempt + 1,
                    max_retries=max_retries,
                    next_delay_seconds=round(actual_delay, 2),
                )
                await asyncio.sleep(actual_delay)
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


# FR-021: Deprecated alias для обратной совместимости
async def retry_with_fixed_delay(
    func: Callable[[], Awaitable[T]],
    max_retries: int = MAX_RETRIES,
    delay_seconds: int = RETRY_DELAY_SECONDS,
    provider_name: str = "unknown",
    model_name: str = "unknown",
) -> T:
    """
    Deprecated: Use retry_with_exponential_backoff instead.

    Сохранено для обратной совместимости тестов.
    Маппинг: delay_seconds -> base_delay=delay_seconds, max_delay=delay_seconds, jitter=0.
    """
    return await retry_with_exponential_backoff(
        func=func,
        max_retries=max_retries,
        base_delay=float(delay_seconds),
        max_delay=float(delay_seconds),
        jitter=0,
        provider_name=provider_name,
        model_name=model_name,
    )
