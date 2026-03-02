"""Social media models — connected accounts and posts."""

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class SocialAccount(BaseModel):
    """A seller's connected social media account."""

    __tablename__ = "social_accounts"
    __table_args__ = (
        UniqueConstraint("seller_id", "platform", name="uq_social_seller_platform"),
    )

    seller_id: Mapped[str] = mapped_column(ForeignKey("seller_profiles.id"), nullable=False, index=True)
    platform: Mapped[str] = mapped_column(
        Enum("instagram", "tiktok", "facebook", "twitter", "pinterest",
             name="social_platform_enum", create_constraint=True),
        nullable=False,
    )
    platform_user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    platform_username: Mapped[str] = mapped_column(String(255), nullable=False)
    access_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    refresh_token_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    account_metadata: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    connected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False,
    )


class SocialPost(BaseModel):
    """A post published (or scheduled) to a social media platform."""

    __tablename__ = "social_posts"

    seller_id: Mapped[str] = mapped_column(ForeignKey("seller_profiles.id"), nullable=False, index=True)
    social_account_id: Mapped[str] = mapped_column(ForeignKey("social_accounts.id"), nullable=False, index=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    platform: Mapped[str] = mapped_column(
        Enum("instagram", "tiktok", "facebook", "twitter", "pinterest",
             name="social_platform_enum", create_constraint=True,
             create_type=False),
        nullable=False,
    )
    post_type: Mapped[str] = mapped_column(
        String(20), default="photo", nullable=False,
    )
    caption: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    link_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    platform_post_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    platform_post_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(
        Enum("pending", "scheduled", "publishing", "published", "failed",
             name="social_post_status_enum", create_constraint=True),
        default="pending",
        nullable=False,
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
