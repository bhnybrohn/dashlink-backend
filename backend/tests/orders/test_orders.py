"""Order module tests — status transitions, seller/buyer views."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.orders.models import Order, OrderItem
from app.orders.service import OrderService
from app.sellers.models import SellerProfile
from app.users.models import User


async def _create_order(db_session: AsyncSession) -> tuple[Order, str, str]:
    """Helper: create a seller, buyer, and a paid order. Returns (order, seller_token, buyer_token)."""
    seller_user = User(
        email="seller@orders.com",
        hashed_password=hash_password("pass12345678"),
        role="seller",
        is_active=True,
    )
    db_session.add(seller_user)
    await db_session.flush()
    await db_session.refresh(seller_user)

    profile = SellerProfile(
        user_id=seller_user.id,
        store_name="Order Store",
        slug="orderstore",
    )
    db_session.add(profile)
    await db_session.flush()
    await db_session.refresh(profile)

    buyer_user = User(
        email="buyer@orders.com",
        hashed_password=hash_password("pass12345678"),
        role="buyer",
        is_active=True,
    )
    db_session.add(buyer_user)
    await db_session.flush()
    await db_session.refresh(buyer_user)

    order = Order(
        order_number="DL-TEST0001",
        buyer_id=buyer_user.id,
        seller_id=profile.id,
        status="paid",
        subtotal=50.00,
        platform_fee=2.50,
        total_amount=50.00,
        currency="NGN",
        buyer_email=buyer_user.email,
    )
    db_session.add(order)
    await db_session.flush()
    await db_session.refresh(order)

    item = OrderItem(
        order_id=order.id,
        product_id="prod-123",
        quantity=1,
        unit_price=50.00,
        product_name="Test Product",
    )
    db_session.add(item)
    await db_session.commit()

    seller_token = create_access_token(
        {"sub": seller_user.id, "role": "seller", "email": seller_user.email},
    )
    buyer_token = create_access_token(
        {"sub": buyer_user.id, "role": "buyer", "email": buyer_user.email},
    )
    return order, seller_token, buyer_token


class TestOrderStatusMachine:
    """Tests for order status transitions."""

    async def test_paid_to_packed(self, client, db_session: AsyncSession):
        order, seller_token, _ = await _create_order(db_session)
        headers = {"Authorization": f"Bearer {seller_token}"}

        response = await client.patch(
            f"/api/v1/orders/seller/{order.id}/status",
            json={"status": "packed"},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "packed"

    async def test_packed_to_shipped(self, client, db_session: AsyncSession):
        order, seller_token, _ = await _create_order(db_session)
        headers = {"Authorization": f"Bearer {seller_token}"}

        await client.patch(
            f"/api/v1/orders/seller/{order.id}/status",
            json={"status": "packed"},
            headers=headers,
        )
        response = await client.patch(
            f"/api/v1/orders/seller/{order.id}/status",
            json={"status": "shipped", "tracking_number": "TRK-12345"},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "shipped"
        assert response.json()["tracking_number"] == "TRK-12345"

    async def test_invalid_transition_fails(self, client, db_session: AsyncSession):
        order, seller_token, _ = await _create_order(db_session)
        headers = {"Authorization": f"Bearer {seller_token}"}

        # paid -> delivered is not valid (must go through packed, shipped)
        response = await client.patch(
            f"/api/v1/orders/seller/{order.id}/status",
            json={"status": "delivered"},
            headers=headers,
        )
        assert response.status_code == 400


class TestOrderViews:
    """Tests for seller and buyer order views."""

    async def test_seller_list_orders(self, client, db_session: AsyncSession):
        order, seller_token, _ = await _create_order(db_session)
        headers = {"Authorization": f"Bearer {seller_token}"}

        response = await client.get("/api/v1/orders/seller", headers=headers)
        assert response.status_code == 200
        assert response.json()["total"] >= 1

    async def test_buyer_list_orders(self, client, db_session: AsyncSession):
        order, _, buyer_token = await _create_order(db_session)
        headers = {"Authorization": f"Bearer {buyer_token}"}

        response = await client.get("/api/v1/orders/buyer", headers=headers)
        assert response.status_code == 200
        assert response.json()["total"] >= 1

    async def test_buyer_cannot_access_seller_orders(self, client, db_session: AsyncSession):
        order, _, buyer_token = await _create_order(db_session)
        headers = {"Authorization": f"Bearer {buyer_token}"}

        response = await client.get(
            f"/api/v1/orders/seller/{order.id}",
            headers=headers,
        )
        assert response.status_code == 403
