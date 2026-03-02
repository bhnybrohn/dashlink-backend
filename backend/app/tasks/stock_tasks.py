"""Periodic stock lock cleanup task."""

from app.tasks import celery_app


@celery_app.task(name="app.tasks.stock_tasks.cleanup_expired_locks", queue="default")
def cleanup_expired_locks():
    """Clean up expired stock locks and restore inventory."""
    import asyncio
    from app.database import async_session_factory
    from app.redis import pool
    from redis.asyncio import Redis

    async def _run():
        async with async_session_factory() as session:
            redis = Redis(connection_pool=pool)
            from app.checkout.stock_locker import StockLocker
            locker = StockLocker(session, redis)
            count = await locker.cleanup_expired()
            await session.commit()
            return count

    return asyncio.get_event_loop().run_until_complete(_run())
