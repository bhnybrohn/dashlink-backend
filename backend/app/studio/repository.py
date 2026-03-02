"""Studio generation repository."""

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import BaseRepository
from app.studio.models import StudioGeneration


class StudioGenerationRepository(BaseRepository[StudioGeneration]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(StudioGeneration, session)

    async def list_by_seller(
        self, seller_id: str, *, offset: int = 0, limit: int = 20,
    ) -> tuple[list[StudioGeneration], int]:
        return await self.list(offset=offset, limit=limit, filters={"seller_id": seller_id})

    async def count_monthly_usage(
        self, seller_id: str, generation_type: str,
    ) -> int:
        """Count generations of a given type for the current month."""
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        query = (
            select(func.count())
            .where(StudioGeneration.seller_id == seller_id)
            .where(StudioGeneration.generation_type == generation_type)
            .where(StudioGeneration.status == "completed")
            .where(StudioGeneration.created_at >= month_start)
            .where(StudioGeneration.deleted_at.is_(None))
        )
        result = await self.session.execute(query)
        return result.scalar_one()

    async def get_all_monthly_usage(self, seller_id: str) -> dict[str, int]:
        """Get usage counts for all generation types this month."""
        types = ["title", "description", "caption", "image", "background_removal"]
        usage = {}
        for t in types:
            usage[t] = await self.count_monthly_usage(seller_id, t)
        return usage
