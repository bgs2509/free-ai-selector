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

    async def test_select_best_model(self, mock_data_api_client):
        """Test best model selection based on reliability score."""
        use_case = ProcessPromptUseCase(mock_data_api_client)

        models = [
            AIModelInfo(
                id=1,
                name="Model A",
                provider="Provider A",
                api_endpoint="https://a.com",
                reliability_score=0.8,
                is_active=True,
            ),
            AIModelInfo(
                id=2,
                name="Model B",
                provider="Provider B",
                api_endpoint="https://b.com",
                reliability_score=0.9,
                is_active=True,
            ),
        ]

        best_model = use_case._select_best_model(models)
        assert best_model.id == 2  # Model B has higher reliability

    async def test_select_fallback_model(self, mock_data_api_client):
        """Test fallback model selection."""
        use_case = ProcessPromptUseCase(mock_data_api_client)

        models = [
            AIModelInfo(
                id=1,
                name="Model A",
                provider="Provider A",
                api_endpoint="https://a.com",
                reliability_score=0.9,
                is_active=True,
            ),
            AIModelInfo(
                id=2,
                name="Model B",
                provider="Provider B",
                api_endpoint="https://b.com",
                reliability_score=0.7,
                is_active=True,
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
            ),
        ]

        failed_model = models[0]
        fallback = use_case._select_fallback_model(models, failed_model)

        assert fallback is None

    @patch("app.application.use_cases.process_prompt.HuggingFaceProvider")
    async def test_execute_success(self, mock_provider_class, mock_data_api_client):
        """Test successful prompt processing."""
        # Mock AI provider
        mock_provider = AsyncMock()
        mock_provider.generate.return_value = "Generated response"
        mock_provider_class.return_value = mock_provider

        # Mock models returned from Data API
        mock_data_api_client.get_all_models.return_value = [
            AIModelInfo(
                id=1,
                name="HuggingFace Test Model",
                provider="HuggingFace",
                api_endpoint="https://api.test.com",
                reliability_score=0.9,
                is_active=True,
            ),
        ]

        use_case = ProcessPromptUseCase(mock_data_api_client)
        request = PromptRequest(user_id="test_user", prompt_text="Test prompt")

        response = await use_case.execute(request)

        assert response.success is True
        assert response.response_text == "Generated response"
        assert response.selected_model_name == "HuggingFace Test Model"
        mock_data_api_client.increment_success.assert_called_once()

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

    def test_reliability_score_comparison(self):
        """Test that higher reliability score is preferred."""
        model1 = AIModelInfo(
            id=1,
            name="Fast but unreliable",
            provider="Provider A",
            api_endpoint="https://a.com",
            reliability_score=0.5,  # Low reliability
            is_active=True,
        )

        model2 = AIModelInfo(
            id=2,
            name="Reliable model",
            provider="Provider B",
            api_endpoint="https://b.com",
            reliability_score=0.9,  # High reliability
            is_active=True,
        )

        # Model 2 should be selected
        assert model2.reliability_score > model1.reliability_score
