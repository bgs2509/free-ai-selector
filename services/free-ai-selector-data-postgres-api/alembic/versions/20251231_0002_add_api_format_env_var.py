"""
Add api_format and env_var columns to ai_models table

These fields support F008 Provider Registry SSOT:
- api_format: Discriminator for health check dispatch ("openai", "gemini", "cohere", etc.)
- env_var: Dynamic ENV variable name for API key lookup

Revision ID: 0002_add_api_format_env_var
Revises: 0001_initial_schema
Create Date: 2025-12-31
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# Revision identifiers
revision: str = "0002_add_api_format_env_var"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Add api_format and env_var columns to ai_models table.
    """
    # Add api_format column with default 'openai' (most common format)
    op.add_column(
        "ai_models",
        sa.Column("api_format", sa.String(length=20), nullable=False, server_default="openai"),
    )

    # Add env_var column for dynamic API key lookup
    op.add_column(
        "ai_models",
        sa.Column("env_var", sa.String(length=50), nullable=False, server_default=""),
    )

    # Create index on api_format for potential future queries
    op.create_index(op.f("ix_ai_models_api_format"), "ai_models", ["api_format"], unique=False)


def downgrade() -> None:
    """
    Remove api_format and env_var columns from ai_models table.
    """
    op.drop_index(op.f("ix_ai_models_api_format"), table_name="ai_models")
    op.drop_column("ai_models", "env_var")
    op.drop_column("ai_models", "api_format")
