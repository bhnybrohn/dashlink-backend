"""Dispute routes — buyer opens, seller responds, admin resolves."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_admin, get_current_buyer, get_current_seller, get_current_user
from app.database import get_db
from app.disputes.schemas import (
    DisputeCreate,
    DisputeListResponse,
    DisputeResolve,
    DisputeRespond,
    DisputeResponse,
)
from app.disputes.service import DisputeService
from app.users.models import User

router = APIRouter(prefix="/disputes", tags=["Disputes"])


def _get_service(db: AsyncSession = Depends(get_db)) -> DisputeService:
    return DisputeService(db)


@router.post("", response_model=DisputeResponse, status_code=201)
async def open_dispute(
    body: DisputeCreate,
    current_user: User = Depends(get_current_user),
    service: DisputeService = Depends(_get_service),
):
    """Open a dispute on a delivered order."""
    return await service.open_dispute(current_user.id, body)


@router.get("", response_model=DisputeListResponse)
async def list_disputes(
    current_user: User = Depends(get_current_user),
    service: DisputeService = Depends(_get_service),
    status: str | None = Query(None, pattern="^(open|seller_responded|escalated|resolved|closed)$"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """List disputes (role-based: buyer sees own, seller sees theirs, admin sees all)."""
    disputes, total = await service.list_disputes(
        current_user.id, current_user.role, status=status, offset=offset, limit=limit,
    )
    return DisputeListResponse(disputes=disputes, total=total)


@router.get("/{dispute_id}", response_model=DisputeResponse)
async def get_dispute(
    dispute_id: str,
    current_user: User = Depends(get_current_user),
    service: DisputeService = Depends(_get_service),
):
    """Get dispute details."""
    return await service.get_dispute(dispute_id)


@router.post("/{dispute_id}/respond", response_model=DisputeResponse)
async def seller_respond(
    dispute_id: str,
    body: DisputeRespond,
    current_user: User = Depends(get_current_seller),
    service: DisputeService = Depends(_get_service),
):
    """Seller responds to a dispute."""
    return await service.seller_respond(current_user.id, dispute_id, body)


@router.post("/{dispute_id}/escalate", response_model=DisputeResponse)
async def escalate_dispute(
    dispute_id: str,
    current_user: User = Depends(get_current_user),
    service: DisputeService = Depends(_get_service),
):
    """Buyer escalates a dispute for admin review."""
    return await service.escalate(current_user.id, dispute_id)


@router.post("/{dispute_id}/resolve", response_model=DisputeResponse)
async def resolve_dispute(
    dispute_id: str,
    body: DisputeResolve,
    current_user: User = Depends(get_current_admin),
    service: DisputeService = Depends(_get_service),
):
    """Admin resolves a dispute."""
    return await service.resolve(current_user.id, dispute_id, body)
