"""add_tiktok_to_oauth_provider_enum

Revision ID: f789abae4a60
Revises: 527d3b33e0e0
Create Date: 2026-02-24 23:53:03.927931
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'f789abae4a60'
down_revision: Union[str, None] = '527d3b33e0e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE oauth_provider_enum ADD VALUE IF NOT EXISTS 'tiktok'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values; requires recreating the type.
    pass
