"""Celery app alias for `celery -A app.tasks.celery_app`."""

from app.tasks import celery_app

__all__ = ["celery_app"]
