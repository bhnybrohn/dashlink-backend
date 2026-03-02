"""Social media repositories."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import BaseRepository
from app.social.models import SocialAccount, SocialPost


class SocialAccountRepository(BaseRepository[SocialAccount]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(SocialAccount, session)

    async def get_by_seller_and_platform(
        self, seller_id: str, platform: str,
    ) -> SocialAccount | None:
        """Find a connected social account for a seller + platform."""
        return await self.get_by(seller_id=seller_id, platform=platform)

    async def get_all_for_seller(self, seller_id: str) -> list[SocialAccount]:
        """List all connected social accounts for a seller."""
        query = self._base_query().where(
            SocialAccount.seller_id == seller_id,
        ).order_by(SocialAccount.connected_at.desc())
        result = await self.session.execute(query)
        return list(result.scalars().all())


class SocialPostRepository(BaseRepository[SocialPost]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(SocialPost, session)

    async def list_by_seller(
        self,
        seller_id: str,
        *,
        platform: str | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[SocialPost], int]:
        """List posts for a seller with optional filters."""
        filters: dict = {"seller_id": seller_id}
        if platform:
            filters["platform"] = platform
        if status:
            filters["status"] = status
        return await self.list(offset=offset, limit=limit, filters=filters)

    async def get_due_scheduled_posts(self) -> list[SocialPost]:
        """Find scheduled posts that are ready to publish."""
        now = datetime.now(timezone.utc)
        query = (
            self._base_query()
            .where(SocialPost.status == "scheduled")
            .where(SocialPost.scheduled_at <= now)
            .order_by(SocialPost.scheduled_at.asc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
