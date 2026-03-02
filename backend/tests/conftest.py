"""Test fixtures — shared across all test modules."""

import asyncio
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.base_model import BaseModel
from app.core.security import create_access_token
from app.database import get_db
from app.main import app

# Import all models so metadata includes all tables for test DB setup
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

# Use a separate test database
TEST_DATABASE_URL = settings.database_url.replace("/dashlink", "/dashlink_test")

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
test_session_factory = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


@pytest.fixture(scope="session")
def event_loop():
    """Create a single event loop for the entire test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(autouse=True)
async def setup_database():
    """Create tables before each test, drop them after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(BaseModel.metadata.drop_all)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a test database session."""
    async with test_session_factory() as session:
        yield session


@pytest.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """Yield an async HTTP test client with DB dependency override."""

    async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    async def _override_get_redis():
        """Return a fakeredis instance for testing."""
        import fakeredis.aioredis
        return fakeredis.aioredis.FakeRedis(decode_responses=True)

    from app.redis import get_redis

    app.dependency_overrides[get_db] = _override_get_db
    app.dependency_overrides[get_redis] = _override_get_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def seller_token() -> str:
    """Generate a valid seller JWT for testing."""
    return create_access_token({
        "sub": "test-seller-id",
        "role": "seller",
        "email": "seller@test.com",
    })


@pytest.fixture
def buyer_token() -> str:
    """Generate a valid buyer JWT for testing."""
    return create_access_token({
        "sub": "test-buyer-id",
        "role": "buyer",
        "email": "buyer@test.com",
    })


@pytest.fixture
def admin_token() -> str:
    """Generate a valid admin JWT for testing."""
    return create_access_token({
        "sub": "test-admin-id",
        "role": "admin",
        "email": "admin@test.com",
    })


@pytest.fixture
def auth_headers(seller_token: str) -> dict[str, str]:
    """Authorization headers with a seller token."""
    return {"Authorization": f"Bearer {seller_token}"}
