"""Analytics module tests — event recording and dashboard queries."""

import pytest
from httpx import AsyncClient

from app.core.security import create_access_token


def _seller_token(user_id: str = "seller-analytics-1") -> str:
    return create_access_token({"sub": user_id, "role": "seller", "email": "analytics@test.com"})


def _buyer_token() -> str:
    return create_access_token({"sub": "buyer-1", "role": "buyer", "email": "buyer@test.com"})


class TestRecordEvent:
    """Tests for POST /api/v1/analytics/event."""

    async def test_record_event_success(self, client: AsyncClient):
        """Record a storefront view event."""
        response = await client.post(
            "/api/v1/analytics/event",
            json={
                "event_type": "view",
                "seller_id": "seller-analytics-1",
                "product_id": "prod-1",
                "referrer": "instagram",
                "session_id": "sess-123",
            },
        )
        assert response.status_code == 201
        assert response.json()["message"] == "Event recorded"

    async def test_record_event_invalid_type(self, client: AsyncClient):
        """Invalid event type returns 422."""
        response = await client.post(
            "/api/v1/analytics/event",
            json={"event_type": "invalid", "seller_id": "s1"},
        )
        assert response.status_code == 422

    async def test_record_purchase_event(self, client: AsyncClient):
        """Record a purchase event."""
        response = await client.post(
            "/api/v1/analytics/event",
            json={
                "event_type": "purchase",
                "seller_id": "seller-analytics-1",
                "product_id": "prod-2",
            },
        )
        assert response.status_code == 201


class TestOverview:
    """Tests for GET /api/v1/analytics/overview."""

    async def test_overview_requires_seller(self, client: AsyncClient):
        """Buyer cannot access seller analytics."""
        token = _buyer_token()
        response = await client.get(
            "/api/v1/analytics/overview?start_date=2025-01-01&end_date=2025-12-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403

    async def test_overview_returns_stats(self, client: AsyncClient):
        """Seller sees analytics overview with zero defaults."""
        token = _seller_token()
        response = await client.get(
            "/api/v1/analytics/overview?start_date=2025-01-01&end_date=2025-12-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_revenue" in data
        assert "total_orders" in data
        assert "total_views" in data
        assert "unique_visitors" in data


class TestFunnel:
    """Tests for GET /api/v1/analytics/funnel."""

    async def test_funnel_empty(self, client: AsyncClient):
        """Funnel with no events returns zeros."""
        token = _seller_token("seller-funnel-1")
        response = await client.get(
            "/api/v1/analytics/funnel?start_date=2025-01-01&end_date=2025-12-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["views"] == 0
        assert data["purchases"] == 0
        assert data["conversion_rate"] == 0.0


class TestRevenueChart:
    """Tests for GET /api/v1/analytics/revenue-chart."""

    async def test_revenue_chart_empty(self, client: AsyncClient):
        """Revenue chart with no data returns empty list."""
        token = _seller_token("seller-chart-1")
        response = await client.get(
            "/api/v1/analytics/revenue-chart?start_date=2025-01-01&end_date=2025-12-31",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["data"] == []
