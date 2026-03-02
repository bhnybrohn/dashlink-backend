"""Trust & fraud scoring routes — seller trust score, admin risk management."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_admin, get_current_seller
from app.database import get_db
from app.trust.schemas import (
    OrderRiskFlagListResponse,
    OrderRiskFlagResponse,
    ReviewRiskFlagRequest,
    TrustScoreListResponse,
    TrustScoreResponse,
)
from app.trust.service import TrustService
from app.users.models import User

router = APIRouter(tags=["Trust & Fraud"])


def _get_service(db: AsyncSession = Depends(get_db)) -> TrustService:
    return TrustService(db)


# ── Seller ──


@router.get("/seller/trust-score", response_model=TrustScoreResponse)
async def get_trust_score(
    current_user: User = Depends(get_current_seller),
    service: TrustService = Depends(_get_service),
):
    """View your seller trust score and breakdown."""
    return await service.get_trust_score(current_user.id)


# ── Admin ──


@router.get("/admin/trust/sellers", response_model=TrustScoreListResponse)
async def list_trust_scores(
    current_user: User = Depends(get_current_admin),
    service: TrustService = Depends(_get_service),
    level: str | None = Query(None, pattern="^(new|basic|trusted|verified|premium)$"),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """List sellers by trust level (admin only)."""
    scores, total = await service.list_by_level(level, offset, limit)
    return TrustScoreListResponse(scores=scores, total=total)


@router.get("/admin/trust/flagged-orders", response_model=OrderRiskFlagListResponse)
async def list_flagged_orders(
    current_user: User = Depends(get_current_admin),
    service: TrustService = Depends(_get_service),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """List orders flagged by the risk scoring system (admin only)."""
    flags, total = await service.list_flagged_orders(offset, limit)
    return OrderRiskFlagListResponse(flagged_orders=flags, total=total)


@router.post("/admin/trust/flagged-orders/{flag_id}/review", response_model=OrderRiskFlagResponse)
async def review_flagged_order(
    flag_id: str,
    body: ReviewRiskFlagRequest,
    current_user: User = Depends(get_current_admin),
    service: TrustService = Depends(_get_service),
):
    """Admin reviews a flagged order and sets action."""
    return await service.review_risk_flag(current_user.id, flag_id, body.action)
