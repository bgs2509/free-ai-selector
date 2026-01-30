"""
Add available_at column to ai_models table

F012: Rate Limit Handling
- available_at: Timestamp when provider becomes available again after rate limit
- NULL = available immediately, future timestamp = temporarily unavailable

Revision ID: 0003_add_available_at
Revises: 0002_add_api_format_env_var
Create Date: 2026-01-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# Revision identifiers
revision: str = "0003_add_available_at"
down_revision: Union[str, None] = "0002_add_api_format_env_var"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add available_at column to ai_models table.
    """
    op.add_column(
        "ai_models",
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Create index for filtering by availability
    op.create_index(
        op.f("ix_ai_models_available_at"), "ai_models", ["available_at"], unique=False
    )


def downgrade() -> None:
    """
    Remove available_at column from ai_models table.
    """
    op.drop_index(op.f("ix_ai_models_available_at"), table_name="ai_models")
    op.drop_column("ai_models", "available_at")
