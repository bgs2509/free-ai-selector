"""
Initial database schema

Creates tables:
- ai_models: AI model information and reliability metrics
- prompt_history: Prompt processing history records

Revision ID: 0001_initial_schema
Revises:
Create Date: 2025-01-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# Revision identifiers
revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Create initial database schema.
    """
    # Create ai_models table
    op.create_table(
        "ai_models",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("provider", sa.String(length=100), nullable=False),
        sa.Column("api_endpoint", sa.String(length=500), nullable=False),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "total_response_time", sa.Numeric(precision=10, scale=3), nullable=False, server_default="0.0"
        ),
        sa.Column("request_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_checked", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # Create indexes on ai_models
    op.create_index(op.f("ix_ai_models_name"), "ai_models", ["name"], unique=True)
    op.create_index(op.f("ix_ai_models_provider"), "ai_models", ["provider"], unique=False)
    op.create_index(op.f("ix_ai_models_is_active"), "ai_models", ["is_active"], unique=False)

    # Create prompt_history table
    op.create_table(
        "prompt_history",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=255), nullable=False),
        sa.Column("prompt_text", sa.Text(), nullable=False),
        sa.Column("selected_model_id", sa.Integer(), nullable=False),
        sa.Column("response_text", sa.Text(), nullable=True),
        sa.Column("response_time", sa.Numeric(precision=10, scale=3), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes on prompt_history
    op.create_index(op.f("ix_prompt_history_user_id"), "prompt_history", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_prompt_history_selected_model_id"), "prompt_history", ["selected_model_id"], unique=False
    )
    op.create_index(op.f("ix_prompt_history_success"), "prompt_history", ["success"], unique=False)
    op.create_index(
        op.f("ix_prompt_history_created_at"), "prompt_history", ["created_at"], unique=False
    )


def downgrade() -> None:
    """
    Drop all tables created in upgrade.
    """
    # Drop indexes and tables in reverse order
    op.drop_index(op.f("ix_prompt_history_created_at"), table_name="prompt_history")
    op.drop_index(op.f("ix_prompt_history_success"), table_name="prompt_history")
    op.drop_index(op.f("ix_prompt_history_selected_model_id"), table_name="prompt_history")
    op.drop_index(op.f("ix_prompt_history_user_id"), table_name="prompt_history")
    op.drop_table("prompt_history")

    op.drop_index(op.f("ix_ai_models_is_active"), table_name="ai_models")
    op.drop_index(op.f("ix_ai_models_provider"), table_name="ai_models")
    op.drop_index(op.f("ix_ai_models_name"), table_name="ai_models")
    op.drop_table("ai_models")
