"""Email verification mixin — OTP-based email verification."""

from __future__ import annotations

import logging
import secrets

from redis.asyncio import Redis
from app.core.exceptions import BadRequestError

logger = logging.getLogger(__name__)


class EmailVerificationMixin:
    async def send_verification_email(self, user_id: str, email: str, redis: Redis) -> None:  # type: ignore[type-arg]
        """Generate a 6-digit OTP and send it via email."""
        code = f"{secrets.randbelow(1_000_000):06d}"
        key = f"verify:{user_id}"
        await redis.set(key, code, ex=600)  # 10-minute TTL

        from app.notifications.channels.email import EmailChannel
        channel = EmailChannel()
        try:
            await channel.send(
                recipient=email,
                subject="DashLink — Verify Your Email",
                template="email_verification",
                context={"code": code},
            )
        except Exception:
            logger.warning("Failed to send verification email to %s", email)

    async def verify_email(self, user_id: str, code: str, redis: Redis) -> None:  # type: ignore[type-arg]
        """Verify the OTP code and mark the user as verified."""
        key = f"verify:{user_id}"
        stored_code = await redis.get(key)

        if not stored_code or stored_code != code:
            raise BadRequestError(detail="Invalid or expired verification code")

        user = await self.user_repo.get_or_404(user_id)
        await self.user_repo.update(user_id, is_verified=True)
        await redis.delete(key)

        # Advance seller onboarding if applicable
        if user.role == "seller":
            from app.sellers.service import SellerService
            seller_service = SellerService(self.session)
            await seller_service.advance_onboarding(user_id)

    async def resend_verification_email(self, user_id: str, redis: Redis) -> None:  # type: ignore[type-arg]
        """Re-send verification email (with its own rate limit)."""
        user = await self.user_repo.get_or_404(user_id)
        if user.is_verified:
            raise BadRequestError(detail="Email is already verified")

        cooldown_key = f"verify_cooldown:{user_id}"
        if await redis.exists(cooldown_key):
            raise BadRequestError(detail="Please wait before requesting a new code")

        await redis.set(cooldown_key, "1", ex=60)  # 60-second cooldown
        await self.send_verification_email(user_id, user.email, redis)
