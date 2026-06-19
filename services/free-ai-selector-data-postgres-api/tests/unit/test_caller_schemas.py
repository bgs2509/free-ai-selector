"""
Unit tests for caller/http_status/requested_model fields and CallerStatisticsResponse (oxl).

These tests do NOT require a database — they validate domain dataclass defaults
and Pydantic schema behaviour only.
"""

from datetime import datetime
from decimal import Decimal

import pytest

from app.api.v1.schemas import (
    CallerStatisticsResponse,
    PromptHistoryCreate,
    PromptHistoryResponse,
)
from app.domain.models import PromptHistory


@pytest.mark.unit
class TestPromptHistoryDomainCallerFields:
    """New optional caller fields on the PromptHistory domain entity."""

    def test_defaults_to_none(self):
        history = PromptHistory(
            id=None,
            user_id="u1",
            prompt_text="hi",
            selected_model_id=1,
            response_text="ok",
            response_time=Decimal("1.0"),
            success=True,
            error_message=None,
            created_at=datetime.utcnow(),
        )
        assert history.caller is None
        assert history.http_status is None
        assert history.requested_model is None

    def test_explicit_values(self):
        history = PromptHistory(
            id=None,
            user_id="u1",
            prompt_text="hi",
            selected_model_id=1,
            response_text="ok",
            response_time=Decimal("1.0"),
            success=True,
            error_message=None,
            created_at=datetime.utcnow(),
            caller="health-worker",
            http_status=429,
            requested_model="gpt-oss-20b",
        )
        assert history.caller == "health-worker"
        assert history.http_status == 429
        assert history.requested_model == "gpt-oss-20b"


@pytest.mark.unit
class TestPromptHistoryCreateSchema:
    """New optional caller fields on the create-request schema."""

    def test_caller_fields_optional(self):
        data = PromptHistoryCreate(
            user_id="u1",
            prompt_text="hi",
            selected_model_id=1,
            response_time=Decimal("1.0"),
            success=True,
        )
        assert data.caller is None
        assert data.http_status is None
        assert data.requested_model is None

    def test_caller_fields_accepted(self):
        data = PromptHistoryCreate(
            user_id="u1",
            prompt_text="hi",
            selected_model_id=1,
            response_time=Decimal("1.0"),
            success=False,
            caller="billing-bot",
            http_status=503,
            requested_model=None,
        )
        assert data.caller == "billing-bot"
        assert data.http_status == 503
        assert data.requested_model is None


@pytest.mark.unit
class TestPromptHistoryResponseSchema:
    """Response schema exposes the new fields."""

    def test_response_includes_caller_fields(self):
        resp = PromptHistoryResponse(
            id=1,
            user_id="u1",
            prompt_text="hi",
            selected_model_id=1,
            response_text="ok",
            response_time=Decimal("1.0"),
            success=True,
            error_message=None,
            created_at=datetime.utcnow(),
            caller="health-worker",
            http_status=200,
            requested_model="qwen",
        )
        assert resp.caller == "health-worker"
        assert resp.http_status == 200
        assert resp.requested_model == "qwen"

    def test_response_caller_fields_default_none(self):
        resp = PromptHistoryResponse(
            id=1,
            user_id="u1",
            prompt_text="hi",
            selected_model_id=1,
            response_text="ok",
            response_time=Decimal("1.0"),
            success=True,
            error_message=None,
            created_at=datetime.utcnow(),
        )
        assert resp.caller is None
        assert resp.http_status is None
        assert resp.requested_model is None


@pytest.mark.unit
class TestCallerStatisticsResponseSchema:
    """Per-caller analytics response schema."""

    def test_valid_payload(self):
        resp = CallerStatisticsResponse(
            caller="health-worker",
            request_count=10,
            success_count=8,
            success_rate=0.8,
            avg_response_time=1.25,
            top_model_id=3,
        )
        assert resp.caller == "health-worker"
        assert resp.request_count == 10
        assert resp.success_count == 8
        assert resp.success_rate == 0.8
        assert resp.avg_response_time == 1.25
        assert resp.top_model_id == 3

    def test_null_caller_bucket_allowed(self):
        resp = CallerStatisticsResponse(
            caller=None,
            request_count=5,
            success_count=5,
            success_rate=1.0,
            avg_response_time=0.5,
            top_model_id=None,
        )
        assert resp.caller is None
        assert resp.top_model_id is None

    def test_success_rate_bounds_enforced(self):
        with pytest.raises(ValueError):
            CallerStatisticsResponse(
                caller="x",
                request_count=1,
                success_count=1,
                success_rate=1.5,  # out of [0, 1]
                avg_response_time=0.1,
                top_model_id=None,
            )
