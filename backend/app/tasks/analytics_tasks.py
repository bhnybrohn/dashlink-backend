"""Celery tasks for analytics aggregation."""

from app.tasks import celery_app


@celery_app.task(name="app.tasks.analytics_tasks.aggregate_daily_events", queue="analytics")
def aggregate_daily_events():
    """Aggregate yesterday's analytics events into daily aggregates.

    Runs hourly via Celery beat. Computes revenue, orders, views,
    and unique visitors per seller for yesterday's date.
    """
    import asyncio
    from datetime import date, datetime, time, timedelta, timezone

    from app.database import async_session_factory
    from app.analytics.repository import AnalyticsEventRepository, DailyAggregateRepository

    yesterday = date.today() - timedelta(days=1)
    start_dt = datetime.combine(yesterday, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(yesterday, time.max, tzinfo=timezone.utc)

    async def _run():
        from sqlalchemy import distinct, func, select
        from app.analytics.models import AnalyticsEvent
        from app.orders.models import Order

        async with async_session_factory() as session:
            event_repo = AnalyticsEventRepository(session)
            agg_repo = DailyAggregateRepository(session)

            # Get all sellers who had events yesterday
            seller_q = (
                select(distinct(AnalyticsEvent.seller_id))
                .where(
                    AnalyticsEvent.created_at >= start_dt,
                    AnalyticsEvent.created_at <= end_dt,
                    AnalyticsEvent.deleted_at.is_(None),
                )
            )
            result = await session.execute(seller_q)
            seller_ids = [r[0] for r in result.all()]

            for seller_id in seller_ids:
                # Views
                views = await event_repo.count_by_type(seller_id, "view", start_dt, end_dt)
                await agg_repo.upsert(seller_id, yesterday, "views", views)

                # Unique visitors
                unique = await event_repo.unique_sessions(seller_id, start_dt, end_dt)
                await agg_repo.upsert(seller_id, yesterday, "unique_visitors", unique)

                # Revenue and orders from orders table
                order_q = (
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
                row = (await session.execute(order_q)).one()
                await agg_repo.upsert(seller_id, yesterday, "revenue", float(row.total_revenue))
                await agg_repo.upsert(seller_id, yesterday, "orders", row.total_orders)

            await session.commit()

    asyncio.get_event_loop().run_until_complete(_run())
