"""Analytics models — event tracking and daily aggregation."""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Integer, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class AnalyticsEvent(BaseModel):
    """Raw analytics event — storefront views, clicks, purchases, searches."""

    __tablename__ = "analytics_events"
    __table_args__ = (
        Index("ix_analytics_events_seller_type", "seller_id", "event_type"),
        Index("ix_analytics_events_created", "created_at"),
    )

    event_type: Mapped[str] = mapped_column(
        Enum("view", "click", "purchase", "search",
             name="analytics_event_type_enum", create_constraint=True),
        nullable=False,
    )
    seller_id: Mapped[str] = mapped_column(ForeignKey("seller_profiles.id"), nullable=False, index=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    referrer: Mapped[str | None] = mapped_column(String(500), nullable=True)
    device_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_: Mapped[dict | None] = mapped_column("metadata", JSONB, nullable=True)


class DailyAggregate(BaseModel):
    """Pre-computed daily metric aggregate for fast dashboard queries."""

    __tablename__ = "daily_aggregates"
    __table_args__ = (
        Index("ix_daily_agg_seller_date_metric", "seller_id", "date", "metric", unique=True),
    )

    seller_id: Mapped[str] = mapped_column(ForeignKey("seller_profiles.id"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    metric: Mapped[str] = mapped_column(
        Enum("revenue", "orders", "views", "unique_visitors",
             name="aggregate_metric_enum", create_constraint=True),
        nullable=False,
    )
    value: Mapped[float] = mapped_column(Numeric(14, 2), default=0, nullable=False)
    dimensions: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
