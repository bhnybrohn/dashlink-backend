"""Product module tests — CRUD, status machine, stock, variants."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.sellers.models import SellerProfile
from app.users.models import User
from app.core.security import hash_password, create_access_token


async def _create_seller(db_session: AsyncSession) -> tuple[User, SellerProfile, str]:
    """Helper: create a seller user + profile and return (user, profile, token)."""
    user = User(
        email="seller@test.com",
        hashed_password=hash_password("securepassword123"),
        role="seller",
        is_verified=True,
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    profile = SellerProfile(
        user_id=user.id,
        store_name="Test Store",
        slug="teststore",
        subscription_tier="free",
    )
    db_session.add(profile)
    await db_session.flush()
    await db_session.refresh(profile)

    token = create_access_token({"sub": user.id, "role": "seller", "email": user.email})
    return user, profile, token


class TestProductCRUD:
    """Tests for product create, read, update, delete."""

    async def test_create_product(self, client: AsyncClient, db_session: AsyncSession):
        _, _, token = await _create_seller(db_session)
        await db_session.commit()

        response = await client.post(
            "/api/v1/products",
            json={
                "name": "Red Lipstick Matte",
                "description": "Beautiful matte lipstick",
                "price": "29.99",
                "currency": "NGN",
                "stock_count": 50,
                "category": "beauty",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "Red Lipstick Matte"
        assert "red-lipstick-matte" in data["slug"]
        assert data["status"] == "draft"
        assert data["stock_count"] == 50

    async def test_list_products(self, client: AsyncClient, db_session: AsyncSession):
        _, _, token = await _create_seller(db_session)
        await db_session.commit()
        headers = {"Authorization": f"Bearer {token}"}

        # Create two products
        await client.post(
            "/api/v1/products",
            json={"name": "Product 1", "price": "10.00", "stock_count": 5},
            headers=headers,
        )
        await client.post(
            "/api/v1/products",
            json={"name": "Product 2", "price": "20.00", "stock_count": 10},
            headers=headers,
        )

        response = await client.get("/api/v1/products", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["items"]) == 2

    async def test_update_product(self, client: AsyncClient, db_session: AsyncSession):
        _, _, token = await _create_seller(db_session)
        await db_session.commit()
        headers = {"Authorization": f"Bearer {token}"}

        create_resp = await client.post(
            "/api/v1/products",
            json={"name": "Old Name", "price": "10.00", "stock_count": 5},
            headers=headers,
        )
        product_id = create_resp.json()["id"]

        response = await client.patch(
            f"/api/v1/products/{product_id}",
            json={"name": "New Name", "price": "15.00"},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["name"] == "New Name"

    async def test_delete_product(self, client: AsyncClient, db_session: AsyncSession):
        _, _, token = await _create_seller(db_session)
        await db_session.commit()
        headers = {"Authorization": f"Bearer {token}"}

        create_resp = await client.post(
            "/api/v1/products",
            json={"name": "To Delete", "price": "10.00", "stock_count": 5},
            headers=headers,
        )
        product_id = create_resp.json()["id"]

        response = await client.delete(f"/api/v1/products/{product_id}", headers=headers)
        assert response.status_code == 204

        # Verify it's gone
        get_resp = await client.get(f"/api/v1/products/{product_id}", headers=headers)
        assert get_resp.status_code == 404

    async def test_buyer_cannot_create_product(self, client: AsyncClient, db_session: AsyncSession):
        user = User(
            email="buyer@test.com",
            hashed_password=hash_password("securepassword123"),
            role="buyer",
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)
        await db_session.commit()

        token = create_access_token({"sub": user.id, "role": "buyer", "email": user.email})
        response = await client.post(
            "/api/v1/products",
            json={"name": "Nope", "price": "10.00"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestProductStatus:
    """Tests for product status machine."""

    async def test_status_transition_draft_to_active(
        self, client: AsyncClient, db_session: AsyncSession,
    ):
        _, _, token = await _create_seller(db_session)
        await db_session.commit()
        headers = {"Authorization": f"Bearer {token}"}

        create_resp = await client.post(
            "/api/v1/products",
            json={"name": "Status Test", "price": "10.00", "stock_count": 5},
            headers=headers,
        )
        product_id = create_resp.json()["id"]

        response = await client.patch(
            f"/api/v1/products/{product_id}/status",
            json={"status": "active"},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "active"

    async def test_invalid_status_transition(
        self, client: AsyncClient, db_session: AsyncSession,
    ):
        _, _, token = await _create_seller(db_session)
        await db_session.commit()
        headers = {"Authorization": f"Bearer {token}"}

        create_resp = await client.post(
            "/api/v1/products",
            json={"name": "Bad Transition", "price": "10.00", "stock_count": 5},
            headers=headers,
        )
        product_id = create_resp.json()["id"]

        # draft -> shipped is not valid
        response = await client.patch(
            f"/api/v1/products/{product_id}/status",
            json={"status": "paused"},
            headers=headers,
        )
        assert response.status_code == 400

    async def test_cannot_activate_zero_stock(
        self, client: AsyncClient, db_session: AsyncSession,
    ):
        _, _, token = await _create_seller(db_session)
        await db_session.commit()
        headers = {"Authorization": f"Bearer {token}"}

        create_resp = await client.post(
            "/api/v1/products",
            json={"name": "No Stock", "price": "10.00", "stock_count": 0},
            headers=headers,
        )
        product_id = create_resp.json()["id"]

        response = await client.patch(
            f"/api/v1/products/{product_id}/status",
            json={"status": "active"},
            headers=headers,
        )
        assert response.status_code == 400


class TestProductStock:
    """Tests for stock updates."""

    async def test_update_stock(self, client: AsyncClient, db_session: AsyncSession):
        _, _, token = await _create_seller(db_session)
        await db_session.commit()
        headers = {"Authorization": f"Bearer {token}"}

        create_resp = await client.post(
            "/api/v1/products",
            json={"name": "Stock Test", "price": "10.00", "stock_count": 50},
            headers=headers,
        )
        product_id = create_resp.json()["id"]

        response = await client.patch(
            f"/api/v1/products/{product_id}/stock",
            json={"stock_count": 100},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["stock_count"] == 100

    async def test_stock_zero_auto_sold_out(
        self, client: AsyncClient, db_session: AsyncSession,
    ):
        _, _, token = await _create_seller(db_session)
        await db_session.commit()
        headers = {"Authorization": f"Bearer {token}"}

        create_resp = await client.post(
            "/api/v1/products",
            json={"name": "Will Sell Out", "price": "10.00", "stock_count": 5},
            headers=headers,
        )
        product_id = create_resp.json()["id"]

        # Activate first
        await client.patch(
            f"/api/v1/products/{product_id}/status",
            json={"status": "active"},
            headers=headers,
        )

        # Set stock to 0
        response = await client.patch(
            f"/api/v1/products/{product_id}/stock",
            json={"stock_count": 0},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["status"] == "sold_out"


class TestProductVariants:
    """Tests for variant management."""

    async def test_create_with_variants(
        self, client: AsyncClient, db_session: AsyncSession,
    ):
        _, _, token = await _create_seller(db_session)
        await db_session.commit()
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.post(
            "/api/v1/products",
            json={
                "name": "T-Shirt",
                "price": "25.00",
                "stock_count": 100,
                "variants": [
                    {"variant_type": "size", "variant_value": "S", "stock_count": 30},
                    {"variant_type": "size", "variant_value": "M", "stock_count": 40},
                    {"variant_type": "size", "variant_value": "L", "stock_count": 30},
                ],
            },
            headers=headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert len(data["variants"]) == 3

    async def test_add_variant(self, client: AsyncClient, db_session: AsyncSession):
        _, _, token = await _create_seller(db_session)
        await db_session.commit()
        headers = {"Authorization": f"Bearer {token}"}

        create_resp = await client.post(
            "/api/v1/products",
            json={"name": "Plain Shirt", "price": "20.00", "stock_count": 50},
            headers=headers,
        )
        product_id = create_resp.json()["id"]

        response = await client.post(
            f"/api/v1/products/{product_id}/variants",
            json={"variant_type": "color", "variant_value": "Red", "stock_count": 25},
            headers=headers,
        )
        assert response.status_code == 201
        assert len(response.json()["variants"]) == 1
