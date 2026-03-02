"""Checkout module tests — stock locking."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.products.models import Product
from app.sellers.models import SellerProfile
from app.users.models import User


async def _setup_product(db_session: AsyncSession) -> tuple[str, str, str]:
    """Create seller + active product. Returns (product_id, seller_token, buyer_token)."""
    seller_user = User(
        email="seller@checkout.com",
        hashed_password=hash_password("pass12345678"),
        role="seller",
        is_active=True,
    )
    db_session.add(seller_user)
    await db_session.flush()
    await db_session.refresh(seller_user)

    profile = SellerProfile(
        user_id=seller_user.id,
        store_name="Checkout Store",
        slug="checkoutstore",
    )
    db_session.add(profile)
    await db_session.flush()
    await db_session.refresh(profile)

    product = Product(
        seller_id=profile.id,
        name="Test Item",
        slug="test-item-abc123",
        price=50.00,
        currency="NGN",
        stock_count=10,
        status="active",
    )
    db_session.add(product)
    await db_session.flush()
    await db_session.refresh(product)
    await db_session.commit()

    seller_token = create_access_token(
        {"sub": seller_user.id, "role": "seller", "email": seller_user.email},
    )

    buyer_user = User(
        email="buyer@checkout.com",
        hashed_password=hash_password("pass12345678"),
        role="buyer",
        is_active=True,
    )
    db_session.add(buyer_user)
    await db_session.flush()
    await db_session.refresh(buyer_user)
    await db_session.commit()

    buyer_token = create_access_token(
        {"sub": buyer_user.id, "role": "buyer", "email": buyer_user.email},
    )

    return product.id, seller_token, buyer_token


class TestStockLocking:
    """Tests for POST /api/v1/checkout/lock."""

    async def test_lock_stock_success(self, client: AsyncClient, db_session: AsyncSession):
        product_id, _, buyer_token = await _setup_product(db_session)

        response = await client.post(
            "/api/v1/checkout/lock",
            json={"product_id": product_id, "quantity": 1},
            headers={"Authorization": f"Bearer {buyer_token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["product_id"] == product_id
        assert data["quantity"] == 1
        assert "lock_id" in data
        assert "expires_at" in data

    async def test_lock_nonexistent_product_fails(self, client: AsyncClient, db_session: AsyncSession):
        _, _, buyer_token = await _setup_product(db_session)

        response = await client.post(
            "/api/v1/checkout/lock",
            json={"product_id": "00000000-0000-0000-0000-000000000000", "quantity": 1},
            headers={"Authorization": f"Bearer {buyer_token}"},
        )
        assert response.status_code == 400

    async def test_lock_anonymous(self, client: AsyncClient, db_session: AsyncSession):
        """Anonymous users can also lock stock."""
        product_id, _, _ = await _setup_product(db_session)

        response = await client.post(
            "/api/v1/checkout/lock",
            json={"product_id": product_id, "quantity": 1},
        )
        assert response.status_code == 201

    async def test_release_lock(self, client: AsyncClient, db_session: AsyncSession):
        product_id, _, _ = await _setup_product(db_session)

        lock_resp = await client.post(
            "/api/v1/checkout/lock",
            json={"product_id": product_id, "quantity": 1},
        )
        lock_id = lock_resp.json()["lock_id"]

        response = await client.delete(f"/api/v1/checkout/lock/{lock_id}")
        assert response.status_code == 200
