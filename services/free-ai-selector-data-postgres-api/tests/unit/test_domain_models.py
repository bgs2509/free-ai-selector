"""
Unit tests for domain models
"""

from datetime import datetime
from decimal import Decimal

import pytest

from app.domain.models import AIModel, PromptHistory


class TestAIModel:
    """Test AIModel domain entity."""

    def test_success_rate_calculation(self):
        """Test success rate property."""
        model = AIModel(
            id=1,
            name="Test Model",
            provider="TestProvider",
            api_endpoint="https://api.test.com",
            success_count=75,
            failure_count=25,
            total_response_time=Decimal("100.0"),
            request_count=100,
            last_checked=None,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        assert model.success_rate == 0.75  # 75/100

    def test_success_rate_zero_requests(self):
        """Test success rate when no requests."""
        model = AIModel(
            id=1,
            name="Test Model",
            provider="TestProvider",
            api_endpoint="https://api.test.com",
            success_count=0,
            failure_count=0,
            total_response_time=Decimal("0.0"),
            request_count=0,
            last_checked=None,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        assert model.success_rate == 0.0

    def test_average_response_time(self):
        """Test average response time calculation."""
        model = AIModel(
            id=1,
            name="Test Model",
            provider="TestProvider",
            api_endpoint="https://api.test.com",
            success_count=50,
            failure_count=0,
            total_response_time=Decimal("250.0"),
            request_count=50,
            last_checked=None,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        assert model.average_response_time == 5.0  # 250/50

    def test_speed_score_fast(self):
        """Test speed score for fast responses."""
        model = AIModel(
            id=1,
            name="Test Model",
            provider="TestProvider",
            api_endpoint="https://api.test.com",
            success_count=10,
            failure_count=0,
            total_response_time=Decimal("20.0"),  # 2s average
            request_count=10,
            last_checked=None,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        assert model.speed_score == 0.8  # 1 - (2/10)

    def test_speed_score_slow(self):
        """Test speed score for slow responses."""
        model = AIModel(
            id=1,
            name="Test Model",
            provider="TestProvider",
            api_endpoint="https://api.test.com",
            success_count=10,
            failure_count=0,
            total_response_time=Decimal("100.0"),  # 10s average
            request_count=10,
            last_checked=None,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        assert model.speed_score == 0.0  # Baseline is 10s

    def test_reliability_score(self):
        """Test reliability score calculation."""
        model = AIModel(
            id=1,
            name="Test Model",
            provider="TestProvider",
            api_endpoint="https://api.test.com",
            success_count=90,
            failure_count=10,
            total_response_time=Decimal("200.0"),  # 2s average
            request_count=100,
            last_checked=None,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        # success_rate = 0.9, speed_score = 0.8
        # reliability = 0.9 * 0.6 + 0.8 * 0.4 = 0.54 + 0.32 = 0.86
        expected_reliability = (0.9 * 0.6) + (0.8 * 0.4)
        assert abs(model.reliability_score - expected_reliability) < 0.001

    def test_reliability_score_zero_when_no_success(self):
        """Test that reliability_score = 0 when success_rate = 0 (F011)."""
        model = AIModel(
            id=1,
            name="Broken Model",
            provider="BrokenProvider",
            api_endpoint="https://api.broken.com",
            success_count=0,
            failure_count=10,  # 10 failures, 0 successes
            total_response_time=Decimal("50.0"),  # 5s avg (would give speed_score=0.5)
            request_count=10,
            last_checked=datetime.utcnow(),
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        assert model.success_rate == 0.0
        # F011: reliability_score must be 0.0, not 0.5 * 0.4 = 0.20
        assert model.reliability_score == 0.0

    def test_reliability_score_zero_when_no_requests(self):
        """Test that reliability_score = 0 for new models with no requests (F011)."""
        model = AIModel(
            id=1,
            name="New Model",
            provider="NewProvider",
            api_endpoint="https://api.new.com",
            success_count=0,
            failure_count=0,
            total_response_time=Decimal("0.0"),
            request_count=0,
            last_checked=None,
            is_active=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        assert model.success_rate == 0.0
        # F011: reliability_score must be 0.0, not 0.40 (from speed_score=1.0)
        assert model.reliability_score == 0.0


class TestPromptHistory:
    """Test PromptHistory domain entity."""

    def test_prompt_history_creation(self):
        """Test creating prompt history record."""
        history = PromptHistory(
            id=1,
            user_id="test_user",
            prompt_text="Test prompt",
            selected_model_id=1,
            response_text="Test response",
            response_time=Decimal("2.5"),
            success=True,
            error_message=None,
            created_at=datetime.utcnow(),
        )

        assert history.user_id == "test_user"
        assert history.success is True
        assert history.response_time == Decimal("2.5")
