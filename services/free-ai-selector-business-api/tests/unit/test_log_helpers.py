"""Тесты для app/utils/log_helpers.py."""
import time
from unittest.mock import MagicMock

from app.utils.log_helpers import (
    log_decision,
    log_request_started,
    log_request_completed,
    log_external_call,
)


class TestLogDecision:
    """Тесты для log_decision."""

    def test_accept_logs_info(self):
        """ACCEPT решение логируется через info."""
        logger = MagicMock()
        log_decision(logger, "ACCEPT", "highest_score", {"score": 0.95})
        logger.info.assert_called_once()

    def test_reject_logs_warning(self):
        """REJECT решение логируется через warning."""
        logger = MagicMock()
        log_decision(logger, "REJECT", "too_slow")
        logger.warning.assert_called_once()

    def test_fallback_logs_warning(self):
        """FALLBACK решение логируется через warning."""
        logger = MagicMock()
        log_decision(logger, "FALLBACK", "primary_failed")
        logger.warning.assert_called_once()

    def test_retry_logs_warning(self):
        """RETRY решение логируется через warning."""
        logger = MagicMock()
        log_decision(logger, "RETRY", "transient_error")
        logger.warning.assert_called_once()

    def test_skip_logs_info(self):
        """SKIP решение логируется через info."""
        logger = MagicMock()
        log_decision(logger, "SKIP", "not_needed")
        logger.info.assert_called_once()

    def test_with_evaluated_conditions(self):
        """Решение с evaluated_conditions включает их в лог."""
        logger = MagicMock()
        conditions = {"models_count": 5, "selected_model": "gemini"}
        log_decision(logger, "ACCEPT", "best_model", conditions)
        logger.info.assert_called_once()
        call_kwargs = logger.info.call_args[1]
        assert call_kwargs["evaluated_conditions"] == conditions

    def test_without_evaluated_conditions(self):
        """Решение без evaluated_conditions не включает их в лог."""
        logger = MagicMock()
        log_decision(logger, "ACCEPT", "best_model")
        logger.info.assert_called_once()
        call_kwargs = logger.info.call_args[1]
        assert "evaluated_conditions" not in call_kwargs

    def test_extra_kwargs_passed(self):
        """Дополнительные kwargs передаются в лог."""
        logger = MagicMock()
        log_decision(logger, "ACCEPT", "reason", model_id=42)
        call_kwargs = logger.info.call_args[1]
        assert call_kwargs["model_id"] == 42


class TestLogRequestStarted:
    """Тесты для log_request_started."""

    def test_returns_float(self):
        """Возвращает float (время начала)."""
        logger = MagicMock()
        start = log_request_started(logger, "GET", "/api/test")
        assert isinstance(start, float)
        logger.info.assert_called_once()

    def test_logs_method_and_path(self):
        """Логирует метод и путь запроса."""
        logger = MagicMock()
        log_request_started(logger, "POST", "/api/v1/prompts/process")
        call_kwargs = logger.info.call_args[1]
        assert call_kwargs["method"] == "POST"
        assert call_kwargs["path"] == "/api/v1/prompts/process"

    def test_extra_kwargs_passed(self):
        """Дополнительные kwargs передаются в лог."""
        logger = MagicMock()
        log_request_started(logger, "GET", "/test", user_id="u1")
        call_kwargs = logger.info.call_args[1]
        assert call_kwargs["user_id"] == "u1"


class TestLogRequestCompleted:
    """Тесты для log_request_completed."""

    def test_200_logs_info(self):
        """Статус 200 логируется через info."""
        logger = MagicMock()
        log_request_completed(logger, "GET", "/api/test", time.perf_counter(), 200)
        logger.info.assert_called_once()

    def test_201_logs_info(self):
        """Статус 201 логируется через info."""
        logger = MagicMock()
        log_request_completed(logger, "POST", "/api/test", time.perf_counter(), 201)
        logger.info.assert_called_once()

    def test_404_logs_warning(self):
        """Статус 404 логируется через warning."""
        logger = MagicMock()
        log_request_completed(logger, "GET", "/api/test", time.perf_counter(), 404)
        logger.warning.assert_called_once()

    def test_422_logs_warning(self):
        """Статус 422 логируется через warning."""
        logger = MagicMock()
        log_request_completed(logger, "POST", "/api/test", time.perf_counter(), 422)
        logger.warning.assert_called_once()

    def test_500_logs_error(self):
        """Статус 500 логируется через error."""
        logger = MagicMock()
        log_request_completed(logger, "POST", "/api/test", time.perf_counter(), 500)
        logger.error.assert_called_once()

    def test_503_logs_error(self):
        """Статус 503 логируется через error."""
        logger = MagicMock()
        log_request_completed(logger, "GET", "/api/test", time.perf_counter(), 503)
        logger.error.assert_called_once()

    def test_includes_duration_ms(self):
        """Лог включает duration_ms."""
        logger = MagicMock()
        start = time.perf_counter()
        log_request_completed(logger, "GET", "/test", start, 200)
        call_kwargs = logger.info.call_args[1]
        assert "duration_ms" in call_kwargs
        assert isinstance(call_kwargs["duration_ms"], float)


class TestLogExternalCall:
    """Тесты для log_external_call."""

    def test_success_logs_info(self):
        """Успешный вызов логируется через info."""
        logger = MagicMock()
        log_external_call(logger, "data_api", "get_models", 150.0, True)
        logger.info.assert_called_once()

    def test_failure_logs_warning(self):
        """Неуспешный вызов логируется через warning."""
        logger = MagicMock()
        log_external_call(logger, "groq", "generate", 500.0, False)
        logger.warning.assert_called_once()

    def test_includes_service_and_operation(self):
        """Лог включает имя сервиса и операцию."""
        logger = MagicMock()
        log_external_call(logger, "cerebras", "health_check", 100.0, True)
        call_kwargs = logger.info.call_args[1]
        assert call_kwargs["external_service"] == "cerebras"
        assert call_kwargs["operation"] == "health_check"
        assert call_kwargs["duration_ms"] == 100.0

    def test_extra_kwargs_passed(self):
        """Дополнительные kwargs передаются в лог."""
        logger = MagicMock()
        log_external_call(logger, "api", "op", 10.0, True, model_id=5)
        call_kwargs = logger.info.call_args[1]
        assert call_kwargs["model_id"] == 5
