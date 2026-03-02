"""Celery tasks for CRM broadcast messaging."""

from app.tasks import celery_app


@celery_app.task(name="app.tasks.crm_tasks.send_broadcast", queue="notifications")
def send_broadcast_task(
    seller_id: str,
    emails: list[str],
    channel: str,
    subject: str,
    message: str,
):
    """Send broadcast messages to a list of customer emails.

    Each recipient gets an individual notification task for isolation.
    """
    from app.tasks.notification_tasks import send_notification_task

    for email in emails:
        send_notification_task.delay(
            user_id=seller_id,
            notification_type="crm_broadcast",
            channel=channel,
            title=subject,
            body=message,
            recipient=email,
        )
