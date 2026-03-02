"""Trust & fraud scoring repositories."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import BaseRepository
from app.trust.models import OrderRiskFlag, TrustScore


class TrustScoreRepository(BaseRepository[TrustScore]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(TrustScore, session)

    async def get_by_seller(self, seller_id: str) -> TrustScore | None:
        return await self.get_by(seller_id=seller_id)

    async def list_by_level(
        self, level: str | None = None, offset: int = 0, limit: int = 20,
    ) -> tuple[list[TrustScore], int]:
        filters = {}
        if level:
            filters["level"] = level
        return await self.list(
            offset=offset, limit=limit,
            filters=filters if filters else None,
            order_by="score",
            descending=True,
        )


class OrderRiskFlagRepository(BaseRepository[OrderRiskFlag]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(OrderRiskFlag, session)

    async def get_by_order(self, order_id: str) -> OrderRiskFlag | None:
        return await self.get_by(order_id=order_id)

    async def list_flagged(
        self, *, offset: int = 0, limit: int = 20,
    ) -> tuple[list[OrderRiskFlag], int]:
        """List orders with non-zero risk scores, unreviewed first."""
        query = (
            self._base_query()
            .where(OrderRiskFlag.risk_score > 0)
            .order_by(
                OrderRiskFlag.reviewed_at.is_(None).desc(),
                OrderRiskFlag.risk_score.desc(),
            )
        )

        from sqlalchemy import func
        count_q = (
            select(func.count())
            .select_from(OrderRiskFlag)
            .where(
                OrderRiskFlag.risk_score > 0,
                OrderRiskFlag.deleted_at.is_(None),
            )
        )
        total = (await self.session.execute(count_q)).scalar_one()

        query = query.offset(offset).limit(limit)
        result = await self.session.execute(query)
        items = list(result.scalars().all())
        return items, total
