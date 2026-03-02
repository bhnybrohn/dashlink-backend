"""Review repository."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import BaseRepository
from app.reviews.models import Review


class ReviewRepository(BaseRepository[Review]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Review, session)

    async def get_by_order(self, order_id: str) -> Review | None:
        return await self.get_by(order_id=order_id)

    async def list_by_product(
        self, product_id: str, *, offset: int = 0, limit: int = 20,
    ) -> tuple[list[Review], int]:
        return await self.list(
            offset=offset, limit=limit,
            filters={"product_id": product_id, "is_visible": True},
        )

    async def list_by_seller(
        self, seller_id: str, *, offset: int = 0, limit: int = 20,
    ) -> tuple[list[Review], int]:
        return await self.list(
            offset=offset, limit=limit,
            filters={"seller_id": seller_id, "is_visible": True},
        )

    async def average_for_seller(self, seller_id: str) -> float:
        """Calculate average rating for a seller."""
        query = (
            select(func.avg(Review.rating))
            .where(Review.seller_id == seller_id)
            .where(Review.is_visible.is_(True))
            .where(Review.deleted_at.is_(None))
        )
        result = await self.session.execute(query)
        avg = result.scalar_one_or_none()
        return round(float(avg), 1) if avg else 0.0
