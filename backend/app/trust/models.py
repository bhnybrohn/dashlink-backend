"""Trust & fraud scoring models — seller trust scores and order risk flags."""

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class TrustScore(BaseModel):
    """Calculated trust score for a seller."""

    __tablename__ = "trust_scores"
    __table_args__ = (
        UniqueConstraint("seller_id", name="uq_trust_score_seller"),
    )

    seller_id: Mapped[str] = mapped_column(ForeignKey("seller_profiles.id"), nullable=False, index=True)
    score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    level: Mapped[str] = mapped_column(
        Enum("new", "basic", "trusted", "verified", "premium",
             name="trust_level_enum", create_constraint=True),
        default="new",
        nullable=False,
    )
    factors: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    last_calculated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )


class OrderRiskFlag(BaseModel):
    """Risk assessment flag for an order."""

    __tablename__ = "order_risk_flags"

    order_id: Mapped[str] = mapped_column(ForeignKey("orders.id"), nullable=False, index=True)
    risk_score: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    flags: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    action_taken: Mapped[str] = mapped_column(
        Enum("none", "review", "hold_payout", "block",
             name="risk_action_enum", create_constraint=True),
        default="none",
        nullable=False,
    )
    reviewed_by: Mapped[str | None] = mapped_column(String, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
