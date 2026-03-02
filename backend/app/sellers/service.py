"""Seller service — profile management, KYC, team RBAC, subscription."""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.core.slug import generate_store_slug
from app.sellers.models import KycSubmission, SellerProfile, TeamMember
from app.sellers.repository import SellerProfileRepository
from app.sellers.schemas import KycReviewRequest, KycSubmitRequest, TeamInviteRequest
from app.social.repository import SocialAccountRepository
from app.users.repository import UserRepository


_ONBOARDING_STEPS = [
    (1, "verify_email"),
    (2, "store_setup"),
    (3, "connect_social"),
    (4, "kyc_submission"),
    (5, "payout_setup"),
]


class SellerService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.seller_repo = SellerProfileRepository(session)
        self.social_repo = SocialAccountRepository(session)
        self.user_repo = UserRepository(session)

    async def get_profile(self, user_id: str) -> SellerProfile:
        """Get seller profile by user ID."""
        profile = await self.seller_repo.get_by_user_id(user_id)
        if not profile:
            raise NotFoundError(resource="seller_profile")
        return profile

    async def update_profile(
        self,
        user_id: str,
        *,
        store_name: str | None = None,
        bio: str | None = None,
        category: str | None = None,
    ) -> SellerProfile:
        """Update seller profile settings."""
        profile = await self.get_profile(user_id)

        updates: dict = {}
        if store_name is not None:
            updates["store_name"] = store_name
            # Update slug if store name changes
            new_slug = generate_store_slug(store_name)
            existing = await self.seller_repo.get_by_slug(new_slug)
            if existing and existing.id != profile.id:
                new_slug = f"{new_slug}{profile.id[:4]}"
            updates["slug"] = new_slug

        if bio is not None:
            updates["bio"] = bio
        if category is not None:
            updates["category"] = category

        if not updates:
            return profile

        result = await self.seller_repo.update(profile.id, **updates)
        await self.advance_onboarding(user_id)
        return result

    async def update_payout(self, user_id: str, payout_account_id: str) -> SellerProfile:
        """Update payout bank account. Should be called after MFA verification."""
        profile = await self.get_profile(user_id)
        result = await self.seller_repo.update(
            profile.id, payout_account_id=payout_account_id
        )
        await self.advance_onboarding(user_id)
        return result

    async def update_subscription(self, user_id: str, tier: str) -> SellerProfile:
        """Change subscription tier."""
        if tier not in ("free", "pro", "business"):
            raise BadRequestError(detail=f"Invalid tier: {tier}")
        profile = await self.get_profile(user_id)
        return await self.seller_repo.update(profile.id, subscription_tier=tier)

    async def generate_share_links(
        self, user_id: str, *, product_slug: str | None = None,
    ) -> dict[str, str | None]:
        """Generate shareable URLs for store or product Flash Page."""
        profile = await self.get_profile(user_id)
        base = "https://dashlink.to"
        result: dict[str, str | None] = {
            "store_url": f"{base}/@{profile.slug}",
            "product_url": None,
        }
        if product_slug:
            result["product_url"] = f"{base}/flash/{product_slug}"
        return result

    # ── Onboarding ──

    async def get_onboarding_status(self, user_id: str) -> dict:
        """Compute onboarding progress from actual data."""
        profile = await self.get_profile(user_id)
        user = await self.user_repo.get_or_404(user_id)
        social_accounts = await self.social_repo.get_all_for_seller(profile.id)

        completed = {
            1: user.is_verified,
            2: profile.category is not None,
            3: len(social_accounts) > 0,
            4: profile.kyc_status in ("id_submitted", "verified"),
            5: profile.payout_account_id is not None,
        }

        steps = [
            {"step": num, "name": name, "completed": completed[num]}
            for num, name in _ONBOARDING_STEPS
        ]

        # Find the first incomplete step (or 0 if all done)
        current_step = 0
        for num in range(1, 6):
            if not completed[num]:
                current_step = num
                break

        # Sync the stored step if it changed
        if current_step != profile.onboarding_step:
            await self.seller_repo.update(profile.id, onboarding_step=current_step)

        return {
            "current_step": current_step,
            "is_complete": current_step == 0,
            "steps": steps,
        }

    async def advance_onboarding(self, user_id: str) -> None:
        """Recompute and update onboarding_step after a step is completed."""
        await self.get_onboarding_status(user_id)

    # ── KYC ──

    async def submit_kyc(self, user_id: str, data: KycSubmitRequest) -> KycSubmission:
        """Seller submits KYC documents for verification."""
        profile = await self.get_profile(user_id)

        submission = KycSubmission(
            seller_profile_id=profile.id,
            document_type=data.document_type,
            document_url=data.document_url,
            selfie_url=data.selfie_url,
        )
        self.session.add(submission)

        # Update seller KYC status to id_submitted
        if profile.kyc_status in ("none", "phone_verified"):
            await self.seller_repo.update(profile.id, kyc_status="id_submitted")

        await self.session.flush()
        await self.session.refresh(submission)
        await self.advance_onboarding(user_id)
        return submission

    async def get_kyc_status(self, user_id: str) -> dict:
        """Get the current KYC status and latest submission."""
        profile = await self.get_profile(user_id)

        query = (
            select(KycSubmission)
            .where(
                KycSubmission.seller_profile_id == profile.id,
                KycSubmission.deleted_at.is_(None),
            )
            .order_by(KycSubmission.created_at.desc())
            .limit(1)
        )
        result = await self.session.execute(query)
        latest = result.scalar_one_or_none()

        return {
            "kyc_status": profile.kyc_status,
            "latest_submission": latest,
        }

    async def review_kyc(
        self, admin_id: str, submission_id: str, data: KycReviewRequest,
    ) -> KycSubmission:
        """Admin approves or rejects a KYC submission."""
        query = (
            select(KycSubmission)
            .where(KycSubmission.id == submission_id, KycSubmission.deleted_at.is_(None))
        )
        result = await self.session.execute(query)
        submission = result.scalar_one_or_none()
        if not submission:
            raise NotFoundError(resource="kyc_submission", resource_id=submission_id)

        submission.status = data.status
        submission.reviewer_notes = data.reviewer_notes
        submission.reviewed_at = datetime.now(timezone.utc)
        submission.reviewed_by = admin_id
        submission.version += 1

        # Update seller KYC status based on review
        if data.status == "approved":
            profile = await self.seller_repo.get(submission.seller_profile_id)
            if profile:
                await self.seller_repo.update(profile.id, kyc_status="verified")

        await self.session.flush()
        await self.session.refresh(submission)
        return submission

    # ── Team RBAC ──

    async def invite_team_member(
        self, user_id: str, data: TeamInviteRequest,
    ) -> TeamMember:
        """Invite a team member to the seller's store."""
        profile = await self.get_profile(user_id)

        # Check for existing invite
        query = (
            select(TeamMember)
            .where(
                TeamMember.seller_profile_id == profile.id,
                TeamMember.invited_email == data.invited_email,
                TeamMember.deleted_at.is_(None),
            )
        )
        result = await self.session.execute(query)
        existing = result.scalar_one_or_none()
        if existing:
            raise ConflictError(detail="This email has already been invited")

        member = TeamMember(
            seller_profile_id=profile.id,
            team_role=data.team_role,
            invited_email=data.invited_email,
        )
        self.session.add(member)
        await self.session.flush()
        await self.session.refresh(member)
        return member

    async def list_team_members(self, user_id: str) -> list[TeamMember]:
        """List all team members for the seller's store."""
        profile = await self.get_profile(user_id)
        query = (
            select(TeamMember)
            .where(
                TeamMember.seller_profile_id == profile.id,
                TeamMember.deleted_at.is_(None),
            )
            .order_by(TeamMember.invited_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def update_team_member(
        self, user_id: str, member_id: str, team_role: str,
    ) -> TeamMember:
        """Update a team member's role."""
        profile = await self.get_profile(user_id)

        query = (
            select(TeamMember)
            .where(
                TeamMember.id == member_id,
                TeamMember.seller_profile_id == profile.id,
                TeamMember.deleted_at.is_(None),
            )
        )
        result = await self.session.execute(query)
        member = result.scalar_one_or_none()
        if not member:
            raise NotFoundError(resource="team_member", resource_id=member_id)

        member.team_role = team_role
        member.version += 1
        await self.session.flush()
        await self.session.refresh(member)
        return member

    async def remove_team_member(self, user_id: str, member_id: str) -> None:
        """Remove a team member from the seller's store."""
        profile = await self.get_profile(user_id)

        query = (
            select(TeamMember)
            .where(
                TeamMember.id == member_id,
                TeamMember.seller_profile_id == profile.id,
                TeamMember.deleted_at.is_(None),
            )
        )
        result = await self.session.execute(query)
        member = result.scalar_one_or_none()
        if not member:
            raise NotFoundError(resource="team_member", resource_id=member_id)

        member.deleted_at = datetime.now(timezone.utc)
        member.version += 1
        await self.session.flush()
