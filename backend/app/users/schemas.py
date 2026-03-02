"""User and Address Pydantic schemas."""

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.core.base_schemas import TimestampMixin


# ── User Schemas ──


class UserResponse(TimestampMixin):
    """Public user profile response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    email: EmailStr
    phone: str | None = None
    role: str
    is_verified: bool
    mfa_enabled: bool
    is_shadow: bool


class UpdateProfileRequest(BaseModel):
    """Update user profile."""

    phone: str | None = None
    email: EmailStr | None = None


class FCMTokenRequest(BaseModel):
    """Register/update a Firebase Cloud Messaging device token."""

    fcm_token: str = Field(..., max_length=255)


class ChangePasswordRequest(BaseModel):
    """Change password — requires current password."""

    current_password: str = Field(min_length=8)
    new_password: str = Field(min_length=8, max_length=128)


# ── Address Schemas ──


class AddressCreate(BaseModel):
    """Create a new saved address."""

    full_name: str = Field(max_length=255)
    line_1: str = Field(max_length=500)
    line_2: str | None = Field(None, max_length=500)
    city: str = Field(max_length=100)
    state: str | None = Field(None, max_length=100)
    postal_code: str | None = Field(None, max_length=20)
    country: str = Field(min_length=2, max_length=2)
    phone: str | None = Field(None, max_length=20)
    is_default: bool = False


class AddressUpdate(BaseModel):
    """Update a saved address."""

    full_name: str | None = Field(None, max_length=255)
    line_1: str | None = Field(None, max_length=500)
    line_2: str | None = Field(None, max_length=500)
    city: str | None = Field(None, max_length=100)
    state: str | None = Field(None, max_length=100)
    postal_code: str | None = Field(None, max_length=20)
    country: str | None = Field(None, min_length=2, max_length=2)
    phone: str | None = Field(None, max_length=20)
    is_default: bool | None = None


class AddressResponse(TimestampMixin):
    """Saved address response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    full_name: str
    line_1: str
    line_2: str | None = None
    city: str
    state: str | None = None
    postal_code: str | None = None
    country: str
    phone: str | None = None
    is_default: bool
