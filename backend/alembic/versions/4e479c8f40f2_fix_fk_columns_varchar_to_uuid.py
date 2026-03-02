"""fix fk columns varchar to uuid

Revision ID: 4e479c8f40f2
Revises: 6f19962942bf
Create Date: 2026-02-22 15:13:33.678620
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e479c8f40f2'
down_revision: Union[str, None] = '6f19962942bf'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _alter_to_uuid(table: str, column: str, nullable: bool = False) -> None:
    """Helper: alter a VARCHAR column to UUID with proper USING cast."""
    op.alter_column(
        table, column,
        existing_type=sa.VARCHAR(),
        type_=sa.UUID(as_uuid=False),
        postgresql_using=f'{column}::uuid',
        existing_nullable=nullable,
    )


def upgrade() -> None:
    # addresses
    _alter_to_uuid('addresses', 'user_id')
    op.create_foreign_key(None, 'addresses', 'users', ['user_id'], ['id'])

    # analytics_events
    _alter_to_uuid('analytics_events', 'seller_id')
    _alter_to_uuid('analytics_events', 'product_id', nullable=True)
    op.create_foreign_key(None, 'analytics_events', 'seller_profiles', ['seller_id'], ['id'])
    op.create_foreign_key(None, 'analytics_events', 'products', ['product_id'], ['id'])

    # daily_aggregates
    _alter_to_uuid('daily_aggregates', 'seller_id')
    op.create_foreign_key(None, 'daily_aggregates', 'seller_profiles', ['seller_id'], ['id'])

    # discount_codes
    _alter_to_uuid('discount_codes', 'seller_id')
    op.create_foreign_key(None, 'discount_codes', 'seller_profiles', ['seller_id'], ['id'])

    # discount_usages
    _alter_to_uuid('discount_usages', 'discount_code_id')
    _alter_to_uuid('discount_usages', 'order_id')
    op.create_foreign_key(None, 'discount_usages', 'discount_codes', ['discount_code_id'], ['id'])
    op.create_foreign_key(None, 'discount_usages', 'orders', ['order_id'], ['id'])

    # disputes
    _alter_to_uuid('disputes', 'order_id')
    _alter_to_uuid('disputes', 'initiated_by')
    _alter_to_uuid('disputes', 'seller_id')
    op.create_foreign_key(None, 'disputes', 'users', ['initiated_by'], ['id'])
    op.create_foreign_key(None, 'disputes', 'seller_profiles', ['seller_id'], ['id'])
    op.create_foreign_key(None, 'disputes', 'orders', ['order_id'], ['id'])

    # kyc_submissions
    _alter_to_uuid('kyc_submissions', 'seller_profile_id')
    op.create_foreign_key(None, 'kyc_submissions', 'seller_profiles', ['seller_profile_id'], ['id'])

    # notification_preferences
    _alter_to_uuid('notification_preferences', 'user_id')
    op.create_foreign_key(None, 'notification_preferences', 'users', ['user_id'], ['id'])

    # notifications
    _alter_to_uuid('notifications', 'user_id')
    op.create_foreign_key(None, 'notifications', 'users', ['user_id'], ['id'])

    # oauth_accounts
    _alter_to_uuid('oauth_accounts', 'user_id')
    op.create_foreign_key(None, 'oauth_accounts', 'users', ['user_id'], ['id'])

    # order_items
    _alter_to_uuid('order_items', 'order_id')
    _alter_to_uuid('order_items', 'product_id')
    _alter_to_uuid('order_items', 'variant_id', nullable=True)
    op.create_foreign_key(None, 'order_items', 'orders', ['order_id'], ['id'])
    op.create_foreign_key(None, 'order_items', 'product_variants', ['variant_id'], ['id'])
    op.create_foreign_key(None, 'order_items', 'products', ['product_id'], ['id'])

    # order_risk_flags
    _alter_to_uuid('order_risk_flags', 'order_id')
    op.create_foreign_key(None, 'order_risk_flags', 'orders', ['order_id'], ['id'])

    # orders
    _alter_to_uuid('orders', 'buyer_id', nullable=True)
    _alter_to_uuid('orders', 'seller_id')
    op.create_foreign_key(None, 'orders', 'seller_profiles', ['seller_id'], ['id'])
    op.create_foreign_key(None, 'orders', 'users', ['buyer_id'], ['id'])

    # payments
    _alter_to_uuid('payments', 'order_id')
    op.create_foreign_key(None, 'payments', 'orders', ['order_id'], ['id'])

    # payouts
    _alter_to_uuid('payouts', 'seller_id')
    op.create_foreign_key(None, 'payouts', 'seller_profiles', ['seller_id'], ['id'])

    # product_images
    _alter_to_uuid('product_images', 'product_id')
    op.create_foreign_key(None, 'product_images', 'products', ['product_id'], ['id'])

    # product_variants
    _alter_to_uuid('product_variants', 'product_id')
    op.create_foreign_key(None, 'product_variants', 'products', ['product_id'], ['id'])

    # products
    _alter_to_uuid('products', 'seller_id')
    op.create_foreign_key(None, 'products', 'seller_profiles', ['seller_id'], ['id'])

    # refresh_tokens
    _alter_to_uuid('refresh_tokens', 'user_id')
    op.create_foreign_key(None, 'refresh_tokens', 'users', ['user_id'], ['id'])

    # reviews
    _alter_to_uuid('reviews', 'order_id')
    _alter_to_uuid('reviews', 'buyer_id')
    _alter_to_uuid('reviews', 'seller_id')
    _alter_to_uuid('reviews', 'product_id')
    op.create_foreign_key(None, 'reviews', 'products', ['product_id'], ['id'])
    op.create_foreign_key(None, 'reviews', 'seller_profiles', ['seller_id'], ['id'])
    op.create_foreign_key(None, 'reviews', 'users', ['buyer_id'], ['id'])
    op.create_foreign_key(None, 'reviews', 'orders', ['order_id'], ['id'])

    # seller_profiles
    _alter_to_uuid('seller_profiles', 'user_id')
    op.create_foreign_key(None, 'seller_profiles', 'users', ['user_id'], ['id'])

    # social_accounts
    _alter_to_uuid('social_accounts', 'seller_id')
    op.create_foreign_key(None, 'social_accounts', 'seller_profiles', ['seller_id'], ['id'])

    # social_posts
    _alter_to_uuid('social_posts', 'seller_id')
    _alter_to_uuid('social_posts', 'social_account_id')
    _alter_to_uuid('social_posts', 'product_id', nullable=True)
    op.create_foreign_key(None, 'social_posts', 'social_accounts', ['social_account_id'], ['id'])
    op.create_foreign_key(None, 'social_posts', 'seller_profiles', ['seller_id'], ['id'])
    op.create_foreign_key(None, 'social_posts', 'products', ['product_id'], ['id'])

    # stock_locks
    _alter_to_uuid('stock_locks', 'product_id')
    _alter_to_uuid('stock_locks', 'variant_id', nullable=True)
    op.create_foreign_key(None, 'stock_locks', 'products', ['product_id'], ['id'])
    op.create_foreign_key(None, 'stock_locks', 'product_variants', ['variant_id'], ['id'])

    # studio_generations
    _alter_to_uuid('studio_generations', 'seller_id')
    _alter_to_uuid('studio_generations', 'product_id', nullable=True)
    op.create_foreign_key(None, 'studio_generations', 'products', ['product_id'], ['id'])
    op.create_foreign_key(None, 'studio_generations', 'seller_profiles', ['seller_id'], ['id'])

    # team_members
    _alter_to_uuid('team_members', 'seller_profile_id')
    _alter_to_uuid('team_members', 'user_id', nullable=True)
    op.create_foreign_key(None, 'team_members', 'users', ['user_id'], ['id'])
    op.create_foreign_key(None, 'team_members', 'seller_profiles', ['seller_profile_id'], ['id'])

    # trust_scores
    _alter_to_uuid('trust_scores', 'seller_id')
    op.create_foreign_key(None, 'trust_scores', 'seller_profiles', ['seller_id'], ['id'])


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'trust_scores', type_='foreignkey')
    op.alter_column('trust_scores', 'seller_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.drop_constraint(None, 'team_members', type_='foreignkey')
    op.drop_constraint(None, 'team_members', type_='foreignkey')
    op.alter_column('team_members', 'user_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=True)
    op.alter_column('team_members', 'seller_profile_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.drop_constraint(None, 'studio_generations', type_='foreignkey')
    op.drop_constraint(None, 'studio_generations', type_='foreignkey')
    op.alter_column('studio_generations', 'product_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=True)
    op.alter_column('studio_generations', 'seller_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.drop_constraint(None, 'stock_locks', type_='foreignkey')
    op.drop_constraint(None, 'stock_locks', type_='foreignkey')
    op.alter_column('stock_locks', 'variant_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=True)
    op.alter_column('stock_locks', 'product_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.drop_constraint(None, 'social_posts', type_='foreignkey')
    op.drop_constraint(None, 'social_posts', type_='foreignkey')
    op.drop_constraint(None, 'social_posts', type_='foreignkey')
    op.alter_column('social_posts', 'product_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=True)
    op.alter_column('social_posts', 'social_account_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.alter_column('social_posts', 'seller_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.drop_constraint(None, 'social_accounts', type_='foreignkey')
    op.alter_column('social_accounts', 'seller_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.drop_constraint(None, 'seller_profiles', type_='foreignkey')
    op.alter_column('seller_profiles', 'user_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.drop_constraint(None, 'reviews', type_='foreignkey')
    op.drop_constraint(None, 'reviews', type_='foreignkey')
    op.drop_constraint(None, 'reviews', type_='foreignkey')
    op.drop_constraint(None, 'reviews', type_='foreignkey')
    op.alter_column('reviews', 'product_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.alter_column('reviews', 'seller_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.alter_column('reviews', 'buyer_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.alter_column('reviews', 'order_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.drop_constraint(None, 'refresh_tokens', type_='foreignkey')
    op.alter_column('refresh_tokens', 'user_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.drop_constraint(None, 'products', type_='foreignkey')
    op.alter_column('products', 'seller_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.drop_constraint(None, 'product_variants', type_='foreignkey')
    op.alter_column('product_variants', 'product_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.drop_constraint(None, 'product_images', type_='foreignkey')
    op.alter_column('product_images', 'product_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.drop_constraint(None, 'payouts', type_='foreignkey')
    op.alter_column('payouts', 'seller_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.drop_constraint(None, 'payments', type_='foreignkey')
    op.alter_column('payments', 'order_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.drop_constraint(None, 'orders', type_='foreignkey')
    op.drop_constraint(None, 'orders', type_='foreignkey')
    op.alter_column('orders', 'seller_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.alter_column('orders', 'buyer_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=True)
    op.drop_constraint(None, 'order_risk_flags', type_='foreignkey')
    op.alter_column('order_risk_flags', 'order_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.drop_constraint(None, 'order_items', type_='foreignkey')
    op.drop_constraint(None, 'order_items', type_='foreignkey')
    op.drop_constraint(None, 'order_items', type_='foreignkey')
    op.alter_column('order_items', 'variant_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=True)
    op.alter_column('order_items', 'product_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.alter_column('order_items', 'order_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.drop_constraint(None, 'oauth_accounts', type_='foreignkey')
    op.alter_column('oauth_accounts', 'user_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.drop_constraint(None, 'notifications', type_='foreignkey')
    op.alter_column('notifications', 'user_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.drop_constraint(None, 'notification_preferences', type_='foreignkey')
    op.alter_column('notification_preferences', 'user_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.drop_constraint(None, 'kyc_submissions', type_='foreignkey')
    op.alter_column('kyc_submissions', 'seller_profile_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.drop_constraint(None, 'disputes', type_='foreignkey')
    op.drop_constraint(None, 'disputes', type_='foreignkey')
    op.drop_constraint(None, 'disputes', type_='foreignkey')
    op.alter_column('disputes', 'seller_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.alter_column('disputes', 'initiated_by',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.alter_column('disputes', 'order_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.drop_constraint(None, 'discount_usages', type_='foreignkey')
    op.drop_constraint(None, 'discount_usages', type_='foreignkey')
    op.alter_column('discount_usages', 'order_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.alter_column('discount_usages', 'discount_code_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.drop_constraint(None, 'discount_codes', type_='foreignkey')
    op.alter_column('discount_codes', 'seller_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.drop_constraint(None, 'daily_aggregates', type_='foreignkey')
    op.alter_column('daily_aggregates', 'seller_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.drop_constraint(None, 'analytics_events', type_='foreignkey')
    op.drop_constraint(None, 'analytics_events', type_='foreignkey')
    op.alter_column('analytics_events', 'product_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=True)
    op.alter_column('analytics_events', 'seller_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    op.drop_constraint(None, 'addresses', type_='foreignkey')
    op.alter_column('addresses', 'user_id',
               existing_type=sa.UUID(as_uuid=False),
               type_=sa.VARCHAR(),
               existing_nullable=False)
    # ### end Alembic commands ###
