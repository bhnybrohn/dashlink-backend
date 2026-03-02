"""Payment and Payout models — owned by the payments module."""

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class Payment(BaseModel):
    __tablename__ = "payments"
    __table_args__ = (
        Index("ix_payments_gateway_ref", "gateway_ref", unique=True),
    )

    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), unique=True, nullable=False, index=True)
    gateway: Mapped[str] = mapped_column(
        Enum("stripe", "paystack", "flutterwave",
             name="payment_gateway_enum", create_constraint=True),
        nullable=False,
    )
    gateway_ref: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    gateway_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("pending", "success", "failed", "refunded",
             name="payment_status_enum", create_constraint=True),
        default="pending",
        nullable=False,
    )
    webhook_verified_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    webhook_payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class Payout(BaseModel):
    __tablename__ = "payouts"

    seller_id: Mapped[str] = mapped_column(ForeignKey("seller_profiles.id"), nullable=False, index=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("pending", "processing", "completed", "failed",
             name="payout_status_enum", create_constraint=True),
        default="pending",
        nullable=False,
    )
    gateway: Mapped[str] = mapped_column(String(50), nullable=False)
    gateway_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    period_start: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    period_end: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
