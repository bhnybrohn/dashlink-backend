"""Notification service — multi-channel dispatch."""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.notifications.models import Notification
from app.notifications.repository import (
    NotificationPreferenceRepository,
    NotificationRepository,
)
from app.notifications.schemas import PreferenceUpdate


class NotificationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.notif_repo = NotificationRepository(session)
        self.pref_repo = NotificationPreferenceRepository(session)

    async def send(
        self,
        *,
        user_id: str,
        type: str,
        channel: str,
        title: str,
        body: str | None = None,
        payload: dict | None = None,
        recipient: str | None = None,
        template: str | None = None,
        context: dict | None = None,
    ) -> Notification:
        """Record a notification and dispatch it via the appropriate channel."""
        notif = await self.notif_repo.create(
            user_id=user_id,
            type=type,
            channel=channel,
            title=title,
            body=body,
            payload=payload,
        )

        # Dispatch via channel (best-effort)
        if recipient and template:
            try:
                channel_impl = self._get_channel(channel)
                await channel_impl.send(
                    recipient=recipient,
                    subject=title,
                    template=template,
                    context=context or {},
                )
                notif = await self.notif_repo.update(
                    notif.id, sent_at=datetime.now(timezone.utc),
                )
            except Exception:
                notif = await self.notif_repo.update(
                    notif.id,
                    failed_at=datetime.now(timezone.utc),
                    retry_count=notif.retry_count + 1,
                )

        return notif

    async def list_notifications(
        self, user_id: str, *, offset: int = 0, limit: int = 20,
    ) -> tuple[list[Notification], int]:
        return await self.notif_repo.list_by_user(user_id, offset=offset, limit=limit)

    async def mark_read(self, notification_id: str) -> Notification:
        return await self.notif_repo.mark_read(notification_id)

    async def get_preferences(self, user_id: str):
        return await self.pref_repo.get_or_create(user_id)

    async def update_preferences(self, user_id: str, data: PreferenceUpdate):
        pref = await self.pref_repo.get_or_create(user_id)
        update_data = data.model_dump(exclude_unset=True)
        if update_data:
            pref = await self.pref_repo.update(pref.id, **update_data)
        return pref

    @staticmethod
    def _get_channel(channel: str):
        if channel == "email":
            from app.notifications.channels.email import EmailChannel
            return EmailChannel()
        elif channel == "push":
            from app.notifications.channels.push import PushChannel
            return PushChannel()
        elif channel == "whatsapp":
            from app.notifications.channels.whatsapp import WhatsAppChannel
            return WhatsAppChannel()
        raise ValueError(f"Unsupported channel: {channel}")
