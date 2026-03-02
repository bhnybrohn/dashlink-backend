"""Notification request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.core.base_schemas import TimestampMixin


class NotificationResponse(TimestampMixin):
    model_config = ConfigDict(from_attributes=True)

    id: str
    type: str
    channel: str
    title: str
    body: str | None
    payload: dict | None
    is_read: bool
    sent_at: datetime | None


class PreferenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    order_updates_email: bool
    order_updates_push: bool
    order_updates_sms: bool
    marketing_email: bool
    marketing_push: bool


class PreferenceUpdate(BaseModel):
    order_updates_email: bool | None = None
    order_updates_push: bool | None = None
    order_updates_sms: bool | None = None
    marketing_email: bool | None = None
    marketing_push: bool | None = None
