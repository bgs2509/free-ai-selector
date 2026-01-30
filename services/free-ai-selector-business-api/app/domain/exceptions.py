"""
Domain exceptions for AI Manager Platform - Business API Service

F012: Rate Limit Handling
Иерархия исключений для классификации ошибок провайдеров.

Exception hierarchy:
- ProviderError (base)
  ├── RateLimitError (429)
  ├── ServerError (5xx)
  ├── TimeoutError (connection timeout)
  ├── AuthenticationError (401, 403)
  └── ValidationError (400, 422)
"""

from typing import Optional


class ProviderError(Exception):
    """
    Base exception for all AI provider errors.

    All provider-specific exceptions inherit from this class.
    """

    def __init__(self, message: str, original_exception: Optional[Exception] = None):
        """
        Initialize provider error.

        Args:
            message: Human-readable error message
            original_exception: Original exception that caused this error
        """
        super().__init__(message)
        self.message = message
        self.original_exception = original_exception


class RateLimitError(ProviderError):
    """
    Rate limit exceeded error (HTTP 429 or equivalent).

    This error is NOT counted as a failure in reliability score (FR-5).
    The provider should be temporarily excluded from selection.
    """

    def __init__(
        self,
        message: str,
        retry_after_seconds: Optional[int] = None,
        original_exception: Optional[Exception] = None,
    ):
        """
        Initialize rate limit error.

        Args:
            message: Human-readable error message
            retry_after_seconds: Seconds until retry is allowed (from Retry-After header)
            original_exception: Original exception that caused this error
        """
        super().__init__(message, original_exception)
        self.retry_after_seconds = retry_after_seconds


class ServerError(ProviderError):
    """
    Server-side error (HTTP 5xx).

    This error triggers retry mechanism (FR-2).
    After all retries exhausted, counted as failure.
    """

    pass


class TimeoutError(ProviderError):
    """
    Connection timeout error.

    This error triggers retry mechanism (FR-2).
    After all retries exhausted, counted as failure.
    """

    pass


class AuthenticationError(ProviderError):
    """
    Authentication/authorization error (HTTP 401, 403).

    This error does NOT trigger retry - credentials won't magically become valid.
    Counted as failure immediately.
    """

    pass


class ValidationError(ProviderError):
    """
    Request validation error (HTTP 400, 422).

    This error does NOT trigger retry - request is malformed.
    Counted as failure immediately.
    """

    pass
