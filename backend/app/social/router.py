"""Social media routes — connect accounts, post content, list history."""

from enum import Enum

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_seller, get_onboarded_seller
from app.core.base_schemas import SuccessResponse
from app.database import get_db
from app.social.schemas import (
    ProductPostCreate,
    SocialAccountListResponse,
    SocialAccountResponse,
    SocialConnectRequest,
    SocialPostCreate,
    SocialPostListResponse,
    SocialPostResponse,
)
from app.sellers.service import SellerService
from app.social.service import SocialService
from app.users.models import User

router = APIRouter(prefix="/social", tags=["Social Media"])


class SocialPlatform(str, Enum):
    instagram = "instagram"
    tiktok = "tiktok"
    facebook = "facebook"
    twitter = "twitter"
    pinterest = "pinterest"


def _get_service(db: AsyncSession = Depends(get_db)) -> SocialService:
    return SocialService(db)


def _get_seller_service(db: AsyncSession = Depends(get_db)) -> SellerService:
    return SellerService(db)


# ── OAuth URL Generation ──


@router.get("/connect-url/{platform}")
async def get_connect_url(
    platform: SocialPlatform,
    _current_user: User = Depends(get_current_seller),
):
    """Get the OAuth authorization URL for connecting a social publishing account."""
    return SocialService.get_connect_url(platform.value)


# ── Account Connection ──


@router.post("/connect/instagram", response_model=SocialAccountResponse, status_code=201)
async def connect_instagram(
    body: SocialConnectRequest,
    current_user: User = Depends(get_current_seller),
    service: SocialService = Depends(_get_service),
    seller_service: SellerService = Depends(_get_seller_service),
):
    """Connect an Instagram Business Account via Facebook OAuth."""
    result = await service.connect_instagram(current_user.id, body)
    await seller_service.advance_onboarding(current_user.id)
    return result


@router.post("/connect/tiktok", response_model=SocialAccountResponse, status_code=201)
async def connect_tiktok(
    body: SocialConnectRequest,
    current_user: User = Depends(get_current_seller),
    service: SocialService = Depends(_get_service),
    seller_service: SellerService = Depends(_get_seller_service),
):
    """Connect a TikTok account via TikTok Login Kit."""
    result = await service.connect_tiktok(current_user.id, body)
    await seller_service.advance_onboarding(current_user.id)
    return result


@router.post("/connect/facebook", response_model=SocialAccountResponse, status_code=201)
async def connect_facebook(
    body: SocialConnectRequest,
    current_user: User = Depends(get_current_seller),
    service: SocialService = Depends(_get_service),
    seller_service: SellerService = Depends(_get_seller_service),
):
    """Connect a Facebook Page for publishing."""
    result = await service.connect_facebook(current_user.id, body)
    await seller_service.advance_onboarding(current_user.id)
    return result


@router.post("/connect/twitter", response_model=SocialAccountResponse, status_code=201)
async def connect_twitter(
    body: SocialConnectRequest,
    current_user: User = Depends(get_current_seller),
    service: SocialService = Depends(_get_service),
    seller_service: SellerService = Depends(_get_seller_service),
):
    """Connect a Twitter/X account for publishing."""
    result = await service.connect_twitter(current_user.id, body)
    await seller_service.advance_onboarding(current_user.id)
    return result


@router.post("/connect/pinterest", response_model=SocialAccountResponse, status_code=201)
async def connect_pinterest(
    body: SocialConnectRequest,
    current_user: User = Depends(get_current_seller),
    service: SocialService = Depends(_get_service),
    seller_service: SellerService = Depends(_get_seller_service),
):
    """Connect a Pinterest account for Pin publishing."""
    result = await service.connect_pinterest(current_user.id, body)
    await seller_service.advance_onboarding(current_user.id)
    return result


@router.delete("/accounts/{platform}", response_model=SuccessResponse)
async def disconnect_account(
    platform: str,
    current_user: User = Depends(get_onboarded_seller),
    service: SocialService = Depends(_get_service),
):
    """Disconnect a social media account."""
    await service.disconnect_account(current_user.id, platform)
    return SuccessResponse(message=f"{platform.capitalize()} account disconnected")


@router.get("/accounts", response_model=SocialAccountListResponse)
async def list_accounts(
    current_user: User = Depends(get_current_seller),
    service: SocialService = Depends(_get_service),
):
    """List all connected social media accounts."""
    accounts = await service.list_accounts(current_user.id)
    return SocialAccountListResponse(accounts=accounts)


# ── Posting ──


@router.post("/post", response_model=SocialPostResponse, status_code=201)
async def create_post(
    body: SocialPostCreate,
    current_user: User = Depends(get_onboarded_seller),
    service: SocialService = Depends(_get_service),
):
    """Create a social media post (immediate or scheduled).

    If `scheduled_at` is provided, the post is saved and published later
    by a background worker. Otherwise it's published immediately.
    """
    return await service.create_post(current_user.id, body)


@router.post("/post/product", response_model=SocialPostResponse, status_code=201)
async def create_product_post(
    body: ProductPostCreate,
    current_user: User = Depends(get_onboarded_seller),
    service: SocialService = Depends(_get_service),
):
    """Post a product directly — image and caption auto-resolved from product data.

    Just provide `product_id` and `social_account_id`. The system pulls the
    product's images and generates a caption from product name, price, and description.
    For Instagram, products with multiple images are posted as carousels.
    """
    seller_profile = current_user.seller_profile
    return await service.create_product_post(
        seller_id=seller_profile.id,
        seller_slug=seller_profile.slug,
        data=body,
    )


@router.get("/posts", response_model=SocialPostListResponse)
async def list_posts(
    current_user: User = Depends(get_onboarded_seller),
    service: SocialService = Depends(_get_service),
    platform: str | None = Query(None, pattern="^(instagram|tiktok|facebook|twitter|pinterest)$"),
    status: str | None = Query(None, pattern="^(pending|scheduled|publishing|published|failed)$"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """List post history with optional filters."""
    posts, total = await service.list_posts(
        current_user.id, platform=platform, status=status, offset=offset, limit=limit,
    )
    return SocialPostListResponse(posts=posts, total=total)
