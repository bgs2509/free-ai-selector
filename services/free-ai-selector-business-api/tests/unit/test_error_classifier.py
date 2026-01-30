"""
Unit tests for Error Classifier Service (F012: Rate Limit Handling)
"""

import pytest
import httpx
from httpx import Response, Request

from app.application.services.error_classifier import classify_error, is_retryable, _parse_retry_after
from app.domain.exceptions import (
    AuthenticationError,
    ProviderError,
    RateLimitError,
    ServerError,
    TimeoutError,
    ValidationError,
)


@pytest.mark.unit
class TestClassifyError:
    """Test error classification (F012: FR-1)."""

    def test_classify_timeout_exception(self):
        """Test that TimeoutException is classified as TimeoutError."""
        exception = httpx.TimeoutException("Connection timed out")
        result = classify_error(exception)

        assert isinstance(result, TimeoutError)
        assert "timed out" in result.message

    def test_classify_connect_timeout(self):
        """Test that ConnectTimeout is classified as TimeoutError."""
        exception = httpx.ConnectTimeout("Connect timeout")
        result = classify_error(exception)

        assert isinstance(result, TimeoutError)

    def test_classify_read_timeout(self):
        """Test that ReadTimeout is classified as TimeoutError."""
        exception = httpx.ReadTimeout("Read timeout")
        result = classify_error(exception)

        assert isinstance(result, TimeoutError)

    def test_classify_429_as_rate_limit(self):
        """Test that HTTP 429 is classified as RateLimitError (F012: FR-1)."""
        request = Request("POST", "https://api.test.com")
        response = Response(429, request=request, headers={"Retry-After": "60"})
        exception = httpx.HTTPStatusError("Rate limited", request=request, response=response)

        result = classify_error(exception)

        assert isinstance(result, RateLimitError)
        assert result.retry_after_seconds == 60

    def test_classify_500_with_429_in_body_as_rate_limit(self):
        """Test that HTTP 500 with '429' in body is classified as RateLimitError (F012: FR-1)."""
        request = Request("POST", "https://api.test.com")
        response = Response(
            500,
            request=request,
            content=b'{"error": "Upstream returned 429 too many requests"}',
        )
        exception = httpx.HTTPStatusError("Server error", request=request, response=response)

        result = classify_error(exception)

        assert isinstance(result, RateLimitError)

    def test_classify_500_as_server_error(self):
        """Test that HTTP 500 (without 429 in body) is classified as ServerError."""
        request = Request("POST", "https://api.test.com")
        response = Response(500, request=request, content=b'{"error": "Internal server error"}')
        exception = httpx.HTTPStatusError("Server error", request=request, response=response)

        result = classify_error(exception)

        assert isinstance(result, ServerError)

    def test_classify_502_as_server_error(self):
        """Test that HTTP 502 is classified as ServerError."""
        request = Request("POST", "https://api.test.com")
        response = Response(502, request=request)
        exception = httpx.HTTPStatusError("Bad gateway", request=request, response=response)

        result = classify_error(exception)

        assert isinstance(result, ServerError)

    def test_classify_503_as_server_error(self):
        """Test that HTTP 503 is classified as ServerError."""
        request = Request("POST", "https://api.test.com")
        response = Response(503, request=request)
        exception = httpx.HTTPStatusError("Service unavailable", request=request, response=response)

        result = classify_error(exception)

        assert isinstance(result, ServerError)

    def test_classify_401_as_authentication_error(self):
        """Test that HTTP 401 is classified as AuthenticationError."""
        request = Request("POST", "https://api.test.com")
        response = Response(401, request=request)
        exception = httpx.HTTPStatusError("Unauthorized", request=request, response=response)

        result = classify_error(exception)

        assert isinstance(result, AuthenticationError)

    def test_classify_403_as_authentication_error(self):
        """Test that HTTP 403 is classified as AuthenticationError."""
        request = Request("POST", "https://api.test.com")
        response = Response(403, request=request)
        exception = httpx.HTTPStatusError("Forbidden", request=request, response=response)

        result = classify_error(exception)

        assert isinstance(result, AuthenticationError)

    def test_classify_400_as_validation_error(self):
        """Test that HTTP 400 is classified as ValidationError."""
        request = Request("POST", "https://api.test.com")
        response = Response(400, request=request)
        exception = httpx.HTTPStatusError("Bad request", request=request, response=response)

        result = classify_error(exception)

        assert isinstance(result, ValidationError)

    def test_classify_422_as_validation_error(self):
        """Test that HTTP 422 is classified as ValidationError."""
        request = Request("POST", "https://api.test.com")
        response = Response(422, request=request)
        exception = httpx.HTTPStatusError("Unprocessable entity", request=request, response=response)

        result = classify_error(exception)

        assert isinstance(result, ValidationError)

    def test_classify_unknown_exception_as_provider_error(self):
        """Test that unknown exceptions are classified as generic ProviderError."""
        exception = RuntimeError("Some unknown error")

        result = classify_error(exception)

        assert isinstance(result, ProviderError)
        assert not isinstance(result, RateLimitError)
        assert not isinstance(result, ServerError)


@pytest.mark.unit
class TestParseRetryAfter:
    """Test Retry-After header parsing (F012)."""

    def test_parse_integer_seconds(self):
        """Test parsing integer seconds format."""
        headers = httpx.Headers({"Retry-After": "120"})

        result = _parse_retry_after(headers)

        assert result == 120

    def test_parse_missing_header(self):
        """Test parsing when header is missing."""
        headers = httpx.Headers({})

        result = _parse_retry_after(headers)

        assert result is None

    def test_parse_invalid_value(self):
        """Test parsing invalid header value."""
        headers = httpx.Headers({"Retry-After": "not-a-number"})

        result = _parse_retry_after(headers)

        # Invalid non-date format should return None
        assert result is None


@pytest.mark.unit
class TestIsRetryable:
    """Test retryable error detection (F012: FR-2)."""

    def test_server_error_is_retryable(self):
        """Test that ServerError is retryable."""
        error = ServerError(message="Server error")

        assert is_retryable(error) is True

    def test_timeout_error_is_retryable(self):
        """Test that TimeoutError is retryable."""
        error = TimeoutError(message="Timeout")

        assert is_retryable(error) is True

    def test_rate_limit_error_is_not_retryable(self):
        """Test that RateLimitError is NOT retryable (F012: FR-5)."""
        error = RateLimitError(message="Rate limited", retry_after_seconds=60)

        assert is_retryable(error) is False

    def test_authentication_error_is_not_retryable(self):
        """Test that AuthenticationError is NOT retryable."""
        error = AuthenticationError(message="Invalid API key")

        assert is_retryable(error) is False

    def test_validation_error_is_not_retryable(self):
        """Test that ValidationError is NOT retryable."""
        error = ValidationError(message="Invalid request")

        assert is_retryable(error) is False

    def test_generic_provider_error_is_not_retryable(self):
        """Test that generic ProviderError is NOT retryable."""
        error = ProviderError(message="Unknown error")

        assert is_retryable(error) is False
