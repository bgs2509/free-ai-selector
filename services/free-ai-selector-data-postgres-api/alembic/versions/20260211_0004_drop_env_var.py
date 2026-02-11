"""
Drop env_var column from ai_models table

F018: SSOT через ProviderRegistry — env_var больше не хранится в БД.
API key env var names определяются через ProviderRegistry.get_api_key_env().

Revision ID: 0004_drop_env_var
Revises: 0003_add_available_at
Create Date: 2026-02-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# Revision identifiers
revision: str = "0004_drop_env_var"
down_revision: Union[str, None] = "0003_add_available_at"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("ai_models", "env_var")


def downgrade() -> None:
    op.add_column(
        "ai_models",
        sa.Column("env_var", sa.String(50), nullable=False, server_default=""),
    )
