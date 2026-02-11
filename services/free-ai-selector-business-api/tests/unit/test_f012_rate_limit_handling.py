"""
Unit tests for F012: Rate Limit Handling

Tests for:
- Full fallback loop through available models
- Rate limit (429) triggers set_availability, not failure count
- Server errors (5xx) and timeouts trigger retry mechanism
- Graceful degradation (429 doesn't reduce reliability_score)
"""

import os
from unittest.mock import AsyncMock, patch

import pytest

from app.application.use_cases.process_prompt import ProcessPromptUseCase
from app.domain.exceptions import (
    AuthenticationError,
    RateLimitError,
    ServerError,
    TimeoutError,
    ValidationError,
)
from app.domain.models import AIModelInfo, PromptRequest


@pytest.mark.unit
class TestF012RateLimitHandling:
    """Test F012: Rate Limit Handling."""

    @patch.dict(os.environ, {"TEST_API_KEY": "test_key"})
    @patch("app.application.use_cases.process_prompt.ProviderRegistry")
    async def test_rate_limit_triggers_set_availability(
        self, mock_registry, mock_data_api_client
    ):
        """Test that RateLimitError triggers set_availability (F012: FR-3)."""
        # Setup: First provider returns 429, second succeeds
        mock_provider1 = AsyncMock()
        mock_provider1.generate.side_effect = RateLimitError(
            message="Rate limited", retry_after_seconds=3600
        )

        mock_provider2 = AsyncMock()
        mock_provider2.generate.return_value = "Success from fallback"

        mock_registry.get_provider.side_effect = [mock_provider1, mock_provider2]
        mock_registry.get_api_key_env.return_value = "TEST_API_KEY"

        # Setup models
        mock_data_api_client.get_all_models.return_value = [
            AIModelInfo(
                id=1,
                name="Model 1",
                provider="Provider1",
                api_endpoint="https://api1.test.com",
                reliability_score=0.9,
                is_active=True,
                effective_reliability_score=0.9,
            ),
            AIModelInfo(
                id=2,
                name="Model 2",
                provider="Provider2",
                api_endpoint="https://api2.test.com",
                reliability_score=0.8,
                is_active=True,
                effective_reliability_score=0.8,
            ),
        ]

        use_case = ProcessPromptUseCase(mock_data_api_client)
        request = PromptRequest(user_id="test_user", prompt_text="Test prompt")

        response = await use_case.execute(request)

        # Verify: set_availability called for rate-limited model
        mock_data_api_client.set_availability.assert_called_once_with(1, 3600)

        # Verify: increment_failure NOT called for rate-limited model (graceful degradation)
        # Only check calls - should not include model_id=1 failure
        failure_calls = mock_data_api_client.increment_failure.call_args_list
        for call in failure_calls:
            assert call[1].get("model_id") != 1 or call[0][0] != 1

        # Verify: Success from fallback
        assert response.success is True
        assert response.response_text == "Success from fallback"

    @patch.dict(os.environ, {"TEST_API_KEY": "test_key"})
    @patch("app.application.use_cases.process_prompt.ProviderRegistry")
    async def test_server_error_triggers_retry_and_fallback(
        self, mock_registry, mock_data_api_client
    ):
        """Test that ServerError triggers retry, then fallback (F012: FR-2, FR-4)."""
        # Setup: First provider always fails with 5xx, second succeeds
        mock_provider1 = AsyncMock()
        mock_provider1.generate.side_effect = ServerError(message="Server error")

        mock_provider2 = AsyncMock()
        mock_provider2.generate.return_value = "Success from fallback"

        mock_registry.get_provider.side_effect = [mock_provider1, mock_provider2]
        mock_registry.get_api_key_env.return_value = "TEST_API_KEY"

        mock_data_api_client.get_all_models.return_value = [
            AIModelInfo(
                id=1,
                name="Model 1",
                provider="Provider1",
                api_endpoint="https://api1.test.com",
                reliability_score=0.9,
                is_active=True,
                effective_reliability_score=0.9,
            ),
            AIModelInfo(
                id=2,
                name="Model 2",
                provider="Provider2",
                api_endpoint="https://api2.test.com",
                reliability_score=0.8,
                is_active=True,
                effective_reliability_score=0.8,
            ),
        ]

        # Mock retry to not wait (for faster tests)
        with patch("app.application.services.retry_service.asyncio.sleep", new_callable=AsyncMock):
            use_case = ProcessPromptUseCase(mock_data_api_client)
            request = PromptRequest(user_id="test_user", prompt_text="Test prompt")

            response = await use_case.execute(request)

        # Verify: increment_failure called for failed model
        mock_data_api_client.increment_failure.assert_called()

        # Verify: Success from fallback
        assert response.success is True
        assert response.response_text == "Success from fallback"

    @patch.dict(os.environ, {"TEST_API_KEY": "test_key"})
    @patch("app.application.use_cases.process_prompt.ProviderRegistry")
    async def test_all_providers_fail_raises_exception(
        self, mock_registry, mock_data_api_client
    ):
        """Test that exception is raised when all providers fail (F012: FR-4)."""
        # Setup: Both providers fail
        mock_provider = AsyncMock()
        mock_provider.generate.side_effect = AuthenticationError(message="Invalid key")
        mock_registry.get_provider.return_value = mock_provider
        mock_registry.get_api_key_env.return_value = "TEST_API_KEY"

        mock_data_api_client.get_all_models.return_value = [
            AIModelInfo(
                id=1,
                name="Model 1",
                provider="Provider1",
                api_endpoint="https://api1.test.com",
                reliability_score=0.9,
                is_active=True,
                effective_reliability_score=0.9,
            ),
            AIModelInfo(
                id=2,
                name="Model 2",
                provider="Provider2",
                api_endpoint="https://api2.test.com",
                reliability_score=0.8,
                is_active=True,
                effective_reliability_score=0.8,
            ),
        ]

        use_case = ProcessPromptUseCase(mock_data_api_client)
        request = PromptRequest(user_id="test_user", prompt_text="Test prompt")

        with pytest.raises(Exception, match="All AI providers failed"):
            await use_case.execute(request)

    @patch.dict(os.environ, {"TEST_API_KEY": "test_key"})
    @patch("app.application.use_cases.process_prompt.ProviderRegistry")
    async def test_rate_limit_does_not_reduce_reliability_score(
        self, mock_registry, mock_data_api_client
    ):
        """Test that 429 doesn't call increment_failure (F012: FR-5 graceful degradation)."""
        # Setup: Provider returns 429
        mock_provider = AsyncMock()
        mock_provider.generate.side_effect = RateLimitError(
            message="Rate limited", retry_after_seconds=60
        )
        mock_registry.get_provider.return_value = mock_provider
        mock_registry.get_api_key_env.return_value = "TEST_API_KEY"

        mock_data_api_client.get_all_models.return_value = [
            AIModelInfo(
                id=1,
                name="Model 1",
                provider="Provider1",
                api_endpoint="https://api1.test.com",
                reliability_score=0.9,
                is_active=True,
                effective_reliability_score=0.9,
            ),
        ]

        use_case = ProcessPromptUseCase(mock_data_api_client)
        request = PromptRequest(user_id="test_user", prompt_text="Test prompt")

        # All providers rate-limited should raise
        with pytest.raises(Exception, match="All AI providers failed"):
            await use_case.execute(request)

        # Verify: set_availability called
        mock_data_api_client.set_availability.assert_called_once()

        # Verify: increment_failure NOT called (graceful degradation)
        mock_data_api_client.increment_failure.assert_not_called()


@pytest.mark.unit
class TestF012FilterConfiguredModels:
    """Test filtering models by configured API keys (F012: FR-8)."""

    @patch.dict(os.environ, {"PROVIDER1_KEY": "key1"}, clear=True)
    @patch("app.application.use_cases.process_prompt.ProviderRegistry")
    def test_filter_models_with_api_key(self, mock_registry, mock_data_api_client):
        """Test that only models with configured API keys are returned (F018: via registry)."""
        # F018: Mock get_api_key_env to return env var names for test providers
        mock_registry.get_api_key_env.side_effect = lambda p: {
            "Provider1": "PROVIDER1_KEY", "Provider2": "PROVIDER2_KEY"
        }.get(p, "")

        use_case = ProcessPromptUseCase(mock_data_api_client)

        models = [
            AIModelInfo(
                id=1,
                name="Model 1",
                provider="Provider1",
                api_endpoint="https://api1.test.com",
                reliability_score=0.9,
                is_active=True,
            ),
            AIModelInfo(
                id=2,
                name="Model 2",
                provider="Provider2",
                api_endpoint="https://api2.test.com",
                reliability_score=0.8,
                is_active=True,
            ),
        ]

        configured = use_case._filter_configured_models(models)

        assert len(configured) == 1
        assert configured[0].id == 1

    @patch.dict(os.environ, {}, clear=True)
    @patch("app.application.use_cases.process_prompt.ProviderRegistry")
    def test_filter_no_configured_models(self, mock_registry, mock_data_api_client):
        """Test that empty list returned when no models have API keys (F018: via registry)."""
        mock_registry.get_api_key_env.return_value = "MISSING_KEY"

        use_case = ProcessPromptUseCase(mock_data_api_client)

        models = [
            AIModelInfo(
                id=1,
                name="Model 1",
                provider="Provider1",
                api_endpoint="https://api1.test.com",
                reliability_score=0.9,
                is_active=True,
            ),
        ]

        configured = use_case._filter_configured_models(models)

        assert len(configured) == 0

    @patch.dict(os.environ, {"KEY1": "value1", "KEY2": "value2"}, clear=True)
    @patch("app.application.use_cases.process_prompt.ProviderRegistry")
    def test_filter_multiple_configured_models(self, mock_registry, mock_data_api_client):
        """Test filtering with multiple configured models (F018: via registry)."""
        mock_registry.get_api_key_env.side_effect = lambda p: {
            "Provider1": "KEY1", "Provider2": "KEY2", "Provider3": "MISSING_KEY"
        }.get(p, "")

        use_case = ProcessPromptUseCase(mock_data_api_client)

        models = [
            AIModelInfo(
                id=1,
                name="Model 1",
                provider="Provider1",
                api_endpoint="https://api1.test.com",
                reliability_score=0.9,
                is_active=True,
            ),
            AIModelInfo(
                id=2,
                name="Model 2",
                provider="Provider2",
                api_endpoint="https://api2.test.com",
                reliability_score=0.8,
                is_active=True,
            ),
            AIModelInfo(
                id=3,
                name="Model 3",
                provider="Provider3",
                api_endpoint="https://api3.test.com",
                reliability_score=0.7,
                is_active=True,
            ),
        ]

        configured = use_case._filter_configured_models(models)

        assert len(configured) == 2
        assert configured[0].id == 1
        assert configured[1].id == 2


@pytest.mark.unit
class TestF012AvailableOnlyParameter:
    """Test available_only parameter for excluding rate-limited models."""

    @patch.dict(os.environ, {"TEST_API_KEY": "test_key"})
    @patch("app.application.use_cases.process_prompt.ProviderRegistry")
    async def test_get_all_models_called_with_available_only(
        self, mock_registry, mock_data_api_client
    ):
        """Test that get_all_models is called with available_only=True."""
        mock_provider = AsyncMock()
        mock_provider.generate.return_value = "Success"
        mock_registry.get_provider.return_value = mock_provider
        mock_registry.get_api_key_env.return_value = "TEST_API_KEY"

        mock_data_api_client.get_all_models.return_value = [
            AIModelInfo(
                id=1,
                name="Model 1",
                provider="Provider1",
                api_endpoint="https://api1.test.com",
                reliability_score=0.9,
                is_active=True,
                effective_reliability_score=0.9,
            ),
        ]

        use_case = ProcessPromptUseCase(mock_data_api_client)
        request = PromptRequest(user_id="test_user", prompt_text="Test prompt")

        await use_case.execute(request)

        # Verify: get_all_models called with correct parameters
        mock_data_api_client.get_all_models.assert_called_once_with(
            active_only=True,
            available_only=True,  # F012: Exclude rate-limited models
            include_recent=True,
        )
