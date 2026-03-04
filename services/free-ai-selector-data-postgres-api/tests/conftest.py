"""
Pytest configuration and fixtures for Data API tests.
Использует реальный PostgreSQL с транзакционной изоляцией.

Паттерн: session.commit() подменён на session.flush() — данные
отправляются в БД (видны в текущей транзакции), но транзакция
НЕ коммитится. После теста ROLLBACK откатывает всё.
"""

import os
from typing import AsyncGenerator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.infrastructure.database.models import Base

# Реальный PostgreSQL из Docker-контейнера
TEST_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://free_ai_selector_user:free_ai_selector_pass@postgres:5432/free_ai_selector_db",
)


@pytest.fixture(scope="function")
async def test_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Тестовая сессия с транзакционной изоляцией.

    - NullPool: каждый тест получает свежее соединение (asyncpg привязан
      к event loop, а pytest-asyncio создаёт новый loop для каждого теста).
    - commit() заменён на flush(): INSERT/UPDATE отправляются в БД,
      но транзакция остаётся открытой.
    - После теста conn.rollback() откатывает все изменения.
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False, poolclass=NullPool)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with engine.connect() as conn:
        await conn.begin()

        session = AsyncSession(bind=conn, expire_on_commit=False)
        session.commit = session.flush  # type: ignore[assignment]

        # Очистить таблицы внутри транзакции — тест видит пустую БД.
        # ROLLBACK после теста восстановит все данные.
        await session.execute(text("DELETE FROM prompt_history"))
        await session.execute(text("DELETE FROM ai_models"))
        await session.flush()

        yield session

        await session.close()
        if conn.in_transaction():
            await conn.rollback()

    await engine.dispose()
