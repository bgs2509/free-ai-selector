"""
Unit tests for F015: Data API Endpoints DRY Refactoring.

Tests the unified _model_to_response function and get_model_or_404 dependency.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.models import _model_to_response, _calculate_recent_metrics
from app.domain.models import AIModel


class TestUnifiedModelToResponse:
    """Tests for unified _model_to_response function (F015: FR-001)."""

    def _create_test_model(self) -> AIModel:
        """Create a test AIModel instance."""
        return AIModel(
            id=1,
            name="Test Model",
            provider="TestProvider",
            api_endpoint="https://api.test.com",
            success_count=80,
            failure_count=20,
            total_response_time=Decimal("100.0"),
            request_count=100,
            last_checked=datetime.utcnow(),
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            api_format="openai",
            env_var="TEST_API_KEY",
            available_at=None,
        )

    def test_model_to_response_without_recent_stats(self):
        """Test _model_to_response without recent_stats returns None for recent fields."""
        model = self._create_test_model()

        response = _model_to_response(model)

        # Basic fields should be populated
        assert response.id == 1
        assert response.name == "Test Model"
        assert response.provider == "TestProvider"
        assert response.is_active is True

        # Recent fields should be None when no recent_stats provided
        assert response.recent_success_rate is None
        assert response.recent_request_count is None
        assert response.recent_reliability_score is None
        assert response.effective_reliability_score is None
        assert response.decision_reason is None

    def test_model_to_response_with_recent_stats(self):
        """Test _model_to_response with recent_stats populates recent fields."""
        model = self._create_test_model()
        recent_stats: Dict[int, Dict[str, Any]] = {
            1: {
                "request_count": 10,
                "success_count": 8,
                "avg_response_time": 1.5,
            }
        }

        response = _model_to_response(model, recent_stats)

        # Basic fields should be populated
        assert response.id == 1
        assert response.name == "Test Model"

        # Recent fields should be calculated from recent_stats
        assert response.recent_success_rate == 0.8
        assert response.recent_request_count == 10
        assert response.recent_reliability_score is not None
        assert response.effective_reliability_score is not None
        assert response.decision_reason == "recent_score"

    def test_model_to_response_with_empty_recent_stats(self):
        """Test _model_to_response with empty recent_stats falls back."""
        model = self._create_test_model()
        recent_stats: Dict[int, Dict[str, Any]] = {}  # No stats for model id=1

        response = _model_to_response(model, recent_stats)

        # Should fallback to long-term score
        assert response.recent_success_rate is None
        assert response.recent_request_count == 0
        assert response.decision_reason == "fallback"
        # effective_reliability_score should be the long-term reliability_score
        assert response.effective_reliability_score is not None


class TestCalculateRecentMetrics:
    """Tests for _calculate_recent_metrics helper function."""

    def _create_test_model(self) -> AIModel:
        """Create a test AIModel instance."""
        return AIModel(
            id=1,
            name="Test Model",
            provider="TestProvider",
            api_endpoint="https://api.test.com",
            success_count=80,
            failure_count=20,
            total_response_time=Decimal("100.0"),
            request_count=100,
            last_checked=datetime.utcnow(),
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

    def test_calculate_recent_metrics_with_sufficient_requests(self):
        """Test recent metrics calculation when request_count >= MIN_REQUESTS_FOR_RECENT."""
        model = self._create_test_model()
        recent_stats = {
            1: {
                "request_count": 5,  # >= MIN_REQUESTS_FOR_RECENT (3)
                "success_count": 4,
                "avg_response_time": 2.0,
            }
        }

        metrics = _calculate_recent_metrics(model, recent_stats)

        assert metrics["recent_success_rate"] == 0.8  # 4/5
        assert metrics["recent_request_count"] == 5
        assert metrics["recent_reliability_score"] is not None
        assert metrics["effective_reliability_score"] is not None
        assert metrics["decision_reason"] == "recent_score"

    def test_calculate_recent_metrics_with_insufficient_requests(self):
        """Test recent metrics fallback when request_count < MIN_REQUESTS_FOR_RECENT."""
        model = self._create_test_model()
        recent_stats = {
            1: {
                "request_count": 2,  # < MIN_REQUESTS_FOR_RECENT (3)
                "success_count": 2,
                "avg_response_time": 1.0,
            }
        }

        metrics = _calculate_recent_metrics(model, recent_stats)

        assert metrics["recent_success_rate"] is None
        assert metrics["recent_request_count"] == 2
        assert metrics["recent_reliability_score"] is None
        # Should fallback to long-term reliability_score
        assert metrics["effective_reliability_score"] == round(model.reliability_score, 4)
        assert metrics["decision_reason"] == "fallback"

    def test_calculate_recent_metrics_zero_success_rate(self):
        """Test F011: Zero success rate results in zero reliability."""
        model = self._create_test_model()
        recent_stats = {
            1: {
                "request_count": 5,
                "success_count": 0,  # Zero success
                "avg_response_time": 2.0,
            }
        }

        metrics = _calculate_recent_metrics(model, recent_stats)

        assert metrics["recent_success_rate"] == 0.0
        assert metrics["recent_reliability_score"] == 0.0
        assert metrics["effective_reliability_score"] == 0.0
        assert metrics["decision_reason"] == "recent_score"


class TestGetModelOr404:
    """Tests for get_model_or_404 dependency (F015: FR-002)."""

    @pytest.mark.asyncio
    async def test_get_model_or_404_returns_model(self):
        """Test get_model_or_404 returns model when found."""
        from app.api.deps import get_model_or_404

        mock_db = AsyncMock()
        mock_model = MagicMock()
        mock_model.id = 1
        mock_model.name = "Test Model"

        with patch(
            "app.api.deps.AIModelRepository"
        ) as MockRepository:
            mock_repo_instance = MockRepository.return_value
            mock_repo_instance.get_by_id = AsyncMock(return_value=mock_model)

            result = await get_model_or_404(model_id=1, db=mock_db)

            assert result == mock_model
            mock_repo_instance.get_by_id.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_get_model_or_404_raises_404(self):
        """Test get_model_or_404 raises HTTPException 404 when model not found."""
        from app.api.deps import get_model_or_404

        mock_db = AsyncMock()

        with patch(
            "app.api.deps.AIModelRepository"
        ) as MockRepository:
            mock_repo_instance = MockRepository.return_value
            mock_repo_instance.get_by_id = AsyncMock(return_value=None)

            with pytest.raises(HTTPException) as exc_info:
                await get_model_or_404(model_id=999, db=mock_db)

            assert exc_info.value.status_code == 404
            assert "999" in str(exc_info.value.detail)
