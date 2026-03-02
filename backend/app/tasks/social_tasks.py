"""Celery tasks for social media post publishing."""

from app.tasks import celery_app


@celery_app.task(name="app.tasks.social_tasks.publish_social_post", queue="media")
def publish_social_post(post_id: str):
    """Publish a single social media post via the platform API."""
    import asyncio
    from app.database import async_session_factory
    from app.social.service import SocialService

    async def _run():
        async with async_session_factory() as session:
            svc = SocialService(session)
            await svc.publish_post(post_id)

    asyncio.get_event_loop().run_until_complete(_run())


@celery_app.task(name="app.tasks.social_tasks.process_scheduled_posts", queue="media")
def process_scheduled_posts():
    """Check for scheduled posts that are due and dispatch them for publishing."""
    import asyncio
    from app.database import async_session_factory
    from app.social.repository import SocialPostRepository

    async def _run():
        async with async_session_factory() as session:
            repo = SocialPostRepository(session)
            due_posts = await repo.get_due_scheduled_posts()
            for post in due_posts:
                # Dispatch each post as a separate task for isolation
                publish_social_post.delay(post.id)

    asyncio.get_event_loop().run_until_complete(_run())
