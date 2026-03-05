"""Auth Pydantic schemas — request/response models for authentication."""

from datetime import datetime

from urllib.parse import unquote

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class RegisterRequest(BaseModel):
    """User registration."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: str = Field(default="seller", pattern="^(seller|buyer)$")
    phone: str | None = Field(None, max_length=20)


class LoginRequest(BaseModel):
    """User login."""

    email: EmailStr
    password: str
    mfa_code: str | None = Field(None, min_length=6, max_length=6)


class TokenResponse(BaseModel):
    """Authentication token pair."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class AuthUserResponse(BaseModel):
    """User info returned alongside tokens."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    role: str
    is_verified: bool
    first_name: str | None = None
    last_name: str | None = None
    avatar_url: str | None = None


class AuthResponse(BaseModel):
    """Full auth response — tokens + user info."""

    user: AuthUserResponse
    tokens: TokenResponse


class VerifyEmailRequest(BaseModel):
    """Email verification OTP."""

    code: str = Field(min_length=6, max_length=6)


class RefreshRequest(BaseModel):
    """Refresh token rotation."""

    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class MFASetupResponse(BaseModel):
    """TOTP setup — secret and provisioning URI for QR code."""

    secret: str
    provisioning_uri: str


class MFAVerifyRequest(BaseModel):
    """Verify a TOTP code."""

    code: str = Field(min_length=6, max_length=6)


class PhoneVerifyRequest(BaseModel):
    phone: str = Field(max_length=20)


class PhoneConfirmRequest(BaseModel):
    phone: str = Field(max_length=20)
    otp: str = Field(min_length=4, max_length=6)


# ── Passwordless ──


class PasswordlessRegisterRequest(BaseModel):
    """Passwordless signup — sends a code to the email."""

    email: EmailStr
    role: str = Field(default="seller", pattern="^(seller|buyer)$")
    phone: str | None = Field(None, max_length=20)


class PasswordlessLoginRequest(BaseModel):
    """Passwordless login — sends a code to the email."""

    email: EmailStr


class PasswordlessVerifyRequest(BaseModel):
    """Verify a passwordless code (signup or login)."""

    email: EmailStr
    code: str = Field(min_length=6, max_length=6)


class CodeSentResponse(BaseModel):
    """Response after sending a passwordless code."""

    message: str
    expires_in: int  # seconds until the code expires
    is_new_user: bool | None = None  # set by unified /start endpoint
    code: str | None = None  # included only in non-production environments


# ── Unified Passwordless ──


class PasswordlessStartRequest(BaseModel):
    """Unified passwordless start — registers or logs in based on email existence."""

    email: EmailStr
    role: str = Field(default="seller", pattern="^(seller|buyer)$")  # only used for new users
    phone: str | None = Field(None, max_length=20)


class OnboardingSnapshot(BaseModel):
    """Lightweight onboarding status for auth responses."""

    current_step: int  # 0 = all done
    is_complete: bool


class PasswordlessAuthResponse(BaseModel):
    """Unified passwordless verify response — tokens + navigation hints."""

    user: AuthUserResponse
    tokens: TokenResponse
    is_new_user: bool
    onboarding: OnboardingSnapshot | None = None  # None for buyers


# ── OAuth ──


class OAuthRequest(BaseModel):
    """OAuth code exchange — frontend sends provider name and authorization code."""

    provider: str = Field(pattern="^(google|facebook|twitter|tiktok)$")
    code: str = Field(min_length=1, max_length=2048)
    code_verifier: str | None = Field(
        None, max_length=128,
        description="Required for Twitter PKCE flow",
    )
    role: str = Field(default="buyer", pattern="^(seller|buyer)$")

    @field_validator("code", mode="before")
    @classmethod
    def decode_code(cls, v: str) -> str:
        return unquote(v)

    @field_validator("code_verifier", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: str | None) -> str | None:
        return None if not v else v


class OAuthLinkRequest(BaseModel):
    """Link an OAuth provider to an existing authenticated account."""

    provider: str = Field(pattern="^(google|facebook|twitter|tiktok)$")
    code: str = Field(min_length=1, max_length=2048)
    code_verifier: str | None = Field(None, max_length=128)

    @field_validator("code", mode="before")
    @classmethod
    def decode_code(cls, v: str) -> str:
        return unquote(v)

    @field_validator("code_verifier", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: str | None) -> str | None:
        return None if not v else v


class OAuthAccountResponse(BaseModel):
    """A linked OAuth account."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    provider: str
    provider_email: str | None
    linked_at: datetime


class OAuthAccountListResponse(BaseModel):
    """List of linked OAuth accounts for a user."""

    accounts: list[OAuthAccountResponse]
