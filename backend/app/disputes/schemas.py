"""Dispute request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.base_schemas import TimestampMixin


# ── Requests ──


class DisputeCreate(BaseModel):
    order_id: str
    reason: str = Field(..., pattern="^(not_received|damaged|wrong_item|not_as_described|other)$")
    description: str = Field(..., min_length=10, max_length=2000)


class DisputeRespond(BaseModel):
    response: str = Field(..., min_length=5, max_length=2000)


class DisputeResolve(BaseModel):
    resolution: str = Field(..., pattern="^(refund|replacement|rejected|partial_refund)$")
    admin_notes: str | None = Field(None, max_length=2000)


# ── Responses ──


class DisputeResponse(TimestampMixin):
    model_config = ConfigDict(from_attributes=True)

    id: str
    order_id: str
    initiated_by: str
    seller_id: str
    reason: str
    description: str
    status: str
    resolution: str | None = None
    seller_response: str | None = None
    admin_notes: str | None = None
    resolved_at: datetime | None = None
    resolved_by: str | None = None


class DisputeListResponse(BaseModel):
    disputes: list[DisputeResponse]
    total: int
