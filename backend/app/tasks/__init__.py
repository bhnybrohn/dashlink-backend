"""Celery application configuration."""

from celery import Celery

from app.config import settings

celery_app = Celery(
    "dashlink",
    broker=settings.redis_url,
    backend=settings.redis_url,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,

    # Task queues
    task_default_queue="default",
    task_queues={
        "default": {},
        "notifications": {},
        "media": {},
        "ai": {},
        "analytics": {},
        "payments": {},
    },

    # Beat schedule (periodic tasks)
    beat_schedule={
        "cleanup-expired-stock-locks": {
            "task": "app.tasks.stock_tasks.cleanup_expired_locks",
            "schedule": 300.0,  # every 5 minutes
            "options": {"queue": "default"},
        },
        "process-scheduled-social-posts": {
            "task": "app.tasks.social_tasks.process_scheduled_posts",
            "schedule": 60.0,  # every 60 seconds
            "options": {"queue": "media"},
        },
        "publish-scheduled-products": {
            "task": "app.tasks.product_tasks.publish_scheduled_products",
            "schedule": 60.0,  # every 60 seconds
            "options": {"queue": "default"},
        },
        "aggregate-daily-analytics": {
            "task": "app.tasks.analytics_tasks.aggregate_daily_events",
            "schedule": 3600.0,  # every hour
            "options": {"queue": "analytics"},
        },
        "recalculate-trust-scores": {
            "task": "app.tasks.trust_tasks.recalculate_trust_scores",
            "schedule": 86400.0,  # every 24 hours
            "options": {"queue": "analytics"},
        },
    },
)

# Auto-discover tasks — all task modules live in app/tasks/
celery_app.autodiscover_tasks(["app.tasks"])
