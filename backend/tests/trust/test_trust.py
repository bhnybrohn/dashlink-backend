"""Trust & fraud scoring module tests."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.sellers.models import SellerProfile


def _seller_token(user_id: str = "seller-trust-1") -> str:
    return create_access_token({"sub": user_id, "role": "seller", "email": "trust@test.com"})


def _admin_token() -> str:
    return create_access_token({"sub": "admin-trust-1", "role": "admin", "email": "admin@test.com"})


def _buyer_token() -> str:
    return create_access_token({"sub": "buyer-1", "role": "buyer", "email": "buyer@test.com"})


async def _create_seller_profile(db_session: AsyncSession, user_id: str = "seller-trust-1") -> SellerProfile:
    """Create a seller profile for trust score testing."""
    from uuid import uuid4
    profile = SellerProfile(
        id=str(uuid4()),
        user_id=user_id,
        store_name="Trust Test Store",
        slug=f"trust-test-{uuid4().hex[:6]}",
    )
    db_session.add(profile)
    await db_session.flush()
    await db_session.refresh(profile)
    return profile


class TestGetTrustScore:
    """Tests for GET /api/v1/seller/trust-score."""

    async def test_trust_score_for_new_seller(self, client: AsyncClient, db_session: AsyncSession):
        """New seller gets a trust score calculated on first access."""
        profile = await _create_seller_profile(db_session, "seller-trust-new")
        await db_session.commit()

        token = _seller_token("seller-trust-new")
        response = await client.get(
            "/api/v1/seller/trust-score",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "score" in data
        assert "level" in data
        assert "factors" in data
        assert data["level"] in ("new", "basic", "trusted", "verified", "premium")

    async def test_trust_score_buyer_forbidden(self, client: AsyncClient):
        """Buyer cannot access trust score endpoint."""
        token = _buyer_token()
        response = await client.get(
            "/api/v1/seller/trust-score",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestAdminTrust:
    """Tests for admin trust endpoints."""

    async def test_list_trust_scores_admin(self, client: AsyncClient):
        """Admin can list sellers by trust level."""
        token = _admin_token()
        response = await client.get(
            "/api/v1/admin/trust/sellers",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "scores" in data
        assert "total" in data

    async def test_list_flagged_orders_admin(self, client: AsyncClient):
        """Admin can list flagged orders."""
        token = _admin_token()
        response = await client.get(
            "/api/v1/admin/trust/flagged-orders",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "flagged_orders" in data
        assert "total" in data

    async def test_seller_cannot_access_admin_trust(self, client: AsyncClient):
        """Seller cannot access admin trust endpoints."""
        token = _seller_token()
        response = await client.get(
            "/api/v1/admin/trust/sellers",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403
