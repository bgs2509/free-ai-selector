"""
Error Classification Service for AI Providers

F012: Rate Limit Handling
Классифицирует исключения провайдеров по типам для корректной обработки.

Classification rules:
- 429 → RateLimitError
- 500 with "429" in text → RateLimitError (some providers wrap 429)
- 5xx → ServerError
- Timeout → TimeoutError
- 401, 402, 403 → AuthenticationError
- 400, 404, 422 → ValidationError
"""

from email.utils import parsedate_to_datetime
from typing import Optional

import httpx

from app.domain.exceptions import (
    AuthenticationError,
    ProviderError,
    RateLimitError,
    ServerError,
    TimeoutError,
    ValidationError,
)


def classify_error(exception: Exception) -> ProviderError:
    """
    Classify provider exception into a specific ProviderError type.

    Args:
        exception: Original exception from AI provider

    Returns:
        Classified ProviderError subclass instance
    """
    # Already classified ProviderError subclasses - return as is
    if isinstance(exception, ProviderError):
        return exception

    # Timeout exceptions
    if isinstance(exception, (httpx.TimeoutException, httpx.ConnectTimeout, httpx.ReadTimeout)):
        return TimeoutError(
            message=str(exception),
            original_exception=exception,
        )

    # HTTP status errors
    if isinstance(exception, httpx.HTTPStatusError):
        status_code = exception.response.status_code
        response_text = exception.response.text

        # Check for rate limit (429 or 500 with "429" in body)
        if status_code == 429 or (status_code == 500 and "429" in response_text):
            retry_after = _parse_retry_after(exception.response.headers)
            return RateLimitError(
                message=str(exception),
                retry_after_seconds=retry_after,
                original_exception=exception,
            )

        # Server errors (5xx)
        if 500 <= status_code < 600:
            return ServerError(
                message=str(exception),
                original_exception=exception,
            )

        # Authentication errors (401, 403)
        if status_code in (401, 403):
            return AuthenticationError(
                message=str(exception),
                original_exception=exception,
            )

        # Validation errors (400, 422)
        if status_code in (400, 422):
            return ValidationError(
                message=str(exception),
                original_exception=exception,
            )

        # F022: Payment required (402) — free tier exhausted
        if status_code == 402:
            return AuthenticationError(
                message=f"Payment required: {str(exception)}",
                original_exception=exception,
            )

        # F022: Not found (404) — wrong endpoint or model ID
        if status_code == 404:
            return ValidationError(
                message=f"Endpoint or model not found: {str(exception)}",
                original_exception=exception,
            )

    # Unknown exceptions - wrap as generic ProviderError
    return ProviderError(
        message=str(exception),
        original_exception=exception,
    )


def _parse_retry_after(headers: httpx.Headers) -> Optional[int]:
    """
    Parse Retry-After header value.

    The header can be:
    - Integer seconds: "60"
    - HTTP date: "Wed, 21 Oct 2026 07:28:00 GMT"

    Args:
        headers: HTTP response headers

    Returns:
        Seconds until retry is allowed, or None if header not present/parseable
    """
    retry_after = headers.get("Retry-After")
    if retry_after is None:
        return None

    # Try integer seconds first
    if retry_after.isdigit():
        return int(retry_after)

    # Try HTTP date format
    try:
        retry_date = parsedate_to_datetime(retry_after)
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        delta = retry_date - now
        return max(0, int(delta.total_seconds()))
    except (ValueError, TypeError):
        pass

    return None


def is_retryable(error: ProviderError) -> bool:
    """
    Check if error should trigger retry mechanism.

    Only ServerError and TimeoutError should be retried.
    RateLimitError should NOT be retried - instead, fallback to next model.
    AuthenticationError and ValidationError should NOT be retried.

    Args:
        error: Classified provider error

    Returns:
        True if error should trigger retry
    """
    return isinstance(error, (ServerError, TimeoutError))
