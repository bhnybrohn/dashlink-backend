"""Auth API routes — registration, login, token management, MFA."""

from enum import Enum

from fastapi import APIRouter, Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.auth.schemas import (
    AuthResponse,
    CodeSentResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MFASetupResponse,
    MFAVerifyRequest,
    OAuthAccountListResponse,
    OAuthAccountResponse,
    OAuthLinkRequest,
    OAuthRequest,
    PasswordlessLoginRequest,
    PasswordlessRegisterRequest,
    PasswordlessVerifyRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from app.auth.service import AuthService
from app.core.base_schemas import SuccessResponse
from app.core.rate_limiter import auth_rate_limiter
from app.database import get_db
from app.redis import get_redis
from app.users.models import User

router = APIRouter(prefix="/auth", tags=["Auth"])


class OAuthProvider(str, Enum):
    google = "google"
    facebook = "facebook"
    twitter = "twitter"
    tiktok = "tiktok"


def _get_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


@router.post("/register", response_model=AuthResponse, status_code=201)
async def register(
    body: RegisterRequest,
    request: Request,
    service: AuthService = Depends(_get_service),
    redis: Redis = Depends(get_redis),  # type: ignore[type-arg]
):
    """Register a new user account."""
    # Rate limit
    key = auth_rate_limiter.get_key(request, prefix="rl:register")
    await auth_rate_limiter.check(redis, key)

    return await service.register(
        email=body.email,
        password=body.password,
        role=body.role,
        phone=body.phone,
        redis=redis,
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    body: LoginRequest,
    request: Request,
    service: AuthService = Depends(_get_service),
    redis: Redis = Depends(get_redis),  # type: ignore[type-arg]
):
    """Authenticate and receive access + refresh tokens."""
    key = auth_rate_limiter.get_key(request, prefix="rl:login")
    await auth_rate_limiter.check(redis, key)

    ip = request.client.host if request.client else "unknown"
    return await service.login(
        email=body.email,
        password=body.password,
        mfa_code=body.mfa_code,
        ip_address=ip,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    body: RefreshRequest,
    service: AuthService = Depends(_get_service),
):
    """Rotate tokens — exchange refresh token for a new token pair."""
    return await service.refresh_tokens(body.refresh_token)


@router.post("/logout", response_model=SuccessResponse)
async def logout(
    body: RefreshRequest,
    service: AuthService = Depends(_get_service),
):
    """Revoke refresh token."""
    await service.logout(body.refresh_token)
    return SuccessResponse(message="Logged out successfully")


@router.post("/forgot-password", response_model=SuccessResponse)
async def forgot_password(
    body: ForgotPasswordRequest,
):
    """Send password reset email. Always returns success to prevent enumeration."""
    # TODO: Implement email sending via notification service
    return SuccessResponse(message="If the email exists, a reset link has been sent")


# ── Passwordless Auth ──


@router.post("/passwordless/register", response_model=CodeSentResponse, status_code=201)
async def passwordless_register(
    body: PasswordlessRegisterRequest,
    request: Request,
    service: AuthService = Depends(_get_service),
    redis: Redis = Depends(get_redis),  # type: ignore[type-arg]
):
    """Passwordless signup — create account and send a verification code."""
    key = auth_rate_limiter.get_key(request, prefix="rl:passwordless_register")
    await auth_rate_limiter.check(redis, key)

    return await service.passwordless_register(
        email=body.email,
        role=body.role,
        phone=body.phone,
        redis=redis,
    )


@router.post("/passwordless/register/verify", response_model=AuthResponse)
async def passwordless_register_verify(
    body: PasswordlessVerifyRequest,
    request: Request,
    service: AuthService = Depends(_get_service),
    redis: Redis = Depends(get_redis),  # type: ignore[type-arg]
):
    """Verify passwordless signup code and receive tokens."""
    key = auth_rate_limiter.get_key(request, prefix="rl:passwordless_verify")
    await auth_rate_limiter.check(redis, key)

    return await service.passwordless_verify_signup(
        email=body.email,
        code=body.code,
        redis=redis,
    )


@router.post("/passwordless/login", response_model=CodeSentResponse)
async def passwordless_login(
    body: PasswordlessLoginRequest,
    request: Request,
    service: AuthService = Depends(_get_service),
    redis: Redis = Depends(get_redis),  # type: ignore[type-arg]
):
    """Passwordless login — send a login code to the user's email."""
    key = auth_rate_limiter.get_key(request, prefix="rl:passwordless_login")
    await auth_rate_limiter.check(redis, key)

    return await service.passwordless_login_request(
        email=body.email,
        redis=redis,
    )


@router.post("/passwordless/login/verify", response_model=AuthResponse)
async def passwordless_login_verify(
    body: PasswordlessVerifyRequest,
    request: Request,
    service: AuthService = Depends(_get_service),
    redis: Redis = Depends(get_redis),  # type: ignore[type-arg]
):
    """Verify passwordless login code and receive tokens."""
    key = auth_rate_limiter.get_key(request, prefix="rl:passwordless_verify")
    await auth_rate_limiter.check(redis, key)

    ip = request.client.host if request.client else "unknown"
    return await service.passwordless_login_verify(
        email=body.email,
        code=body.code,
        redis=redis,
        ip_address=ip,
    )


# ── Email Verification ──


@router.post("/verify-email", response_model=SuccessResponse)
async def verify_email(
    body: VerifyEmailRequest,
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(_get_service),
    redis: Redis = Depends(get_redis),  # type: ignore[type-arg]
):
    """Verify email address with OTP code."""
    await service.verify_email(current_user.id, body.code, redis)
    return SuccessResponse(message="Email verified successfully")


@router.post("/resend-verification", response_model=SuccessResponse)
async def resend_verification(
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(_get_service),
    redis: Redis = Depends(get_redis),  # type: ignore[type-arg]
):
    """Resend email verification code."""
    await service.resend_verification_email(current_user.id, redis)
    return SuccessResponse(message="Verification code sent")


# ── MFA ──


@router.post("/mfa/setup", response_model=MFASetupResponse)
async def mfa_setup(
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(_get_service),
):
    """Generate TOTP secret and QR code URI for MFA setup."""
    return await service.setup_mfa(current_user.id)


@router.post("/mfa/verify", response_model=SuccessResponse)
async def mfa_verify(
    body: MFAVerifyRequest,
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(_get_service),
):
    """Verify TOTP code and activate MFA on the account."""
    await service.verify_mfa(current_user.id, body.code)
    return SuccessResponse(message="MFA enabled successfully")


@router.post("/mfa/disable", response_model=SuccessResponse)
async def mfa_disable(
    body: MFAVerifyRequest,
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(_get_service),
):
    """Disable MFA — requires a valid TOTP code."""
    await service.disable_mfa(current_user.id, body.code)
    return SuccessResponse(message="MFA disabled")


# ── OAuth Social Login ──


@router.get("/oauth/{provider}/url")
async def get_oauth_url(provider: OAuthProvider):
    """Get the OAuth authorization URL for a provider. Frontend redirects user here."""
    return AuthService.get_oauth_url(provider.value)


@router.post("/oauth", response_model=AuthResponse)
async def oauth_authenticate(
    body: OAuthRequest,
    request: Request,
    service: AuthService = Depends(_get_service),
    redis: Redis = Depends(get_redis),  # type: ignore[type-arg]
):
    """Authenticate via OAuth provider (Google, Facebook/Meta, Twitter/X).

    The frontend handles the OAuth redirect and sends the authorization code here.
    Creates a new account if the user doesn't exist, or logs in an existing user.
    """
    key = auth_rate_limiter.get_key(request, prefix="rl:oauth")
    await auth_rate_limiter.check(redis, key)

    ip = request.client.host if request.client else "unknown"
    return await service.oauth_authenticate(
        provider=body.provider,
        code=body.code,
        code_verifier=body.code_verifier,
        role=body.role,
        ip_address=ip,
    )


@router.post("/oauth/link", response_model=OAuthAccountResponse, status_code=201)
async def link_oauth_account(
    body: OAuthLinkRequest,
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(_get_service),
):
    """Link an OAuth provider to the current user's account."""
    return await service.link_oauth_account(
        user_id=current_user.id,
        provider=body.provider,
        code=body.code,
        code_verifier=body.code_verifier,
    )


@router.delete("/oauth/{provider}", response_model=SuccessResponse)
async def unlink_oauth_account(
    provider: str,
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(_get_service),
):
    """Unlink an OAuth provider from the current user's account.

    Cannot unlink if it's the user's only authentication method.
    """
    await service.unlink_oauth_account(
        user_id=current_user.id,
        provider=provider,
    )
    return SuccessResponse(message=f"{provider} account unlinked successfully")


@router.get("/oauth/accounts", response_model=OAuthAccountListResponse)
async def list_linked_accounts(
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(_get_service),
):
    """List all OAuth providers linked to the current user's account."""
    accounts = await service.get_linked_oauth_accounts(current_user.id)
    return OAuthAccountListResponse(accounts=accounts)
