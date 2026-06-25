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
        """bmm/ADR-0003: _model_to_response populates v2 recent fields (laplace_ucb)."""
        model = self._create_test_model()
        recent_stats: Dict[int, Dict[str, Any]] = {
            1: {
                "request_count": 10,
                "weighted_success_rate": 0.8,
                "w_success": 8.0,
                "w_fail_hard": 2.0,
                "median_response_time": 1.5,
            }
        }

        response = _model_to_response(model, recent_stats)

        # Basic fields should be populated
        assert response.id == 1
        assert response.name == "Test Model"

        # Recent fields calculated from v2 (Laplace + multiplicative + UCB)
        assert response.recent_success_rate == 0.8
        assert response.recent_request_count == 10
        assert response.recent_reliability_score is not None
        assert response.effective_reliability_score is not None
        assert response.decision_reason == "laplace_ucb"

    def test_model_to_response_with_empty_recent_stats(self):
        """bmm/ADR-0003: no recent data → ~0.5 (NOT 1.0), decision_reason explore_ucb."""
        model = self._create_test_model()
        recent_stats: Dict[int, Dict[str, Any]] = {}  # No stats for model id=1

        response = _model_to_response(model, recent_stats)

        # No data → quality 0.5, neutral speed 0.5 → base 0.375 (NOT the old 1.0)
        assert response.recent_success_rate is None
        assert response.recent_request_count == 0
        assert response.decision_reason == "explore_ucb"
        assert response.effective_reliability_score == pytest.approx(0.375, abs=1e-3)
        assert response.effective_reliability_score < 1.0


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

    def test_calculate_recent_metrics_with_data(self):
        """bmm/ADR-0003: v2 metrics with data → decision_reason laplace_ucb."""
        model = self._create_test_model()
        recent_stats = {
            1: {
                "request_count": 5,
                "weighted_success_rate": 0.8,
                "w_success": 4.0,
                "w_fail_hard": 1.0,
                "median_response_time": 2.0,
            }
        }

        metrics = _calculate_recent_metrics(model, recent_stats)

        assert metrics["recent_success_rate"] == 0.8
        assert metrics["recent_request_count"] == 5
        assert metrics["recent_reliability_score"] is not None
        assert metrics["effective_reliability_score"] is not None
        assert metrics["decision_reason"] == "laplace_ucb"

    def test_calculate_recent_metrics_no_data_explore(self):
        """bmm/ADR-0003: no data → 0.375 base (NOT 1.0), explore_ucb."""
        model = self._create_test_model()
        recent_stats: Dict[int, Dict[str, Any]] = {}  # Нет данных для model.id=1

        metrics = _calculate_recent_metrics(model, recent_stats)

        assert metrics["recent_success_rate"] is None
        assert metrics["recent_request_count"] == 0
        # No data → Laplace quality 0.5, neutral speed 0.5 → base 0.375, no UCB (total=0)
        assert metrics["recent_reliability_score"] == pytest.approx(0.375, abs=1e-3)
        assert metrics["effective_reliability_score"] == pytest.approx(0.375, abs=1e-3)
        assert metrics["effective_reliability_score"] < 1.0
        assert metrics["decision_reason"] == "explore_ucb"

    def test_calculate_recent_metrics_all_hard_failures_low_not_zero(self):
        """bmm/ADR-0003: Laplace replaces the hard zero — all-hard-fail → low, not 0.0."""
        model = self._create_test_model()
        recent_stats = {
            1: {
                "request_count": 50,
                "weighted_success_rate": 0.0,
                "w_success": 0.0,
                "w_fail_hard": 50.0,
                "median_response_time": 2.0,
            }
        }

        metrics = _calculate_recent_metrics(model, recent_stats)

        assert metrics["recent_success_rate"] == 0.0
        # Quality ≈ (0+1)/(0+50+2) ≈ 0.019 → effective stays well below the 0.3 gate
        assert metrics["effective_reliability_score"] < 0.2
        assert metrics["effective_reliability_score"] > 0.0
        assert metrics["decision_reason"] == "laplace_ucb"


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

        with patch("app.api.deps.AIModelRepository") as MockRepository:
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

        with patch("app.api.deps.AIModelRepository") as MockRepository:
            mock_repo_instance = MockRepository.return_value
            mock_repo_instance.get_by_id = AsyncMock(return_value=None)

            with pytest.raises(HTTPException) as exc_info:
                await get_model_or_404(model_id=999, db=mock_db)

            assert exc_info.value.status_code == 404
            assert "999" in str(exc_info.value.detail)
