"""Notification module tests — list, read, preferences."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.notifications.models import Notification
from app.users.models import User


async def _create_user_with_notifications(
    db_session: AsyncSession,
) -> tuple[User, str, list[Notification]]:
    """Create a user with some notifications."""
    user = User(
        email="notif@test.com",
        hashed_password=hash_password("pass12345678"),
        role="buyer",
        is_active=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    notifications = []
    for i in range(3):
        n = Notification(
            user_id=user.id,
            type="order_update",
            channel="email",
            title=f"Order Update {i+1}",
            body=f"Your order has been updated ({i+1})",
        )
        db_session.add(n)
        notifications.append(n)

    await db_session.flush()
    for n in notifications:
        await db_session.refresh(n)
    await db_session.commit()

    token = create_access_token({"sub": user.id, "role": "buyer", "email": user.email})
    return user, token, notifications


class TestNotifications:
    async def test_list_notifications(self, client: AsyncClient, db_session: AsyncSession):
        _, token, _ = await _create_user_with_notifications(db_session)
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.get("/api/v1/notifications", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 3

    async def test_mark_read(self, client: AsyncClient, db_session: AsyncSession):
        _, token, notifications = await _create_user_with_notifications(db_session)
        headers = {"Authorization": f"Bearer {token}"}

        notif_id = notifications[0].id
        response = await client.patch(
            f"/api/v1/notifications/{notif_id}/read",
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["is_read"] is True


class TestNotificationPreferences:
    async def test_get_default_preferences(self, client: AsyncClient, db_session: AsyncSession):
        user = User(
            email="prefs@test.com",
            hashed_password=hash_password("pass12345678"),
            role="buyer",
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)
        await db_session.commit()

        token = create_access_token({"sub": user.id, "role": "buyer", "email": user.email})
        headers = {"Authorization": f"Bearer {token}"}

        response = await client.get("/api/v1/notifications/preferences", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["order_updates_email"] is True
        assert data["marketing_push"] is False

    async def test_update_preferences(self, client: AsyncClient, db_session: AsyncSession):
        user = User(
            email="update_prefs@test.com",
            hashed_password=hash_password("pass12345678"),
            role="buyer",
            is_active=True,
        )
        db_session.add(user)
        await db_session.flush()
        await db_session.refresh(user)
        await db_session.commit()

        token = create_access_token({"sub": user.id, "role": "buyer", "email": user.email})
        headers = {"Authorization": f"Bearer {token}"}

        # First get to create defaults
        await client.get("/api/v1/notifications/preferences", headers=headers)

        # Update
        response = await client.put(
            "/api/v1/notifications/preferences",
            json={"marketing_push": True, "order_updates_sms": True},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["marketing_push"] is True
        assert response.json()["order_updates_sms"] is True
