"""Notification repository."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import BaseRepository
from app.notifications.models import Notification, NotificationPreference


class NotificationRepository(BaseRepository[Notification]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Notification, session)

    async def list_by_user(
        self, user_id: str, *, offset: int = 0, limit: int = 20,
    ) -> tuple[list[Notification], int]:
        return await self.list(
            offset=offset, limit=limit, filters={"user_id": user_id},
        )

    async def mark_read(self, notification_id: str) -> Notification:
        return await self.update(notification_id, is_read=True)


class NotificationPreferenceRepository(BaseRepository[NotificationPreference]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(NotificationPreference, session)

    async def get_by_user(self, user_id: str) -> NotificationPreference | None:
        return await self.get_by(user_id=user_id)

    async def get_or_create(self, user_id: str) -> NotificationPreference:
        pref = await self.get_by_user(user_id)
        if not pref:
            pref = await self.create(user_id=user_id)
        return pref
