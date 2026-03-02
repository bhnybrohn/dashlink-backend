"""Product, ProductImage, and ProductVariant models — owned by the products module."""

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel


class Product(BaseModel):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("stock_count >= 0", name="ck_products_stock_non_negative"),
        CheckConstraint("price > 0", name="ck_products_price_positive"),
        Index("ix_products_seller_status", "seller_id", "status"),
    )

    seller_id: Mapped[str] = mapped_column(ForeignKey("seller_profiles.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    compare_at_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="NGN")
    stock_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    low_stock_threshold: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(
            "draft", "active", "paused", "sold_out", "archived",
            name="product_status_enum",
            create_constraint=True,
        ),
        default="draft",
        nullable=False,
    )
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    scheduled_at: Mapped[str | None] = mapped_column(nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)

    # Relationships
    images: Mapped[list["ProductImage"]] = relationship(
        back_populates="product", lazy="selectin", order_by="ProductImage.position",
        cascade="all, delete-orphan",
    )
    variants: Mapped[list["ProductVariant"]] = relationship(
        back_populates="product", lazy="selectin",
        cascade="all, delete-orphan",
    )


class ProductImage(BaseModel):
    __tablename__ = "product_images"

    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    alt_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_bg_removed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    product: Mapped["Product"] = relationship(back_populates="images")


class ProductVariant(BaseModel):
    __tablename__ = "product_variants"
    __table_args__ = (
        CheckConstraint("stock_count >= 0", name="ck_variants_stock_non_negative"),
    )

    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    variant_type: Mapped[str] = mapped_column(String(50), nullable=False)
    variant_value: Mapped[str] = mapped_column(String(100), nullable=False)
    stock_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    price_override: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    sku: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Relationships
    product: Mapped["Product"] = relationship(back_populates="variants")
