"""
SQLAlchemy ORM models for AI Manager Platform - Data API Service

These are infrastructure models that map domain entities to database tables.
Uses SQLAlchemy 2.0 async patterns.
"""

from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""

    pass


class AIModelORM(Base):
    """
    AI Model database table.

    Maps to the ai_models table in PostgreSQL.
    Stores AI model information and reliability metrics.
    """

    __tablename__ = "ai_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    api_endpoint: Mapped[str] = mapped_column(String(500), nullable=False)

    # Reliability metrics
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_response_time: Mapped[Decimal] = mapped_column(
        Numeric(10, 3), nullable=False, default=0.0
    )
    request_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_checked: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Provider configuration (F008 SSOT)
    api_format: Mapped[str] = mapped_column(
        String(20), nullable=False, default="openai", index=True
    )
    env_var: Mapped[str] = mapped_column(String(50), nullable=False, default="")

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<AIModelORM(id={self.id}, name='{self.name}', provider='{self.provider}', "
            f"api_format='{self.api_format}', is_active={self.is_active})>"
        )


class PromptHistoryORM(Base):
    """
    Prompt History database table.

    Maps to the prompt_history table in PostgreSQL.
    Records all prompt processing requests with metrics.
    """

    __tablename__ = "prompt_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    selected_model_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    # Response data
    response_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    response_time: Mapped[Decimal] = mapped_column(Numeric(10, 3), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Timestamp
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    def __repr__(self) -> str:
        return (
            f"<PromptHistoryORM(id={self.id}, user_id='{self.user_id}', "
            f"model_id={self.selected_model_id}, success={self.success})>"
        )
