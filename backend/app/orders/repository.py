"""Order repository."""

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.base_repository import BaseRepository
from app.orders.models import Order, OrderItem
from app.sellers.models import SellerProfile


class OrderRepository(BaseRepository[Order]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Order, session)

    async def get_with_items(self, order_id: str) -> Order | None:
        """Get an order with items eagerly loaded."""
        query = (
            self._base_query()
            .where(Order.id == order_id)
            .options(selectinload(Order.items))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_order_number(self, order_number: str) -> Order | None:
        return await self.get_by(order_number=order_number)

    async def list_by_seller(
        self,
        seller_id: str,
        *,
        status: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Order], int]:
        filters: dict = {"seller_id": seller_id}
        if status:
            filters["status"] = status
        return await self.list(offset=offset, limit=limit, filters=filters)

    async def list_by_buyer(
        self,
        buyer_id: str,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Order], int]:
        return await self.list(offset=offset, limit=limit, filters={"buyer_id": buyer_id})

    async def order_number_exists(self, order_number: str) -> bool:
        query = select(Order.id).where(Order.order_number == order_number)
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None

    async def list_active_by_buyer(self, buyer_id: str) -> list[Order]:
        """Get buyer's active (non-terminal) orders."""
        active_statuses = ("pending", "paid", "packed", "shipped")
        query = (
            self._base_query()
            .where(Order.buyer_id == buyer_id, Order.status.in_(active_statuses))
            .options(selectinload(Order.items))
            .order_by(Order.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def buyer_total_spent(self, buyer_id: str) -> float:
        """Sum total_amount for all paid+ orders by a buyer."""
        paid_statuses = ("paid", "packed", "shipped", "delivered")
        query = (
            select(func.coalesce(func.sum(Order.total_amount), 0))
            .where(
                Order.buyer_id == buyer_id,
                Order.status.in_(paid_statuses),
                Order.deleted_at.is_(None),
            )
        )
        result = await self.session.execute(query)
        return float(result.scalar_one())

    async def buyer_top_sellers(self, buyer_id: str, limit: int = 5) -> list[dict]:
        """Get sellers the buyer purchases from most, with spend totals."""
        paid_statuses = ("paid", "packed", "shipped", "delivered")
        query = (
            select(
                Order.seller_id,
                SellerProfile.store_name,
                SellerProfile.slug,
                SellerProfile.logo_url,
                func.count(Order.id).label("order_count"),
                func.sum(Order.total_amount).label("total_spent"),
            )
            .join(SellerProfile, SellerProfile.id == Order.seller_id)
            .where(
                Order.buyer_id == buyer_id,
                Order.status.in_(paid_statuses),
                Order.deleted_at.is_(None),
            )
            .group_by(
                Order.seller_id,
                SellerProfile.store_name,
                SellerProfile.slug,
                SellerProfile.logo_url,
            )
            .order_by(func.count(Order.id).desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return [
            {
                "seller_id": row.seller_id,
                "store_name": row.store_name,
                "slug": row.slug,
                "logo_url": row.logo_url,
                "order_count": row.order_count,
                "total_spent": float(row.total_spent),
            }
            for row in result.all()
        ]


class OrderItemRepository(BaseRepository[OrderItem]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(OrderItem, session)
