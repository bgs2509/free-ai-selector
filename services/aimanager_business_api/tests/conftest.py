"""
Pytest configuration and fixtures for Business API tests
"""

import pytest


@pytest.fixture
def mock_data_api_client(monkeypatch):
    """
    Mock Data API client for testing.

    Returns a mock client that doesn't make real HTTP calls.
    """
    from unittest.mock import AsyncMock

    from app.domain.models import AIModelInfo

    mock_client = AsyncMock()

    # Mock get_all_models to return test models
    mock_client.get_all_models.return_value = [
        AIModelInfo(
            id=1,
            name="Test Model 1",
            provider="TestProvider1",
            api_endpoint="https://api1.test.com",
            reliability_score=0.9,
            is_active=True,
        ),
        AIModelInfo(
            id=2,
            name="Test Model 2",
            provider="TestProvider2",
            api_endpoint="https://api2.test.com",
            reliability_score=0.7,
            is_active=True,
        ),
    ]

    # Mock other methods
    mock_client.increment_success.return_value = None
    mock_client.increment_failure.return_value = None
    mock_client.create_history.return_value = 1
    mock_client.close.return_value = None

    return mock_client
