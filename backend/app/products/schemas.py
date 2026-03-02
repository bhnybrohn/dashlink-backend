"""Product request/response schemas."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.core.base_schemas import TimestampMixin


# ── Variant Schemas ──


class VariantCreate(BaseModel):
    variant_type: str = Field(..., max_length=50, examples=["size"])
    variant_value: str = Field(..., max_length=100, examples=["XL"])
    stock_count: int = Field(default=0, ge=0)
    price_override: Decimal | None = Field(default=None, ge=0)
    sku: str | None = Field(default=None, max_length=100)


class VariantUpdate(BaseModel):
    variant_type: str | None = Field(default=None, max_length=50)
    variant_value: str | None = Field(default=None, max_length=100)
    stock_count: int | None = Field(default=None, ge=0)
    price_override: Decimal | None = None
    sku: str | None = Field(default=None, max_length=100)


class VariantResponse(TimestampMixin):
    model_config = ConfigDict(from_attributes=True)

    id: str
    product_id: str
    variant_type: str
    variant_value: str
    stock_count: int
    price_override: Decimal | None
    sku: str | None


# ── Image Schemas ──


class ImageResponse(TimestampMixin):
    model_config = ConfigDict(from_attributes=True)

    id: str
    product_id: str
    url: str
    alt_text: str | None
    position: int
    is_bg_removed: bool
    is_ai_generated: bool


class ImageReorder(BaseModel):
    image_id: str
    position: int = Field(ge=0)


# ── Product Schemas ──


class ProductCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    price: Decimal = Field(..., gt=0, max_digits=12, decimal_places=2)
    compare_at_price: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="NGN", max_length=3)
    stock_count: int = Field(default=0, ge=0)
    low_stock_threshold: int = Field(default=3, ge=0)
    category: str | None = Field(default=None, max_length=100)
    is_pinned: bool = False
    scheduled_at: datetime | None = None
    variants: list[VariantCreate] | None = None


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    price: Decimal | None = Field(default=None, gt=0)
    compare_at_price: Decimal | None = None
    currency: str | None = Field(default=None, max_length=3)
    stock_count: int | None = Field(default=None, ge=0)
    low_stock_threshold: int | None = Field(default=None, ge=0)
    category: str | None = None
    is_pinned: bool | None = None
    scheduled_at: datetime | None = None


class ProductStatusUpdate(BaseModel):
    status: str = Field(..., pattern="^(draft|active|paused|sold_out|archived)$")


class StockUpdate(BaseModel):
    stock_count: int = Field(..., ge=0)


class ProductResponse(TimestampMixin):
    model_config = ConfigDict(from_attributes=True)

    id: str
    seller_id: str
    name: str
    slug: str
    description: str | None
    price: Decimal
    compare_at_price: Decimal | None
    currency: str
    stock_count: int
    low_stock_threshold: int
    status: str
    category: str | None
    is_pinned: bool
    images: list[ImageResponse] = []
    variants: list[VariantResponse] = []


class ProductListResponse(TimestampMixin):
    """Lighter response for list views (no variants)."""
    model_config = ConfigDict(from_attributes=True)

    id: str
    seller_id: str
    name: str
    slug: str
    price: Decimal
    compare_at_price: Decimal | None
    currency: str
    stock_count: int
    status: str
    category: str | None
    is_pinned: bool
    images: list[ImageResponse] = []
