"""Celery tasks for trust score recalculation."""

from app.tasks import celery_app


@celery_app.task(name="app.tasks.trust_tasks.recalculate_trust_scores", queue="analytics")
def recalculate_trust_scores():
    """Recalculate trust scores for all active sellers.

    Runs daily via Celery beat.
    """
    import asyncio

    from sqlalchemy import select
    from app.database import async_session_factory
    from app.sellers.models import SellerProfile
    from app.trust.service import TrustService

    async def _run():
        async with async_session_factory() as session:
            query = (
                select(SellerProfile.user_id)
                .where(SellerProfile.deleted_at.is_(None))
            )
            result = await session.execute(query)
            seller_user_ids = [r[0] for r in result.all()]

            svc = TrustService(session)
            for user_id in seller_user_ids:
                try:
                    await svc.calculate_trust_score(user_id)
                except Exception:
                    continue  # Skip individual failures

            await session.commit()

    asyncio.get_event_loop().run_until_complete(_run())
