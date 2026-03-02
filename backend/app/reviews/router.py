"""Review routes."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_buyer
from app.core.base_schemas import PaginatedResponse
from app.core.pagination import paginate
from app.database import get_db
from app.reviews.schemas import ReviewCreate, ReviewResponse
from app.reviews.service import ReviewService
from app.users.models import User

router = APIRouter(prefix="/reviews", tags=["Reviews"])


def _get_service(db: AsyncSession = Depends(get_db)) -> ReviewService:
    return ReviewService(db)


@router.post("", response_model=ReviewResponse, status_code=201)
async def submit_review(
    data: ReviewCreate,
    current_user: User = Depends(get_current_buyer),
    svc: ReviewService = Depends(_get_service),
):
    """Submit a review for a delivered order."""
    return await svc.submit_review(
        current_user.id,
        order_id=data.order_id,
        product_id=data.product_id,
        rating=data.rating,
        comment=data.comment,
    )


@router.get("/product/{product_id}", response_model=PaginatedResponse[ReviewResponse])
async def list_product_reviews(
    product_id: str,
    svc: ReviewService = Depends(_get_service),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """Get reviews for a product (public)."""
    items, total = await svc.list_product_reviews(product_id, offset=offset, limit=limit)
    return paginate(items, total, offset, limit)


@router.get("/seller/{seller_slug}", response_model=PaginatedResponse[ReviewResponse])
async def list_seller_reviews(
    seller_slug: str,
    svc: ReviewService = Depends(_get_service),
    db: AsyncSession = Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """Get reviews for a seller (public, by slug)."""
    from app.sellers.repository import SellerProfileRepository
    seller_repo = SellerProfileRepository(db)
    seller = await seller_repo.get_by_slug(seller_slug)
    if not seller:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(resource="seller", resource_id=seller_slug)
    items, total = await svc.list_seller_reviews(seller.id, offset=offset, limit=limit)
    return paginate(items, total, offset, limit)
