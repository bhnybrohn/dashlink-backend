"""Storefront module tests — public /@slug pages, product listing, flash pages."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.products.models import Product
from app.sellers.models import SellerProfile
from app.users.models import User


async def _create_store_with_products(
    db_session: AsyncSession, *, num_products: int = 3,
) -> tuple[SellerProfile, list[Product]]:
    """Helper: create a seller with active products."""
    user = User(
        email="storefront@test.com",
        hashed_password=hash_password("pass12345678"),
        role="seller",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    profile = SellerProfile(
        user_id=user.id,
        store_name="TestShop",
        slug="testshop",
        subscription_tier="free",
    )
    db_session.add(profile)
    await db_session.flush()
    await db_session.refresh(profile)

    products = []
    for i in range(num_products):
        product = Product(
            seller_id=profile.id,
            name=f"Product {i+1}",
            slug=f"product-{i+1}",
            price=10.00 + i,
            currency="NGN",
            stock_count=50,
            status="active",
        )
        db_session.add(product)
        products.append(product)

    await db_session.flush()
    for p in products:
        await db_session.refresh(p)
    await db_session.commit()

    return profile, products


class TestStorefront:
    """Tests for public storefront page."""

    async def test_get_storefront_by_slug(self, client: AsyncClient, db_session: AsyncSession):
        profile, products = await _create_store_with_products(db_session)

        response = await client.get(f"/api/v1/storefront/@{profile.slug}")
        assert response.status_code == 200
        data = response.json()
        assert data["seller"]["store_name"] == "TestShop"
        assert data["seller"]["slug"] == "testshop"
        assert data["total_products"] == 3
        assert len(data["products"]) == 3

    async def test_storefront_not_found(self, client: AsyncClient):
        response = await client.get("/api/v1/storefront/@nonexistent")
        assert response.status_code == 404

    async def test_storefront_only_shows_active_products(
        self, client: AsyncClient, db_session: AsyncSession,
    ):
        user = User(
            email="mixed@test.com",
            hashed_password=hash_password("pass12345678"),
            role="seller",
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)

        profile = SellerProfile(
            user_id=user.id,
            store_name="MixedShop",
            slug="mixedshop",
            subscription_tier="free",
        )
        db_session.add(profile)
        await db_session.flush()
        await db_session.refresh(profile)

        # One active, one draft
        active = Product(
            seller_id=profile.id, name="Active", slug="active-prod",
            price=10.00, currency="NGN", stock_count=10, status="active",
        )
        draft = Product(
            seller_id=profile.id, name="Draft", slug="draft-prod",
            price=10.00, currency="NGN", stock_count=10, status="draft",
        )
        db_session.add_all([active, draft])
        await db_session.commit()

        response = await client.get("/api/v1/storefront/@mixedshop")
        assert response.status_code == 200
        data = response.json()
        assert data["total_products"] == 1
        assert data["products"][0]["name"] == "Active"


class TestStoreProducts:
    """Tests for paginated store products endpoint."""

    async def test_paginated_products(self, client: AsyncClient, db_session: AsyncSession):
        profile, _ = await _create_store_with_products(db_session, num_products=5)

        response = await client.get(
            f"/api/v1/storefront/@{profile.slug}/products?limit=2&offset=0",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2

    async def test_products_second_page(self, client: AsyncClient, db_session: AsyncSession):
        profile, _ = await _create_store_with_products(db_session, num_products=5)

        response = await client.get(
            f"/api/v1/storefront/@{profile.slug}/products?limit=2&offset=2",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 5
        assert len(data["items"]) == 2


class TestFlashPage:
    """Tests for single-product Flash Page."""

    async def test_flash_page(self, client: AsyncClient, db_session: AsyncSession):
        _, products = await _create_store_with_products(db_session, num_products=1)
        product = products[0]

        response = await client.get(f"/api/v1/flash/{product.slug}")
        assert response.status_code == 200
        data = response.json()
        assert data["product"]["slug"] == product.slug
        assert data["seller"]["store_name"] == "TestShop"

    async def test_flash_page_not_found(self, client: AsyncClient):
        response = await client.get("/api/v1/flash/nonexistent-slug")
        assert response.status_code == 404

    async def test_flash_page_draft_product_not_found(
        self, client: AsyncClient, db_session: AsyncSession,
    ):
        """Draft products should not be accessible via Flash Page."""
        user = User(
            email="flashtest@test.com",
            hashed_password=hash_password("pass12345678"),
            role="seller",
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)

        profile = SellerProfile(
            user_id=user.id, store_name="Flash Store",
            slug="flashstore", subscription_tier="free",
        )
        db_session.add(profile)
        await db_session.flush()
        await db_session.refresh(profile)

        draft = Product(
            seller_id=profile.id, name="Draft Product", slug="draft-flash",
            price=25.00, currency="NGN", stock_count=10, status="draft",
        )
        db_session.add(draft)
        await db_session.commit()

        response = await client.get("/api/v1/flash/draft-flash")
        assert response.status_code == 404
