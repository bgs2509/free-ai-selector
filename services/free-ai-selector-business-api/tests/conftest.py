"""
Pytest configuration and fixtures for Business API tests
"""

import pytest


@pytest.fixture(autouse=True)
def reset_circuit_breaker():
    """F024: Сброс CB state между тестами для изоляции."""
    from app.application.services.circuit_breaker import CircuitBreakerManager

    CircuitBreakerManager.reset()
    yield
    CircuitBreakerManager.reset()


@pytest.fixture
def mock_data_api_client(monkeypatch):
    """
    Mock Data API client for testing.

    Returns a mock client that doesn't make real HTTP calls.
    """
    from unittest.mock import AsyncMock

    from app.domain.models import AIModelInfo

    mock_client = AsyncMock()

    # Mock get_all_models to return test models with F010 + F012 fields
    mock_client.get_all_models.return_value = [
        AIModelInfo(
            id=1,
            name="Test Model 1",
            provider="TestProvider1",
            api_endpoint="https://api1.test.com",
            reliability_score=0.9,
            is_active=True,
            effective_reliability_score=0.9,
            recent_request_count=0,
            decision_reason="fallback",
        ),
        AIModelInfo(
            id=2,
            name="Test Model 2",
            provider="TestProvider2",
            api_endpoint="https://api2.test.com",
            reliability_score=0.7,
            is_active=True,
            effective_reliability_score=0.7,
            recent_request_count=0,
            decision_reason="fallback",
        ),
    ]

    # Mock other methods
    mock_client.increment_success.return_value = None
    mock_client.increment_failure.return_value = None
    mock_client.create_history.return_value = 1
    mock_client.close.return_value = None
    # F012: set_availability for rate limit handling
    mock_client.set_availability.return_value = None

    return mock_client
