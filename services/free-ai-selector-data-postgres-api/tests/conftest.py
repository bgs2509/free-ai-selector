"""
Pytest configuration and fixtures for Data API tests.
Использует реальный PostgreSQL с транзакционной изоляцией.
"""

import asyncio
import os
from typing import AsyncGenerator

import pytest
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    create_async_engine,
    async_sessionmaker,
)

from app.infrastructure.database.models import Base

# Реальный PostgreSQL из Docker-контейнера
TEST_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://free_ai_selector_user:free_ai_selector_pass@postgres:5432/free_ai_selector_db",
)


@pytest.fixture(scope="session")
def event_loop():
    """Event loop для всей тестовой сессии."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Engine создаётся один раз за сессию."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture(scope="function")
async def test_db(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """
    Тестовая сессия с транзакционной изоляцией.
    Каждый тест — отдельная транзакция, откатывается после завершения.
    """
    connection = await test_engine.connect()
    transaction = await connection.begin()

    session_factory = async_sessionmaker(
        bind=connection,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_factory() as session:
        yield session

    await transaction.rollback()
    await connection.close()
