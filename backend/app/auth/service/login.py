"""Login mixin — email/password authentication."""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime

from redis.asyncio import Redis

from app.core.exceptions import BadRequestError, UnauthorizedError
from app.core.security import check_needs_rehash, hash_password, verify_password

logger = logging.getLogger(__name__)


class LoginMixin:
    async def login(
        self,
        *,
        email: str,
        password: str,
        mfa_code: str | None = None,
        ip_address: str = "unknown",
    ) -> dict:
        """Authenticate a user and return token pair."""
        user = await self.user_repo.get_by_email(email)

        # Always return the same error to prevent account enumeration
        if not user or not user.hashed_password:
            await self.attempt_repo.record_attempt(email, ip_address, False, "user_not_found")
            raise UnauthorizedError(detail="Invalid email or password")

        if not user.is_active:
            await self.attempt_repo.record_attempt(email, ip_address, False, "inactive")
            raise UnauthorizedError(detail="Invalid email or password")

        if not verify_password(password, user.hashed_password):
            await self.attempt_repo.record_attempt(email, ip_address, False, "wrong_password")
            raise UnauthorizedError(detail="Invalid email or password")

        # MFA check
        if user.mfa_enabled:
            if not mfa_code:
                raise BadRequestError(detail="MFA code is required")
            if not self._verify_totp(user.mfa_secret, mfa_code):  # type: ignore[arg-type]
                await self.attempt_repo.record_attempt(email, ip_address, False, "invalid_mfa")
                raise UnauthorizedError(detail="Invalid MFA code")

        # Rehash if needed (Argon2 parameter upgrade)
        if check_needs_rehash(user.hashed_password):
            await self.user_repo.update(
                user.id, hashed_password=hash_password(password)
            )

        # Update last login
        await self.user_repo.update(user.id, last_login_at=datetime.now(UTC).isoformat())
        await self.attempt_repo.record_attempt(email, ip_address, True)

        return await self._create_token_pair(user)

    async def passwordless_login_request(
        self,
        *,
        email: str,
        redis: Redis,  # type: ignore[type-arg]
    ) -> dict:
        """Send a login code to the user's email."""
        user = await self.user_repo.get_by_email(email.lower().strip())

        # Same error regardless of whether user exists (prevent enumeration)
        if not user or not user.is_active:
            raise UnauthorizedError(detail="Invalid email")

        code = f"{secrets.randbelow(1_000_000):06d}"
        await redis.set(f"login:{user.id}", code, ex=600)

        from app.notifications.channels.email import EmailChannel

        channel = EmailChannel()
        try:
            await channel.send(
                recipient=user.email,
                subject="DashLink — Your Login Code",
                template="email_verification",
                context={"code": code},
            )
        except Exception:
            logger.warning("Failed to send login code to %s", user.email)

        from app.config import settings

        response: dict = {"message": "Login code sent", "expires_in": 600}
        if not settings.is_production:
            response["code"] = code
        return response

    async def passwordless_login_verify(
        self,
        *,
        email: str,
        code: str,
        redis: Redis,  # type: ignore[type-arg]
        ip_address: str = "unknown",
    ) -> dict:
        """Verify the login code and return tokens."""
        user = await self.user_repo.get_by_email(email.lower().strip())
        if not user or not user.is_active:
            raise UnauthorizedError(detail="Invalid email or code")

        key = f"login:{user.id}"
        stored_code = await redis.get(key)
        if not stored_code or stored_code != code:
            await self.attempt_repo.record_attempt(email, ip_address, False, "invalid_code")
            raise BadRequestError(detail="Invalid or expired code")

        await redis.delete(key)
        await self.user_repo.update(user.id, last_login_at=datetime.now(UTC).isoformat())
        await self.attempt_repo.record_attempt(email, ip_address, True)

        return await self._create_token_pair(user)
