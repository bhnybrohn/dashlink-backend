"""Storefront public response schemas."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.core.base_schemas import TimestampMixin
from app.products.schemas import ImageResponse


class PublicSellerProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    store_name: str
    slug: str
    logo_url: str | None = None
    banner_url: str | None = None
    bio: str | None = None
    category: str | None = None
    total_orders: int
    average_rating: float


class PublicProduct(TimestampMixin):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    slug: str
    description: str | None
    price: Decimal
    compare_at_price: Decimal | None
    currency: str
    stock_count: int
    status: str
    category: str | None
    is_pinned: bool
    images: list[ImageResponse] = []


class StorefrontResponse(BaseModel):
    seller: PublicSellerProfile
    products: list[PublicProduct]
    total_products: int


class FlashPageResponse(BaseModel):
    """Single-product Flash Page data."""

    product: PublicProduct
    seller: PublicSellerProfile
