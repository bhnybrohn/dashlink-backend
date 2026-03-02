"""Social media integration tests — Instagram & TikTok connect, post, schedule."""

from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.social.models import SocialAccount, SocialPost
from app.social.publishers.instagram import InstagramAccountInfo
from app.social.publishers.tiktok import TikTokAccountInfo


def _seller_token(user_id: str = "seller-social-1") -> str:
    """Generate a seller JWT."""
    return create_access_token({
        "sub": user_id,
        "role": "seller",
        "email": "social-seller@test.com",
    })


def _buyer_token() -> str:
    return create_access_token({
        "sub": "buyer-1",
        "role": "buyer",
        "email": "buyer@test.com",
    })


def _mock_ig_info() -> InstagramAccountInfo:
    return InstagramAccountInfo(
        ig_user_id="ig-123456",
        username="teststore",
        page_id="page-789",
        page_access_token="page-token-abc",
        access_token="long-lived-token-xyz",
        token_expires_at=datetime.now(timezone.utc) + timedelta(days=60),
    )


def _mock_tiktok_info() -> TikTokAccountInfo:
    return TikTokAccountInfo(
        open_id="tt-open-123",
        display_name="TestStore",
        avatar_url="https://example.com/avatar.jpg",
        access_token="tt-access-token",
        refresh_token="tt-refresh-token",
        token_expires_at=datetime.now(timezone.utc) + timedelta(days=30),
    )


class TestConnectInstagram:
    """Tests for POST /api/v1/social/connect/instagram."""

    @patch("app.social.service.InstagramPublisher")
    async def test_connect_instagram_success(self, mock_pub_cls, client: AsyncClient):
        """Seller can connect an Instagram Business Account."""
        mock_pub = AsyncMock()
        mock_pub.exchange_code = AsyncMock(return_value=_mock_ig_info())
        mock_pub_cls.return_value = mock_pub

        token = _seller_token()
        response = await client.post(
            "/api/v1/social/connect/instagram",
            json={"code": "fb-auth-code-123"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["platform"] == "instagram"
        assert data["platform_username"] == "teststore"

    @patch("app.social.service.InstagramPublisher")
    async def test_connect_instagram_duplicate_fails(self, mock_pub_cls, client: AsyncClient):
        """Connecting Instagram twice returns 409."""
        mock_pub = AsyncMock()
        mock_pub.exchange_code = AsyncMock(return_value=_mock_ig_info())
        mock_pub_cls.return_value = mock_pub

        token = _seller_token("seller-dup-ig")
        await client.post(
            "/api/v1/social/connect/instagram",
            json={"code": "code-1"},
            headers={"Authorization": f"Bearer {token}"},
        )
        response = await client.post(
            "/api/v1/social/connect/instagram",
            json={"code": "code-2"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 409

    async def test_connect_instagram_buyer_forbidden(self, client: AsyncClient):
        """Buyers cannot connect social accounts."""
        token = _buyer_token()
        response = await client.post(
            "/api/v1/social/connect/instagram",
            json={"code": "code-buyer"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 403


class TestConnectTikTok:
    """Tests for POST /api/v1/social/connect/tiktok."""

    @patch("app.social.service.TikTokPublisher")
    async def test_connect_tiktok_success(self, mock_pub_cls, client: AsyncClient):
        """Seller can connect a TikTok account."""
        mock_pub = AsyncMock()
        mock_pub.exchange_code = AsyncMock(return_value=_mock_tiktok_info())
        mock_pub_cls.return_value = mock_pub

        token = _seller_token("seller-tt-1")
        response = await client.post(
            "/api/v1/social/connect/tiktok",
            json={"code": "tt-auth-code-456"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["platform"] == "tiktok"
        assert data["platform_username"] == "TestStore"


class TestDisconnect:
    """Tests for DELETE /api/v1/social/accounts/{platform}."""

    @patch("app.social.service.InstagramPublisher")
    async def test_disconnect_success(self, mock_pub_cls, client: AsyncClient):
        """Seller can disconnect a connected account."""
        mock_pub = AsyncMock()
        mock_pub.exchange_code = AsyncMock(return_value=_mock_ig_info())
        mock_pub_cls.return_value = mock_pub

        token = _seller_token("seller-disconnect-1")
        await client.post(
            "/api/v1/social/connect/instagram",
            json={"code": "code-disc"},
            headers={"Authorization": f"Bearer {token}"},
        )

        response = await client.delete(
            "/api/v1/social/accounts/instagram",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    async def test_disconnect_nonexistent_404(self, client: AsyncClient):
        """Disconnecting an unlinked platform returns 404."""
        token = _seller_token("seller-no-link")
        response = await client.delete(
            "/api/v1/social/accounts/tiktok",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404


class TestListAccounts:
    """Tests for GET /api/v1/social/accounts."""

    @patch("app.social.service.InstagramPublisher")
    async def test_list_accounts(self, mock_pub_cls, client: AsyncClient):
        """Returns all connected social accounts."""
        mock_pub = AsyncMock()
        mock_pub.exchange_code = AsyncMock(return_value=_mock_ig_info())
        mock_pub_cls.return_value = mock_pub

        token = _seller_token("seller-list-1")
        await client.post(
            "/api/v1/social/connect/instagram",
            json={"code": "code-list"},
            headers={"Authorization": f"Bearer {token}"},
        )

        response = await client.get(
            "/api/v1/social/accounts",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["accounts"]) == 1
        assert data["accounts"][0]["platform"] == "instagram"

    async def test_list_accounts_empty(self, client: AsyncClient):
        """Returns empty list when no accounts connected."""
        token = _seller_token("seller-empty")
        response = await client.get(
            "/api/v1/social/accounts",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert len(response.json()["accounts"]) == 0


class TestCreatePost:
    """Tests for POST /api/v1/social/post."""

    @patch("app.social.service.InstagramPublisher")
    async def test_post_immediate_success(self, mock_pub_cls, client: AsyncClient):
        """Immediate post publishes to Instagram and returns published status."""
        mock_pub = AsyncMock()
        mock_pub.exchange_code = AsyncMock(return_value=_mock_ig_info())
        mock_pub.publish_photo = AsyncMock(return_value={
            "id": "ig-post-12345",
            "permalink": "https://www.instagram.com/p/abc123/",
        })
        mock_pub_cls.return_value = mock_pub

        token = _seller_token("seller-post-1")

        # Connect first
        connect_resp = await client.post(
            "/api/v1/social/connect/instagram",
            json={"code": "code-post"},
            headers={"Authorization": f"Bearer {token}"},
        )
        account_id = connect_resp.json()["id"]

        # Post
        response = await client.post(
            "/api/v1/social/post",
            json={
                "social_account_id": account_id,
                "caption": "Check out our new product! #fashion",
                "image_url": "https://cdn.dashlink.to/products/photo.jpg",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["platform"] == "instagram"
        assert data["status"] == "published"
        assert data["platform_post_id"] == "ig-post-12345"

    @patch("app.social.service.InstagramPublisher")
    async def test_post_scheduled(self, mock_pub_cls, client: AsyncClient):
        """Scheduled post is saved with status='scheduled'."""
        mock_pub = AsyncMock()
        mock_pub.exchange_code = AsyncMock(return_value=_mock_ig_info())
        mock_pub_cls.return_value = mock_pub

        token = _seller_token("seller-sched-1")

        connect_resp = await client.post(
            "/api/v1/social/connect/instagram",
            json={"code": "code-sched"},
            headers={"Authorization": f"Bearer {token}"},
        )
        account_id = connect_resp.json()["id"]

        future = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        response = await client.post(
            "/api/v1/social/post",
            json={
                "social_account_id": account_id,
                "caption": "Coming soon!",
                "image_url": "https://cdn.dashlink.to/products/soon.jpg",
                "scheduled_at": future,
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "scheduled"
        assert data["scheduled_at"] is not None

    async def test_post_wrong_account_fails(self, client: AsyncClient):
        """Posting with another seller's account ID returns 400."""
        token = _seller_token("seller-wrong-acct")
        response = await client.post(
            "/api/v1/social/post",
            json={
                "social_account_id": "nonexistent-id",
                "caption": "test",
                "image_url": "https://example.com/img.jpg",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400

    async def test_post_unauthenticated_fails(self, client: AsyncClient):
        """Posting without auth returns 401/403."""
        response = await client.post(
            "/api/v1/social/post",
            json={
                "social_account_id": "some-id",
                "caption": "test",
                "image_url": "https://example.com/img.jpg",
            },
        )
        assert response.status_code in (401, 403)


class TestListPosts:
    """Tests for GET /api/v1/social/posts."""

    @patch("app.social.service.InstagramPublisher")
    async def test_list_posts(self, mock_pub_cls, client: AsyncClient):
        """Returns paginated post history."""
        mock_pub = AsyncMock()
        mock_pub.exchange_code = AsyncMock(return_value=_mock_ig_info())
        mock_pub.publish_photo = AsyncMock(return_value={
            "id": "ig-listed-post",
            "permalink": "https://www.instagram.com/p/xyz/",
        })
        mock_pub_cls.return_value = mock_pub

        token = _seller_token("seller-listpost-1")

        connect_resp = await client.post(
            "/api/v1/social/connect/instagram",
            json={"code": "code-lp"},
            headers={"Authorization": f"Bearer {token}"},
        )
        account_id = connect_resp.json()["id"]

        await client.post(
            "/api/v1/social/post",
            json={
                "social_account_id": account_id,
                "caption": "Post for listing",
                "image_url": "https://cdn.dashlink.to/products/listed.jpg",
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        response = await client.get(
            "/api/v1/social/posts",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["total"] >= 1
        assert len(data["posts"]) >= 1

    async def test_list_posts_empty(self, client: AsyncClient):
        """Returns empty list when no posts exist."""
        token = _seller_token("seller-noposts")
        response = await client.get(
            "/api/v1/social/posts",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert data := response.json()
        assert data["total"] == 0
        assert len(data["posts"]) == 0
