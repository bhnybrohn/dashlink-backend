"""Registration mixin — user signup and seller profile creation."""

from __future__ import annotations

import json
import logging
import secrets
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from redis.asyncio import Redis

from app.core.exceptions import BadRequestError, ConflictError, UnauthorizedError
from app.core.security import hash_password
from app.core.slug import generate_store_slug

if TYPE_CHECKING:
    from app.users.models import User

logger = logging.getLogger(__name__)


class RegistrationMixin:
    async def register(
        self,
        *,
        email: str,
        password: str,
        role: str = "seller",
        phone: str | None = None,
        redis: Redis | None = None,  # type: ignore[type-arg]
    ) -> dict:
        """Register a new user. Creates seller profile if role is 'seller'."""

        # Check for existing account
        existing = await self.user_repo.get_by_email(email)
        if existing and not existing.is_shadow:
            raise ConflictError(detail="Registration failed, account with this email already exists")

        # If shadow account exists, convert it
        if existing and existing.is_shadow:
            user = await self.user_repo.update(
                existing.id,
                hashed_password=hash_password(password),
                role=role,
                phone=phone,
                is_shadow=False,
            )
        else:
            user = await self.user_repo.create(
                email=email.lower().strip(),
                hashed_password=hash_password(password),
                role=role,
                phone=phone,
            )

        # Create seller profile with placeholder name (updated during onboarding)
        if role == "seller":
            await self._ensure_seller_profile(user)

        # Send verification email
        if redis:
            await self.send_verification_email(user.id, user.email, redis)

        # Send welcome email (background task)
        self._send_welcome_email(user)

        # Generate tokens
        tokens = await self._create_token_pair(user)
        return tokens

    @staticmethod
    def _send_welcome_email(user: User) -> None:
        """Queue the welcome email as a background Celery task."""
        from app.tasks.notification_tasks import send_notification_task

        seller_name = user.first_name if user.first_name else user.email.split("@")[0]

        send_notification_task.delay(
            user_id=user.id,
            notification_type="welcome",
            channel="email",
            title="Welcome to DashLink — Your socials are your store",
            recipient=user.email,
            template="welcome_signup",
            context={
                "seller_name": seller_name,
                "dashboard_url": "https://dashlink.to/dashboard",
                "twitter_url": "https://twitter.com/dashlink",
                "instagram_url": "https://instagram.com/dashlink",
                "help_url": "https://help.dashlink.to",
                "unsubscribe_url": "https://dashlink.to/unsubscribe",
            },
        )

    async def passwordless_register(
        self,
        *,
        email: str,
        role: str = "seller",
        phone: str | None = None,
        redis: Redis,  # type: ignore[type-arg]
    ) -> dict:
        """Passwordless signup — create account and send a code to the email."""
        clean_email = email.lower().strip()

        existing = await self.user_repo.get_by_email(clean_email)
        if existing and not existing.is_shadow:
            raise ConflictError(
                detail="Registration failed, account with this email already exists",
            )

        if existing and existing.is_shadow:
            user = await self.user_repo.update(
                existing.id,
                hashed_password=None,
                role=role,
                phone=phone,
                is_shadow=False,
            )
        else:
            user = await self.user_repo.create(
                email=clean_email,
                hashed_password=None,
                role=role,
                phone=phone,
            )

        if role == "seller":
            await self._ensure_seller_profile(user)

        # Generate OTP and store in Redis
        code = f"{secrets.randbelow(1_000_000):06d}"
        await redis.set(f"signup:{user.id}", code, ex=600)

        # Send code via email
        from app.notifications.channels.email import EmailChannel

        channel = EmailChannel()
        try:
            await channel.send(
                recipient=user.email,
                subject="DashLink — Your Signup Code",
                template="email_verification",
                context={"code": code},
            )
        except Exception:
            logger.warning("Failed to send signup code to %s", user.email)

        from app.config import settings

        response: dict = {"message": "Verification code sent", "expires_in": 600}
        if not settings.is_production:
            response["code"] = code
        return response

    async def passwordless_verify_signup(
        self,
        *,
        email: str,
        code: str,
        redis: Redis,  # type: ignore[type-arg]
    ) -> dict:
        """Verify the passwordless signup code and return tokens."""
        user = await self.user_repo.get_by_email(email.lower().strip())
        if not user:
            raise BadRequestError(detail="Invalid email or code")

        key = f"signup:{user.id}"
        stored_code = await redis.get(key)
        if not stored_code or stored_code != code:
            raise BadRequestError(detail="Invalid or expired code")

        await redis.delete(key)
        await self.user_repo.update(user.id, is_verified=True)

        # Advance seller onboarding if applicable
        if user.role == "seller":
            from app.sellers.service import SellerService

            seller_service = SellerService(self.session)
            await seller_service.advance_onboarding(user.id)

        self._send_welcome_email(user)

        return await self._create_token_pair(user)

    async def passwordless_start(
        self,
        *,
        email: str,
        role: str = "seller",
        phone: str | None = None,
        redis: Redis,  # type: ignore[type-arg]
    ) -> dict:
        """Unified passwordless flow — registers new users or sends login code to existing ones."""
        clean_email = email.lower().strip()
        existing = await self.user_repo.get_by_email(clean_email)

        is_new_user = False

        if existing and not existing.is_shadow:
            # Existing user — login flow
            if not existing.is_active:
                raise UnauthorizedError(detail="Account is inactive")
            user = existing
        else:
            # New user (or shadow) — register flow
            is_new_user = True
            if existing and existing.is_shadow:
                user = await self.user_repo.update(
                    existing.id,
                    hashed_password=None,
                    role=role,
                    phone=phone,
                    is_shadow=False,
                )
            else:
                user = await self.user_repo.create(
                    email=clean_email,
                    hashed_password=None,
                    role=role,
                    phone=phone,
                )
            if role == "seller":
                await self._ensure_seller_profile(user)

        # Generate OTP and store with metadata in Redis
        code = f"{secrets.randbelow(1_000_000):06d}"
        payload = json.dumps({"code": code, "type": "register" if is_new_user else "login"})
        await redis.set(f"passwordless:{clean_email}", payload, ex=600)

        # Send code via email
        from app.notifications.channels.email import EmailChannel

        subject = "DashLink — Your Signup Code" if is_new_user else "DashLink — Your Login Code"
        channel = EmailChannel()
        try:
            await channel.send(
                recipient=user.email,
                subject=subject,
                template="email_verification",
                context={"code": code},
            )
        except Exception:
            logger.warning("Failed to send passwordless code to %s", user.email)

        from app.config import settings

        response: dict = {
            "message": "Verification code sent",
            "expires_in": 600,
            "is_new_user": is_new_user,
        }
        if not settings.is_production:
            response["code"] = code
        return response

    async def passwordless_verify(
        self,
        *,
        email: str,
        code: str,
        redis: Redis,  # type: ignore[type-arg]
        ip_address: str = "unknown",
    ) -> dict:
        """Unified passwordless verify — handles both register and login verification."""
        clean_email = email.lower().strip()

        # Read stored payload
        raw = await redis.get(f"passwordless:{clean_email}")
        if not raw:
            raise BadRequestError(detail="Invalid or expired code")

        payload = json.loads(raw)
        stored_code = payload["code"]
        flow_type = payload["type"]  # "register" or "login"

        if stored_code != code:
            await self.attempt_repo.record_attempt(clean_email, ip_address, False, "invalid_code")
            raise BadRequestError(detail="Invalid or expired code")

        await redis.delete(f"passwordless:{clean_email}")

        user = await self.user_repo.get_by_email(clean_email)
        if not user:
            raise BadRequestError(detail="Invalid email or code")

        is_new_user = flow_type == "register"

        if is_new_user:
            # Mark verified + advance onboarding + welcome email
            await self.user_repo.update(user.id, is_verified=True)
            if user.role == "seller":
                from app.sellers.service import SellerService

                seller_service = SellerService(self.session)
                await seller_service.advance_onboarding(user.id)
            self._send_welcome_email(user)
        else:
            # Login bookkeeping
            await self.user_repo.update(user.id, last_login_at=datetime.now(UTC).isoformat())
            await self.attempt_repo.record_attempt(clean_email, ip_address, True)

        # Build token pair
        token_data = await self._create_token_pair(user)

        # Fetch onboarding status for sellers
        onboarding = None
        if user.role == "seller":
            from app.sellers.service import SellerService

            seller_service = SellerService(self.session)
            status = await seller_service.get_onboarding_status(user.id)
            onboarding = {
                "current_step": status["current_step"],
                "is_complete": status["is_complete"],
            }

        return {
            **token_data,
            "is_new_user": is_new_user,
            "onboarding": onboarding,
        }

    async def _ensure_seller_profile(self, user: User) -> None:
        """Create seller profile with placeholder name (set properly during onboarding)."""
        if user.role != "seller":
            return

        # Check if profile already exists
        existing = await self.seller_repo.get_by_user_id(user.id)
        if existing:
            return

        # Use email prefix as placeholder store name
        placeholder_name = user.email.split("@")[0]
        slug = generate_store_slug(placeholder_name)

        existing_seller = await self.seller_repo.get_by_slug(slug)
        if existing_seller:
            slug = f"{slug}{user.id[:4]}"

        await self.seller_repo.create(
            user_id=user.id,
            store_name=placeholder_name,
            slug=slug,
        )
