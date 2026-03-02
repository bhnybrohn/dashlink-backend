"""Auth service — composed from domain-specific mixins."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.repository import LoginAttemptRepository, OAuthAccountRepository, RefreshTokenRepository
from app.auth.service.email_verification import EmailVerificationMixin
from app.auth.service.login import LoginMixin
from app.auth.service.mfa import MFAMixin
from app.auth.service.oauth import OAuthMixin
from app.auth.service.registration import RegistrationMixin
from app.auth.service.tokens import TokenMixin
from app.sellers.repository import SellerProfileRepository
from app.users.repository import UserRepository


class AuthService(
    RegistrationMixin,
    LoginMixin,
    TokenMixin,
    MFAMixin,
    OAuthMixin,
    EmailVerificationMixin,
):
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)
        self.token_repo = RefreshTokenRepository(session)
        self.attempt_repo = LoginAttemptRepository(session)
        self.seller_repo = SellerProfileRepository(session)
        self.oauth_repo = OAuthAccountRepository(session)
