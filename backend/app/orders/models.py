"""Order and OrderItem models — owned by the orders module."""

from sqlalchemy import (
    CheckConstraint,
    DateTime,
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


class Order(BaseModel):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_buyer", "buyer_id", "created_at"),
        Index("ix_orders_seller_status", "seller_id", "status"),
    )

    order_number: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=False, index=True,
    )
    buyer_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    seller_id: Mapped[str] = mapped_column(ForeignKey("seller_profiles.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        Enum(
            "pending", "paid", "packed", "shipped", "delivered",
            "cancelled", "refunded",
            name="order_status_enum",
            create_constraint=True,
        ),
        default="pending",
        nullable=False,
    )
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    platform_fee: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    shipping_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    buyer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    buyer_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    tracking_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    delivery_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payout_eligible_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    paid_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    shipped_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order", lazy="selectin", cascade="all, delete-orphan",
    )


class OrderItem(BaseModel):
    __tablename__ = "order_items"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_order_items_qty_positive"),
    )

    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False)
    variant_id: Mapped[str | None] = mapped_column(ForeignKey("product_variants.id"), nullable=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    variant_info: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    # Relationships
    order: Mapped["Order"] = relationship(back_populates="items")
