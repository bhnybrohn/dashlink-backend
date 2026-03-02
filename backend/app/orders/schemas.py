"""Order request/response schemas."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.core.base_schemas import TimestampMixin


class OrderItemResponse(TimestampMixin):
    model_config = ConfigDict(from_attributes=True)

    id: str
    product_id: str
    variant_id: str | None
    quantity: int
    unit_price: Decimal
    product_name: str
    variant_info: dict | None


class OrderResponse(TimestampMixin):
    model_config = ConfigDict(from_attributes=True)

    id: str
    order_number: str
    buyer_id: str | None
    seller_id: str
    status: str
    subtotal: Decimal
    platform_fee: Decimal
    total_amount: Decimal
    currency: str
    buyer_email: str
    buyer_phone: str | None
    tracking_number: str | None
    delivery_notes: str | None
    payment_ref: str | None
    paid_at: datetime | None
    shipped_at: datetime | None
    delivered_at: datetime | None
    items: list[OrderItemResponse] = []


class OrderStatusUpdate(BaseModel):
    status: str = Field(
        ...,
        pattern="^(packed|shipped|delivered|cancelled)$",
    )
    tracking_number: str | None = None
    delivery_notes: str | None = None


class BulkStatusUpdate(BaseModel):
    order_ids: list[str]
    status: str = Field(..., pattern="^(packed|shipped)$")
    tracking_number: str | None = None


class TrackingUpdate(BaseModel):
    tracking_number: str = Field(..., max_length=100)
    delivery_notes: str | None = None


# ── Buyer Dashboard ──


class TopSellerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    seller_id: str
    store_name: str
    slug: str
    logo_url: str | None
    order_count: int
    total_spent: Decimal


class BuyerDashboardResponse(BaseModel):
    active_orders: list[OrderResponse]
    active_count: int
    total_orders: int
    total_spent: Decimal
    top_sellers: list[TopSellerResponse]
