"""Discount code routes — seller CRUD and public checkout validation."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_onboarded_seller
from app.core.base_schemas import SuccessResponse
from app.database import get_db
from app.discounts.schemas import (
    ApplyDiscountRequest,
    DiscountCodeCreate,
    DiscountCodeListResponse,
    DiscountCodeResponse,
    DiscountCodeUpdate,
    DiscountPreviewResponse,
)
from app.discounts.service import DiscountService
from app.users.models import User

router = APIRouter(tags=["Discounts"])


def _get_service(db: AsyncSession = Depends(get_db)) -> DiscountService:
    return DiscountService(db)


# ── Seller CRUD ──


@router.post("/seller/discounts", response_model=DiscountCodeResponse, status_code=201)
async def create_discount_code(
    body: DiscountCodeCreate,
    current_user: User = Depends(get_onboarded_seller),
    service: DiscountService = Depends(_get_service),
):
    """Create a new discount code."""
    return await service.create_code(current_user.id, body)


@router.get("/seller/discounts", response_model=DiscountCodeListResponse)
async def list_discount_codes(
    current_user: User = Depends(get_onboarded_seller),
    service: DiscountService = Depends(_get_service),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """List all discount codes for the current seller."""
    codes, total = await service.list_codes(current_user.id, offset, limit)
    return DiscountCodeListResponse(codes=codes, total=total)


@router.patch("/seller/discounts/{code_id}", response_model=DiscountCodeResponse)
async def update_discount_code(
    code_id: str,
    body: DiscountCodeUpdate,
    current_user: User = Depends(get_onboarded_seller),
    service: DiscountService = Depends(_get_service),
):
    """Update a discount code."""
    return await service.update_code(current_user.id, code_id, body)


@router.delete("/seller/discounts/{code_id}", response_model=SuccessResponse)
async def deactivate_discount_code(
    code_id: str,
    current_user: User = Depends(get_onboarded_seller),
    service: DiscountService = Depends(_get_service),
):
    """Deactivate a discount code."""
    await service.deactivate_code(current_user.id, code_id)
    return SuccessResponse(message="Discount code deactivated")


# ── Public: Apply at Checkout ──


@router.post("/checkout/apply-discount", response_model=DiscountPreviewResponse)
async def apply_discount(
    body: ApplyDiscountRequest,
    service: DiscountService = Depends(_get_service),
):
    """Validate and preview a discount code (public, for checkout)."""
    return await service.apply_discount(body)
