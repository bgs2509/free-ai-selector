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


@pytest.mark.unit
class TestF012RateLimitHandling:
    """Test F012: Rate Limit Handling repository methods."""

    async def test_set_availability_with_cooldown(self, test_db: AsyncSession):
        """Test setting availability cooldown (F012)."""
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

        # Set availability cooldown (3600 seconds = 1 hour)
        updated_model = await repository.set_availability(
            created_model.id, retry_after_seconds=3600
        )
        await test_db.commit()

        assert updated_model.available_at is not None
        # available_at should be approximately 1 hour from now
        time_diff = (updated_model.available_at - datetime.utcnow()).total_seconds()
        assert 3500 < time_diff < 3700  # Allow some tolerance

    async def test_set_availability_clear_cooldown(self, test_db: AsyncSession):
        """Test clearing availability cooldown (F012)."""
        from datetime import timedelta

        repository = AIModelRepository(test_db)

        # Create model with existing cooldown
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
            available_at=datetime.utcnow() + timedelta(hours=1),  # 1 hour cooldown
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        created_model = await repository.create(model)
        await test_db.commit()

        # Clear cooldown (retry_after_seconds=0)
        updated_model = await repository.set_availability(
            created_model.id, retry_after_seconds=0
        )
        await test_db.commit()

        assert updated_model.available_at is None

    async def test_get_all_available_only_excludes_rate_limited(self, test_db: AsyncSession):
        """Test that available_only excludes rate-limited models (F012)."""
        from datetime import timedelta

        repository = AIModelRepository(test_db)

        # Create available model
        available_model = AIModel(
            id=None,
            name="Available Model",
            provider="TestProvider",
            api_endpoint="https://api1.test.com",
            success_count=0,
            failure_count=0,
            total_response_time=Decimal("0.0"),
            request_count=0,
            last_checked=None,
            is_active=True,
            available_at=None,  # No cooldown
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        # Create rate-limited model (available_at in future)
        rate_limited_model = AIModel(
            id=None,
            name="Rate Limited Model",
            provider="TestProvider",
            api_endpoint="https://api2.test.com",
            success_count=0,
            failure_count=0,
            total_response_time=Decimal("0.0"),
            request_count=0,
            last_checked=None,
            is_active=True,
            available_at=datetime.utcnow() + timedelta(hours=1),  # Rate limited
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        await repository.create(available_model)
        await repository.create(rate_limited_model)
        await test_db.commit()

        # Fetch with available_only=True
        models = await repository.get_all(active_only=True, available_only=True)

        assert len(models) == 1
        assert models[0].name == "Available Model"

    async def test_get_all_available_only_includes_expired_cooldown(self, test_db: AsyncSession):
        """Test that available_only includes models with expired cooldown (F012)."""
        from datetime import timedelta

        repository = AIModelRepository(test_db)

        # Create model with expired cooldown (available_at in past)
        expired_cooldown_model = AIModel(
            id=None,
            name="Expired Cooldown Model",
            provider="TestProvider",
            api_endpoint="https://api.test.com",
            success_count=0,
            failure_count=0,
            total_response_time=Decimal("0.0"),
            request_count=0,
            last_checked=None,
            is_active=True,
            available_at=datetime.utcnow() - timedelta(hours=1),  # Expired cooldown
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        await repository.create(expired_cooldown_model)
        await test_db.commit()

        # Fetch with available_only=True
        models = await repository.get_all(active_only=True, available_only=True)

        assert len(models) == 1
        assert models[0].name == "Expired Cooldown Model"

    async def test_get_all_without_available_only_returns_all(self, test_db: AsyncSession):
        """Test that available_only=False returns all models including rate-limited."""
        from datetime import timedelta

        repository = AIModelRepository(test_db)

        # Create available model
        available_model = AIModel(
            id=None,
            name="Available Model",
            provider="TestProvider",
            api_endpoint="https://api1.test.com",
            success_count=0,
            failure_count=0,
            total_response_time=Decimal("0.0"),
            request_count=0,
            last_checked=None,
            is_active=True,
            available_at=None,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        # Create rate-limited model
        rate_limited_model = AIModel(
            id=None,
            name="Rate Limited Model",
            provider="TestProvider",
            api_endpoint="https://api2.test.com",
            success_count=0,
            failure_count=0,
            total_response_time=Decimal("0.0"),
            request_count=0,
            last_checked=None,
            is_active=True,
            available_at=datetime.utcnow() + timedelta(hours=1),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        await repository.create(available_model)
        await repository.create(rate_limited_model)
        await test_db.commit()

        # Fetch with available_only=False (default)
        models = await repository.get_all(active_only=True, available_only=False)

        assert len(models) == 2
