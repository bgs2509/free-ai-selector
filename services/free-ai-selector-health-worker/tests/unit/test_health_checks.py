"""Тесты для health check функций из app/main.py."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import (
    check_openai_format,
    check_huggingface_format,
    check_cloudflare_format,
    universal_health_check,
    format_exception_message,
    _get_api_key,
    _build_trace_headers,
)


class TestFormatExceptionMessage:
    def test_regular_exception(self):
        err = ValueError("something went wrong")
        result = format_exception_message(err)
        assert "ValueError" in result
        assert "something went wrong" in result

    def test_empty_exception(self):
        err = TimeoutError()
        result = format_exception_message(err)
        assert "TimeoutError" in result

    def test_sanitizes_secrets(self):
        key = "sk-" + "a" * 48
        err = ValueError(f"Auth failed: {key}")
        result = format_exception_message(err)
        assert "sk-***" in result


class TestGetApiKey:
    def test_returns_value(self, monkeypatch):
        monkeypatch.setenv("TEST_KEY", "my-key")
        assert _get_api_key("TEST_KEY") == "my-key"

    def test_returns_none_for_empty(self, monkeypatch):
        monkeypatch.setenv("TEST_KEY", "")
        assert _get_api_key("TEST_KEY") is None

    def test_returns_none_for_missing(self, monkeypatch):
        monkeypatch.delenv("NONEXISTENT_KEY", raising=False)
        assert _get_api_key("NONEXISTENT_KEY") is None


class TestBuildTraceHeaders:
    def test_always_has_request_id(self):
        headers = _build_trace_headers()
        assert "X-Request-ID" in headers
        assert len(headers["X-Request-ID"]) == 32

    def test_includes_run_id(self):
        with patch("app.main.RUN_ID", "test-run"):
            headers = _build_trace_headers()
            assert headers.get("X-Run-Id") == "test-run"
            assert headers["X-Correlation-ID"] == "test-run"

    def test_no_run_context(self):
        with (
            patch("app.main.RUN_ID", ""),
            patch("app.main.RUN_SOURCE", ""),
            patch("app.main.RUN_SCENARIO", ""),
            patch("app.main.RUN_STARTED_AT", ""),
        ):
            headers = _build_trace_headers()
            assert "X-Run-Id" not in headers


class TestCheckOpenaiFormat:
    async def test_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            healthy, resp_time = await check_openai_format(
                "https://api.test/v1/chat", "key-123", "TestProv"
            )

        assert healthy is True
        assert resp_time > 0

    async def test_failure_500(self):
        mock_response = MagicMock()
        mock_response.status_code = 500

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            healthy, _ = await check_openai_format(
                "https://api.test/v1/chat", "key-123", "TestProv"
            )

        assert healthy is False

    async def test_timeout(self):
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(side_effect=Exception("timeout"))

        with patch("httpx.AsyncClient", return_value=mock_client):
            healthy, _ = await check_openai_format(
                "https://api.test/v1/chat", "key-123", "TestProv"
            )

        assert healthy is False

    async def test_openrouter_headers(self):
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            await check_openai_format(
                "https://openrouter.ai/api/v1/chat", "key", "OpenRouter"
            )

        # Проверяем, что HTTP-Referer был в headers
        call_kwargs = mock_client.post.call_args
        headers = call_kwargs.kwargs.get("headers") or call_kwargs[1].get("headers", {})
        assert "HTTP-Referer" in headers


class TestCheckHuggingfaceFormat:
    async def test_success_200(self):
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            healthy, _ = await check_huggingface_format(
                "https://hf.co/api", "key", "HuggingFace"
            )

        assert healthy is True

    async def test_model_loading_503(self):
        mock_response = MagicMock()
        mock_response.status_code = 503

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            healthy, _ = await check_huggingface_format(
                "https://hf.co/api", "key", "HuggingFace"
            )

        assert healthy is True  # 503 = model loading, still healthy

    async def test_failure_400(self):
        mock_response = MagicMock()
        mock_response.status_code = 400

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with patch("httpx.AsyncClient", return_value=mock_client):
            healthy, _ = await check_huggingface_format(
                "https://hf.co/api", "key", "HuggingFace"
            )

        assert healthy is False


class TestCheckCloudflareFormat:
    async def test_success(self):
        mock_response = MagicMock()
        mock_response.status_code = 200

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.post = AsyncMock(return_value=mock_response)

        with (
            patch("httpx.AsyncClient", return_value=mock_client),
            patch("app.main.CLOUDFLARE_ACCOUNT_ID", "test-account-id"),
        ):
            healthy, _ = await check_cloudflare_format(
                "https://api.cloudflare.com/{account_id}/ai/run/model",
                "token",
                "Cloudflare",
            )

        assert healthy is True

    async def test_missing_account_id(self):
        with patch("app.main.CLOUDFLARE_ACCOUNT_ID", ""):
            healthy, resp_time = await check_cloudflare_format(
                "https://api.cloudflare.com/{account_id}/ai/run/model",
                "token",
                "Cloudflare",
            )

        assert healthy is False
        assert resp_time == 0.0


class TestUniversalHealthCheck:
    async def test_dispatches_to_openai(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")

        with patch("app.main.check_openai_format", new_callable=AsyncMock) as mock_check:
            mock_check.return_value = (True, 1.0)
            healthy, resp_time = await universal_health_check(
                "https://api.groq.com/v1/chat", "openai", "Groq"
            )

        assert healthy is True
        mock_check.assert_called_once()

    async def test_unknown_provider(self):
        healthy, resp_time = await universal_health_check(
            "https://api.unknown.com", "openai", "UnknownProvider"
        )
        assert healthy is False
        assert resp_time == 0.0

    async def test_missing_api_key(self, monkeypatch):
        monkeypatch.delenv("GROQ_API_KEY", raising=False)

        healthy, resp_time = await universal_health_check(
            "https://api.groq.com/v1/chat", "openai", "Groq"
        )
        assert healthy is False
        assert resp_time == 0.0

    async def test_unknown_api_format(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "test-key")

        healthy, resp_time = await universal_health_check(
            "https://api.groq.com/v1/chat", "unknown_format", "Groq"
        )
        assert healthy is False
        assert resp_time == 0.0
