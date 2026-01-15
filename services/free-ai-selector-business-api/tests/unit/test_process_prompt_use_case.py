"""
Unit tests for ProcessPrompt use case
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.application.use_cases.process_prompt import ProcessPromptUseCase
from app.domain.models import AIModelInfo, PromptRequest


@pytest.mark.unit
class TestProcessPromptUseCase:
    """Test ProcessPrompt use case."""

    async def test_select_best_model_by_effective_score(self, mock_data_api_client):
        """Test best model selection based on effective_reliability_score (F010)."""
        use_case = ProcessPromptUseCase(mock_data_api_client)

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

        best_model = use_case._select_best_model(models)
        # F010: Model B should be selected because of higher effective_reliability_score
        assert best_model.id == 2

    async def test_select_best_model_fallback_to_longterm(self, mock_data_api_client):
        """Test model selection uses fallback when no recent data (F010)."""
        use_case = ProcessPromptUseCase(mock_data_api_client)

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

        best_model = use_case._select_best_model(models)
        # Model B has higher effective_reliability_score (fallback to long-term)
        assert best_model.id == 2

    async def test_select_fallback_model_by_effective_score(self, mock_data_api_client):
        """Test fallback model selection uses effective_reliability_score (F010)."""
        use_case = ProcessPromptUseCase(mock_data_api_client)

        models = [
            AIModelInfo(
                id=1,
                name="Model A",
                provider="Provider A",
                api_endpoint="https://a.com",
                reliability_score=0.9,
                is_active=True,
                effective_reliability_score=0.9,
                recent_request_count=10,
                decision_reason="recent_score",
            ),
            AIModelInfo(
                id=2,
                name="Model B",
                provider="Provider B",
                api_endpoint="https://b.com",
                reliability_score=0.7,
                is_active=True,
                effective_reliability_score=0.75,
                recent_request_count=5,
                decision_reason="recent_score",
            ),
        ]

        failed_model = models[0]
        fallback = use_case._select_fallback_model(models, failed_model)

        assert fallback is not None
        assert fallback.id == 2  # Model B is the fallback

    async def test_no_fallback_when_only_one_model(self, mock_data_api_client):
        """Test no fallback when only one model available."""
        use_case = ProcessPromptUseCase(mock_data_api_client)

        models = [
            AIModelInfo(
                id=1,
                name="Model A",
                provider="Provider A",
                api_endpoint="https://a.com",
                reliability_score=0.9,
                is_active=True,
                effective_reliability_score=0.9,
                recent_request_count=10,
                decision_reason="recent_score",
            ),
        ]

        failed_model = models[0]
        fallback = use_case._select_fallback_model(models, failed_model)

        assert fallback is None

    @patch("app.application.use_cases.process_prompt.ProviderRegistry")
    async def test_execute_success(self, mock_registry, mock_data_api_client):
        """Test successful prompt processing (F008 SSOT via ProviderRegistry)."""
        # Mock AI provider from registry
        mock_provider = AsyncMock()
        mock_provider.generate.return_value = "Generated response"
        mock_registry.get_provider.return_value = mock_provider

        # Mock models returned from Data API with F010 fields
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
        """Test error when no active models available."""
        mock_data_api_client.get_all_models.return_value = []

        use_case = ProcessPromptUseCase(mock_data_api_client)
        request = PromptRequest(user_id="test_user", prompt_text="Test prompt")

        with pytest.raises(Exception, match="No active AI models available"):
            await use_case.execute(request)


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

    @patch("app.application.use_cases.process_prompt.ProviderRegistry")
    async def test_system_prompt_passed_to_provider(self, mock_registry, mock_data_api_client):
        """Test that system_prompt is correctly passed to AI provider (F011-B)."""
        # Mock AI provider from registry
        mock_provider = AsyncMock()
        mock_provider.generate.return_value = "Generated response"
        mock_registry.get_provider.return_value = mock_provider

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

    @patch("app.application.use_cases.process_prompt.ProviderRegistry")
    async def test_response_format_passed_to_provider(self, mock_registry, mock_data_api_client):
        """Test that response_format is correctly passed to AI provider (F011-B)."""
        # Mock AI provider from registry
        mock_provider = AsyncMock()
        mock_provider.generate.return_value = '{"result": "test"}'
        mock_registry.get_provider.return_value = mock_provider

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

    @patch("app.application.use_cases.process_prompt.ProviderRegistry")
    async def test_both_system_prompt_and_response_format(self, mock_registry, mock_data_api_client):
        """Test that both system_prompt and response_format are passed together (F011-B)."""
        # Mock AI provider from registry
        mock_provider = AsyncMock()
        mock_provider.generate.return_value = '{"answer": "42"}'
        mock_registry.get_provider.return_value = mock_provider

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
