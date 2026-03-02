"""add_pinterest_to_social_platform_enum

Revision ID: c4d91f2a0e35
Revises: 86b3f9069218
Create Date: 2026-02-25 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'c4d91f2a0e35'
down_revision: Union[str, None] = '86b3f9069218'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ADD VALUE must run outside a transaction in PostgreSQL
    op.execute("ALTER TYPE social_platform_enum ADD VALUE IF NOT EXISTS 'pinterest'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values; requires recreating the type.
    pass
