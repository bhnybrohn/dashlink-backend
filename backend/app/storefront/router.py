"""Storefront public routes — /@slug and Flash Page."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_schemas import PaginatedResponse
from app.core.pagination import paginate
from app.database import get_db
from app.storefront.schemas import (
    FlashPageResponse,
    PublicProduct,
    StorefrontResponse,
)
from app.storefront.service import StorefrontService

router = APIRouter(tags=["Storefront"])


def _get_service(db: AsyncSession = Depends(get_db)) -> StorefrontService:
    return StorefrontService(db)


@router.get("/storefront/@{slug}", response_model=StorefrontResponse)
async def get_storefront(
    slug: str,
    svc: StorefrontService = Depends(_get_service),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """Get public storefront page data."""
    return await svc.get_storefront(slug, offset=offset, limit=limit)


@router.get("/storefront/@{slug}/products", response_model=PaginatedResponse[PublicProduct])
async def get_store_products(
    slug: str,
    svc: StorefrontService = Depends(_get_service),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """Get paginated products for a store."""
    items, total = await svc.get_store_products(slug, offset=offset, limit=limit)
    return paginate(items, total, offset, limit)


@router.get("/flash/{product_slug}", response_model=FlashPageResponse)
async def get_flash_page(
    product_slug: str,
    svc: StorefrontService = Depends(_get_service),
):
    """Get product Flash Page data (single-product landing page)."""
    return await svc.get_flash_page(product_slug)
