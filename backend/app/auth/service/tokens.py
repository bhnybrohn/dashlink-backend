"""Token mixin — access/refresh token lifecycle."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from app.config import settings
from app.core.exceptions import UnauthorizedError
from app.core.security import create_access_token, create_refresh_token

if TYPE_CHECKING:
    from app.users.models import User


class TokenMixin:
    async def refresh_tokens(self, refresh_token_str: str) -> dict:
        """Rotate refresh token — old one is revoked, new pair is issued."""
        token_hash = self._hash_token(refresh_token_str)
        stored_token = await self.token_repo.get_by_hash(token_hash)

        if not stored_token:
            raise UnauthorizedError(detail="Invalid or expired refresh token")

        # Revoke old token
        await self.token_repo.revoke(token_hash)

        # Load user
        user = await self.user_repo.get_or_404(stored_token.user_id)
        if not user.is_active:
            raise UnauthorizedError(detail="Account is deactivated")

        return await self._create_token_pair(user)

    async def logout(self, refresh_token_str: str) -> None:
        """Revoke a refresh token."""
        token_hash = self._hash_token(refresh_token_str)
        await self.token_repo.revoke(token_hash)

    async def _create_token_pair(self, user: User) -> dict:
        """Create access + refresh token pair and store the refresh token."""
        token_data = {
            "sub": user.id,
            "role": user.role,
            "email": user.email,
        }

        # Include seller profile ID if available
        if user.role == "seller" and user.seller_profile:
            token_data["seller_profile_id"] = user.seller_profile.id

        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        # Store refresh token hash
        token_hash = self._hash_token(refresh_token)
        await self.token_repo.create(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(UTC) + timedelta(days=settings.jwt_refresh_token_expire_days),
        )

        return {
            "user": {
                "id": user.id,
                "email": user.email,
                "role": user.role,
                "is_verified": user.is_verified,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "avatar_url": user.avatar_url,
            },
            "tokens": {
                "access_token": access_token,
                "refresh_token": refresh_token,
                "token_type": "bearer",
                "expires_in": settings.jwt_access_token_expire_minutes * 60,
            },
        }

    @staticmethod
    def _hash_token(token: str) -> str:
        """Hash a token for storage (we never store raw tokens)."""
        return hashlib.sha256(token.encode()).hexdigest()
