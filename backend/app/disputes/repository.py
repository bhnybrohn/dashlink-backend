"""Dispute repository."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import BaseRepository
from app.disputes.models import Dispute


class DisputeRepository(BaseRepository[Dispute]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Dispute, session)

    async def get_by_order(self, order_id: str) -> Dispute | None:
        """Find a dispute by order ID."""
        return await self.get_by(order_id=order_id)

    async def list_by_seller(
        self, seller_id: str, *, status: str | None = None,
        offset: int = 0, limit: int = 20,
    ) -> tuple[list[Dispute], int]:
        filters: dict = {"seller_id": seller_id}
        if status:
            filters["status"] = status
        return await self.list(offset=offset, limit=limit, filters=filters)

    async def list_by_buyer(
        self, buyer_id: str, *, offset: int = 0, limit: int = 20,
    ) -> tuple[list[Dispute], int]:
        return await self.list(
            offset=offset, limit=limit, filters={"initiated_by": buyer_id},
        )
