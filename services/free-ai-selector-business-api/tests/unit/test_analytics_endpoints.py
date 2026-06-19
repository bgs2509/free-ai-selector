"""Tests for the analytics & journal proxy endpoints (fm6)."""
import pytest
from unittest.mock import AsyncMock, patch
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def async_client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as client:
        yield client


def _mock_client():
    instance = AsyncMock()
    instance.close = AsyncMock()
    return instance


class TestAnalyticsByProject:
    """GET /api/v1/analytics/by-project."""

    async def test_returns_caller_aggregates(self, async_client):
        rows = [
            {
                "caller": "sensedar",
                "request_count": 10,
                "success_count": 9,
                "success_rate": 0.9,
                "avg_response_time": 1.23,
                "top_model_id": 3,
            }
        ]
        with patch("app.api.v1.analytics.DataAPIClient") as MockClient:
            instance = _mock_client()
            instance.get_caller_statistics = AsyncMock(return_value=rows)
            MockClient.return_value = instance

            response = await async_client.get("/api/v1/analytics/by-project?window_days=14")

        assert response.status_code == 200
        assert response.json()[0]["caller"] == "sensedar"
        instance.get_caller_statistics.assert_awaited_once_with(window_days=14)
        instance.close.assert_awaited_once()

    async def test_data_api_failure_returns_500(self, async_client):
        with patch("app.api.v1.analytics.DataAPIClient") as MockClient:
            instance = _mock_client()
            instance.get_caller_statistics = AsyncMock(side_effect=Exception("boom"))
            MockClient.return_value = instance

            response = await async_client.get("/api/v1/analytics/by-project")

        assert response.status_code == 500
        instance.close.assert_awaited_once()


class TestJournalList:
    """GET /api/v1/history (journal list)."""

    async def test_passes_filters_through(self, async_client):
        with patch("app.api.v1.analytics.DataAPIClient") as MockClient:
            instance = _mock_client()
            instance.get_history = AsyncMock(return_value=[{"id": 1, "caller": "taro"}])
            MockClient.return_value = instance

            response = await async_client.get(
                "/api/v1/history",
                params={"caller": "taro", "success": "false", "limit": 5, "offset": 10},
            )

        assert response.status_code == 200
        assert response.json()[0]["caller"] == "taro"
        kwargs = instance.get_history.await_args.kwargs
        assert kwargs["caller"] == "taro"
        assert kwargs["success"] is False
        assert kwargs["limit"] == 5
        assert kwargs["offset"] == 10


class TestJournalDetail:
    """GET /api/v1/history/{id} (drill-down)."""

    async def test_returns_record(self, async_client):
        record = {
            "id": 7,
            "caller": "sensedar",
            "prompt_text": "hi",
            "response_text": "hello",
            "http_status": 200,
            "success": True,
        }
        with patch("app.api.v1.analytics.DataAPIClient") as MockClient:
            instance = _mock_client()
            instance.get_history_by_id = AsyncMock(return_value=record)
            MockClient.return_value = instance

            response = await async_client.get("/api/v1/history/7")

        assert response.status_code == 200
        assert response.json()["http_status"] == 200

    async def test_missing_record_returns_404(self, async_client):
        with patch("app.api.v1.analytics.DataAPIClient") as MockClient:
            instance = _mock_client()
            instance.get_history_by_id = AsyncMock(return_value=None)
            MockClient.return_value = instance

            response = await async_client.get("/api/v1/history/999")

        assert response.status_code == 404
        instance.close.assert_awaited_once()
