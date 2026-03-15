"""Social media request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.base_schemas import TimestampMixin


# ── Requests ──


class SocialConnectRequest(BaseModel):
    """Request to connect a social media account."""

    code: str
    redirect_uri: str | None = None
    code_verifier: str | None = None  # Required for Twitter PKCE


class SocialPostCreate(BaseModel):
    """Create a social media post (immediate or scheduled)."""

    social_account_id: str
    product_id: str | None = None
    post_type: str = Field(default="photo", pattern="^(photo|text|link)$")
    caption: str = Field(max_length=2200)
    image_url: str | None = None
    link_url: str | None = None
    scheduled_at: datetime | None = None

    @model_validator(mode="after")
    def validate_post_type_fields(self) -> "SocialPostCreate":
        if self.post_type == "photo" and not self.image_url:
            raise ValueError("image_url is required for photo posts")
        if self.post_type == "link" and not self.link_url:
            raise ValueError("link_url is required for link posts")
        return self


class ProductPostCreate(BaseModel):
    """Post a product directly — image and caption auto-resolved from product data."""

    product_id: str
    social_account_id: str
    caption: str | None = Field(None, max_length=2200)
    post_type: str = Field(default="photo", pattern="^(photo|link)$")
    scheduled_at: datetime | None = None
    include_link: bool = True


# ── Responses ──


class SocialAccountResponse(TimestampMixin):
    """Connected social media account."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    seller_id: str
    platform: str
    platform_user_id: str
    platform_username: str
    connected_at: datetime


class SocialAccountListResponse(BaseModel):
    accounts: list[SocialAccountResponse]


class SocialPostResponse(TimestampMixin):
    """Social media post record."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    seller_id: str
    social_account_id: str
    product_id: str | None = None
    platform: str
    post_type: str = "photo"
    caption: str
    image_url: str | None = None
    link_url: str | None = None
    platform_post_id: str | None = None
    platform_post_url: str | None = None
    status: str
    scheduled_at: datetime | None = None
    published_at: datetime | None = None
    error_message: str | None = None


class SocialPostListResponse(BaseModel):
    posts: list[SocialPostResponse]
    total: int
