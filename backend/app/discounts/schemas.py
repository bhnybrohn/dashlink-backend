"""Discount code request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.base_schemas import TimestampMixin


# ── Requests ──


class DiscountCodeCreate(BaseModel):
    code: str = Field(..., min_length=2, max_length=50)
    discount_type: str = Field(..., pattern="^(percentage|fixed)$")
    discount_value: float = Field(..., gt=0)
    min_order_amount: float | None = Field(None, ge=0)
    max_uses: int | None = Field(None, ge=1)
    starts_at: datetime | None = None
    expires_at: datetime | None = None


class DiscountCodeUpdate(BaseModel):
    discount_value: float | None = Field(None, gt=0)
    min_order_amount: float | None = Field(None, ge=0)
    max_uses: int | None = Field(None, ge=1)
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    is_active: bool | None = None


class ApplyDiscountRequest(BaseModel):
    code: str
    order_subtotal: float = Field(..., gt=0)
    currency: str = Field(default="NGN", max_length=3)


# ── Responses ──


class DiscountCodeResponse(TimestampMixin):
    model_config = ConfigDict(from_attributes=True)

    id: str
    seller_id: str
    code: str
    discount_type: str
    discount_value: float
    min_order_amount: float | None = None
    max_uses: int | None = None
    used_count: int
    starts_at: datetime | None = None
    expires_at: datetime | None = None
    is_active: bool


class DiscountCodeListResponse(BaseModel):
    codes: list[DiscountCodeResponse]
    total: int


class DiscountPreviewResponse(BaseModel):
    code: str
    discount_type: str
    discount_value: float
    amount_saved: float
    new_total: float
