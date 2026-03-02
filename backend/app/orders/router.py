"""Order routes — seller and buyer views."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_buyer, get_onboarded_seller
from app.core.base_schemas import PaginatedResponse
from app.core.pagination import paginate
from app.database import get_db
from app.orders.schemas import (
    BulkStatusUpdate,
    BuyerDashboardResponse,
    OrderResponse,
    OrderStatusUpdate,
    TrackingUpdate,
)
from app.orders.service import OrderService
from app.sellers.repository import SellerProfileRepository
from app.users.models import User

router = APIRouter(prefix="/orders", tags=["Orders"])


async def _get_seller_profile_id(
    current_user: User = Depends(get_onboarded_seller),
    db: AsyncSession = Depends(get_db),
) -> str:
    repo = SellerProfileRepository(db)
    profile = await repo.get_by_user_id(current_user.id)
    if not profile:
        from app.core.exceptions import BadRequestError
        raise BadRequestError(detail="Seller profile not found")
    return profile.id


# ── Seller Endpoints ──


@router.get("/seller", response_model=PaginatedResponse[OrderResponse])
async def list_seller_orders(
    seller_id: str = Depends(_get_seller_profile_id),
    db: AsyncSession = Depends(get_db),
    status: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """List orders for the current seller."""
    svc = OrderService(db)
    items, total = await svc.list_seller_orders(
        seller_id, status=status, offset=offset, limit=limit,
    )
    return paginate(items, total, offset, limit)


@router.get("/seller/{order_id}", response_model=OrderResponse)
async def get_seller_order(
    order_id: str,
    seller_id: str = Depends(_get_seller_profile_id),
    db: AsyncSession = Depends(get_db),
):
    """Get a single order for the current seller."""
    svc = OrderService(db)
    return await svc.get_seller_order(order_id, seller_id)


@router.patch("/seller/{order_id}/status", response_model=OrderResponse)
async def update_order_status(
    order_id: str,
    data: OrderStatusUpdate,
    seller_id: str = Depends(_get_seller_profile_id),
    db: AsyncSession = Depends(get_db),
):
    """Update order status (packed, shipped, delivered, cancelled)."""
    svc = OrderService(db)
    return await svc.update_status(
        order_id, seller_id, data.status,
        tracking_number=data.tracking_number,
        delivery_notes=data.delivery_notes,
    )


@router.post("/seller/{order_id}/tracking", response_model=OrderResponse)
async def add_tracking(
    order_id: str,
    data: TrackingUpdate,
    seller_id: str = Depends(_get_seller_profile_id),
    db: AsyncSession = Depends(get_db),
):
    """Add tracking number to an order."""
    svc = OrderService(db)
    return await svc.add_tracking(order_id, seller_id, data.tracking_number, data.delivery_notes)


@router.post("/seller/bulk-status", response_model=list[OrderResponse])
async def bulk_update_status(
    data: BulkStatusUpdate,
    seller_id: str = Depends(_get_seller_profile_id),
    db: AsyncSession = Depends(get_db),
):
    """Bulk update order status."""
    svc = OrderService(db)
    return await svc.bulk_update_status(
        seller_id, data.order_ids, data.status, data.tracking_number,
    )


# ── Buyer Endpoints ──


@router.get("/buyer", response_model=PaginatedResponse[OrderResponse])
async def list_buyer_orders(
    current_user: User = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """List orders for the current buyer."""
    svc = OrderService(db)
    items, total = await svc.list_buyer_orders(
        current_user.id, offset=offset, limit=limit,
    )
    return paginate(items, total, offset, limit)


@router.get("/buyer/dashboard", response_model=BuyerDashboardResponse)
async def get_buyer_dashboard(
    current_user: User = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db),
):
    """Buyer dashboard — active orders, total spend, top sellers."""
    svc = OrderService(db)
    return await svc.get_buyer_dashboard(current_user.id)


@router.get("/buyer/{order_id}", response_model=OrderResponse)
async def get_buyer_order(
    order_id: str,
    current_user: User = Depends(get_current_buyer),
    db: AsyncSession = Depends(get_db),
):
    """Get a single order for the current buyer."""
    svc = OrderService(db)
    return await svc.get_buyer_order(order_id, current_user.id)
