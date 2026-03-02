"""Analytics repositories — event ingestion and aggregate queries."""

from datetime import date, datetime, timezone

from sqlalchemy import Date, cast, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import BaseRepository
from app.analytics.models import AnalyticsEvent, DailyAggregate


class AnalyticsEventRepository(BaseRepository[AnalyticsEvent]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(AnalyticsEvent, session)

    async def count_by_type(
        self, seller_id: str, event_type: str,
        start: datetime, end: datetime,
    ) -> int:
        query = (
            select(func.count())
            .select_from(AnalyticsEvent)
            .where(
                AnalyticsEvent.seller_id == seller_id,
                AnalyticsEvent.event_type == event_type,
                AnalyticsEvent.created_at >= start,
                AnalyticsEvent.created_at <= end,
                AnalyticsEvent.deleted_at.is_(None),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one()

    async def top_products(
        self, seller_id: str, event_type: str,
        start: datetime, end: datetime,
        limit: int = 10,
    ) -> list[dict]:
        """Top products by event count (views or purchases)."""
        query = (
            select(
                AnalyticsEvent.product_id,
                func.count().label("count"),
            )
            .where(
                AnalyticsEvent.seller_id == seller_id,
                AnalyticsEvent.event_type == event_type,
                AnalyticsEvent.product_id.is_not(None),
                AnalyticsEvent.created_at >= start,
                AnalyticsEvent.created_at <= end,
                AnalyticsEvent.deleted_at.is_(None),
            )
            .group_by(AnalyticsEvent.product_id)
            .order_by(func.count().desc())
            .limit(limit)
        )
        result = await self.session.execute(query)
        return [{"product_id": r.product_id, "count": r.count} for r in result.all()]

    async def referrer_breakdown(
        self, seller_id: str, start: datetime, end: datetime,
    ) -> list[dict]:
        """Count events by referrer source."""
        query = (
            select(
                AnalyticsEvent.referrer,
                func.count().label("count"),
            )
            .where(
                AnalyticsEvent.seller_id == seller_id,
                AnalyticsEvent.created_at >= start,
                AnalyticsEvent.created_at <= end,
                AnalyticsEvent.deleted_at.is_(None),
            )
            .group_by(AnalyticsEvent.referrer)
            .order_by(func.count().desc())
            .limit(20)
        )
        result = await self.session.execute(query)
        return [{"referrer": r.referrer or "direct", "count": r.count} for r in result.all()]

    async def unique_sessions(
        self, seller_id: str, start: datetime, end: datetime,
    ) -> int:
        """Count unique sessions (visitors)."""
        query = (
            select(func.count(func.distinct(AnalyticsEvent.session_id)))
            .where(
                AnalyticsEvent.seller_id == seller_id,
                AnalyticsEvent.session_id.is_not(None),
                AnalyticsEvent.created_at >= start,
                AnalyticsEvent.created_at <= end,
                AnalyticsEvent.deleted_at.is_(None),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one()


class DailyAggregateRepository(BaseRepository[DailyAggregate]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(DailyAggregate, session)

    async def get_range(
        self, seller_id: str, metric: str,
        start_date: date, end_date: date,
    ) -> list[DailyAggregate]:
        """Get aggregates for a seller/metric within a date range."""
        query = (
            self._base_query()
            .where(
                DailyAggregate.seller_id == seller_id,
                DailyAggregate.metric == metric,
                DailyAggregate.date >= start_date,
                DailyAggregate.date <= end_date,
            )
            .order_by(DailyAggregate.date.asc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def upsert(
        self, seller_id: str, agg_date: date, metric: str, value: float,
        dimensions: dict | None = None,
    ) -> DailyAggregate:
        """Insert or update a daily aggregate."""
        existing = await self.get_by(
            seller_id=seller_id, date=agg_date, metric=metric,
        )
        if existing:
            existing.value = value
            if dimensions:
                existing.dimensions = dimensions
            existing.version += 1
            await self.session.flush()
            return existing
        return await self.create(
            seller_id=seller_id, date=agg_date, metric=metric,
            value=value, dimensions=dimensions,
        )
