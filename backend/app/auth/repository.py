"""Auth repository — refresh token persistence and login attempt tracking."""

from datetime import datetime, timezone

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import LoginAttempt, OAuthAccount, RefreshToken
from app.core.base_repository import BaseRepository


class RefreshTokenRepository(BaseRepository[RefreshToken]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(RefreshToken, session)

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        """Find a refresh token by its hash."""
        query = (
            self._base_query()
            .where(
                RefreshToken.token_hash == token_hash,
                RefreshToken.is_revoked.is_(False),
                RefreshToken.expires_at > datetime.now(timezone.utc),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def revoke(self, token_hash: str) -> None:
        """Revoke a refresh token."""
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.token_hash == token_hash)
            .values(is_revoked=True)
        )
        await self.session.execute(stmt)
        await self.session.flush()

    async def revoke_all_for_user(self, user_id: str) -> None:
        """Revoke all refresh tokens for a user (e.g., password change)."""
        stmt = (
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.is_revoked.is_(False))
            .values(is_revoked=True)
        )
        await self.session.execute(stmt)
        await self.session.flush()


class LoginAttemptRepository(BaseRepository[LoginAttempt]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(LoginAttempt, session)

    async def record_attempt(
        self, email: str, ip_address: str, success: bool, failure_reason: str | None = None
    ) -> LoginAttempt:
        """Record a login attempt."""
        return await self.create(
            email=email,
            ip_address=ip_address,
            success=success,
            failure_reason=failure_reason,
        )


class OAuthAccountRepository(BaseRepository[OAuthAccount]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(OAuthAccount, session)

    async def get_by_provider_user_id(
        self, provider: str, provider_user_id: str,
    ) -> OAuthAccount | None:
        """Find an OAuth account by provider and provider-specific user ID."""
        query = (
            self._base_query()
            .where(
                OAuthAccount.provider == provider,
                OAuthAccount.provider_user_id == provider_user_id,
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_user_and_provider(
        self, user_id: str, provider: str,
    ) -> OAuthAccount | None:
        """Find a user's linked account for a specific provider."""
        query = (
            self._base_query()
            .where(
                OAuthAccount.user_id == user_id,
                OAuthAccount.provider == provider,
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_all_for_user(self, user_id: str) -> list[OAuthAccount]:
        """Get all linked OAuth accounts for a user."""
        query = (
            self._base_query()
            .where(OAuthAccount.user_id == user_id)
            .order_by(OAuthAccount.linked_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_for_user(self, user_id: str) -> int:
        """Count how many OAuth providers are linked to a user."""
        query = (
            select(func.count())
            .select_from(OAuthAccount)
            .where(
                OAuthAccount.user_id == user_id,
                OAuthAccount.deleted_at.is_(None),
            )
        )
        result = await self.session.execute(query)
        return result.scalar_one()
