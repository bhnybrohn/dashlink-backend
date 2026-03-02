"""Discount code models — codes and usage tracking."""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class DiscountCode(BaseModel):
    """A seller-created discount code."""

    __tablename__ = "discount_codes"
    __table_args__ = (
        UniqueConstraint("seller_id", "code", name="uq_discount_seller_code"),
    )

    seller_id: Mapped[str] = mapped_column(ForeignKey("seller_profiles.id"), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    discount_type: Mapped[str] = mapped_column(
        Enum("percentage", "fixed", name="discount_type_enum", create_constraint=True),
        nullable=False,
    )
    discount_value: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    min_order_amount: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    max_uses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    used_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class DiscountUsage(BaseModel):
    """Record of a discount code being used on an order."""

    __tablename__ = "discount_usages"

    discount_code_id: Mapped[str] = mapped_column(ForeignKey("discount_codes.id"), nullable=False, index=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    buyer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    amount_saved: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
