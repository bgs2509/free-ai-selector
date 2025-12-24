"""
Unit tests for AIModel repository
"""

from datetime import datetime
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.models import AIModel
from app.infrastructure.repositories.ai_model_repository import AIModelRepository


@pytest.mark.unit
class TestAIModelRepository:
    """Test AIModel repository operations."""

    async def test_create_model(self, test_db: AsyncSession):
        """Test creating a new AI model."""
        repository = AIModelRepository(test_db)

        model = AIModel(
            id=None,
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

        created_model = await repository.create(model)
        await test_db.commit()

        assert created_model.id is not None
        assert created_model.name == "Test Model"
        assert created_model.provider == "TestProvider"

    async def test_get_by_id(self, test_db: AsyncSession):
        """Test fetching model by ID."""
        repository = AIModelRepository(test_db)

        # Create model
        model = AIModel(
            id=None,
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

        created_model = await repository.create(model)
        await test_db.commit()

        # Fetch by ID
        fetched_model = await repository.get_by_id(created_model.id)

        assert fetched_model is not None
        assert fetched_model.id == created_model.id
        assert fetched_model.name == "Test Model"

    async def test_get_by_name(self, test_db: AsyncSession):
        """Test fetching model by name."""
        repository = AIModelRepository(test_db)

        # Create model
        model = AIModel(
            id=None,
            name="Unique Test Model",
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

        await repository.create(model)
        await test_db.commit()

        # Fetch by name
        fetched_model = await repository.get_by_name("Unique Test Model")

        assert fetched_model is not None
        assert fetched_model.name == "Unique Test Model"

    async def test_get_all_active_only(self, test_db: AsyncSession):
        """Test fetching only active models."""
        repository = AIModelRepository(test_db)

        # Create active model
        active_model = AIModel(
            id=None,
            name="Active Model",
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

        # Create inactive model
        inactive_model = AIModel(
            id=None,
            name="Inactive Model",
            provider="TestProvider",
            api_endpoint="https://api.test.com",
            success_count=0,
            failure_count=0,
            total_response_time=Decimal("0.0"),
            request_count=0,
            last_checked=None,
            is_active=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        await repository.create(active_model)
        await repository.create(inactive_model)
        await test_db.commit()

        # Fetch active only
        models = await repository.get_all(active_only=True)

        assert len(models) == 1
        assert models[0].name == "Active Model"

    async def test_increment_success(self, test_db: AsyncSession):
        """Test incrementing success count."""
        repository = AIModelRepository(test_db)

        # Create model
        model = AIModel(
            id=None,
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

        created_model = await repository.create(model)
        await test_db.commit()

        # Increment success
        updated_model = await repository.increment_success(
            created_model.id, response_time=Decimal("2.5")
        )
        await test_db.commit()

        assert updated_model.success_count == 1
        assert updated_model.request_count == 1
        assert updated_model.total_response_time == Decimal("2.5")

    async def test_increment_failure(self, test_db: AsyncSession):
        """Test incrementing failure count."""
        repository = AIModelRepository(test_db)

        # Create model
        model = AIModel(
            id=None,
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

        created_model = await repository.create(model)
        await test_db.commit()

        # Increment failure
        updated_model = await repository.increment_failure(
            created_model.id, response_time=Decimal("1.5")
        )
        await test_db.commit()

        assert updated_model.failure_count == 1
        assert updated_model.request_count == 1
        assert updated_model.total_response_time == Decimal("1.5")

    async def test_set_active(self, test_db: AsyncSession):
        """Test setting model active status."""
        repository = AIModelRepository(test_db)

        # Create active model
        model = AIModel(
            id=None,
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

        created_model = await repository.create(model)
        await test_db.commit()

        # Deactivate
        updated_model = await repository.set_active(created_model.id, is_active=False)
        await test_db.commit()

        assert updated_model.is_active is False
