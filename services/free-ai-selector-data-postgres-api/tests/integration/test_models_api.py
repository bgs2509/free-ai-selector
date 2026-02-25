"""
Integration tests for AI Models API endpoints
"""

import pytest
from httpx import AsyncClient
from uuid import uuid4

from app.main import app


@pytest.mark.integration
class TestModelsAPI:
    """Test AI Models API endpoints."""

    @staticmethod
    def _unique_model_name(prefix: str) -> str:
        """Генерирует уникальное имя модели для изоляции интеграционных тестов."""
        return f"{prefix}-{uuid4().hex[:8]}"

    @pytest.fixture
    async def client(self):
        """Create test client."""
        async with AsyncClient(app=app, base_url="http://test") as ac:
            yield ac

    async def test_health_check(self, client: AsyncClient):
        """Test health check endpoint."""
        response = await client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] in ["healthy", "unhealthy"]
        assert data["service"] == "free-ai-selector-data-postgres-api"

    async def test_root_endpoint(self, client: AsyncClient):
        """Test root endpoint."""
        response = await client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "free-ai-selector-data-postgres-api"
        assert "version" in data

    async def test_get_all_models_empty(self, client: AsyncClient):
        """Test fetching models when database is empty."""
        response = await client.get("/api/v1/models")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    async def test_create_and_get_model(self, client: AsyncClient):
        """Test creating and fetching a model."""
        model_name = self._unique_model_name("Test-Integration-Model")

        # Create model
        create_payload = {
            "name": model_name,
            "provider": "TestProvider",
            "api_endpoint": "https://api.test.com",
            "is_active": True,
        }

        create_response = await client.post("/api/v1/models", json=create_payload)
        assert create_response.status_code == 201
        created_model = create_response.json()
        assert created_model["name"] == model_name
        model_id = created_model["id"]

        # Get model by ID
        get_response = await client.get(f"/api/v1/models/{model_id}")
        assert get_response.status_code == 200
        fetched_model = get_response.json()
        assert fetched_model["id"] == model_id
        assert fetched_model["name"] == model_name

    async def test_create_duplicate_model(self, client: AsyncClient):
        """Test creating model with duplicate name."""
        model_name = self._unique_model_name("Duplicate-Test-Model")

        payload = {
            "name": model_name,
            "provider": "TestProvider",
            "api_endpoint": "https://api.test.com",
            "is_active": True,
        }

        # First creation should succeed
        response1 = await client.post("/api/v1/models", json=payload)
        assert response1.status_code == 201

        # Second creation should fail (409 Conflict)
        response2 = await client.post("/api/v1/models", json=payload)
        assert response2.status_code == 409

    async def test_get_nonexistent_model(self, client: AsyncClient):
        """Test fetching non-existent model."""
        response = await client.get("/api/v1/models/99999")
        assert response.status_code == 404

    async def test_increment_success_endpoint(self, client: AsyncClient):
        """Test incrementing success count."""
        model_name = self._unique_model_name("Success-Test-Model")

        # Create model
        create_payload = {
            "name": model_name,
            "provider": "TestProvider",
            "api_endpoint": "https://api.test.com",
            "is_active": True,
        }

        create_response = await client.post("/api/v1/models", json=create_payload)
        model_id = create_response.json()["id"]

        # Increment success
        response = await client.post(
            f"/api/v1/models/{model_id}/increment-success",
            params={"response_time": 2.5},
        )

        assert response.status_code == 200
        updated_model = response.json()
        assert updated_model["success_count"] == 1
        assert updated_model["request_count"] == 1
