"""Notification routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.base_schemas import PaginatedResponse
from app.core.pagination import paginate
from app.database import get_db
from app.notifications.schemas import NotificationResponse, PreferenceResponse, PreferenceUpdate
from app.notifications.service import NotificationService
from app.users.models import User

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=PaginatedResponse[NotificationResponse])
async def list_notifications(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """List notifications for the current user."""
    svc = NotificationService(db)
    items, total = await svc.list_notifications(current_user.id, offset=offset, limit=limit)
    return paginate(items, total, offset, limit)


@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_read(
    notification_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a notification as read."""
    svc = NotificationService(db)
    return await svc.mark_read(notification_id)


@router.get("/preferences", response_model=PreferenceResponse)
async def get_preferences(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get notification preferences."""
    svc = NotificationService(db)
    return await svc.get_preferences(current_user.id)


@router.put("/preferences", response_model=PreferenceResponse)
async def update_preferences(
    data: PreferenceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update notification preferences."""
    svc = NotificationService(db)
    return await svc.update_preferences(current_user.id, data)
