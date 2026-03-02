"""CRM request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class CustomerSummary(BaseModel):
    buyer_email: str
    purchase_count: int
    total_spent: float
    last_order_at: datetime | None = None


class CustomerListResponse(BaseModel):
    customers: list[CustomerSummary]
    total: int


class CustomerProfile(BaseModel):
    buyer_email: str
    purchase_count: int
    total_spent: float
    average_order_value: float
    first_order_at: datetime | None = None
    last_order_at: datetime | None = None
    orders: list[dict] = []


class BroadcastRequest(BaseModel):
    segment: str = Field(..., pattern="^(all|new|repeat|high_value|inactive)$")
    channel: str = Field(..., pattern="^(email|sms)$")
    subject: str = Field(..., max_length=200)
    message: str = Field(..., max_length=5000)


class BroadcastResponse(BaseModel):
    message: str
    recipient_count: int


class SegmentResponse(BaseModel):
    name: str
    description: str
    count: int


class SegmentListResponse(BaseModel):
    segments: list[SegmentResponse]
