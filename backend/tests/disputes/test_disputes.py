"""Disputes module tests — open, respond, escalate, resolve."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.orders.models import Order


def _seller_token(user_id: str = "seller-dispute-1") -> str:
    return create_access_token({"sub": user_id, "role": "seller", "email": "seller@test.com"})


def _buyer_token(user_id: str = "buyer-dispute-1") -> str:
    return create_access_token({"sub": user_id, "role": "buyer", "email": "buyer@test.com"})


def _admin_token() -> str:
    return create_access_token({"sub": "admin-1", "role": "admin", "email": "admin@test.com"})


async def _create_delivered_order(db_session: AsyncSession, seller_id: str = "seller-dispute-1") -> Order:
    """Create a delivered order for testing disputes."""
    from uuid import uuid4
    order = Order(
        id=str(uuid4()),
        order_number=f"ORD-{uuid4().hex[:8].upper()}",
        buyer_id="buyer-dispute-1",
        seller_id=seller_id,
        status="delivered",
        subtotal=10000,
        platform_fee=500,
        total_amount=10000,
        currency="NGN",
        buyer_email="buyer@test.com",
    )
    db_session.add(order)
    await db_session.flush()
    await db_session.refresh(order)
    return order


class TestOpenDispute:
    """Tests for POST /api/v1/disputes."""

    async def test_open_dispute_success(self, client: AsyncClient, db_session: AsyncSession):
        """Buyer can open a dispute on a delivered order."""
        order = await _create_delivered_order(db_session)
        await db_session.commit()

        token = _buyer_token()
        response = await client.post(
            "/api/v1/disputes",
            json={
                "order_id": order.id,
                "reason": "not_received",
                "description": "I never received my package despite it showing delivered.",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "open"
        assert data["reason"] == "not_received"

    async def test_duplicate_dispute_fails(self, client: AsyncClient, db_session: AsyncSession):
        """Opening a second dispute on the same order returns 409."""
        order = await _create_delivered_order(db_session, seller_id="seller-dup-disp")
        await db_session.commit()

        token = _buyer_token()
        await client.post(
            "/api/v1/disputes",
            json={"order_id": order.id, "reason": "damaged", "description": "Package arrived broken."},
            headers={"Authorization": f"Bearer {token}"},
        )
        response = await client.post(
            "/api/v1/disputes",
            json={"order_id": order.id, "reason": "wrong_item", "description": "Second dispute attempt."},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 409

    async def test_unauthenticated_fails(self, client: AsyncClient):
        """Opening a dispute without auth fails."""
        response = await client.post(
            "/api/v1/disputes",
            json={"order_id": "fake-id", "reason": "other", "description": "No auth provided."},
        )
        assert response.status_code in (401, 403)


class TestListDisputes:
    """Tests for GET /api/v1/disputes."""

    async def test_list_disputes_empty(self, client: AsyncClient):
        """Returns empty list when no disputes exist."""
        token = _seller_token("seller-no-disputes")
        response = await client.get(
            "/api/v1/disputes",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["disputes"] == []


class TestSellerRespond:
    """Tests for POST /api/v1/disputes/{id}/respond."""

    async def test_seller_respond(self, client: AsyncClient, db_session: AsyncSession):
        """Seller can respond to an open dispute."""
        order = await _create_delivered_order(db_session, seller_id="seller-respond-1")
        await db_session.commit()

        buyer_token = _buyer_token("buyer-respond-1")
        create_resp = await client.post(
            "/api/v1/disputes",
            json={"order_id": order.id, "reason": "damaged", "description": "Item was broken on arrival."},
            headers={"Authorization": f"Bearer {buyer_token}"},
        )
        dispute_id = create_resp.json()["id"]

        seller_token = _seller_token("seller-respond-1")
        response = await client.post(
            f"/api/v1/disputes/{dispute_id}/respond",
            json={"response": "We apologize. We will send a replacement immediately."},
            headers={"Authorization": f"Bearer {seller_token}"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "seller_responded"


class TestResolveDispute:
    """Tests for POST /api/v1/disputes/{id}/resolve."""

    async def test_admin_resolve(self, client: AsyncClient, db_session: AsyncSession):
        """Admin can resolve a dispute."""
        order = await _create_delivered_order(db_session, seller_id="seller-resolve-1")
        await db_session.commit()

        buyer_token = _buyer_token("buyer-resolve-1")
        create_resp = await client.post(
            "/api/v1/disputes",
            json={"order_id": order.id, "reason": "not_as_described", "description": "Product color was wrong."},
            headers={"Authorization": f"Bearer {buyer_token}"},
        )
        dispute_id = create_resp.json()["id"]

        admin_token = _admin_token()
        response = await client.post(
            f"/api/v1/disputes/{dispute_id}/resolve",
            json={"resolution": "partial_refund", "admin_notes": "Refunding 50% due to color mismatch."},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "resolved"
        assert data["resolution"] == "partial_refund"
