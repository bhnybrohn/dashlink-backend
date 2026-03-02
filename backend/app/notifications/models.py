"""Notification and NotificationPreference models."""

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class Notification(BaseModel):
    __tablename__ = "notifications"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    channel: Mapped[str] = mapped_column(
        Enum("push", "sms", "whatsapp", "email",
             name="notification_channel_enum", create_constraint=True),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(String(500), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    sent_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    failed_at: Mapped[str | None] = mapped_column(DateTime(timezone=True), nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class NotificationPreference(BaseModel):
    __tablename__ = "notification_preferences"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False, index=True)
    order_updates_email: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    order_updates_push: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    order_updates_sms: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    marketing_email: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    marketing_push: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
