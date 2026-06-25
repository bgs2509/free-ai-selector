"""
Unit tests for provider error surfacing (ex9).

Regression guard: transport errors with an empty ``str()`` (RemoteProtocolError,
empty ReadTimeout) previously produced a useless "{Provider} error: " in the
journal. They must now surface a non-empty detail, and ConnectError must be
retryable while read/protocol hangs are not.
"""

from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.application.services.error_classifier import is_retryable
from app.domain.exceptions import ProviderError, TimeoutError
from app.infrastructure.ai_providers.deepseek import DeepSeekProvider


def _provider() -> DeepSeekProvider:
    return DeepSeekProvider(api_key="test-key")


@pytest.mark.unit
class TestDescribeError:
    """_describe_error must never return an empty string (ex9)."""

    def test_empty_transport_falls_back_to_class_name(self):
        assert (
            _provider()._describe_error(httpx.RemoteProtocolError(""))
            == "RemoteProtocolError"
        )

    def test_nonempty_detail_is_preserved(self):
        assert _provider()._describe_error(httpx.ConnectError("boom")) == "boom"


@pytest.mark.unit
class TestProviderErrorSurfacing:
    """generate() must surface a non-empty error and classify transport errors."""

    @pytest.mark.asyncio
    async def test_empty_protocol_error_surfaces_nonempty_message(self):
        provider = _provider()
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.RemoteProtocolError("")
            )
            with pytest.raises(ProviderError) as exc_info:
                await provider.generate("hi")

        message = exc_info.value.message
        assert message.strip() != f"{provider.PROVIDER_NAME} error:"
        assert "RemoteProtocolError" in message
        # RemoteProtocolError → non-retryable, fall back to next provider
        assert is_retryable(exc_info.value) is False
        assert not isinstance(exc_info.value, TimeoutError)

    @pytest.mark.asyncio
    async def test_read_timeout_is_nonretryable_provider_error(self):
        provider = _provider()
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.ReadTimeout("")
            )
            with pytest.raises(ProviderError) as exc_info:
                await provider.generate("hi")

        # Expensive ~30s hang → non-retryable (plain ProviderError, not TimeoutError)
        assert not isinstance(exc_info.value, TimeoutError)
        assert "ReadTimeout" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_connect_error_is_retryable_timeout(self):
        provider = _provider()
        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=httpx.ConnectError("")
            )
            with pytest.raises(TimeoutError) as exc_info:
                await provider.generate("hi")

        # Connection never established = cheap to retry
        assert is_retryable(exc_info.value) is True
        assert "ConnectError" in exc_info.value.message
