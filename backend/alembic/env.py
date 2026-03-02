"""Alembic migration environment — async-aware."""

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.config import settings

# Import all models so Alembic can detect them
from app.core.base_model import BaseModel
from app.users.models import User, Address  # noqa: F401
from app.sellers.models import SellerProfile, KycSubmission, TeamMember  # noqa: F401
from app.auth.models import RefreshToken, LoginAttempt, OAuthAccount  # noqa: F401
from app.products.models import Product, ProductImage, ProductVariant  # noqa: F401
from app.checkout.models import StockLock  # noqa: F401
from app.orders.models import Order, OrderItem  # noqa: F401
from app.payments.models import Payment, Payout  # noqa: F401
from app.notifications.models import Notification, NotificationPreference  # noqa: F401
from app.studio.models import StudioGeneration  # noqa: F401
from app.reviews.models import Review  # noqa: F401
from app.social.models import SocialAccount, SocialPost  # noqa: F401
from app.analytics.models import AnalyticsEvent, DailyAggregate  # noqa: F401
from app.discounts.models import DiscountCode, DiscountUsage  # noqa: F401
from app.disputes.models import Dispute  # noqa: F401
from app.trust.models import TrustScore, OrderRiskFlag  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = BaseModel.metadata

# Override sqlalchemy.url with our settings
config.set_main_option("sqlalchemy.url", settings.database_url)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode — generates SQL without a live DB."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations using an async engine."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode — with a live async DB connection."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
