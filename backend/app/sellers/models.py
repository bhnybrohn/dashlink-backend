"""Seller profile, KYC submission, and team member models."""

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel


class SellerProfile(BaseModel):
    __tablename__ = "seller_profiles"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), unique=True, nullable=False, index=True
    )
    store_name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    logo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    banner_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(
        Enum("fashion", "beauty", "electronics", "food", "other",
             name="store_category_enum", create_constraint=True),
        nullable=True,
    )
    kyc_status: Mapped[str] = mapped_column(
        Enum("none", "phone_verified", "id_submitted", "verified",
             name="kyc_status_enum", create_constraint=True),
        default="none",
        nullable=False,
    )
    country: Mapped[str] = mapped_column(String(2), default="NG", nullable=False)
    payout_account_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payout_hold_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    total_orders: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    average_rating: Mapped[float] = mapped_column(Numeric(2, 1), default=0.0, nullable=False)
    subscription_tier: Mapped[str] = mapped_column(
        Enum("free", "pro", "business",
             name="subscription_tier_enum", create_constraint=True),
        default="free",
        nullable=False,
    )
    onboarding_step: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="seller_profile")  # type: ignore[name-defined]  # noqa: F821


class KycSubmission(BaseModel):
    """A KYC document submission from a seller."""

    __tablename__ = "kyc_submissions"

    seller_profile_id: Mapped[str] = mapped_column(ForeignKey("seller_profiles.id"), nullable=False, index=True)
    document_type: Mapped[str] = mapped_column(
        Enum("national_id", "passport", "drivers_license", "business_registration",
             name="kyc_document_type_enum", create_constraint=True),
        nullable=False,
    )
    document_url: Mapped[str] = mapped_column(String(500), nullable=False)
    selfie_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("pending", "approved", "rejected",
             name="kyc_submission_status_enum", create_constraint=True),
        default="pending",
        nullable=False,
    )
    reviewer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    reviewed_by: Mapped[str | None] = mapped_column(String, nullable=True)


class TeamMember(BaseModel):
    """A team member invited by a seller."""

    __tablename__ = "team_members"

    seller_profile_id: Mapped[str] = mapped_column(ForeignKey("seller_profiles.id"), nullable=False, index=True)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    team_role: Mapped[str] = mapped_column(
        Enum("owner", "manager", "fulfiller",
             name="team_role_enum", create_constraint=True),
        nullable=False,
    )
    invited_email: Mapped[str] = mapped_column(String(255), nullable=False)
    invitation_status: Mapped[str] = mapped_column(
        Enum("pending", "accepted", "rejected",
             name="invitation_status_enum", create_constraint=True),
        default="pending",
        nullable=False,
    )
    invited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )
