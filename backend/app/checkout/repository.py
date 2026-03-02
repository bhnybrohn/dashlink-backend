"""Checkout repository — stock lock persistence."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.checkout.models import StockLock
from app.core.base_repository import BaseRepository


class StockLockRepository(BaseRepository[StockLock]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(StockLock, session)

    async def get_by_session(self, session_id: str) -> list[StockLock]:
        """Get all active locks for a checkout session."""
        query = (
            self._base_query()
            .where(StockLock.session_id == session_id)
            .order_by(StockLock.locked_at.asc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
