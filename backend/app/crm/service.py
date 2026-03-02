"""CRM service — customer queries, segmentation, and broadcast."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.orders.models import Order


class CrmService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_customers(
        self, seller_id: str, *, offset: int = 0, limit: int = 20,
    ) -> tuple[list[dict], int]:
        """List customers for a seller with purchase stats."""
        base_filter = [
            Order.seller_id == seller_id,
            Order.status.in_(["paid", "packed", "shipped", "delivered"]),
            Order.deleted_at.is_(None),
        ]

        # Total unique customers
        count_q = (
            select(func.count(distinct(Order.buyer_email)))
            .where(*base_filter)
        )
        total = (await self.session.execute(count_q)).scalar_one()

        # Customer summaries
        query = (
            select(
                Order.buyer_email,
                func.count().label("purchase_count"),
                func.sum(Order.total_amount).label("total_spent"),
                func.max(Order.created_at).label("last_order_at"),
            )
            .where(*base_filter)
            .group_by(Order.buyer_email)
            .order_by(func.sum(Order.total_amount).desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self.session.execute(query)
        customers = [
            {
                "buyer_email": r.buyer_email,
                "purchase_count": r.purchase_count,
                "total_spent": float(r.total_spent),
                "last_order_at": r.last_order_at,
            }
            for r in result.all()
        ]
        return customers, total

    async def get_customer_profile(
        self, seller_id: str, buyer_email: str,
    ) -> dict:
        """Detailed customer profile with order history."""
        base_filter = [
            Order.seller_id == seller_id,
            Order.buyer_email == buyer_email,
            Order.status.in_(["paid", "packed", "shipped", "delivered"]),
            Order.deleted_at.is_(None),
        ]

        stats_q = (
            select(
                func.count().label("purchase_count"),
                func.coalesce(func.sum(Order.total_amount), 0).label("total_spent"),
                func.coalesce(func.avg(Order.total_amount), 0).label("avg_order"),
                func.min(Order.created_at).label("first_order_at"),
                func.max(Order.created_at).label("last_order_at"),
            )
            .where(*base_filter)
        )
        stats = (await self.session.execute(stats_q)).one()

        orders_q = (
            select(
                Order.id, Order.order_number, Order.total_amount,
                Order.currency, Order.status, Order.created_at,
            )
            .where(*base_filter)
            .order_by(Order.created_at.desc())
            .limit(50)
        )
        result = await self.session.execute(orders_q)
        orders = [
            {
                "id": r.id,
                "order_number": r.order_number,
                "total_amount": float(r.total_amount),
                "currency": r.currency,
                "status": r.status,
                "created_at": r.created_at.isoformat(),
            }
            for r in result.all()
        ]

        return {
            "buyer_email": buyer_email,
            "purchase_count": stats.purchase_count,
            "total_spent": float(stats.total_spent),
            "average_order_value": float(stats.avg_order),
            "first_order_at": stats.first_order_at,
            "last_order_at": stats.last_order_at,
            "orders": orders,
        }

    async def get_segments(self, seller_id: str) -> list[dict]:
        """Pre-defined customer segments with counts."""
        base_filter = [
            Order.seller_id == seller_id,
            Order.status.in_(["paid", "packed", "shipped", "delivered"]),
            Order.deleted_at.is_(None),
        ]
        now = datetime.now(timezone.utc)
        thirty_days_ago = now - timedelta(days=30)
        ninety_days_ago = now - timedelta(days=90)

        # All customers
        all_q = select(func.count(distinct(Order.buyer_email))).where(*base_filter)
        all_count = (await self.session.execute(all_q)).scalar_one()

        # New (first order in last 30 days)
        new_subq = (
            select(Order.buyer_email)
            .where(*base_filter)
            .group_by(Order.buyer_email)
            .having(func.min(Order.created_at) >= thirty_days_ago)
            .subquery()
        )
        new_count = (await self.session.execute(
            select(func.count()).select_from(new_subq)
        )).scalar_one()

        # Repeat (>1 order)
        repeat_subq = (
            select(Order.buyer_email)
            .where(*base_filter)
            .group_by(Order.buyer_email)
            .having(func.count() > 1)
            .subquery()
        )
        repeat_count = (await self.session.execute(
            select(func.count()).select_from(repeat_subq)
        )).scalar_one()

        # High value (top 10% by spend or >100k total)
        high_value_subq = (
            select(Order.buyer_email)
            .where(*base_filter)
            .group_by(Order.buyer_email)
            .having(func.sum(Order.total_amount) > 100000)
            .subquery()
        )
        high_value_count = (await self.session.execute(
            select(func.count()).select_from(high_value_subq)
        )).scalar_one()

        # Inactive (no order in 90 days)
        inactive_subq = (
            select(Order.buyer_email)
            .where(*base_filter)
            .group_by(Order.buyer_email)
            .having(func.max(Order.created_at) < ninety_days_ago)
            .subquery()
        )
        inactive_count = (await self.session.execute(
            select(func.count()).select_from(inactive_subq)
        )).scalar_one()

        return [
            {"name": "all", "description": "All customers", "count": all_count},
            {"name": "new", "description": "First order in last 30 days", "count": new_count},
            {"name": "repeat", "description": "More than 1 order", "count": repeat_count},
            {"name": "high_value", "description": "Total spend > 100,000", "count": high_value_count},
            {"name": "inactive", "description": "No order in 90 days", "count": inactive_count},
        ]

    async def get_segment_emails(
        self, seller_id: str, segment: str,
    ) -> list[str]:
        """Get email addresses for a customer segment."""
        base_filter = [
            Order.seller_id == seller_id,
            Order.status.in_(["paid", "packed", "shipped", "delivered"]),
            Order.deleted_at.is_(None),
        ]
        now = datetime.now(timezone.utc)

        if segment == "all":
            q = select(distinct(Order.buyer_email)).where(*base_filter)
        elif segment == "new":
            thirty_days_ago = now - timedelta(days=30)
            q = (
                select(Order.buyer_email)
                .where(*base_filter)
                .group_by(Order.buyer_email)
                .having(func.min(Order.created_at) >= thirty_days_ago)
            )
        elif segment == "repeat":
            q = (
                select(Order.buyer_email)
                .where(*base_filter)
                .group_by(Order.buyer_email)
                .having(func.count() > 1)
            )
        elif segment == "high_value":
            q = (
                select(Order.buyer_email)
                .where(*base_filter)
                .group_by(Order.buyer_email)
                .having(func.sum(Order.total_amount) > 100000)
            )
        elif segment == "inactive":
            ninety_days_ago = now - timedelta(days=90)
            q = (
                select(Order.buyer_email)
                .where(*base_filter)
                .group_by(Order.buyer_email)
                .having(func.max(Order.created_at) < ninety_days_ago)
            )
        else:
            return []

        result = await self.session.execute(q)
        return [r[0] for r in result.all()]
