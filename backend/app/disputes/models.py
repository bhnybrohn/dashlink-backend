"""Dispute model — buyer/seller dispute resolution."""

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class Dispute(BaseModel):
    """A dispute opened by a buyer against an order."""

    __tablename__ = "disputes"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_dispute_order"),
    )

    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    initiated_by: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    seller_id: Mapped[str] = mapped_column(ForeignKey("seller_profiles.id"), nullable=False, index=True)
    reason: Mapped[str] = mapped_column(
        Enum("not_received", "damaged", "wrong_item", "not_as_described", "other",
             name="dispute_reason_enum", create_constraint=True),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum("open", "seller_responded", "escalated", "resolved", "closed",
             name="dispute_status_enum", create_constraint=True),
        default="open",
        nullable=False,
    )
    resolution: Mapped[str | None] = mapped_column(
        Enum("refund", "replacement", "rejected", "partial_refund",
             name="dispute_resolution_enum", create_constraint=True),
        nullable=True,
    )
    seller_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    resolved_by: Mapped[str | None] = mapped_column(String, nullable=True)
