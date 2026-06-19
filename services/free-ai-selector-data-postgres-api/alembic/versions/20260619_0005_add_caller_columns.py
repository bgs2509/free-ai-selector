"""Add caller / http_status / requested_model columns to prompt_history

oxl: Per-project ("caller") dimension + precise HTTP status for analytics & journal.
- caller: external project that called the API (INDEXED, nullable)
- http_status: HTTP status returned to the caller (200/429/503/500, nullable)
- requested_model: model_name the caller requested (nullable, null = auto-select)

All nullable so existing rows backfill to NULL cleanly.

Revision ID: 0005_add_caller_columns
Revises: 0004_drop_env_var
Create Date: 2026-06-19
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# Revision identifiers
revision: str = "0005_add_caller_columns"
down_revision: Union[str, None] = "0004_drop_env_var"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add caller / http_status / requested_model columns to prompt_history.
    """
    op.add_column(
        "prompt_history",
        sa.Column("caller", sa.String(255), nullable=True),
    )
    op.add_column(
        "prompt_history",
        sa.Column("http_status", sa.Integer(), nullable=True),
    )
    op.add_column(
        "prompt_history",
        sa.Column("requested_model", sa.String(255), nullable=True),
    )

    # Index caller for per-project analytics / journal filtering.
    op.create_index(
        op.f("ix_prompt_history_caller"), "prompt_history", ["caller"], unique=False
    )


def downgrade() -> None:
    """
    Remove caller / http_status / requested_model columns from prompt_history.
    """
    op.drop_index(op.f("ix_prompt_history_caller"), table_name="prompt_history")
    op.drop_column("prompt_history", "requested_model")
    op.drop_column("prompt_history", "http_status")
    op.drop_column("prompt_history", "caller")
