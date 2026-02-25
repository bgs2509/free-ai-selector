"""
Unit tests for ProcessPrompt use case

Note: F012 implementation changed the use case to use a full fallback loop
instead of _select_best_model and _select_fallback_model methods.
Model selection tests now verify sorting by effective_reliability_score.
"""

import os
from unittest.mock import AsyncMock, patch

import pytest

from app.application.services.circuit_breaker import (
    CB_FAILURE_THRESHOLD,
    CircuitBreakerManager,
)
from app.application.use_cases.process_prompt import ProcessPromptUseCase
from app.domain.models import AIModelInfo, PromptRequest


@pytest.mark.unit
class TestProcessPromptUseCase:
    """Test ProcessPrompt use case."""

    def test_models_sorted_by_effective_score(self, mock_data_api_client):
        """Test that models are sorted by effective_reliability_score (F010)."""
        models = [
            AIModelInfo(
                id=1,
                name="Model A",
                provider="Provider A",
                api_endpoint="https://a.com",
                reliability_score=0.9,  # High long-term score
                is_active=True,
                effective_reliability_score=0.7,  # But lower effective (recent degraded)
                recent_request_count=10,
                decision_reason="recent_score",
            ),
            AIModelInfo(
                id=2,
                name="Model B",
                provider="Provider B",
                api_endpoint="https://b.com",
                reliability_score=0.7,  # Lower long-term score
                is_active=True,
                effective_reliability_score=0.85,  # But higher effective (recent good)
                recent_request_count=15,
                decision_reason="recent_score",
            ),
        ]

        # F010: Sort by effective_reliability_score descending
        sorted_models = sorted(models, key=lambda m: m.effective_reliability_score, reverse=True)

        # Model B (id=2) should be first because of higher effective score
        assert sorted_models[0].id == 2
        assert sorted_models[1].id == 1

    def test_models_sorted_with_fallback_scores(self, mock_data_api_client):
        """Test model sorting uses fallback when no recent data (F010)."""
        models = [
            AIModelInfo(
                id=1,
                name="Model A",
                provider="Provider A",
                api_endpoint="https://a.com",
                reliability_score=0.8,
                is_active=True,
                effective_reliability_score=0.8,  # Fallback to long-term
                recent_request_count=2,  # Less than threshold
                decision_reason="fallback",
            ),
            AIModelInfo(
                id=2,
                name="Model B",
                provider="Provider B",
                api_endpoint="https://b.com",
                reliability_score=0.9,
                is_active=True,
                effective_reliability_score=0.9,  # Fallback to long-term
                recent_request_count=1,  # Less than threshold
                decision_reason="fallback",
            ),
        ]

        sorted_models = sorted(models, key=lambda m: m.effective_reliability_score, reverse=True)

        # Model B has higher effective_reliability_score (fallback to long-term)
        assert sorted_models[0].id == 2

    @patch.dict(os.environ, {"HUGGINGFACE_API_KEY": "test_key"})
    @patch("app.application.use_cases.process_prompt.ProviderRegistry")
    async def test_execute_success(self, mock_registry, mock_data_api_client):
        """Test successful prompt processing (F008 SSOT via ProviderRegistry)."""
        # Mock AI provider from registry
        mock_provider = AsyncMock()
        mock_provider.generate.return_value = "Generated response"
        mock_registry.get_provider.return_value = mock_provider
        # F018: Mock get_api_key_env for _filter_configured_models
        mock_registry.get_api_key_env.return_value = "HUGGINGFACE_API_KEY"

        # Mock models returned from Data API with F010 + F012 fields
        mock_data_api_client.get_all_models.return_value = [
            AIModelInfo(
                id=1,
                name="HuggingFace Test Model",
                provider="HuggingFace",
                api_endpoint="https://api.test.com",
                reliability_score=0.9,
                is_active=True,
                effective_reliability_score=0.9,
                recent_request_count=0,
                decision_reason="fallback",
            ),
        ]

        use_case = ProcessPromptUseCase(mock_data_api_client)
        request = PromptRequest(user_id="test_user", prompt_text="Test prompt")

        response = await use_case.execute(request)

        assert response.success is True
        assert response.response_text == "Generated response"
        assert response.selected_model_name == "HuggingFace Test Model"
        mock_data_api_client.increment_success.assert_called_once()
        # F008: Verify provider was fetched from registry
        mock_registry.get_provider.assert_called_with("HuggingFace")

    async def test_execute_no_active_models(self, mock_data_api_client):
        """Test error when no active models available (F025: ServiceUnavailable)."""
        from app.domain.exceptions import ServiceUnavailable

        mock_data_api_client.get_all_models.return_value = []

        use_case = ProcessPromptUseCase(mock_data_api_client)
        request = PromptRequest(user_id="test_user", prompt_text="Test prompt")

        with pytest.raises(ServiceUnavailable, match="No active AI models available"):
            await use_case.execute(request)

    @patch.dict(os.environ, {}, clear=True)
    async def test_execute_no_configured_models(self, mock_data_api_client):
        """Test error when no models have configured API keys (F025: ServiceUnavailable)."""
        from app.domain.exceptions import ServiceUnavailable

        # Models exist but none have API keys configured
        mock_data_api_client.get_all_models.return_value = [
            AIModelInfo(
                id=1,
                name="Model 1",
                provider="Provider1",
                api_endpoint="https://api.test.com",
                reliability_score=0.9,
                is_active=True,
                effective_reliability_score=0.9,
            ),
        ]

        use_case = ProcessPromptUseCase(mock_data_api_client)
        request = PromptRequest(user_id="test_user", prompt_text="Test prompt")

        with pytest.raises(ServiceUnavailable, match="No configured AI models available"):
            await use_case.execute(request)

    @patch.dict(os.environ, {"HIGH_KEY": "high", "LOW_KEY": "low"})
    @patch("app.application.use_cases.process_prompt.ProviderRegistry")
    async def test_execute_with_requested_model_id_prioritizes_requested(
        self, mock_registry, mock_data_api_client
    ):
        """Requested model_id should be tried first even with lower score (F019)."""
        high_provider = AsyncMock()
        high_provider.generate.return_value = "high response"
        low_provider = AsyncMock()
        low_provider.generate.return_value = "forced response"

        mock_registry.get_provider.side_effect = lambda provider: {
            "ProviderHigh": high_provider,
            "ProviderLow": low_provider,
        }[provider]
        mock_registry.get_api_key_env.side_effect = lambda provider: {
            "ProviderHigh": "HIGH_KEY",
            "ProviderLow": "LOW_KEY",
        }.get(provider, "")

        mock_data_api_client.get_all_models.return_value = [
            AIModelInfo(
                id=1,
                name="High Model",
                provider="ProviderHigh",
                api_endpoint="https://high.test.com",
                reliability_score=0.95,
                is_active=True,
                effective_reliability_score=0.95,
                recent_request_count=10,
                decision_reason="recent_score",
            ),
            AIModelInfo(
                id=2,
                name="Low Model",
                provider="ProviderLow",
                api_endpoint="https://low.test.com",
                reliability_score=0.6,
                is_active=True,
                effective_reliability_score=0.6,
                recent_request_count=10,
                decision_reason="recent_score",
            ),
        ]

        use_case = ProcessPromptUseCase(mock_data_api_client)
        request = PromptRequest(
            user_id="test_user",
            prompt_text="Test prompt",
            model_id=2,
        )

        response = await use_case.execute(request)

        assert response.success is True
        assert response.selected_model_name == "Low Model"
        low_provider.generate.assert_called_once()
        high_provider.generate.assert_not_called()

    @patch.dict(os.environ, {"HIGH_KEY": "high", "LOW_KEY": "low"})
    @patch("app.application.use_cases.process_prompt.ProviderRegistry")
    async def test_execute_with_missing_requested_model_id_falls_back_to_auto_selection(
        self, mock_registry, mock_data_api_client
    ):
        """Missing requested model_id should keep auto-selection behavior (F019)."""
        high_provider = AsyncMock()
        high_provider.generate.return_value = "best response"
        low_provider = AsyncMock()
        low_provider.generate.return_value = "secondary response"

        mock_registry.get_provider.side_effect = lambda provider: {
            "ProviderHigh": high_provider,
            "ProviderLow": low_provider,
        }[provider]
        mock_registry.get_api_key_env.side_effect = lambda provider: {
            "ProviderHigh": "HIGH_KEY",
            "ProviderLow": "LOW_KEY",
        }.get(provider, "")

        mock_data_api_client.get_all_models.return_value = [
            AIModelInfo(
                id=1,
                name="High Model",
                provider="ProviderHigh",
                api_endpoint="https://high.test.com",
                reliability_score=0.95,
                is_active=True,
                effective_reliability_score=0.95,
                recent_request_count=10,
                decision_reason="recent_score",
            ),
            AIModelInfo(
                id=2,
                name="Low Model",
                provider="ProviderLow",
                api_endpoint="https://low.test.com",
                reliability_score=0.6,
                is_active=True,
                effective_reliability_score=0.6,
                recent_request_count=10,
                decision_reason="recent_score",
            ),
        ]

        use_case = ProcessPromptUseCase(mock_data_api_client)
        request = PromptRequest(
            user_id="test_user",
            prompt_text="Test prompt",
            model_id=999,
        )

        response = await use_case.execute(request)

        assert response.success is True
        assert response.selected_model_name == "High Model"
        high_provider.generate.assert_called_once()

    @patch.dict(os.environ, {"HIGH_KEY": "high", "LOW_KEY": "low"})
    @patch("app.application.use_cases.process_prompt.ProviderRegistry")
    async def test_execute_with_requested_model_error_uses_fallback_model(
        self, mock_registry, mock_data_api_client
    ):
        """If requested model fails, use case should continue with fallback models (F019)."""
        high_provider = AsyncMock()
        high_provider.generate.return_value = "fallback response"
        low_provider = AsyncMock()
        low_provider.generate.side_effect = Exception("forced model failed")

        mock_registry.get_provider.side_effect = lambda provider: {
            "ProviderHigh": high_provider,
            "ProviderLow": low_provider,
        }[provider]
        mock_registry.get_api_key_env.side_effect = lambda provider: {
            "ProviderHigh": "HIGH_KEY",
            "ProviderLow": "LOW_KEY",
        }.get(provider, "")

        mock_data_api_client.get_all_models.return_value = [
            AIModelInfo(
                id=1,
                name="High Model",
                provider="ProviderHigh",
                api_endpoint="https://high.test.com",
                reliability_score=0.95,
                is_active=True,
                effective_reliability_score=0.95,
                recent_request_count=10,
                decision_reason="recent_score",
            ),
            AIModelInfo(
                id=2,
                name="Low Model",
                provider="ProviderLow",
                api_endpoint="https://low.test.com",
                reliability_score=0.6,
                is_active=True,
                effective_reliability_score=0.6,
                recent_request_count=10,
                decision_reason="recent_score",
            ),
        ]

        use_case = ProcessPromptUseCase(mock_data_api_client)
        request = PromptRequest(
            user_id="test_user",
            prompt_text="Test prompt",
            model_id=2,
        )

        response = await use_case.execute(request)

        assert response.success is True
        assert response.selected_model_name == "High Model"
        low_provider.generate.assert_called_once()
        high_provider.generate.assert_called_once()


@pytest.mark.unit
class TestModelSelection:
    """Test model selection logic."""

    def test_effective_score_overrides_longterm(self):
        """Test that effective_reliability_score overrides long-term score (F010)."""
        # Model with high long-term but degraded recently
        model1 = AIModelInfo(
            id=1,
            name="Degraded recently",
            provider="Provider A",
            api_endpoint="https://a.com",
            reliability_score=0.95,  # High long-term
            is_active=True,
            effective_reliability_score=0.6,  # Low recent (degraded)
            recent_request_count=10,
            decision_reason="recent_score",
        )

        # Model with lower long-term but improved recently
        model2 = AIModelInfo(
            id=2,
            name="Improved recently",
            provider="Provider B",
            api_endpoint="https://b.com",
            reliability_score=0.7,  # Lower long-term
            is_active=True,
            effective_reliability_score=0.88,  # High recent (improved)
            recent_request_count=15,
            decision_reason="recent_score",
        )

        # F010: Model 2 should be selected based on effective score
        assert model2.effective_reliability_score > model1.effective_reliability_score

    def test_fallback_uses_longterm_score(self):
        """Test that fallback uses reliability_score when no recent data (F010)."""
        # Model with cold start (no recent data)
        model1 = AIModelInfo(
            id=1,
            name="New model",
            provider="Provider A",
            api_endpoint="https://a.com",
            reliability_score=0.8,
            is_active=True,
            effective_reliability_score=0.8,  # Fallback to long-term
            recent_request_count=1,  # Not enough for recent
            decision_reason="fallback",
        )

        model2 = AIModelInfo(
            id=2,
            name="Another new model",
            provider="Provider B",
            api_endpoint="https://b.com",
            reliability_score=0.9,
            is_active=True,
            effective_reliability_score=0.9,  # Fallback to long-term
            recent_request_count=2,  # Not enough for recent
            decision_reason="fallback",
        )

        # F010: Both use fallback, model2 has higher effective_score
        assert model1.decision_reason == "fallback"
        assert model2.decision_reason == "fallback"
        assert model2.effective_reliability_score > model1.effective_reliability_score


@pytest.mark.unit
class TestF011BSystemPromptsAndResponseFormat:
    """Test F011-B: System Prompts & JSON Response Support."""

    @patch.dict(os.environ, {"GROQ_API_KEY": "test_key"})
    @patch("app.application.use_cases.process_prompt.ProviderRegistry")
    async def test_system_prompt_passed_to_provider(self, mock_registry, mock_data_api_client):
        """Test that system_prompt is correctly passed to AI provider (F011-B)."""
        # Mock AI provider from registry
        mock_provider = AsyncMock()
        mock_provider.generate.return_value = "Generated response"
        mock_registry.get_provider.return_value = mock_provider
        mock_registry.get_api_key_env.return_value = "GROQ_API_KEY"

        # Mock models returned from Data API
        mock_data_api_client.get_all_models.return_value = [
            AIModelInfo(
                id=1,
                name="Test Model",
                provider="Groq",
                api_endpoint="https://api.test.com",
                reliability_score=0.9,
                is_active=True,
                effective_reliability_score=0.9,
                recent_request_count=0,
                decision_reason="fallback",
            ),
        ]

        use_case = ProcessPromptUseCase(mock_data_api_client)
        request = PromptRequest(
            user_id="test_user",
            prompt_text="Test prompt",
            system_prompt="You are a helpful assistant.",  # F011-B
        )

        response = await use_case.execute(request)

        assert response.success is True
        # Verify system_prompt was passed to provider.generate()
        mock_provider.generate.assert_called_once()
        call_args = mock_provider.generate.call_args
        assert call_args[0][0] == "Test prompt"  # First positional arg is prompt
        assert call_args[1]["system_prompt"] == "You are a helpful assistant."  # F011-B kwarg

    @patch.dict(os.environ, {"SAMBANOVA_API_KEY": "test_key"})
    @patch("app.application.use_cases.process_prompt.ProviderRegistry")
    async def test_response_format_passed_to_provider(self, mock_registry, mock_data_api_client):
        """Test that response_format is correctly passed to AI provider (F011-B)."""
        # Mock AI provider from registry
        mock_provider = AsyncMock()
        mock_provider.generate.return_value = '{"result": "test"}'
        mock_registry.get_provider.return_value = mock_provider
        mock_registry.get_api_key_env.return_value = "SAMBANOVA_API_KEY"

        # Mock models returned from Data API
        mock_data_api_client.get_all_models.return_value = [
            AIModelInfo(
                id=1,
                name="Test Model",
                provider="SambaNova",
                api_endpoint="https://api.test.com",
                reliability_score=0.9,
                is_active=True,
                effective_reliability_score=0.9,
                recent_request_count=0,
                decision_reason="fallback",
            ),
        ]

        use_case = ProcessPromptUseCase(mock_data_api_client)
        request = PromptRequest(
            user_id="test_user",
            prompt_text="Test prompt",
            response_format={"type": "json_object"},  # F011-B
        )

        response = await use_case.execute(request)

        assert response.success is True
        # Verify response_format was passed to provider.generate()
        mock_provider.generate.assert_called_once()
        call_args = mock_provider.generate.call_args
        assert call_args[0][0] == "Test prompt"  # First positional arg is prompt
        assert call_args[1]["response_format"] == {"type": "json_object"}  # F011-B kwarg

    @patch.dict(os.environ, {"CLOUDFLARE_API_TOKEN": "test_key"})
    @patch("app.application.use_cases.process_prompt.ProviderRegistry")
    async def test_both_system_prompt_and_response_format(self, mock_registry, mock_data_api_client):
        """Test that both system_prompt and response_format are passed together (F011-B)."""
        # Mock AI provider from registry
        mock_provider = AsyncMock()
        mock_provider.generate.return_value = '{"answer": "42"}'
        mock_registry.get_provider.return_value = mock_provider
        mock_registry.get_api_key_env.return_value = "CLOUDFLARE_API_TOKEN"

        # Mock models returned from Data API
        mock_data_api_client.get_all_models.return_value = [
            AIModelInfo(
                id=1,
                name="Test Model",
                provider="Cloudflare",
                api_endpoint="https://api.test.com",
                reliability_score=0.9,
                is_active=True,
                effective_reliability_score=0.9,
                recent_request_count=0,
                decision_reason="fallback",
            ),
        ]

        use_case = ProcessPromptUseCase(mock_data_api_client)
        request = PromptRequest(
            user_id="test_user",
            prompt_text="What is the answer?",
            system_prompt="You are a JSON-only assistant.",  # F011-B
            response_format={"type": "json_object"},  # F011-B
        )

        response = await use_case.execute(request)

        assert response.success is True
        # Verify both parameters were passed to provider.generate()
        mock_provider.generate.assert_called_once()
        call_args = mock_provider.generate.call_args
        assert call_args[0][0] == "What is the answer?"
        assert call_args[1]["system_prompt"] == "You are a JSON-only assistant."
        assert call_args[1]["response_format"] == {"type": "json_object"}

    @patch.dict(os.environ, {"GROQ_API_KEY": "key1", "CEREBRAS_API_KEY": "key2"})
    @patch("app.application.use_cases.process_prompt.ProviderRegistry")
    async def test_fallback_preserves_system_prompt_and_response_format(
        self, mock_registry, mock_data_api_client
    ):
        """Test that system_prompt and response_format are passed to fallback provider (F011-B)."""
        # Mock primary provider (fails)
        mock_primary_provider = AsyncMock()
        mock_primary_provider.generate.side_effect = Exception("API Error")

        # Mock fallback provider (succeeds)
        mock_fallback_provider = AsyncMock()
        mock_fallback_provider.generate.return_value = "Fallback response"

        # Registry returns different providers for primary and fallback
        mock_registry.get_provider.side_effect = [mock_primary_provider, mock_fallback_provider]
        mock_registry.get_api_key_env.side_effect = lambda p: {
            "Groq": "GROQ_API_KEY", "Cerebras": "CEREBRAS_API_KEY"
        }.get(p, "")

        # Mock models returned from Data API (2 models for fallback)
        mock_data_api_client.get_all_models.return_value = [
            AIModelInfo(
                id=1,
                name="Primary Model",
                provider="Groq",
                api_endpoint="https://api1.test.com",
                reliability_score=0.9,
                is_active=True,
                effective_reliability_score=0.9,
                recent_request_count=0,
                decision_reason="fallback",
            ),
            AIModelInfo(
                id=2,
                name="Fallback Model",
                provider="Cerebras",
                api_endpoint="https://api2.test.com",
                reliability_score=0.85,
                is_active=True,
                effective_reliability_score=0.85,
                recent_request_count=0,
                decision_reason="fallback",
            ),
        ]

        use_case = ProcessPromptUseCase(mock_data_api_client)
        request = PromptRequest(
            user_id="test_user",
            prompt_text="Test prompt",
            system_prompt="Test system",  # F011-B
            response_format={"type": "json_object"},  # F011-B
        )

        response = await use_case.execute(request)

        assert response.success is True
        assert response.response_text == "Fallback response"

        # Verify fallback provider received the same parameters
        assert mock_fallback_provider.generate.call_count == 1
        fallback_call_args = mock_fallback_provider.generate.call_args
        assert fallback_call_args[0][0] == "Test prompt"
        assert fallback_call_args[1]["system_prompt"] == "Test system"
        assert fallback_call_args[1]["response_format"] == {"type": "json_object"}


@pytest.mark.unit
class TestF014ErrorHandlingConsolidation:
    """Test F014: Error Handling Consolidation - private methods."""

    async def test_handle_rate_limit_calls_set_availability(self, mock_data_api_client):
        """Test that _handle_rate_limit calls set_availability (F014)."""
        from app.domain.exceptions import RateLimitError

        use_case = ProcessPromptUseCase(mock_data_api_client)
        model = AIModelInfo(
            id=1,
            name="Test Model",
            provider="TestProvider",
            api_endpoint="https://test.com",
            reliability_score=0.9,
            is_active=True,
        )
        error = RateLimitError("Rate limit exceeded", retry_after_seconds=120)

        await use_case._handle_rate_limit(model, error)

        # Verify set_availability was called with correct arguments
        mock_data_api_client.set_availability.assert_called_once_with(
            model_id=1,
            retry_after_seconds=120,
            reason="rate_limit",
            error_type="RateLimitError",
            source="process_prompt",
        )

    async def test_handle_rate_limit_uses_default_cooldown(self, mock_data_api_client):
        """Test that _handle_rate_limit uses default cooldown when not specified (F014)."""
        from app.domain.exceptions import RateLimitError

        use_case = ProcessPromptUseCase(mock_data_api_client)
        model = AIModelInfo(
            id=2,
            name="Test Model",
            provider="TestProvider",
            api_endpoint="https://test.com",
            reliability_score=0.9,
            is_active=True,
        )
        # Error without retry_after_seconds
        error = RateLimitError("Rate limit exceeded")

        await use_case._handle_rate_limit(model, error)

        # Verify set_availability was called with default cooldown (3600)
        mock_data_api_client.set_availability.assert_called_once()
        call_kwargs = mock_data_api_client.set_availability.call_args.kwargs
        assert call_kwargs["model_id"] == 2
        assert call_kwargs["retry_after_seconds"] == 3600
        assert call_kwargs["reason"] == "rate_limit"
        assert call_kwargs["error_type"] == "RateLimitError"
        assert call_kwargs["source"] == "process_prompt"

    async def test_handle_rate_limit_handles_set_availability_error(
        self, mock_data_api_client, caplog
    ):
        """Test that _handle_rate_limit gracefully handles set_availability errors (F014)."""
        from app.domain.exceptions import RateLimitError

        mock_data_api_client.set_availability.side_effect = Exception("API Error")

        use_case = ProcessPromptUseCase(mock_data_api_client)
        model = AIModelInfo(
            id=3,
            name="Test Model",
            provider="TestProvider",
            api_endpoint="https://test.com",
            reliability_score=0.9,
            is_active=True,
        )
        error = RateLimitError("Rate limit exceeded", retry_after_seconds=60)

        # Should not raise, error is logged
        await use_case._handle_rate_limit(model, error)

        # Verify set_availability was called (even though it failed)
        mock_data_api_client.set_availability.assert_called_once()

    async def test_handle_transient_error_calls_increment_failure(self, mock_data_api_client):
        """Test that _handle_transient_error calls increment_failure (F014)."""
        import time

        from app.domain.exceptions import ServerError

        use_case = ProcessPromptUseCase(mock_data_api_client)
        model = AIModelInfo(
            id=1,
            name="Test Model",
            provider="TestProvider",
            api_endpoint="https://test.com",
            reliability_score=0.9,
            is_active=True,
        )
        error = ServerError("Internal server error")
        start_time = time.time() - 1.5  # 1.5 seconds ago

        await use_case._handle_transient_error(model, error, start_time)

        # Verify increment_failure was called
        mock_data_api_client.increment_failure.assert_called_once()
        call_args = mock_data_api_client.increment_failure.call_args
        assert call_args[1]["model_id"] == 1
        # response_time should be approximately 1.5 seconds
        assert 1.4 < call_args[1]["response_time"] < 2.0

    async def test_handle_transient_error_handles_increment_failure_error(
        self, mock_data_api_client, caplog
    ):
        """Test that _handle_transient_error gracefully handles increment_failure errors (F014)."""
        import time

        from app.domain.exceptions import TimeoutError

        mock_data_api_client.increment_failure.side_effect = Exception("API Error")

        use_case = ProcessPromptUseCase(mock_data_api_client)
        model = AIModelInfo(
            id=2,
            name="Test Model",
            provider="TestProvider",
            api_endpoint="https://test.com",
            reliability_score=0.9,
            is_active=True,
        )
        error = TimeoutError("Request timed out")
        start_time = time.time() - 2.0

        # Should not raise, error is logged
        await use_case._handle_transient_error(model, error, start_time)

        # Verify increment_failure was called (even though it failed)
        mock_data_api_client.increment_failure.assert_called_once()

    async def test_handle_transient_error_works_with_various_exception_types(
        self, mock_data_api_client
    ):
        """Test that _handle_transient_error works with all transient error types (F014)."""
        import time

        from app.domain.exceptions import (
            AuthenticationError,
            ProviderError,
            ServerError,
            TimeoutError,
            ValidationError,
        )

        use_case = ProcessPromptUseCase(mock_data_api_client)
        model = AIModelInfo(
            id=1,
            name="Test Model",
            provider="TestProvider",
            api_endpoint="https://test.com",
            reliability_score=0.9,
            is_active=True,
        )

        error_types = [
            ServerError("Server error"),
            TimeoutError("Timeout"),
            AuthenticationError("Auth failed"),
            ValidationError("Invalid request"),
            ProviderError("Provider error"),
        ]

        for error in error_types:
            mock_data_api_client.increment_failure.reset_mock()
            mock_data_api_client.set_availability.reset_mock()
            start_time = time.time()

            await use_case._handle_transient_error(model, error, start_time)

            # Each error type should trigger increment_failure
            mock_data_api_client.increment_failure.assert_called_once()


@pytest.mark.unit
class TestF023Cooldown:
    """Test F023: Cooldown для AuthenticationError и ValidationError."""

    async def test_authentication_error_triggers_cooldown(self, mock_data_api_client):
        """TRQ-001: AuthenticationError -> set_availability(86400)."""
        import time

        from app.domain.exceptions import AuthenticationError

        use_case = ProcessPromptUseCase(mock_data_api_client)
        model = AIModelInfo(
            id=1,
            name="Test Model",
            provider="TestProvider",
            api_endpoint="https://test.com",
            reliability_score=0.9,
            is_active=True,
        )
        error = AuthenticationError("Invalid API key")
        start_time = time.time()

        await use_case._handle_transient_error(model, error, start_time)

        mock_data_api_client.set_availability.assert_called_once_with(
            model_id=1,
            retry_after_seconds=86400,
            reason="permanent_error",
            error_type="AuthenticationError",
            source="process_prompt",
        )
        mock_data_api_client.increment_failure.assert_called_once()

    async def test_validation_error_triggers_cooldown(self, mock_data_api_client):
        """TRQ-002: ValidationError -> set_availability(86400)."""
        import time

        from app.domain.exceptions import ValidationError

        use_case = ProcessPromptUseCase(mock_data_api_client)
        model = AIModelInfo(
            id=2,
            name="Test Model",
            provider="TestProvider",
            api_endpoint="https://test.com",
            reliability_score=0.9,
            is_active=True,
        )
        error = ValidationError("Endpoint not found")
        start_time = time.time()

        await use_case._handle_transient_error(model, error, start_time)

        mock_data_api_client.set_availability.assert_called_once_with(
            model_id=2,
            retry_after_seconds=86400,
            reason="permanent_error",
            error_type="ValidationError",
            source="process_prompt",
        )
        mock_data_api_client.increment_failure.assert_called_once()

    async def test_server_error_does_not_trigger_cooldown(self, mock_data_api_client):
        """ServerError НЕ должен вызывать cooldown."""
        import time

        from app.domain.exceptions import ServerError

        use_case = ProcessPromptUseCase(mock_data_api_client)
        model = AIModelInfo(
            id=3,
            name="Test Model",
            provider="TestProvider",
            api_endpoint="https://test.com",
            reliability_score=0.9,
            is_active=True,
        )
        error = ServerError("Internal server error")
        start_time = time.time()

        await use_case._handle_transient_error(model, error, start_time)

        mock_data_api_client.set_availability.assert_not_called()
        mock_data_api_client.increment_failure.assert_called_once()

    async def test_cooldown_failure_does_not_break_flow(self, mock_data_api_client):
        """TRQ-008: set_availability ошибка не ломает запрос."""
        import time

        from app.domain.exceptions import AuthenticationError

        mock_data_api_client.set_availability.side_effect = Exception("Data API down")

        use_case = ProcessPromptUseCase(mock_data_api_client)
        model = AIModelInfo(
            id=1,
            name="Test Model",
            provider="TestProvider",
            api_endpoint="https://test.com",
            reliability_score=0.9,
            is_active=True,
        )
        error = AuthenticationError("Invalid API key")
        start_time = time.time()

        # Не должен бросить исключение
        await use_case._handle_transient_error(model, error, start_time)

        mock_data_api_client.set_availability.assert_called_once()
        mock_data_api_client.increment_failure.assert_called_once()


@pytest.mark.unit
class TestF023Telemetry:
    """Test F023: Per-request telemetry."""

    @patch.dict(os.environ, {"HUGGINGFACE_API_KEY": "test_key"})
    @patch("app.application.use_cases.process_prompt.ProviderRegistry")
    async def test_success_first_model_telemetry(self, mock_registry, mock_data_api_client):
        """TRQ-006: attempts=1, fallback_used=False при успехе первой модели."""
        mock_provider = AsyncMock()
        mock_provider.generate.return_value = "response"
        mock_registry.get_provider.return_value = mock_provider
        mock_registry.get_api_key_env.return_value = "HUGGINGFACE_API_KEY"

        mock_data_api_client.get_all_models.return_value = [
            AIModelInfo(
                id=1,
                name="Model",
                provider="HuggingFace",
                api_endpoint="https://test.com",
                reliability_score=0.9,
                is_active=True,
                effective_reliability_score=0.9,
            ),
        ]

        use_case = ProcessPromptUseCase(mock_data_api_client)
        request = PromptRequest(user_id="test", prompt_text="test")
        response = await use_case.execute(request)

        assert response.attempts == 1
        assert response.fallback_used is False

    @patch.dict(os.environ, {"KEY1": "key1", "KEY2": "key2"})
    @patch("app.application.use_cases.process_prompt.ProviderRegistry")
    async def test_fallback_model_telemetry(self, mock_registry, mock_data_api_client):
        """TRQ-006: attempts>=2, fallback_used=True при fallback."""
        from app.domain.exceptions import ServerError

        mock_primary = AsyncMock()
        mock_primary.generate.side_effect = ServerError("Error")
        mock_fallback = AsyncMock()
        mock_fallback.generate.return_value = "fallback response"

        mock_registry.get_provider.side_effect = [mock_primary, mock_fallback]
        mock_registry.get_api_key_env.side_effect = lambda p: {
            "Primary": "KEY1", "Fallback": "KEY2"
        }.get(p, "")

        mock_data_api_client.get_all_models.return_value = [
            AIModelInfo(
                id=1,
                name="Primary",
                provider="Primary",
                api_endpoint="https://test.com",
                reliability_score=0.9,
                is_active=True,
                effective_reliability_score=0.9,
            ),
            AIModelInfo(
                id=2,
                name="Fallback",
                provider="Fallback",
                api_endpoint="https://test2.com",
                reliability_score=0.8,
                is_active=True,
                effective_reliability_score=0.8,
            ),
        ]

        use_case = ProcessPromptUseCase(mock_data_api_client)
        request = PromptRequest(user_id="test", prompt_text="test")
        response = await use_case.execute(request)

        assert response.attempts == 2
        assert response.fallback_used is True

    def test_prompt_response_has_telemetry_defaults(self):
        """TRQ-006: PromptResponse defaults: attempts=1, fallback_used=False."""
        from decimal import Decimal

        from app.domain.models import PromptResponse

        response = PromptResponse(
            prompt_text="test",
            response_text="result",
            selected_model_name="Model",
            selected_model_provider="Provider",
            response_time=Decimal("1.5"),
            success=True,
        )

        assert response.attempts == 1
        assert response.fallback_used is False

    def test_process_prompt_response_has_telemetry_fields(self):
        """TRQ-007: ProcessPromptResponse содержит attempts и fallback_used."""
        from decimal import Decimal

        from app.api.v1.schemas import ProcessPromptResponse

        response = ProcessPromptResponse(
            prompt="test",
            response="result",
            selected_model="Model",
            provider="Provider",
            response_time_seconds=Decimal("1.5"),
            success=True,
            attempts=3,
            fallback_used=True,
        )

        assert response.attempts == 3
        assert response.fallback_used is True


@pytest.mark.unit
class TestF024CircuitBreaker:
    """F024: Circuit breaker integration in failover loop."""

    @patch.dict(os.environ, {"KEY1": "key1", "KEY2": "key2"})
    @patch("app.application.use_cases.process_prompt.ProviderRegistry")
    async def test_open_circuit_skips_provider(
        self, mock_registry, mock_data_api_client
    ):
        """F024: Provider with OPEN circuit is skipped in failover."""
        # Открыть CB для Provider1
        for _ in range(CB_FAILURE_THRESHOLD):
            CircuitBreakerManager.record_failure("Provider1")

        # Provider2 отвечает успешно
        mock_provider2 = AsyncMock()
        mock_provider2.generate.return_value = "response from provider2"
        mock_registry.get_provider.return_value = mock_provider2
        mock_registry.get_api_key_env.side_effect = lambda p: {
            "Provider1": "KEY1", "Provider2": "KEY2"
        }.get(p, "")

        mock_data_api_client.get_all_models.return_value = [
            AIModelInfo(
                id=1,
                name="Model1",
                provider="Provider1",
                api_endpoint="https://test1.com",
                reliability_score=0.95,
                is_active=True,
                effective_reliability_score=0.95,
            ),
            AIModelInfo(
                id=2,
                name="Model2",
                provider="Provider2",
                api_endpoint="https://test2.com",
                reliability_score=0.8,
                is_active=True,
                effective_reliability_score=0.8,
            ),
        ]

        use_case = ProcessPromptUseCase(mock_data_api_client)
        request = PromptRequest(user_id="test", prompt_text="test")
        response = await use_case.execute(request)

        assert response.success is True
        assert response.selected_model_name == "Model2"
        # Provider1 пропущен по CB — только 1 попытка (Provider2)
        assert response.attempts == 1

    @patch.dict(os.environ, {"KEY1": "key1"})
    @patch("app.application.use_cases.process_prompt.ProviderRegistry")
    async def test_failure_records_to_circuit_breaker(
        self, mock_registry, mock_data_api_client
    ):
        """F024: Failed generation records failure in CB."""
        from app.domain.exceptions import ServerError

        mock_provider = AsyncMock()
        mock_provider.generate.side_effect = ServerError("Server error")
        mock_registry.get_provider.return_value = mock_provider
        mock_registry.get_api_key_env.return_value = "KEY1"

        mock_data_api_client.get_all_models.return_value = [
            AIModelInfo(
                id=1,
                name="Model1",
                provider="FailProvider",
                api_endpoint="https://test.com",
                reliability_score=0.9,
                is_active=True,
                effective_reliability_score=0.9,
            ),
        ]

        use_case = ProcessPromptUseCase(mock_data_api_client)
        request = PromptRequest(user_id="test", prompt_text="test")

        with pytest.raises(Exception, match="All AI providers failed"):
            await use_case.execute(request)

        statuses = CircuitBreakerManager.get_all_statuses()
        assert statuses["FailProvider"] == "closed"  # 1 failure < threshold
        assert CircuitBreakerManager._circuits["FailProvider"].failure_count == 1


@pytest.mark.unit
class TestF025Backpressure:
    """F025: Server-side backpressure (HTTP 429/503)."""

    @patch.dict(os.environ, {"KEY1": "key1", "KEY2": "key2"})
    @patch("app.application.use_cases.process_prompt.ProviderRegistry")
    async def test_all_rate_limited_raises_all_providers_rate_limited(
        self, mock_registry, mock_data_api_client
    ):
        """TRQ-001: Все провайдеры RateLimited → AllProvidersRateLimited."""
        from app.domain.exceptions import AllProvidersRateLimited, RateLimitError

        mock_provider = AsyncMock()
        mock_provider.generate.side_effect = RateLimitError(
            "Rate limited", retry_after_seconds=30
        )
        mock_registry.get_provider.return_value = mock_provider
        mock_registry.get_api_key_env.side_effect = lambda p: {
            "Provider1": "KEY1", "Provider2": "KEY2"
        }.get(p, "")

        mock_data_api_client.get_all_models.return_value = [
            AIModelInfo(
                id=1,
                name="Model1",
                provider="Provider1",
                api_endpoint="https://test1.com",
                reliability_score=0.9,
                is_active=True,
                effective_reliability_score=0.9,
            ),
            AIModelInfo(
                id=2,
                name="Model2",
                provider="Provider2",
                api_endpoint="https://test2.com",
                reliability_score=0.8,
                is_active=True,
                effective_reliability_score=0.8,
            ),
        ]

        use_case = ProcessPromptUseCase(mock_data_api_client)
        request = PromptRequest(user_id="test", prompt_text="test")

        with pytest.raises(AllProvidersRateLimited) as exc_info:
            await use_case.execute(request)

        assert exc_info.value.retry_after_seconds == 30
        assert exc_info.value.attempts == 2
        assert exc_info.value.providers_tried == 2

    async def test_no_models_raises_service_unavailable(self, mock_data_api_client):
        """TRQ-002: Нет моделей → ServiceUnavailable с reason='no_active_models'."""
        from app.domain.exceptions import ServiceUnavailable

        mock_data_api_client.get_all_models.return_value = []

        use_case = ProcessPromptUseCase(mock_data_api_client)
        request = PromptRequest(user_id="test", prompt_text="test")

        with pytest.raises(ServiceUnavailable) as exc_info:
            await use_case.execute(request)

        assert exc_info.value.reason == "no_active_models"

    @patch.dict(os.environ, {"KEY1": "key1", "KEY2": "key2"})
    @patch("app.application.use_cases.process_prompt.ProviderRegistry")
    async def test_all_cb_open_raises_service_unavailable(
        self, mock_registry, mock_data_api_client
    ):
        """TRQ-003: Все CB open → ServiceUnavailable с reason='all_circuit_breaker_open'."""
        from app.domain.exceptions import ServiceUnavailable

        mock_registry.get_api_key_env.side_effect = lambda p: {
            "Provider1": "KEY1", "Provider2": "KEY2"
        }.get(p, "")

        # Открыть CB для обоих провайдеров
        for _ in range(CB_FAILURE_THRESHOLD):
            CircuitBreakerManager.record_failure("Provider1")
            CircuitBreakerManager.record_failure("Provider2")

        mock_data_api_client.get_all_models.return_value = [
            AIModelInfo(
                id=1,
                name="Model1",
                provider="Provider1",
                api_endpoint="https://test1.com",
                reliability_score=0.9,
                is_active=True,
                effective_reliability_score=0.9,
            ),
            AIModelInfo(
                id=2,
                name="Model2",
                provider="Provider2",
                api_endpoint="https://test2.com",
                reliability_score=0.8,
                is_active=True,
                effective_reliability_score=0.8,
            ),
        ]

        use_case = ProcessPromptUseCase(mock_data_api_client)
        request = PromptRequest(user_id="test", prompt_text="test")

        with pytest.raises(ServiceUnavailable) as exc_info:
            await use_case.execute(request)

        assert exc_info.value.reason == "all_circuit_breaker_open"

    @patch.dict(os.environ, {}, clear=True)
    async def test_no_api_keys_raises_service_unavailable(self, mock_data_api_client):
        """TRQ-004: Нет API-ключей → ServiceUnavailable с reason='no_api_keys'."""
        from app.domain.exceptions import ServiceUnavailable

        mock_data_api_client.get_all_models.return_value = [
            AIModelInfo(
                id=1,
                name="Model1",
                provider="Provider1",
                api_endpoint="https://test.com",
                reliability_score=0.9,
                is_active=True,
                effective_reliability_score=0.9,
            ),
        ]

        use_case = ProcessPromptUseCase(mock_data_api_client)
        request = PromptRequest(user_id="test", prompt_text="test")

        with pytest.raises(ServiceUnavailable) as exc_info:
            await use_case.execute(request)

        assert exc_info.value.reason == "no_api_keys"

    @patch.dict(os.environ, {"KEY1": "key1", "KEY2": "key2"})
    @patch("app.application.use_cases.process_prompt.ProviderRegistry")
    async def test_mixed_errors_raises_exception(
        self, mock_registry, mock_data_api_client
    ):
        """TRQ-005: Смешанные ошибки (RateLimit + Server) → Exception (HTTP 500)."""
        from app.domain.exceptions import RateLimitError, ServerError

        mock_provider1 = AsyncMock()
        mock_provider1.generate.side_effect = RateLimitError("Rate limited")
        mock_provider2 = AsyncMock()
        mock_provider2.generate.side_effect = ServerError("Server error")

        mock_registry.get_provider.side_effect = [mock_provider1, mock_provider2]
        mock_registry.get_api_key_env.side_effect = lambda p: {
            "Provider1": "KEY1", "Provider2": "KEY2"
        }.get(p, "")

        mock_data_api_client.get_all_models.return_value = [
            AIModelInfo(
                id=1,
                name="Model1",
                provider="Provider1",
                api_endpoint="https://test1.com",
                reliability_score=0.9,
                is_active=True,
                effective_reliability_score=0.9,
            ),
            AIModelInfo(
                id=2,
                name="Model2",
                provider="Provider2",
                api_endpoint="https://test2.com",
                reliability_score=0.8,
                is_active=True,
                effective_reliability_score=0.8,
            ),
        ]

        use_case = ProcessPromptUseCase(mock_data_api_client)
        request = PromptRequest(user_id="test", prompt_text="test")

        with pytest.raises(Exception, match="All AI providers failed"):
            await use_case.execute(request)

    @patch.dict(os.environ, {"KEY1": "key1"})
    @patch("app.application.use_cases.process_prompt.ProviderRegistry")
    async def test_rate_limited_retry_after_uses_min(
        self, mock_registry, mock_data_api_client
    ):
        """TRQ-007: retry_after_seconds = min(значений провайдеров)."""
        from app.domain.exceptions import AllProvidersRateLimited, RateLimitError

        # Два вызова с разными retry_after
        call_count = 0

        async def rate_limit_generator(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RateLimitError("Rate limited", retry_after_seconds=120)
            raise RateLimitError("Rate limited", retry_after_seconds=45)

        mock_provider = AsyncMock()
        mock_provider.generate.side_effect = rate_limit_generator
        mock_registry.get_provider.return_value = mock_provider
        mock_registry.get_api_key_env.return_value = "KEY1"

        mock_data_api_client.get_all_models.return_value = [
            AIModelInfo(
                id=1,
                name="Model1",
                provider="Provider1",
                api_endpoint="https://test1.com",
                reliability_score=0.9,
                is_active=True,
                effective_reliability_score=0.9,
            ),
            AIModelInfo(
                id=2,
                name="Model2",
                provider="Provider1",
                api_endpoint="https://test2.com",
                reliability_score=0.8,
                is_active=True,
                effective_reliability_score=0.8,
            ),
        ]

        use_case = ProcessPromptUseCase(mock_data_api_client)
        request = PromptRequest(user_id="test", prompt_text="test")

        with pytest.raises(AllProvidersRateLimited) as exc_info:
            await use_case.execute(request)

        assert exc_info.value.retry_after_seconds == 45
