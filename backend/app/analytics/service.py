"""Analytics service — event recording, overview, and chart queries."""

from datetime import date, datetime, time, timezone
from decimal import Decimal

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.models import AnalyticsEvent, DailyAggregate
from app.analytics.repository import AnalyticsEventRepository, DailyAggregateRepository
from app.analytics.schemas import RecordEventRequest
from app.orders.models import Order


class AnalyticsService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.event_repo = AnalyticsEventRepository(session)
        self.agg_repo = DailyAggregateRepository(session)

    async def record_event(self, data: RecordEventRequest) -> AnalyticsEvent:
        """Record a raw analytics event."""
        return await self.event_repo.create(
            event_type=data.event_type,
            seller_id=data.seller_id,
            product_id=data.product_id,
            referrer=data.referrer,
            device_type=data.device_type,
            session_id=data.session_id,
            metadata_=data.metadata,
        )

    async def get_overview(
        self, seller_id: str, start_date: date, end_date: date,
    ) -> dict:
        """High-level overview: revenue, orders, views, unique visitors."""
        start_dt = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        end_dt = datetime.combine(end_date, time.max, tzinfo=timezone.utc)

        # Revenue + orders from orders table
        order_query = (
            select(
                func.count().label("total_orders"),
                func.coalesce(func.sum(Order.total_amount), 0).label("total_revenue"),
            )
            .where(
                Order.seller_id == seller_id,
                Order.status.in_(["paid", "packed", "shipped", "delivered"]),
                Order.created_at >= start_dt,
                Order.created_at <= end_dt,
                Order.deleted_at.is_(None),
            )
        )
        result = await self.session.execute(order_query)
        row = result.one()

        views = await self.event_repo.count_by_type(seller_id, "view", start_dt, end_dt)
        unique = await self.event_repo.unique_sessions(seller_id, start_dt, end_dt)

        return {
            "total_revenue": float(row.total_revenue),
            "total_orders": row.total_orders,
            "total_views": views,
            "unique_visitors": unique,
            "start_date": start_date,
            "end_date": end_date,
        }

    async def get_top_products(
        self, seller_id: str, start_date: date, end_date: date,
        metric: str = "views",
    ) -> dict:
        """Top products by views or purchases."""
        start_dt = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        end_dt = datetime.combine(end_date, time.max, tzinfo=timezone.utc)
        event_type = "purchase" if metric == "sales" else "view"
        products = await self.event_repo.top_products(
            seller_id, event_type, start_dt, end_dt,
        )
        return {"products": products, "metric": metric}

    async def get_traffic(
        self, seller_id: str, start_date: date, end_date: date,
    ) -> dict:
        """Referrer traffic breakdown."""
        start_dt = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        end_dt = datetime.combine(end_date, time.max, tzinfo=timezone.utc)
        referrers = await self.event_repo.referrer_breakdown(seller_id, start_dt, end_dt)
        return {"referrers": referrers}

    async def get_customer_stats(
        self, seller_id: str, start_date: date, end_date: date,
    ) -> dict:
        """Customer count, repeat rate, avg order value."""
        start_dt = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        end_dt = datetime.combine(end_date, time.max, tzinfo=timezone.utc)

        # Total unique customers
        total_q = (
            select(func.count(distinct(Order.buyer_email)))
            .where(
                Order.seller_id == seller_id,
                Order.status.in_(["paid", "packed", "shipped", "delivered"]),
                Order.created_at >= start_dt,
                Order.created_at <= end_dt,
                Order.deleted_at.is_(None),
            )
        )
        total_customers = (await self.session.execute(total_q)).scalar_one()

        # Repeat customers (>1 order)
        repeat_q = (
            select(func.count())
            .select_from(
                select(Order.buyer_email)
                .where(
                    Order.seller_id == seller_id,
                    Order.status.in_(["paid", "packed", "shipped", "delivered"]),
                    Order.created_at >= start_dt,
                    Order.created_at <= end_dt,
                    Order.deleted_at.is_(None),
                )
                .group_by(Order.buyer_email)
                .having(func.count() > 1)
                .subquery()
            )
        )
        repeat_customers = (await self.session.execute(repeat_q)).scalar_one()

        # Average order value
        avg_q = (
            select(func.coalesce(func.avg(Order.total_amount), 0))
            .where(
                Order.seller_id == seller_id,
                Order.status.in_(["paid", "packed", "shipped", "delivered"]),
                Order.created_at >= start_dt,
                Order.created_at <= end_dt,
                Order.deleted_at.is_(None),
            )
        )
        avg_order = (await self.session.execute(avg_q)).scalar_one()

        return {
            "total_customers": total_customers,
            "repeat_customers": repeat_customers,
            "average_order_value": float(avg_order),
        }

    async def get_funnel(
        self, seller_id: str, start_date: date, end_date: date,
    ) -> dict:
        """View → purchase conversion funnel."""
        start_dt = datetime.combine(start_date, time.min, tzinfo=timezone.utc)
        end_dt = datetime.combine(end_date, time.max, tzinfo=timezone.utc)

        views = await self.event_repo.count_by_type(seller_id, "view", start_dt, end_dt)
        purchases = await self.event_repo.count_by_type(seller_id, "purchase", start_dt, end_dt)
        conversion = (purchases / views * 100) if views > 0 else 0.0

        return {
            "views": views,
            "purchases": purchases,
            "conversion_rate": round(conversion, 2),
        }

    async def get_revenue_chart(
        self, seller_id: str, start_date: date, end_date: date,
    ) -> dict:
        """Time-series revenue data from daily aggregates (fallback to orders)."""
        aggregates = await self.agg_repo.get_range(
            seller_id, "revenue", start_date, end_date,
        )
        if aggregates:
            data = [
                {"date": agg.date, "revenue": float(agg.value)}
                for agg in aggregates
            ]
        else:
            # Fallback: compute from orders
            from sqlalchemy import cast, Date
            query = (
                select(
                    cast(Order.created_at, Date).label("order_date"),
                    func.coalesce(func.sum(Order.total_amount), 0).label("revenue"),
                )
                .where(
                    Order.seller_id == seller_id,
                    Order.status.in_(["paid", "packed", "shipped", "delivered"]),
                    Order.created_at >= datetime.combine(start_date, time.min, tzinfo=timezone.utc),
                    Order.created_at <= datetime.combine(end_date, time.max, tzinfo=timezone.utc),
                    Order.deleted_at.is_(None),
                )
                .group_by("order_date")
                .order_by("order_date")
            )
            result = await self.session.execute(query)
            data = [
                {"date": row.order_date, "revenue": float(row.revenue)}
                for row in result.all()
            ]
        return {"data": data}
