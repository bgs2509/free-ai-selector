"""Тесты для app/infrastructure/database/seed.py — seed AI-моделей."""
import pytest
from unittest.mock import patch
from sqlalchemy import select

from app.infrastructure.database.models import AIModelORM
from app.infrastructure.database.seed import seed_database, clear_seed_data, SEED_MODELS


class _FakeSessionCtx:
    """Контекстный менеджер, подменяющий AsyncSessionLocal тестовой сессией."""

    def __init__(self, session):
        self._session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *args):
        pass


@pytest.fixture
async def seeded_db(test_db):
    """Запускает seed с подменённой сессией."""
    with patch(
        "app.infrastructure.database.seed.AsyncSessionLocal",
        _FakeSessionCtx(test_db),
    ):
        await seed_database()
    return test_db


class TestSeedDatabase:
    async def test_creates_all_models(self, seeded_db):
        result = await seeded_db.execute(select(AIModelORM))
        models = result.scalars().all()
        assert len(models) == len(SEED_MODELS)

    async def test_model_names_match(self, seeded_db):
        result = await seeded_db.execute(select(AIModelORM.name))
        names = {row[0] for row in result.all()}
        expected = {m["name"] for m in SEED_MODELS}
        assert names == expected

    async def test_upsert_idempotent(self, seeded_db):
        """Повторный seed не создаёт дубликаты."""
        with patch(
            "app.infrastructure.database.seed.AsyncSessionLocal",
            _FakeSessionCtx(seeded_db),
        ):
            await seed_database()

        result = await seeded_db.execute(select(AIModelORM))
        models = result.scalars().all()
        assert len(models) == len(SEED_MODELS)

    async def test_orphan_cleanup(self, seeded_db):
        """Модели отсутствующие в SEED_MODELS удаляются."""
        orphan = AIModelORM(
            name="OrphanModel",
            provider="OrphanProvider",
            api_endpoint="https://orphan.test",
            success_count=0,
            failure_count=0,
            total_response_time=0,
            request_count=0,
            is_active=True,
        )
        seeded_db.add(orphan)
        await seeded_db.flush()

        with patch(
            "app.infrastructure.database.seed.AsyncSessionLocal",
            _FakeSessionCtx(seeded_db),
        ):
            await seed_database()

        result = await seeded_db.execute(
            select(AIModelORM).where(AIModelORM.name == "OrphanModel")
        )
        assert result.scalar_one_or_none() is None


class TestClearSeedData:
    async def test_clears_seeded_models(self, seeded_db):
        with patch(
            "app.infrastructure.database.seed.AsyncSessionLocal",
            _FakeSessionCtx(seeded_db),
        ):
            await clear_seed_data()

        result = await seeded_db.execute(select(AIModelORM))
        models = result.scalars().all()
        assert len(models) == 0
