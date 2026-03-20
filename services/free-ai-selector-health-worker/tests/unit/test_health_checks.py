"""Тесты для health check функций из app/main.py."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.main import (
    format_exception_message,
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
