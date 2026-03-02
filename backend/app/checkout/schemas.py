"""Checkout request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class LockRequest(BaseModel):
    product_id: str
    variant_id: str | None = None
    quantity: int = Field(default=1, ge=1)


class LockResponse(BaseModel):
    lock_id: str
    product_id: str
    variant_id: str | None
    quantity: int
    locked_at: datetime
    expires_at: datetime
    session_id: str


class CheckoutInitiate(BaseModel):
    lock_id: str
    buyer_email: str = Field(..., max_length=255)
    buyer_phone: str | None = Field(default=None, max_length=20)
    shipping_address_id: str | None = None
    shipping_address: dict | None = None
    payment_gateway: str | None = Field(
        default=None, pattern="^(stripe|paystack|flutterwave)$"
    )
    success_url: str
    cancel_url: str


class CheckoutSessionResponse(BaseModel):
    order_id: str
    payment_session_url: str
    payment_ref: str
    expires_at: datetime
