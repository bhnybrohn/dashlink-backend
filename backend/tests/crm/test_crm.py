"""CRM module tests — customer listing, profile, segments, broadcast."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.orders.models import Order
from app.sellers.models import SellerProfile


def _seller_token(user_id: str = "seller-crm-1") -> str:
    return create_access_token({"sub": user_id, "role": "seller", "email": "crm@test.com"})


def _buyer_token() -> str:
    return create_access_token({"sub": "buyer-1", "role": "buyer", "email": "buyer@test.com"})


async def _setup_seller_with_orders(db_session: AsyncSession, seller_user_id: str = "seller-crm-1"):
    """Create a seller with some delivered orders for CRM testing."""
    from uuid import uuid4

    profile = SellerProfile(
        id=str(uuid4()),
        user_id=seller_user_id,
        store_name="CRM Test Store",
        slug=f"crm-{uuid4().hex[:6]}",
    )
    db_session.add(profile)

    for i in range(3):
        order = Order(
            id=str(uuid4()),
            order_number=f"ORD-CRM-{i}",
            buyer_id="buyer-crm-1",
            seller_id=seller_user_id,
            status="delivered",
            subtotal=5000 * (i + 1),
            platform_fee=250 * (i + 1),
            total_amount=5000 * (i + 1),
            currency="NGN",
            buyer_email=f"customer{i}@test.com" if i < 2 else "customer0@test.com",
        )
        db_session.add(order)

    await db_session.flush()
    await db_session.commit()


class TestListCustomers:
    """Tests for GET /api/v1/crm/customers."""

    async def test_list_customers_with_orders(self, client: AsyncClient, db_session: AsyncSession):
        """Returns customer list with purchase stats."""
        await _setup_seller_with_orders(db_session, "seller-crm-list")
        token = _seller_token("seller-crm-list")
        response = await client.get(
            "/api/v1/crm/customers",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert len(data["customers"]) >= 1
        # Check customer summary fields
        customer = data["customers"][0]
        assert "buyer_email" in customer
        assert "purchase_count" in customer
        assert "total_spent" in customer

    async def test_list_customers_empty(self, client: AsyncClient):
        """Returns empty when no orders exist."""
        token = _seller_token("seller-crm-empty")
        response = await client.get(
            "/api/v1/crm/customers",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["total"] == 0

    async def test_buyer_forbidden(self, client: AsyncClient):
        """Buyers cannot access CRM."""
        token = _buyer_token()
        response = await client.get(
            "/api/v1/crm/customers",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestSegments:
    """Tests for GET /api/v1/crm/segments."""

    async def test_segments_returns_all(self, client: AsyncClient, db_session: AsyncSession):
        """Returns all pre-defined customer segments."""
        await _setup_seller_with_orders(db_session, "seller-crm-seg")
        token = _seller_token("seller-crm-seg")
        response = await client.get(
            "/api/v1/crm/segments",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        segment_names = [s["name"] for s in data["segments"]]
        assert "all" in segment_names
        assert "new" in segment_names
        assert "repeat" in segment_names
        assert "high_value" in segment_names
        assert "inactive" in segment_names


class TestBroadcast:
    """Tests for POST /api/v1/crm/broadcast."""

    async def test_broadcast_queued(self, client: AsyncClient, db_session: AsyncSession):
        """Broadcast is queued for delivery."""
        await _setup_seller_with_orders(db_session, "seller-crm-bcast")
        token = _seller_token("seller-crm-bcast")
        response = await client.post(
            "/api/v1/crm/broadcast",
            json={
                "segment": "all",
                "channel": "email",
                "subject": "New Collection Alert!",
                "message": "Check out our latest arrivals.",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "recipient_count" in data
        assert data["recipient_count"] >= 0
