"""Discount codes module tests — CRUD and checkout validation."""

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token


def _seller_token(user_id: str = "seller-discount-1") -> str:
    return create_access_token({"sub": user_id, "role": "seller", "email": "discount@test.com"})


def _buyer_token() -> str:
    return create_access_token({"sub": "buyer-1", "role": "buyer", "email": "buyer@test.com"})


class TestCreateDiscountCode:
    """Tests for POST /api/v1/seller/discounts."""

    async def test_create_percentage_discount(self, client: AsyncClient):
        """Seller creates a percentage discount code."""
        token = _seller_token()
        response = await client.post(
            "/api/v1/seller/discounts",
            json={
                "code": "SAVE20",
                "discount_type": "percentage",
                "discount_value": 20,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["code"] == "SAVE20"
        assert data["discount_type"] == "percentage"
        assert data["discount_value"] == 20
        assert data["is_active"] is True

    async def test_create_fixed_discount(self, client: AsyncClient):
        """Seller creates a fixed amount discount code."""
        token = _seller_token("seller-disc-fixed")
        response = await client.post(
            "/api/v1/seller/discounts",
            json={
                "code": "FLAT500",
                "discount_type": "fixed",
                "discount_value": 500,
                "min_order_amount": 2000,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        assert response.json()["min_order_amount"] == 2000

    async def test_duplicate_code_fails(self, client: AsyncClient):
        """Creating duplicate code returns 409."""
        token = _seller_token("seller-disc-dup")
        await client.post(
            "/api/v1/seller/discounts",
            json={"code": "DUP10", "discount_type": "percentage", "discount_value": 10},
            headers={"Authorization": f"Bearer {token}"},
        )
        response = await client.post(
            "/api/v1/seller/discounts",
            json={"code": "DUP10", "discount_type": "percentage", "discount_value": 15},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 409

    async def test_buyer_cannot_create(self, client: AsyncClient):
        """Buyers cannot create discount codes."""
        token = _buyer_token()
        response = await client.post(
            "/api/v1/seller/discounts",
            json={"code": "NOPE", "discount_type": "fixed", "discount_value": 100},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestListDiscountCodes:
    """Tests for GET /api/v1/seller/discounts."""

    async def test_list_codes(self, client: AsyncClient):
        """Returns paginated discount codes."""
        token = _seller_token("seller-disc-list")
        await client.post(
            "/api/v1/seller/discounts",
            json={"code": "LIST10", "discount_type": "percentage", "discount_value": 10},
            headers={"Authorization": f"Bearer {token}"},
        )
        response = await client.get(
            "/api/v1/seller/discounts",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert len(data["codes"]) >= 1

    async def test_list_empty(self, client: AsyncClient):
        """No codes returns empty list."""
        token = _seller_token("seller-disc-empty")
        response = await client.get(
            "/api/v1/seller/discounts",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["total"] == 0


class TestApplyDiscount:
    """Tests for POST /api/v1/checkout/apply-discount."""

    async def test_apply_percentage(self, client: AsyncClient):
        """Apply a percentage discount code."""
        token = _seller_token("seller-apply-pct")
        await client.post(
            "/api/v1/seller/discounts",
            json={"code": "PCT25", "discount_type": "percentage", "discount_value": 25},
            headers={"Authorization": f"Bearer {token}"},
        )
        response = await client.post(
            "/api/v1/checkout/apply-discount",
            json={"code": "PCT25", "order_subtotal": 10000},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["amount_saved"] == 2500
        assert data["new_total"] == 7500

    async def test_apply_invalid_code(self, client: AsyncClient):
        """Invalid code returns 400."""
        response = await client.post(
            "/api/v1/checkout/apply-discount",
            json={"code": "NOSUCHCODE", "order_subtotal": 5000},
        )
        assert response.status_code == 400
