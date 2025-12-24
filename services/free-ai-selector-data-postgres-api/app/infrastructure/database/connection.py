"""
Database connection management for AI Manager Platform - Data API Service

Provides async database session management using SQLAlchemy 2.0.
Implements the dependency injection pattern for FastAPI.
"""

import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.infrastructure.database.models import Base

# Database URL from environment variable
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://free_ai_selector_user:password@localhost:5432/free_ai_selector_db")

# Create async engine
# echo=True for development (SQL logging), should be False in production
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
engine = create_async_engine(
    DATABASE_URL,
    echo=(ENVIRONMENT == "development"),
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # Verify connections before using
)

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency injection function for FastAPI routes.

    Provides an async database session that is automatically closed
    when the request is complete.

    Usage in FastAPI:
        @app.get("/models")
        async def get_models(db: AsyncSession = Depends(get_db)):
            ...
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


async def init_db() -> None:
    """
    Initialize database tables.

    Creates all tables defined in Base metadata.
    Should be called on application startup.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def drop_db() -> None:
    """
    Drop all database tables.

    WARNING: This will delete all data!
    Should only be used in tests or development.
    """
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
