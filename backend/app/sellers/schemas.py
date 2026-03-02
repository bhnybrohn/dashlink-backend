"""Seller Pydantic schemas — profile, KYC, and team."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.base_schemas import TimestampMixin


# ── Profile ──


class SellerProfileCreate(BaseModel):
    """Create seller profile (during registration)."""

    store_name: str = Field(max_length=100)
    country: str = Field(default="NG", max_length=2, pattern="^(NG|GH|GB)$")
    category: str | None = Field(None, pattern="^(fashion|beauty|electronics|food|other)$")
    bio: str | None = Field(None, max_length=500)


class SellerProfileUpdate(BaseModel):
    """Update seller profile."""

    store_name: str | None = Field(None, max_length=100)
    country: str | None = Field(None, max_length=2, pattern="^(NG|GH|GB)$")
    bio: str | None = Field(None, max_length=500)
    category: str | None = Field(None, pattern="^(fashion|beauty|electronics|food|other)$")
    # logo_url and banner_url are set via image upload endpoint


class SellerProfileResponse(TimestampMixin):
    """Public seller profile response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    store_name: str
    slug: str
    logo_url: str | None = None
    banner_url: str | None = None
    bio: str | None = None
    category: str | None = None
    country: str
    kyc_status: str
    subscription_tier: str
    total_orders: int
    average_rating: float
    payout_hold_days: int
    onboarding_step: int


class OnboardingStepDetail(BaseModel):
    """Detail for a single onboarding step."""

    step: int
    name: str
    completed: bool


class OnboardingStatusResponse(BaseModel):
    """Current onboarding progress."""

    current_step: int  # 0 = complete
    is_complete: bool
    steps: list[OnboardingStepDetail]


class PayoutSettingsUpdate(BaseModel):
    """Update payout bank account — requires MFA verification."""

    payout_account_id: str


class SubscriptionUpdate(BaseModel):
    """Change subscription tier."""

    tier: str = Field(pattern="^(free|pro|business)$")


class ShareLinkResponse(BaseModel):
    """Generated share links for a store or product."""

    store_url: str
    product_url: str | None = None


# ── KYC ──


class KycSubmitRequest(BaseModel):
    """Submit KYC documents for verification."""

    document_type: str = Field(
        ..., pattern="^(national_id|passport|drivers_license|business_registration)$"
    )
    document_url: str = Field(..., max_length=500)
    selfie_url: str | None = Field(None, max_length=500)


class KycReviewRequest(BaseModel):
    """Admin reviews a KYC submission."""

    status: str = Field(..., pattern="^(approved|rejected)$")
    reviewer_notes: str | None = Field(None, max_length=1000)


class KycSubmissionResponse(TimestampMixin):
    model_config = ConfigDict(from_attributes=True)

    id: str
    seller_profile_id: str
    document_type: str
    document_url: str
    selfie_url: str | None = None
    status: str
    reviewer_notes: str | None = None
    reviewed_at: datetime | None = None
    reviewed_by: str | None = None


class KycStatusResponse(BaseModel):
    kyc_status: str
    latest_submission: KycSubmissionResponse | None = None


# ── Team RBAC ──


class TeamInviteRequest(BaseModel):
    """Invite a team member."""

    invited_email: str = Field(..., max_length=255)
    team_role: str = Field(..., pattern="^(manager|fulfiller)$")


class TeamMemberUpdate(BaseModel):
    """Update a team member's role."""

    team_role: str = Field(..., pattern="^(owner|manager|fulfiller)$")


class TeamMemberResponse(TimestampMixin):
    model_config = ConfigDict(from_attributes=True)

    id: str
    seller_profile_id: str
    user_id: str | None = None
    team_role: str
    invited_email: str
    invitation_status: str
    invited_at: datetime


class TeamListResponse(BaseModel):
    members: list[TeamMemberResponse]
