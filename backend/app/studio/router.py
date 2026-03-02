"""Studio routes — AI generation endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_onboarded_seller
from app.core.base_schemas import PaginatedResponse
from app.core.pagination import paginate
from app.database import get_db
from app.sellers.repository import SellerProfileRepository
from app.studio.schemas import (
    BackgroundRemoveRequest,
    CaptionRequest,
    DescriptionRequest,
    EnhanceRequest,
    GenerationResponse,
    ImageGenRequest,
    TitleRequest,
    UsageResponse,
)
from app.studio.service import StudioService
from app.users.models import User

router = APIRouter(prefix="/studio", tags=["Studio"])


async def _get_seller_context(
    current_user: User = Depends(get_onboarded_seller),
    db: AsyncSession = Depends(get_db),
) -> tuple[str, str]:
    """Return (seller_profile_id, subscription_tier)."""
    repo = SellerProfileRepository(db)
    profile = await repo.get_by_user_id(current_user.id)
    if not profile:
        from app.core.exceptions import BadRequestError
        raise BadRequestError(detail="Seller profile not found")
    return profile.id, profile.subscription_tier


def _get_studio_service(db: AsyncSession = Depends(get_db)) -> StudioService:
    from app.integrations.openai_client import get_openai_client
    from app.integrations.removebg_client import get_removebg_client
    from app.integrations.storage_client import get_storage
    return StudioService(
        db,
        ai_client=get_openai_client(),
        removebg_client=get_removebg_client(),
        storage=get_storage(),
    )


# ── Generation Endpoints ──


@router.post("/generate/title", response_model=GenerationResponse, status_code=201)
async def generate_title(
    data: TitleRequest,
    seller_ctx: tuple[str, str] = Depends(_get_seller_context),
    svc: StudioService = Depends(_get_studio_service),
):
    """Generate product title options from category + keywords."""
    seller_id, tier = seller_ctx
    return await svc.generate_title(
        seller_id, tier,
        category=data.category, keywords=data.keywords,
        image_url=data.image_url, product_id=data.product_id,
    )


@router.post("/generate/description", response_model=GenerationResponse, status_code=201)
async def generate_description(
    data: DescriptionRequest,
    seller_ctx: tuple[str, str] = Depends(_get_seller_context),
    svc: StudioService = Depends(_get_studio_service),
):
    """Generate SEO-optimized product description."""
    seller_id, tier = seller_ctx
    return await svc.generate_description(
        seller_id, tier,
        title=data.title, category=data.category,
        tone=data.tone, image_url=data.image_url, product_id=data.product_id,
    )


@router.post("/generate/caption", response_model=GenerationResponse, status_code=201)
async def generate_caption(
    data: CaptionRequest,
    seller_ctx: tuple[str, str] = Depends(_get_seller_context),
    svc: StudioService = Depends(_get_studio_service),
):
    """Generate social media caption with hashtags."""
    seller_id, tier = seller_ctx
    return await svc.generate_caption(
        seller_id, tier,
        product_name=data.product_name, platform=data.platform,
        tone=data.tone, product_id=data.product_id,
    )


@router.post("/generate/image", response_model=GenerationResponse, status_code=201)
async def generate_image(
    data: ImageGenRequest,
    seller_ctx: tuple[str, str] = Depends(_get_seller_context),
    svc: StudioService = Depends(_get_studio_service),
):
    """Generate product image from text prompt (DALL-E 3)."""
    seller_id, tier = seller_ctx
    return await svc.generate_image(
        seller_id, tier,
        prompt=data.prompt, style=data.style, product_id=data.product_id,
    )


@router.post("/background-remove", response_model=GenerationResponse, status_code=201)
async def remove_background(
    data: BackgroundRemoveRequest,
    seller_ctx: tuple[str, str] = Depends(_get_seller_context),
    svc: StudioService = Depends(_get_studio_service),
):
    """Remove background from an image (Remove.bg)."""
    seller_id, tier = seller_ctx
    return await svc.remove_background(
        seller_id, tier, image_url=data.image_url, product_id=data.product_id,
    )


@router.post("/enhance", status_code=201)
async def enhance_product(
    data: EnhanceRequest,
    seller_ctx: tuple[str, str] = Depends(_get_seller_context),
    svc: StudioService = Depends(_get_studio_service),
):
    """Full product enhancement — title + description + caption in one call."""
    seller_id, tier = seller_ctx
    results = await svc.enhance_product(
        seller_id, tier,
        product_id=data.product_id, category=data.category, tone=data.tone,
    )
    return {k: GenerationResponse.model_validate(v, from_attributes=True) for k, v in results.items()}


# ── Queries ──


@router.get("/generations", response_model=PaginatedResponse[GenerationResponse])
async def list_generations(
    seller_ctx: tuple[str, str] = Depends(_get_seller_context),
    svc: StudioService = Depends(_get_studio_service),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """List past generations (paginated)."""
    seller_id, _ = seller_ctx
    items, total = await svc.list_generations(seller_id, offset=offset, limit=limit)
    return paginate(items, total, offset, limit)


@router.get("/generations/{generation_id}", response_model=GenerationResponse)
async def get_generation(
    generation_id: str,
    _seller_ctx: tuple[str, str] = Depends(_get_seller_context),
    svc: StudioService = Depends(_get_studio_service),
):
    """Get a single generation result."""
    return await svc.get_generation(generation_id)


@router.get("/usage", response_model=UsageResponse)
async def get_usage(
    seller_ctx: tuple[str, str] = Depends(_get_seller_context),
    svc: StudioService = Depends(_get_studio_service),
):
    """Get current month usage vs tier limits."""
    seller_id, tier = seller_ctx
    return await svc.get_usage(seller_id, tier)
