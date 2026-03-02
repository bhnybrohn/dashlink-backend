"""OAuth mixin — provider authentication, linking, and social profile extraction."""

from __future__ import annotations

import base64
import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from urllib.parse import urlencode

from app.auth.oauth import OAuthUserInfo, get_oauth_client
from app.config import settings
from app.core.encryption import encrypt_value
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError, UnauthorizedError

if TYPE_CHECKING:
    from app.users.models import User

logger = logging.getLogger(__name__)


class OAuthMixin:
    @staticmethod
    def _generate_pkce() -> tuple[str, str]:
        """Generate PKCE code_verifier and S256 code_challenge."""
        code_verifier = secrets.token_urlsafe(64)[:128]
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        return code_verifier, code_challenge

    @staticmethod
    def get_oauth_url(provider: str) -> dict:
        """Build the OAuth authorization URL for a given provider."""
        state = secrets.token_urlsafe(32)
        result: dict = {"provider": provider, "state": state}

        if provider == "google":
            params = {
                "client_id": settings.google_oauth_client_id,
                "redirect_uri": settings.google_oauth_redirect_uri,
                "response_type": "code",
                "scope": "email profile",
                "access_type": "offline",
                "prompt": "consent",
                "state": state,
            }
            result["url"] = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

        elif provider == "facebook":
            params = {
                "client_id": settings.facebook_oauth_client_id,
                "redirect_uri": settings.facebook_oauth_redirect_uri,
                "response_type": "code",
                "scope": "email,public_profile",
                "state": state,
            }
            result["url"] = f"https://www.facebook.com/v19.0/dialog/oauth?{urlencode(params)}"

        elif provider == "twitter":
            code_verifier, code_challenge = OAuthMixin._generate_pkce()
            params = {
                "client_id": settings.twitter_oauth_client_id,
                "redirect_uri": settings.twitter_oauth_redirect_uri,
                "response_type": "code",
                "scope": "users.read tweet.read offline.access",
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
            result["url"] = f"https://x.com/i/oauth2/authorize?{urlencode(params)}"
            result["code_verifier"] = code_verifier

        elif provider == "tiktok":
            params = {
                "client_key": settings.tiktok_client_key,
                "redirect_uri": settings.tiktok_redirect_uri,
                "response_type": "code",
                "scope": "user.info.basic",
                "state": state,
            }
            result["url"] = f"https://www.tiktok.com/v2/auth/authorize/?{urlencode(params)}"

        return result

    async def oauth_authenticate(
        self,
        *,
        provider: str,
        code: str,
        code_verifier: str | None = None,
        role: str = "buyer",
        ip_address: str = "unknown",
    ) -> dict:
        """Authenticate via OAuth provider. Creates user if needed, handles shadow conversion."""
        # Step 1: Exchange code with provider
        oauth_client = get_oauth_client(provider)
        if provider == "twitter":
            user_info: OAuthUserInfo = await oauth_client.exchange_code(code, code_verifier)
        else:
            user_info = await oauth_client.exchange_code(code)

        # Step 1b: Bot detection for Twitter
        if provider == "twitter" and user_info.raw_data:
            self._check_twitter_bot(user_info.raw_data)

        # Step 2: Check if this OAuth identity is already linked
        existing_oauth = await self.oauth_repo.get_by_provider_user_id(
            provider=user_info.provider,
            provider_user_id=user_info.provider_user_id,
        )

        if existing_oauth:
            # Known OAuth link — load user and log them in
            user = await self.user_repo.get_or_404(existing_oauth.user_id)
            if not user.is_active:
                raise UnauthorizedError(detail="Account is deactivated")

            await self._update_oauth_tokens(existing_oauth.id, user_info)
            await self._save_profile_from_oauth(user, user_info)
            await self.user_repo.update(user.id, last_login_at=datetime.now(UTC).isoformat())
            await self.attempt_repo.record_attempt(user.email, ip_address, True)
            return await self._create_token_pair(user)

        # Step 3: Check for existing user by email (email match → auto-link)
        user = None
        if user_info.email:
            user = await self.user_repo.get_by_email(user_info.email)

        if user and user.is_shadow:
            # Shadow account conversion
            user = await self.user_repo.update(
                user.id,
                role=role,
                is_shadow=False,
                is_verified=True,
            )
            await self._save_profile_from_oauth(user, user_info)
            await self._ensure_seller_profile(user)

        elif user:
            # Existing non-shadow user with matching email — auto-link
            if not user.is_active:
                raise UnauthorizedError(detail="Account is deactivated")
            if not user.is_verified:
                await self.user_repo.update(user.id, is_verified=True)

        else:
            # Step 4: Create brand new user
            if user_info.email:
                email = user_info.email.lower().strip()
                is_verified = True
            else:
                # No email from provider (e.g. Twitter) — placeholder until onboarding
                email = f"{user_info.provider}_{user_info.provider_user_id}@pending.dashlink.com"
                is_verified = False

            user = await self.user_repo.create(
                email=email,
                hashed_password=None,
                role=role,
                is_verified=is_verified,
                is_shadow=False,
            )
            await self._save_profile_from_oauth(user, user_info)
            await self._ensure_seller_profile(user)

        # Create the OAuth link record
        await self._create_oauth_link(user.id, user_info)

        await self.user_repo.update(user.id, last_login_at=datetime.now(UTC).isoformat())
        await self.attempt_repo.record_attempt(user.email, ip_address, True)
        return await self._create_token_pair(user)

    async def link_oauth_account(
        self,
        *,
        user_id: str,
        provider: str,
        code: str,
        code_verifier: str | None = None,
    ) -> dict:
        """Link an OAuth provider to an existing authenticated user."""
        oauth_client = get_oauth_client(provider)
        if provider == "twitter":
            user_info = await oauth_client.exchange_code(code, code_verifier)
        else:
            user_info = await oauth_client.exchange_code(code)

        # Check if this provider identity is already linked to another user
        existing_oauth = await self.oauth_repo.get_by_provider_user_id(
            provider=user_info.provider,
            provider_user_id=user_info.provider_user_id,
        )
        if existing_oauth and existing_oauth.user_id != user_id:
            raise ConflictError(
                detail=f"This {provider} account is already linked to a different user",
            )

        # Check if user already has this provider linked
        existing_link = await self.oauth_repo.get_by_user_and_provider(user_id, provider)
        if existing_link:
            raise ConflictError(detail=f"{provider} is already linked to your account")

        await self._create_oauth_link(user_id, user_info)

        return {
            "id": user_info.provider_user_id,
            "provider": provider,
            "provider_email": user_info.email,
            "linked_at": datetime.now(UTC).isoformat(),
        }

    async def unlink_oauth_account(
        self,
        *,
        user_id: str,
        provider: str,
    ) -> None:
        """Unlink an OAuth provider from a user."""
        user = await self.user_repo.get_or_404(user_id)

        oauth_link = await self.oauth_repo.get_by_user_and_provider(user_id, provider)
        if not oauth_link:
            raise NotFoundError(resource="oauth_account", resource_id=provider)

        # Safety check: don't orphan the account
        has_password = user.hashed_password is not None
        oauth_count = await self.oauth_repo.count_for_user(user_id)

        if not has_password and oauth_count <= 1:
            raise BadRequestError(
                detail="Cannot unlink your only login method. "
                "Set a password first or link another provider.",
            )

        await self.oauth_repo.soft_delete(oauth_link.id)

    async def get_linked_oauth_accounts(self, user_id: str) -> list[dict]:
        """Get all linked OAuth accounts for a user."""
        accounts = await self.oauth_repo.get_all_for_user(user_id)
        return [
            {
                "id": acc.id,
                "provider": acc.provider,
                "provider_email": acc.provider_email,
                "linked_at": acc.linked_at,
            }
            for acc in accounts
        ]

    @staticmethod
    def _extract_social_profile(user_info: OAuthUserInfo) -> dict:
        """Extract social profile fields from provider data."""
        raw = user_info.raw_data or {}
        profile: dict = {
            "display_name": user_info.name,
            "avatar_url": user_info.picture_url,
        }

        if user_info.provider == "twitter":
            profile["provider_username"] = raw.get("username")
            profile["profile_data"] = {
                "username": raw.get("username"),
                "created_at": raw.get("created_at"),
                "verified": raw.get("verified", False),
                "public_metrics": raw.get("public_metrics", {}),
            }
        elif user_info.provider == "google":
            profile["provider_username"] = user_info.email
            profile["profile_data"] = {
                "email": user_info.email,
                "verified_email": raw.get("verified_email", True),
            }
        elif user_info.provider == "facebook":
            profile["provider_username"] = user_info.email
            profile["profile_data"] = {
                "email": user_info.email,
            }
        elif user_info.provider == "tiktok":
            profile["provider_username"] = raw.get("username")
            profile["profile_data"] = {
                "username": raw.get("username"),
                "open_id": raw.get("open_id"),
                "follower_count": raw.get("follower_count", 0),
                "video_count": raw.get("video_count", 0),
            }

        return profile

    async def _create_oauth_link(self, user_id: str, user_info: OAuthUserInfo) -> None:
        """Create an OAuthAccount record with encrypted tokens and social profile."""
        access_encrypted = encrypt_value(user_info.access_token) if user_info.access_token else None
        refresh_encrypted = (
            encrypt_value(user_info.refresh_token) if user_info.refresh_token else None
        )

        token_expires_at = None
        if user_info.expires_in:
            token_expires_at = datetime.now(UTC) + timedelta(seconds=user_info.expires_in)

        social = self._extract_social_profile(user_info)

        await self.oauth_repo.create(
            user_id=user_id,
            provider=user_info.provider,
            provider_user_id=user_info.provider_user_id,
            provider_email=user_info.email,
            access_token_encrypted=access_encrypted,
            refresh_token_encrypted=refresh_encrypted,
            token_expires_at=token_expires_at,
            **social,
        )

    async def _update_oauth_tokens(self, oauth_account_id: str, user_info: OAuthUserInfo) -> None:
        """Update stored encrypted tokens and social profile on an existing OAuthAccount."""
        access_encrypted = encrypt_value(user_info.access_token) if user_info.access_token else None
        refresh_encrypted = (
            encrypt_value(user_info.refresh_token) if user_info.refresh_token else None
        )

        token_expires_at = None
        if user_info.expires_in:
            token_expires_at = datetime.now(UTC) + timedelta(seconds=user_info.expires_in)

        social = self._extract_social_profile(user_info)

        update_kwargs: dict = {
            "access_token_encrypted": access_encrypted,
            "token_expires_at": token_expires_at,
            **social,
        }
        if refresh_encrypted:
            update_kwargs["refresh_token_encrypted"] = refresh_encrypted

        await self.oauth_repo.update(oauth_account_id, **update_kwargs)

    @staticmethod
    def _check_twitter_bot(data: dict) -> None:
        """Reject suspicious Twitter accounts based on public metrics and profile signals."""
        metrics = data.get("public_metrics", {})
        followers = metrics.get("followers_count", 0)
        following = metrics.get("following_count", 0)
        tweet_count = metrics.get("tweet_count", 0)

        # Brand new account with zero activity
        if followers == 0 and tweet_count == 0:
            raise BadRequestError(
                detail="This Twitter account appears to be too new or inactive. "
                "Please use an established account or sign up with email.",
            )

        # Extreme follow ratio (following thousands, no followers) — spam pattern
        if following > 200 and followers < 5:
            raise BadRequestError(
                detail="This Twitter account has been flagged as suspicious. "
                "Please use a different sign-in method.",
            )

        logger.info(
            "Twitter bot check passed: followers=%s following=%s tweets=%s",
            followers, following, tweet_count,
        )

    async def _save_profile_from_oauth(self, user: User, user_info: OAuthUserInfo) -> None:
        """Save name and avatar from OAuth provider (only fills empty fields)."""
        updates: dict = {}
        if user_info.name and not user.first_name:
            parts = user_info.name.split(" ", 1)
            updates["first_name"] = parts[0]
            if len(parts) > 1:
                updates["last_name"] = parts[1]
        if user_info.picture_url and not user.avatar_url:
            updates["avatar_url"] = user_info.picture_url
        if updates:
            await self.user_repo.update(user.id, **updates)
