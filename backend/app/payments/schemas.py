"""Payment request/response schemas."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.core.base_schemas import TimestampMixin


class PaymentResponse(TimestampMixin):
    model_config = ConfigDict(from_attributes=True)

    id: str
    order_id: str
    gateway: str
    gateway_ref: str
    amount: Decimal
    currency: str
    status: str
    webhook_verified_at: datetime | None


class PayoutResponse(TimestampMixin):
    model_config = ConfigDict(from_attributes=True)

    id: str
    seller_id: str
    amount: Decimal
    currency: str
    status: str
    gateway: str
    gateway_ref: str | None
    period_start: datetime | None
    period_end: datetime | None


class PayoutRequest(BaseModel):
    """Manual payout request from seller."""
    currency: str = "NGN"
