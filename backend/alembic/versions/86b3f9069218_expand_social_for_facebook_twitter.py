"""expand_social_for_facebook_twitter

Revision ID: 86b3f9069218
Revises: f789abae4a60
Create Date: 2026-02-25 01:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '86b3f9069218'
down_revision: Union[str, None] = 'f789abae4a60'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new values to social_platform_enum (must be outside transaction)
    op.execute("ALTER TYPE social_platform_enum ADD VALUE IF NOT EXISTS 'facebook'")
    op.execute("ALTER TYPE social_platform_enum ADD VALUE IF NOT EXISTS 'twitter'")

    # Add post_type column
    op.add_column(
        'social_posts',
        sa.Column('post_type', sa.String(20), nullable=False, server_default='photo'),
    )

    # Make image_url nullable (text/link posts don't require images)
    op.alter_column(
        'social_posts', 'image_url',
        existing_type=sa.String(500),
        nullable=True,
    )

    # Add link_url column
    op.add_column(
        'social_posts',
        sa.Column('link_url', sa.String(500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('social_posts', 'link_url')
    op.alter_column(
        'social_posts', 'image_url',
        existing_type=sa.String(500),
        nullable=False,
    )
    op.drop_column('social_posts', 'post_type')
    # PostgreSQL does not support removing enum values; requires recreating the type.
