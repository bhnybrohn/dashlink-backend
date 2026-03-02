"""Analytics request/response schemas."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


# ── Requests ──


class RecordEventRequest(BaseModel):
    """Record an analytics event (from storefront)."""

    event_type: str = Field(..., pattern="^(view|click|purchase|search)$")
    seller_id: str
    product_id: str | None = None
    referrer: str | None = None
    device_type: str | None = Field(None, max_length=20)
    session_id: str | None = None
    metadata: dict | None = None


class DateRangeParams(BaseModel):
    """Query params for date-filtered analytics."""

    start_date: date
    end_date: date


# ── Responses ──


class OverviewResponse(BaseModel):
    """High-level analytics overview."""

    total_revenue: float
    total_orders: int
    total_views: int
    unique_visitors: int
    start_date: date
    end_date: date


class TopProductItem(BaseModel):
    product_id: str
    count: int


class TopProductsResponse(BaseModel):
    products: list[TopProductItem]
    metric: str


class ReferrerItem(BaseModel):
    referrer: str
    count: int


class TrafficResponse(BaseModel):
    referrers: list[ReferrerItem]


class CustomerStatsResponse(BaseModel):
    total_customers: int
    repeat_customers: int
    average_order_value: float


class FunnelResponse(BaseModel):
    views: int
    purchases: int
    conversion_rate: float


class RevenueChartPoint(BaseModel):
    date: date
    revenue: float


class RevenueChartResponse(BaseModel):
    data: list[RevenueChartPoint]
