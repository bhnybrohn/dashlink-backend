"""Reviews module tests — submit, list, duplicate prevention, rating aggregation."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.orders.models import Order, OrderItem
from app.products.models import Product
from app.reviews.models import Review
from app.sellers.models import SellerProfile
from app.users.models import User


async def _create_review_fixtures(
    db_session: AsyncSession,
) -> tuple[SellerProfile, Product, Order, str, str]:
    """Create seller, buyer, product, and a delivered order."""
    seller_user = User(
        email="seller@reviews.com",
        hashed_password=hash_password("pass12345678"),
        role="seller",
        is_active=True,
    )
    db_session.add(seller_user)
    await db_session.flush()
    await db_session.refresh(seller_user)

    profile = SellerProfile(
        user_id=seller_user.id,
        store_name="Review Store",
        slug="reviewstore",
        subscription_tier="free",
    )
    db_session.add(profile)
    await db_session.flush()
    await db_session.refresh(profile)

    buyer_user = User(
        email="buyer@reviews.com",
        hashed_password=hash_password("pass12345678"),
        role="buyer",
        is_active=True,
    )
    db_session.add(buyer_user)
    await db_session.flush()
    await db_session.refresh(buyer_user)

    product = Product(
        seller_id=profile.id,
        name="Reviewable Product",
        slug="reviewable-product",
        price=30.00,
        currency="NGN",
        stock_count=50,
        status="active",
    )
    db_session.add(product)
    await db_session.flush()
    await db_session.refresh(product)

    order = Order(
        order_number="DL-REV0001",
        buyer_id=buyer_user.id,
        seller_id=profile.id,
        status="delivered",
        subtotal=30.00,
        platform_fee=1.50,
        total_amount=30.00,
        currency="NGN",
        buyer_email=buyer_user.email,
    )
    db_session.add(order)
    await db_session.flush()
    await db_session.refresh(order)

    item = OrderItem(
        order_id=order.id,
        product_id=product.id,
        quantity=1,
        unit_price=30.00,
        product_name="Reviewable Product",
    )
    db_session.add(item)
    await db_session.commit()

    seller_token = create_access_token(
        {"sub": seller_user.id, "role": "seller", "email": seller_user.email},
    )
    buyer_token = create_access_token(
        {"sub": buyer_user.id, "role": "buyer", "email": buyer_user.email},
    )
    return profile, product, order, seller_token, buyer_token


class TestSubmitReview:
    """Tests for submitting reviews."""

    async def test_submit_review_success(self, client: AsyncClient, db_session: AsyncSession):
        profile, product, order, _, buyer_token = await _create_review_fixtures(db_session)
        headers = {"Authorization": f"Bearer {buyer_token}"}

        response = await client.post(
            "/api/v1/reviews",
            json={
                "order_id": order.id,
                "product_id": product.id,
                "rating": 5,
                "comment": "Excellent product!",
            },
            headers=headers,
        )
        assert response.status_code == 201
        data = response.json()
        assert data["rating"] == 5
        assert data["comment"] == "Excellent product!"
        assert data["order_id"] == order.id
        assert data["seller_id"] == profile.id

    async def test_cannot_review_non_delivered_order(
        self, client: AsyncClient, db_session: AsyncSession,
    ):
        """Only delivered orders can be reviewed."""
        profile, product, order, _, buyer_token = await _create_review_fixtures(db_session)
        # Change order status to paid (not delivered)
        order.status = "paid"
        db_session.add(order)
        await db_session.commit()

        headers = {"Authorization": f"Bearer {buyer_token}"}
        response = await client.post(
            "/api/v1/reviews",
            json={
                "order_id": order.id,
                "product_id": product.id,
                "rating": 4,
            },
            headers=headers,
        )
        assert response.status_code == 400

    async def test_cannot_review_same_order_twice(
        self, client: AsyncClient, db_session: AsyncSession,
    ):
        """Duplicate reviews for the same order should be rejected."""
        profile, product, order, _, buyer_token = await _create_review_fixtures(db_session)
        headers = {"Authorization": f"Bearer {buyer_token}"}

        # First review succeeds
        first = await client.post(
            "/api/v1/reviews",
            json={"order_id": order.id, "product_id": product.id, "rating": 5},
            headers=headers,
        )
        assert first.status_code == 201

        # Second review fails
        second = await client.post(
            "/api/v1/reviews",
            json={"order_id": order.id, "product_id": product.id, "rating": 4},
            headers=headers,
        )
        assert second.status_code == 409

    async def test_cannot_review_others_order(
        self, client: AsyncClient, db_session: AsyncSession,
    ):
        """Buyers can only review their own orders."""
        _, product, order, _, _ = await _create_review_fixtures(db_session)

        # Create a different buyer
        other_buyer = User(
            email="other@reviews.com",
            hashed_password=hash_password("pass12345678"),
            role="buyer",
            is_active=True,
        )
        db_session.add(other_buyer)
        await db_session.flush()
        await db_session.refresh(other_buyer)
        await db_session.commit()

        other_token = create_access_token(
            {"sub": other_buyer.id, "role": "buyer", "email": other_buyer.email},
        )
        headers = {"Authorization": f"Bearer {other_token}"}

        response = await client.post(
            "/api/v1/reviews",
            json={"order_id": order.id, "product_id": product.id, "rating": 3},
            headers=headers,
        )
        assert response.status_code == 400

    async def test_rating_validation(self, client: AsyncClient, db_session: AsyncSession):
        """Rating must be between 1 and 5."""
        _, product, order, _, buyer_token = await _create_review_fixtures(db_session)
        headers = {"Authorization": f"Bearer {buyer_token}"}

        # Rating 0 — too low
        response = await client.post(
            "/api/v1/reviews",
            json={"order_id": order.id, "product_id": product.id, "rating": 0},
            headers=headers,
        )
        assert response.status_code == 422

        # Rating 6 — too high
        response = await client.post(
            "/api/v1/reviews",
            json={"order_id": order.id, "product_id": product.id, "rating": 6},
            headers=headers,
        )
        assert response.status_code == 422


class TestListReviews:
    """Tests for listing reviews by product and seller."""

    async def test_list_product_reviews(self, client: AsyncClient, db_session: AsyncSession):
        profile, product, order, _, buyer_token = await _create_review_fixtures(db_session)

        # Submit a review first
        headers = {"Authorization": f"Bearer {buyer_token}"}
        await client.post(
            "/api/v1/reviews",
            json={"order_id": order.id, "product_id": product.id, "rating": 4, "comment": "Good"},
            headers=headers,
        )

        # List product reviews (public, no auth needed)
        response = await client.get(f"/api/v1/reviews/product/{product.id}")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["rating"] == 4

    async def test_list_seller_reviews(self, client: AsyncClient, db_session: AsyncSession):
        profile, product, order, _, buyer_token = await _create_review_fixtures(db_session)

        # Submit a review
        headers = {"Authorization": f"Bearer {buyer_token}"}
        await client.post(
            "/api/v1/reviews",
            json={"order_id": order.id, "product_id": product.id, "rating": 5},
            headers=headers,
        )

        # List seller reviews by slug (public)
        response = await client.get(f"/api/v1/reviews/seller/{profile.slug}")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["rating"] == 5

    async def test_list_seller_reviews_not_found(self, client: AsyncClient):
        response = await client.get("/api/v1/reviews/seller/nonexistent-slug")
        assert response.status_code == 404


class TestSellerRatingUpdate:
    """Tests for auto-updating seller average rating after review."""

    async def test_seller_rating_updated_after_review(
        self, db_session: AsyncSession, client: AsyncClient,
    ):
        profile, product, order, _, buyer_token = await _create_review_fixtures(db_session)
        headers = {"Authorization": f"Bearer {buyer_token}"}

        # Submit review with rating 4
        await client.post(
            "/api/v1/reviews",
            json={"order_id": order.id, "product_id": product.id, "rating": 4},
            headers=headers,
        )

        # Refresh seller profile and check rating
        await db_session.refresh(profile)
        assert profile.average_rating == 4.0
