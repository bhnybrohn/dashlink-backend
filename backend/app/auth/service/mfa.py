"""MFA mixin — TOTP-based multi-factor authentication."""

from __future__ import annotations

import pyotp
from app.core.exceptions import BadRequestError


class MFAMixin:
    async def setup_mfa(self, user_id: str) -> dict:
        """Generate TOTP secret and provisioning URI for MFA setup."""
        user = await self.user_repo.get_or_404(user_id)
        secret = pyotp.random_base32()
        provisioning_uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=user.email, issuer_name="DashLink"
        )
        # Store secret temporarily (not activated until verified)
        await self.user_repo.update(user_id, mfa_secret=secret)
        return {"secret": secret, "provisioning_uri": provisioning_uri}

    async def verify_mfa(self, user_id: str, code: str) -> bool:
        """Verify TOTP code and activate MFA."""
        user = await self.user_repo.get_or_404(user_id)
        if not user.mfa_secret:
            raise BadRequestError(detail="MFA not set up. Call /mfa/setup first.")

        if not self._verify_totp(user.mfa_secret, code):
            raise BadRequestError(detail="Invalid MFA code")

        await self.user_repo.update(user_id, mfa_enabled=True)
        return True

    async def disable_mfa(self, user_id: str, code: str) -> None:
        """Disable MFA — requires valid TOTP code."""
        user = await self.user_repo.get_or_404(user_id)
        if not user.mfa_enabled or not user.mfa_secret:
            raise BadRequestError(detail="MFA is not enabled")

        if not self._verify_totp(user.mfa_secret, code):
            raise BadRequestError(detail="Invalid MFA code")

        await self.user_repo.update(user_id, mfa_enabled=False, mfa_secret=None)

    @staticmethod
    def _verify_totp(secret: str, code: str) -> bool:
        """Verify a TOTP code with a 30-second window."""
        totp = pyotp.TOTP(secret)
        return totp.verify(code, valid_window=1)
