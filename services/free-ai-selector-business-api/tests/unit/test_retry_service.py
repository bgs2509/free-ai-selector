"""
Unit tests for Retry Service (F012: Rate Limit Handling)
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.application.services.retry_service import retry_with_fixed_delay
from app.domain.exceptions import (
    AuthenticationError,
    RateLimitError,
    ServerError,
    TimeoutError,
    ValidationError,
)


@pytest.mark.unit
class TestRetryWithFixedDelay:
    """Test retry mechanism (F012: FR-2)."""

    async def test_success_on_first_attempt(self):
        """Test successful execution on first attempt."""
        mock_func = AsyncMock(return_value="success")

        result = await retry_with_fixed_delay(
            func=mock_func,
            max_retries=3,
            delay_seconds=0,  # No delay for tests
            provider_name="test_provider",
            model_name="test_model",
        )

        assert result == "success"
        assert mock_func.call_count == 1

    async def test_retry_on_server_error(self):
        """Test retry on ServerError (F012: FR-2)."""
        mock_func = AsyncMock()
        mock_func.side_effect = [
            ServerError(message="Server error 1"),
            ServerError(message="Server error 2"),
            "success",
        ]

        result = await retry_with_fixed_delay(
            func=mock_func,
            max_retries=3,
            delay_seconds=0,
            provider_name="test_provider",
            model_name="test_model",
        )

        assert result == "success"
        assert mock_func.call_count == 3

    async def test_retry_on_timeout_error(self):
        """Test retry on TimeoutError (F012: FR-2)."""
        mock_func = AsyncMock()
        mock_func.side_effect = [
            TimeoutError(message="Timeout 1"),
            "success",
        ]

        result = await retry_with_fixed_delay(
            func=mock_func,
            max_retries=3,
            delay_seconds=0,
            provider_name="test_provider",
            model_name="test_model",
        )

        assert result == "success"
        assert mock_func.call_count == 2

    async def test_no_retry_on_rate_limit_error(self):
        """Test NO retry on RateLimitError - raised immediately (F012: FR-5)."""
        mock_func = AsyncMock()
        mock_func.side_effect = RateLimitError(message="Rate limited", retry_after_seconds=60)

        with pytest.raises(RateLimitError) as exc_info:
            await retry_with_fixed_delay(
                func=mock_func,
                max_retries=3,
                delay_seconds=0,
                provider_name="test_provider",
                model_name="test_model",
            )

        assert "Rate limited" in str(exc_info.value.message)
        assert mock_func.call_count == 1  # Only 1 attempt, no retry

    async def test_no_retry_on_authentication_error(self):
        """Test NO retry on AuthenticationError."""
        mock_func = AsyncMock()
        mock_func.side_effect = AuthenticationError(message="Invalid API key")

        with pytest.raises(AuthenticationError):
            await retry_with_fixed_delay(
                func=mock_func,
                max_retries=3,
                delay_seconds=0,
                provider_name="test_provider",
                model_name="test_model",
            )

        assert mock_func.call_count == 1  # Only 1 attempt, no retry

    async def test_no_retry_on_validation_error(self):
        """Test NO retry on ValidationError."""
        mock_func = AsyncMock()
        mock_func.side_effect = ValidationError(message="Invalid request")

        with pytest.raises(ValidationError):
            await retry_with_fixed_delay(
                func=mock_func,
                max_retries=3,
                delay_seconds=0,
                provider_name="test_provider",
                model_name="test_model",
            )

        assert mock_func.call_count == 1  # Only 1 attempt, no retry

    async def test_exhausted_retries_raises_last_error(self):
        """Test that exhausted retries raise the last ServerError."""
        mock_func = AsyncMock()
        mock_func.side_effect = ServerError(message="Persistent server error")

        with pytest.raises(ServerError) as exc_info:
            await retry_with_fixed_delay(
                func=mock_func,
                max_retries=2,  # 3 total attempts (1 + 2 retries)
                delay_seconds=0,
                provider_name="test_provider",
                model_name="test_model",
            )

        assert "Persistent server error" in str(exc_info.value.message)
        assert mock_func.call_count == 3  # 1 initial + 2 retries

    async def test_mixed_errors_retry_only_retryable(self):
        """Test that only retryable errors trigger retry."""
        mock_func = AsyncMock()
        mock_func.side_effect = [
            TimeoutError(message="Timeout 1"),
            ServerError(message="Server error"),
            "success",
        ]

        result = await retry_with_fixed_delay(
            func=mock_func,
            max_retries=5,
            delay_seconds=0,
            provider_name="test_provider",
            model_name="test_model",
        )

        assert result == "success"
        assert mock_func.call_count == 3

    @patch("app.application.services.retry_service.asyncio.sleep", new_callable=AsyncMock)
    async def test_delay_between_retries(self, mock_sleep):
        """Test that delay is applied between retries."""
        mock_func = AsyncMock()
        mock_func.side_effect = [
            ServerError(message="Error 1"),
            ServerError(message="Error 2"),
            "success",
        ]

        result = await retry_with_fixed_delay(
            func=mock_func,
            max_retries=3,
            delay_seconds=10,  # 10 seconds delay
            provider_name="test_provider",
            model_name="test_model",
        )

        assert result == "success"
        assert mock_sleep.call_count == 2  # 2 delays (before 2nd and 3rd attempts)
        mock_sleep.assert_called_with(10)

    async def test_http_status_error_classified_and_handled(self):
        """Test that httpx.HTTPStatusError is classified before handling."""
        import httpx
        from httpx import Request, Response

        mock_func = AsyncMock()
        request = Request("POST", "https://api.test.com")
        response = Response(503, request=request)
        mock_func.side_effect = [
            httpx.HTTPStatusError("Service unavailable", request=request, response=response),
            "success",
        ]

        result = await retry_with_fixed_delay(
            func=mock_func,
            max_retries=3,
            delay_seconds=0,
            provider_name="test_provider",
            model_name="test_model",
        )

        assert result == "success"
        assert mock_func.call_count == 2


@pytest.mark.unit
class TestRetryConfiguration:
    """Test retry configuration (F012)."""

    async def test_max_retries_zero_means_single_attempt(self):
        """Test that max_retries=0 means only 1 attempt."""
        mock_func = AsyncMock()
        mock_func.side_effect = ServerError(message="Server error")

        with pytest.raises(ServerError):
            await retry_with_fixed_delay(
                func=mock_func,
                max_retries=0,  # 0 retries = 1 attempt only
                delay_seconds=0,
                provider_name="test_provider",
                model_name="test_model",
            )

        assert mock_func.call_count == 1

    async def test_custom_max_retries(self):
        """Test custom max_retries configuration."""
        mock_func = AsyncMock()
        mock_func.side_effect = ServerError(message="Server error")

        with pytest.raises(ServerError):
            await retry_with_fixed_delay(
                func=mock_func,
                max_retries=5,  # 5 retries = 6 attempts total
                delay_seconds=0,
                provider_name="test_provider",
                model_name="test_model",
            )

        assert mock_func.call_count == 6  # 1 initial + 5 retries
