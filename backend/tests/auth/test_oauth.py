"""OAuth social login tests — Google, Facebook/Meta, Twitter/X flows."""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.oauth import OAuthUserInfo
from app.core.security import create_access_token, hash_password
from app.users.models import User


def _make_user_info(
    provider: str = "google",
    provider_user_id: str = "google-123",
    email: str = "oauth@test.com",
) -> OAuthUserInfo:
    """Helper to build a mock OAuthUserInfo."""
    return OAuthUserInfo(
        provider=provider,
        provider_user_id=provider_user_id,
        email=email,
        name="Test User",
        picture_url="https://example.com/photo.jpg",
        access_token="mock-access-token",
        refresh_token="mock-refresh-token",
        expires_in=3600,
    )


def _mock_exchange(user_info: OAuthUserInfo):
    """Create a mock OAuth client whose exchange_code returns user_info."""
    mock_client = AsyncMock()
    mock_client.exchange_code = AsyncMock(return_value=user_info)
    return mock_client


class TestOAuthAuthenticate:
    """Tests for POST /api/v1/auth/oauth."""

    @patch("app.auth.service.get_oauth_client")
    async def test_new_user_google(self, mock_get_client, client: AsyncClient):
        """First-time Google OAuth creates a new user and returns tokens."""
        info = _make_user_info(provider="google", email="new-google@test.com")
        mock_get_client.return_value = _mock_exchange(info)

        response = await client.post(
            "/api/v1/auth/oauth",
            json={"provider": "google", "code": "auth-code-123"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"

    @patch("app.auth.service.get_oauth_client")
    async def test_existing_user_google_login(self, mock_get_client, client: AsyncClient):
        """OAuth login for user who already registered via OAuth returns tokens."""
        info = _make_user_info(provider="google", email="returning@test.com")
        mock_get_client.return_value = _mock_exchange(info)

        # First call — creates user
        await client.post(
            "/api/v1/auth/oauth",
            json={"provider": "google", "code": "code-1"},
        )

        # Second call — same provider_user_id, should login
        response = await client.post(
            "/api/v1/auth/oauth",
            json={"provider": "google", "code": "code-2"},
        )
        assert response.status_code == 200
        assert "access_token" in response.json()

    @patch("app.auth.service.get_oauth_client")
    async def test_email_match_auto_links(self, mock_get_client, client: AsyncClient):
        """OAuth login with email matching existing password user auto-links."""
        # First register with password
        await client.post(
            "/api/v1/auth/register",
            json={
                "email": "existing@test.com",
                "password": "securepassword123",
                "role": "buyer",
            },
        )

        # Then OAuth with same email
        info = _make_user_info(
            provider="google",
            provider_user_id="google-existing-456",
            email="existing@test.com",
        )
        mock_get_client.return_value = _mock_exchange(info)

        response = await client.post(
            "/api/v1/auth/oauth",
            json={"provider": "google", "code": "code-link"},
        )
        assert response.status_code == 200
        assert "access_token" in response.json()

    @patch("app.auth.service.get_oauth_client")
    async def test_shadow_account_conversion(
        self, mock_get_client, client: AsyncClient, db_session: AsyncSession,
    ):
        """OAuth login converts a shadow account to a full account."""
        # Create shadow user directly
        shadow = User(
            email="shadow@test.com",
            hashed_password=None,
            role="buyer",
            is_shadow=True,
        )
        db_session.add(shadow)
        await db_session.flush()
        await db_session.refresh(shadow)
        await db_session.commit()

        info = _make_user_info(
            provider="facebook",
            provider_user_id="fb-shadow-789",
            email="shadow@test.com",
        )
        mock_get_client.return_value = _mock_exchange(info)

        response = await client.post(
            "/api/v1/auth/oauth",
            json={"provider": "facebook", "code": "code-shadow"},
        )
        assert response.status_code == 200

    @patch("app.auth.service.get_oauth_client")
    async def test_seller_registration_via_oauth(self, mock_get_client, client: AsyncClient):
        """OAuth registration with role=seller requires store_name."""
        info = _make_user_info(provider="google", email="seller-oauth@test.com")
        mock_get_client.return_value = _mock_exchange(info)

        # Without store_name → 400
        response = await client.post(
            "/api/v1/auth/oauth",
            json={"provider": "google", "code": "code-seller", "role": "seller"},
        )
        assert response.status_code == 400

        # With store_name → success (need fresh user info with different email)
        info2 = _make_user_info(
            provider="google",
            provider_user_id="google-seller-2",
            email="seller-oauth2@test.com",
        )
        mock_get_client.return_value = _mock_exchange(info2)

        response = await client.post(
            "/api/v1/auth/oauth",
            json={
                "provider": "google",
                "code": "code-seller-2",
                "role": "seller",
                "store_name": "OAuth Store",
            },
        )
        assert response.status_code == 200

    async def test_invalid_provider_rejected(self, client: AsyncClient):
        """Unknown provider returns 422 (Pydantic validation)."""
        response = await client.post(
            "/api/v1/auth/oauth",
            json={"provider": "github", "code": "code-invalid"},
        )
        assert response.status_code == 422

    @patch("app.auth.service.get_oauth_client")
    async def test_twitter_no_email_rejected_for_new_user(
        self, mock_get_client, client: AsyncClient,
    ):
        """Twitter OAuth without email returns 400 for new users."""
        info = OAuthUserInfo(
            provider="twitter",
            provider_user_id="tw-999",
            email=None,
            name="TwitterUser",
            picture_url=None,
            access_token="tw-token",
            refresh_token=None,
            expires_in=7200,
        )
        mock_get_client.return_value = _mock_exchange(info)

        response = await client.post(
            "/api/v1/auth/oauth",
            json={
                "provider": "twitter",
                "code": "tw-code",
                "code_verifier": "a" * 43,
            },
        )
        assert response.status_code == 400


class TestOAuthLink:
    """Tests for POST /api/v1/auth/oauth/link."""

    @patch("app.auth.service.get_oauth_client")
    async def test_link_provider_success(self, mock_get_client, client: AsyncClient):
        """Authenticated user can link a new OAuth provider."""
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "linker@test.com",
                "password": "securepassword123",
                "role": "buyer",
            },
        )
        token = reg.json()["access_token"]

        info = _make_user_info(
            provider="facebook",
            provider_user_id="fb-link-123",
            email="linker@test.com",
        )
        mock_get_client.return_value = _mock_exchange(info)

        response = await client.post(
            "/api/v1/auth/oauth/link",
            json={"provider": "facebook", "code": "link-code"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["provider"] == "facebook"

    @patch("app.auth.service.get_oauth_client")
    async def test_link_duplicate_provider_fails(self, mock_get_client, client: AsyncClient):
        """Linking the same provider twice returns 409."""
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "duplink@test.com",
                "password": "securepassword123",
                "role": "buyer",
            },
        )
        token = reg.json()["access_token"]

        info = _make_user_info(
            provider="google",
            provider_user_id="goog-dup-123",
            email="duplink@test.com",
        )
        mock_get_client.return_value = _mock_exchange(info)

        # First link
        await client.post(
            "/api/v1/auth/oauth/link",
            json={"provider": "google", "code": "code-a"},
            headers={"Authorization": f"Bearer {token}"},
        )

        # Second link — same provider
        response = await client.post(
            "/api/v1/auth/oauth/link",
            json={"provider": "google", "code": "code-b"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 409

    async def test_link_unauthenticated_fails(self, client: AsyncClient):
        """Linking without auth token returns 401/403."""
        response = await client.post(
            "/api/v1/auth/oauth/link",
            json={"provider": "google", "code": "code-noauth"},
        )
        assert response.status_code in (401, 403)


class TestOAuthUnlink:
    """Tests for DELETE /api/v1/auth/oauth/{provider}."""

    @patch("app.auth.service.get_oauth_client")
    async def test_unlink_with_password_succeeds(self, mock_get_client, client: AsyncClient):
        """User with password can unlink their only OAuth provider."""
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "unlinker@test.com",
                "password": "securepassword123",
                "role": "buyer",
            },
        )
        token = reg.json()["access_token"]

        # Link Google
        info = _make_user_info(
            provider="google",
            provider_user_id="goog-unlink-1",
            email="unlinker@test.com",
        )
        mock_get_client.return_value = _mock_exchange(info)

        await client.post(
            "/api/v1/auth/oauth/link",
            json={"provider": "google", "code": "code-unlink"},
            headers={"Authorization": f"Bearer {token}"},
        )

        # Unlink Google — should succeed because user has password
        response = await client.delete(
            "/api/v1/auth/oauth/google",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200

    @patch("app.auth.service.get_oauth_client")
    async def test_unlink_only_method_fails(self, mock_get_client, client: AsyncClient):
        """OAuth-only user cannot unlink their only provider."""
        info = _make_user_info(
            provider="google",
            provider_user_id="goog-only-1",
            email="oauthonly@test.com",
        )
        mock_get_client.return_value = _mock_exchange(info)

        reg = await client.post(
            "/api/v1/auth/oauth",
            json={"provider": "google", "code": "code-only"},
        )
        token = reg.json()["access_token"]

        # Try to unlink — should fail (no password, only 1 OAuth)
        response = await client.delete(
            "/api/v1/auth/oauth/google",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 400

    async def test_unlink_nonexistent_provider_404(self, client: AsyncClient):
        """Unlinking a provider that isn't linked returns 404."""
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "no-link@test.com",
                "password": "securepassword123",
                "role": "buyer",
            },
        )
        token = reg.json()["access_token"]

        response = await client.delete(
            "/api/v1/auth/oauth/twitter",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 404


class TestOAuthListAccounts:
    """Tests for GET /api/v1/auth/oauth/accounts."""

    @patch("app.auth.service.get_oauth_client")
    async def test_list_linked_accounts(self, mock_get_client, client: AsyncClient):
        """Returns all linked OAuth providers for the current user."""
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "lister@test.com",
                "password": "securepassword123",
                "role": "buyer",
            },
        )
        token = reg.json()["access_token"]

        # Link Google
        info = _make_user_info(
            provider="google",
            provider_user_id="goog-list-1",
            email="lister@test.com",
        )
        mock_get_client.return_value = _mock_exchange(info)

        await client.post(
            "/api/v1/auth/oauth/link",
            json={"provider": "google", "code": "code-list"},
            headers={"Authorization": f"Bearer {token}"},
        )

        response = await client.get(
            "/api/v1/auth/oauth/accounts",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data["accounts"]) == 1
        assert data["accounts"][0]["provider"] == "google"

    async def test_empty_list_when_no_providers_linked(self, client: AsyncClient):
        """Returns empty list when user has no OAuth providers linked."""
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "nooauth@test.com",
                "password": "securepassword123",
                "role": "buyer",
            },
        )
        token = reg.json()["access_token"]

        response = await client.get(
            "/api/v1/auth/oauth/accounts",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert len(response.json()["accounts"]) == 0
