"""Tests for F024: Circuit Breaker Manager."""

from unittest.mock import patch

import pytest

from app.application.services.circuit_breaker import (
    CB_FAILURE_THRESHOLD,
    CB_RECOVERY_TIMEOUT,
    CircuitBreakerManager,
    CircuitState,
)


@pytest.mark.unit
class TestCircuitBreakerManager:
    """F024: Circuit breaker state machine tests."""

    def setup_method(self):
        CircuitBreakerManager.reset()

    def test_new_provider_is_available(self):
        """F024: Unknown provider defaults to CLOSED (available)."""
        assert CircuitBreakerManager.is_available("NewProvider") is True

    def test_closed_after_single_failure(self):
        """F024: Single failure doesn't open circuit."""
        CircuitBreakerManager.record_failure("Groq")
        assert CircuitBreakerManager.is_available("Groq") is True

    def test_opens_after_threshold_failures(self):
        """F024: Circuit opens after CB_FAILURE_THRESHOLD consecutive failures."""
        for _ in range(CB_FAILURE_THRESHOLD):
            CircuitBreakerManager.record_failure("Groq")
        assert CircuitBreakerManager.is_available("Groq") is False

    def test_success_resets_failure_count(self):
        """F024: Success in CLOSED resets failure counter."""
        for _ in range(CB_FAILURE_THRESHOLD - 1):
            CircuitBreakerManager.record_failure("Groq")
        CircuitBreakerManager.record_success("Groq")
        # Одна ошибка после reset — не открывает
        CircuitBreakerManager.record_failure("Groq")
        assert CircuitBreakerManager.is_available("Groq") is True

    @patch("app.application.services.circuit_breaker.time.time")
    def test_half_open_after_recovery_timeout(self, mock_time):
        """F024: OPEN -> HALF-OPEN after recovery_timeout seconds."""
        mock_time.return_value = 1000.0
        for _ in range(CB_FAILURE_THRESHOLD):
            CircuitBreakerManager.record_failure("Groq")
        assert CircuitBreakerManager.is_available("Groq") is False

        mock_time.return_value = 1000.0 + CB_RECOVERY_TIMEOUT + 1
        assert CircuitBreakerManager.is_available("Groq") is True
        statuses = CircuitBreakerManager.get_all_statuses()
        assert statuses["Groq"] == "half_open"

    @patch("app.application.services.circuit_breaker.time.time")
    def test_closes_after_success_in_half_open(self, mock_time):
        """F024: HALF-OPEN -> CLOSED after successful probe."""
        mock_time.return_value = 1000.0
        for _ in range(CB_FAILURE_THRESHOLD):
            CircuitBreakerManager.record_failure("Groq")
        mock_time.return_value = 1000.0 + CB_RECOVERY_TIMEOUT + 1
        CircuitBreakerManager.is_available("Groq")  # -> HALF-OPEN

        CircuitBreakerManager.record_success("Groq")
        assert CircuitBreakerManager.get_all_statuses()["Groq"] == "closed"

    @patch("app.application.services.circuit_breaker.time.time")
    def test_reopens_after_failure_in_half_open(self, mock_time):
        """F024: HALF-OPEN -> OPEN after failed probe."""
        mock_time.return_value = 1000.0
        for _ in range(CB_FAILURE_THRESHOLD):
            CircuitBreakerManager.record_failure("Groq")
        mock_time.return_value = 1000.0 + CB_RECOVERY_TIMEOUT + 1
        CircuitBreakerManager.is_available("Groq")  # -> HALF-OPEN

        CircuitBreakerManager.record_failure("Groq")
        assert CircuitBreakerManager.is_available("Groq") is False
        assert CircuitBreakerManager.get_all_statuses()["Groq"] == "open"

    def test_get_all_statuses_empty(self):
        """F024: Empty statuses for fresh manager."""
        assert CircuitBreakerManager.get_all_statuses() == {}

    def test_get_all_statuses_multiple_providers(self):
        """F024: Statuses reflect each provider independently."""
        for _ in range(CB_FAILURE_THRESHOLD):
            CircuitBreakerManager.record_failure("DeadProvider")
        CircuitBreakerManager.record_failure("AliveProvider")

        statuses = CircuitBreakerManager.get_all_statuses()
        assert statuses["DeadProvider"] == "open"
        assert statuses["AliveProvider"] == "closed"
