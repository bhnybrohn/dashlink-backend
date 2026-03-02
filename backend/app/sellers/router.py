"""Seller API routes — profile, KYC, team, and share links."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_admin, get_current_seller
from app.core.base_schemas import SuccessResponse
from app.database import get_db
from app.sellers.schemas import (
    KycReviewRequest,
    KycStatusResponse,
    KycSubmissionResponse,
    KycSubmitRequest,
    OnboardingStatusResponse,
    PayoutSettingsUpdate,
    SellerProfileResponse,
    SellerProfileUpdate,
    ShareLinkResponse,
    SubscriptionUpdate,
    TeamInviteRequest,
    TeamListResponse,
    TeamMemberResponse,
    TeamMemberUpdate,
)
from app.sellers.service import SellerService
from app.users.models import User

router = APIRouter(prefix="/seller", tags=["Seller"])


def _get_service(db: AsyncSession = Depends(get_db)) -> SellerService:
    return SellerService(db)


# ── Profile ──


@router.get("/profile", response_model=SellerProfileResponse)
async def get_profile(
    current_user: User = Depends(get_current_seller),
    service: SellerService = Depends(_get_service),
):
    """Get the current seller's profile."""
    return await service.get_profile(current_user.id)


@router.patch("/profile", response_model=SellerProfileResponse)
async def update_profile(
    body: SellerProfileUpdate,
    current_user: User = Depends(get_current_seller),
    service: SellerService = Depends(_get_service),
):
    """Update seller profile (store name, bio, category)."""
    return await service.update_profile(
        current_user.id,
        store_name=body.store_name,
        bio=body.bio,
        category=body.category,
    )


@router.put("/profile/payout", response_model=SellerProfileResponse)
async def update_payout(
    body: PayoutSettingsUpdate,
    current_user: User = Depends(get_current_seller),
    service: SellerService = Depends(_get_service),
):
    """Update payout bank account settings."""
    return await service.update_payout(current_user.id, body.payout_account_id)


@router.post("/profile/subscription", response_model=SellerProfileResponse)
async def update_subscription(
    body: SubscriptionUpdate,
    current_user: User = Depends(get_current_seller),
    service: SellerService = Depends(_get_service),
):
    """Change subscription tier (free, pro, business)."""
    return await service.update_subscription(current_user.id, body.tier)


# ── Onboarding ──


@router.get("/onboarding", response_model=OnboardingStatusResponse)
async def get_onboarding_status(
    current_user: User = Depends(get_current_seller),
    service: SellerService = Depends(_get_service),
):
    """Get current onboarding progress and step details."""
    return await service.get_onboarding_status(current_user.id)


# ── Share Links ──


@router.get("/share-link", response_model=ShareLinkResponse)
async def get_share_link(
    current_user: User = Depends(get_current_seller),
    service: SellerService = Depends(_get_service),
    product_slug: str | None = None,
):
    """Generate shareable links for the store or a specific product."""
    return await service.generate_share_links(current_user.id, product_slug=product_slug)


# ── KYC ──


@router.post("/kyc/submit", response_model=KycSubmissionResponse, status_code=201)
async def submit_kyc(
    body: KycSubmitRequest,
    current_user: User = Depends(get_current_seller),
    service: SellerService = Depends(_get_service),
):
    """Submit KYC documents for verification."""
    return await service.submit_kyc(current_user.id, body)


@router.get("/kyc/status", response_model=KycStatusResponse)
async def get_kyc_status(
    current_user: User = Depends(get_current_seller),
    service: SellerService = Depends(_get_service),
):
    """Check current KYC verification status."""
    return await service.get_kyc_status(current_user.id)


# ── Team RBAC ──


@router.post("/team/invite", response_model=TeamMemberResponse, status_code=201)
async def invite_team_member(
    body: TeamInviteRequest,
    current_user: User = Depends(get_current_seller),
    service: SellerService = Depends(_get_service),
):
    """Invite a team member to the store."""
    return await service.invite_team_member(current_user.id, body)


@router.get("/team", response_model=TeamListResponse)
async def list_team_members(
    current_user: User = Depends(get_current_seller),
    service: SellerService = Depends(_get_service),
):
    """List all team members."""
    members = await service.list_team_members(current_user.id)
    return TeamListResponse(members=members)


@router.patch("/team/{member_id}", response_model=TeamMemberResponse)
async def update_team_member(
    member_id: str,
    body: TeamMemberUpdate,
    current_user: User = Depends(get_current_seller),
    service: SellerService = Depends(_get_service),
):
    """Update a team member's role."""
    return await service.update_team_member(current_user.id, member_id, body.team_role)


@router.delete("/team/{member_id}", response_model=SuccessResponse)
async def remove_team_member(
    member_id: str,
    current_user: User = Depends(get_current_seller),
    service: SellerService = Depends(_get_service),
):
    """Remove a team member from the store."""
    await service.remove_team_member(current_user.id, member_id)
    return SuccessResponse(message="Team member removed")


# ── Admin KYC Review ──


@router.post("/admin/kyc/{submission_id}/review", response_model=KycSubmissionResponse, tags=["Admin"])
async def review_kyc(
    submission_id: str,
    body: KycReviewRequest,
    current_user: User = Depends(get_current_admin),
    service: SellerService = Depends(_get_service),
):
    """Admin approves or rejects a KYC submission."""
    return await service.review_kyc(current_user.id, submission_id, body)
