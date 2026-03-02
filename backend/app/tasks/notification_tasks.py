"""Celery tasks for async notification dispatch."""

from app.tasks import celery_app


@celery_app.task(name="app.tasks.notification_tasks.send_notification", queue="notifications")
def send_notification_task(
    user_id: str,
    notification_type: str,
    channel: str,
    title: str,
    body: str | None = None,
    recipient: str | None = None,
    template: str | None = None,
    context: dict | None = None,
    payload: dict | None = None,
):
    """Async notification dispatch via Celery.

    Usage:
        send_notification_task.delay(
            user_id="...",
            notification_type="order_confirmed",
            channel="email",
            title="Order Confirmed",
            recipient="buyer@email.com",
            template="order_confirmed",
            context={"buyer_name": "...", "order_number": "..."},
        )
    """
    import asyncio
    from app.database import async_session_factory
    from app.notifications.service import NotificationService

    async def _run():
        async with async_session_factory() as session:
            svc = NotificationService(session)
            await svc.send(
                user_id=user_id,
                type=notification_type,
                channel=channel,
                title=title,
                body=body,
                payload=payload,
                recipient=recipient,
                template=template,
                context=context,
            )
            await session.commit()

    asyncio.get_event_loop().run_until_complete(_run())
