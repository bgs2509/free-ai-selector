"""
Unit tests for Retry Service (F012: Rate Limit Handling, F023: Exponential Backoff)
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.application.services.retry_service import (
    retry_with_exponential_backoff,
    retry_with_fixed_delay,
)
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


@pytest.mark.unit
class TestRetryWithExponentialBackoff:
    """Test exponential backoff (F023: FR-003, FR-004)."""

    @patch("app.application.services.retry_service.asyncio.sleep", new_callable=AsyncMock)
    @patch("app.application.services.retry_service.random.uniform", return_value=0.5)
    async def test_exponential_delays(self, mock_random, mock_sleep):
        """TRQ-003: Delays 2s, 4s, 8s with exponential backoff."""
        mock_func = AsyncMock()
        mock_func.side_effect = [
            ServerError(message="Error 1"),
            ServerError(message="Error 2"),
            ServerError(message="Error 3"),
            "success",
        ]

        result = await retry_with_exponential_backoff(
            func=mock_func,
            max_retries=3,
            base_delay=2.0,
            max_delay=30.0,
            jitter=1.0,
            provider_name="test",
            model_name="test",
        )

        assert result == "success"
        assert mock_sleep.call_count == 3
        # С jitter=0.5 (замокан): 2.0+0.5=2.5, 4.0+0.5=4.5, 8.0+0.5=8.5
        calls = [c.args[0] for c in mock_sleep.call_args_list]
        assert calls[0] == pytest.approx(2.5)
        assert calls[1] == pytest.approx(4.5)
        assert calls[2] == pytest.approx(8.5)

    @patch("app.application.services.retry_service.asyncio.sleep", new_callable=AsyncMock)
    @patch("app.application.services.retry_service.random.uniform", return_value=0.0)
    async def test_max_delay_cap(self, mock_random, mock_sleep):
        """Delay не превышает max_delay."""
        mock_func = AsyncMock()
        mock_func.side_effect = [
            ServerError(message="Error 1"),
            ServerError(message="Error 2"),
            "success",
        ]

        await retry_with_exponential_backoff(
            func=mock_func,
            max_retries=3,
            base_delay=10.0,
            max_delay=15.0,
            jitter=0.0,
            provider_name="test",
            model_name="test",
        )

        calls = [c.args[0] for c in mock_sleep.call_args_list]
        # attempt 0: min(10*2^0, 15) = min(10, 15) = 10.0
        # attempt 1: min(10*2^1, 15) = min(20, 15) = 15.0
        assert calls[0] == pytest.approx(10.0)
        assert calls[1] == pytest.approx(15.0)

    async def test_max_retries_3_means_4_total_attempts(self):
        """TRQ-004: MAX_RETRIES=3 -> 4 total attempts max."""
        mock_func = AsyncMock()
        mock_func.side_effect = ServerError(message="Persistent error")

        with pytest.raises(ServerError):
            await retry_with_exponential_backoff(
                func=mock_func,
                max_retries=3,
                base_delay=0,
                max_delay=0,
                jitter=0,
                provider_name="test",
                model_name="test",
            )

        assert mock_func.call_count == 4  # 1 initial + 3 retries

    @patch("app.application.services.retry_service.asyncio.sleep", new_callable=AsyncMock)
    async def test_jitter_adds_randomness(self, mock_sleep):
        """TRQ-005: Jitter добавляется к delay."""
        mock_func = AsyncMock()
        mock_func.side_effect = [
            ServerError(message="Error"),
            "success",
        ]

        await retry_with_exponential_backoff(
            func=mock_func,
            max_retries=3,
            base_delay=2.0,
            max_delay=30.0,
            jitter=1.0,
            provider_name="test",
            model_name="test",
        )

        # Delay должен быть в диапазоне [2.0, 3.0] (base_delay + [0, jitter])
        actual_delay = mock_sleep.call_args[0][0]
        assert 2.0 <= actual_delay <= 3.0

    async def test_non_retryable_error_raised_immediately(self):
        """Non-retryable ошибки не ретраятся."""
        mock_func = AsyncMock()
        mock_func.side_effect = AuthenticationError(message="Invalid key")

        with pytest.raises(AuthenticationError):
            await retry_with_exponential_backoff(
                func=mock_func,
                max_retries=3,
                base_delay=0,
                max_delay=0,
                jitter=0,
                provider_name="test",
                model_name="test",
            )

        assert mock_func.call_count == 1

    async def test_success_on_first_attempt(self):
        """Успех с первой попытки — без retry."""
        mock_func = AsyncMock(return_value="success")

        result = await retry_with_exponential_backoff(
            func=mock_func,
            max_retries=3,
            base_delay=2.0,
            max_delay=30.0,
            jitter=1.0,
            provider_name="test",
            model_name="test",
        )

        assert result == "success"
        assert mock_func.call_count == 1
