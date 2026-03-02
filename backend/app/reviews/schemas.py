"""Review request/response schemas."""

from pydantic import BaseModel, ConfigDict, Field

from app.core.base_schemas import TimestampMixin


class ReviewCreate(BaseModel):
    order_id: str
    product_id: str
    rating: int = Field(..., ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class ReviewResponse(TimestampMixin):
    model_config = ConfigDict(from_attributes=True)

    id: str
    order_id: str
    buyer_id: str
    seller_id: str
    product_id: str
    rating: int
    comment: str | None
    is_visible: bool
