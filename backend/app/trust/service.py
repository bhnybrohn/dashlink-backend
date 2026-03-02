"""Trust & fraud scoring service — score calculation, risk assessment."""

from datetime import datetime, timezone

from sqlalchemy import distinct, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.disputes.models import Dispute
from app.orders.models import Order
from app.sellers.models import SellerProfile
from app.sellers.repository import SellerProfileRepository
from app.social.models import SocialAccount
from app.trust.models import OrderRiskFlag, TrustScore
from app.trust.repository import OrderRiskFlagRepository, TrustScoreRepository


class TrustService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.score_repo = TrustScoreRepository(session)
        self.risk_repo = OrderRiskFlagRepository(session)
        self.seller_repo = SellerProfileRepository(session)

    # ── Trust Score Calculation ──

    async def calculate_trust_score(self, seller_id: str) -> TrustScore:
        """Calculate or recalculate the trust score for a seller."""
        seller = await self.seller_repo.get_by_user_id(seller_id)
        if not seller:
            raise NotFoundError(resource="seller_profile")

        factors: dict = {}
        score = 0

        # KYC verified → +20
        if seller.kyc_status == "verified":
            factors["kyc_verified"] = 20
            score += 20

        # Account age → up to +15
        age_days = (datetime.now(timezone.utc) - seller.created_at).days
        age_score = min(age_days // 30, 15)  # 1 point per month, max 15
        factors["account_age_days"] = age_days
        factors["account_age_score"] = age_score
        score += age_score

        # Total completed orders → up to +20
        order_q = (
            select(func.count())
            .select_from(Order)
            .where(
                Order.seller_id == seller_id,
                Order.status.in_(["delivered"]),
                Order.deleted_at.is_(None),
            )
        )
        completed_orders = (await self.session.execute(order_q)).scalar_one()
        order_score = min(completed_orders // 5, 20)  # 1 point per 5 orders, max 20
        factors["total_completed_orders"] = completed_orders
        factors["order_score"] = order_score
        score += order_score

        # Average rating → up to +15
        rating = float(seller.average_rating)
        rating_score = int(rating * 3)  # 3 points per star, max 15
        factors["average_rating"] = rating
        factors["rating_score"] = min(rating_score, 15)
        score += min(rating_score, 15)

        # Dispute rate → up to -30
        dispute_q = (
            select(func.count())
            .select_from(Dispute)
            .where(
                Dispute.seller_id == seller_id,
                Dispute.deleted_at.is_(None),
            )
        )
        dispute_count = (await self.session.execute(dispute_q)).scalar_one()
        if completed_orders > 0:
            dispute_rate = dispute_count / completed_orders
            dispute_penalty = int(min(dispute_rate * 100, 30))
        else:
            dispute_penalty = 0
        factors["dispute_count"] = dispute_count
        factors["dispute_penalty"] = dispute_penalty
        score -= dispute_penalty

        # Social accounts linked → up to +10
        social_q = (
            select(func.count())
            .select_from(SocialAccount)
            .where(
                SocialAccount.seller_id == seller_id,
                SocialAccount.deleted_at.is_(None),
            )
        )
        social_count = (await self.session.execute(social_q)).scalar_one()
        social_score = min(social_count * 5, 10)
        factors["social_accounts"] = social_count
        factors["social_score"] = social_score
        score += social_score

        # Payout account verified → +10
        if seller.payout_account_id:
            factors["payout_verified"] = 10
            score += 10

        # Clamp score to 0-100
        score = max(0, min(score, 100))

        # Determine level
        if score >= 81:
            level = "premium"
        elif score >= 61:
            level = "verified" if seller.kyc_status == "verified" else "trusted"
        elif score >= 41:
            level = "trusted"
        elif score >= 21:
            level = "basic"
        else:
            level = "new"

        # Upsert trust score
        existing = await self.score_repo.get_by_seller(seller_id)
        if existing:
            return await self.score_repo.update(
                existing.id,
                score=score,
                level=level,
                factors=factors,
                last_calculated_at=datetime.now(timezone.utc),
            )

        return await self.score_repo.create(
            seller_id=seller_id,
            score=score,
            level=level,
            factors=factors,
            last_calculated_at=datetime.now(timezone.utc),
        )

    async def get_trust_score(self, seller_id: str) -> TrustScore:
        """Get trust score for a seller, calculating if not yet present."""
        existing = await self.score_repo.get_by_seller(seller_id)
        if existing:
            return existing
        return await self.calculate_trust_score(seller_id)

    async def list_by_level(
        self, level: str | None = None, offset: int = 0, limit: int = 20,
    ) -> tuple[list[TrustScore], int]:
        return await self.score_repo.list_by_level(level, offset, limit)

    # ── Order Risk Assessment ──

    async def assess_order_risk(self, order_id: str) -> OrderRiskFlag:
        """Calculate risk score for an order after creation."""
        from app.orders.repository import OrderRepository
        order_repo = OrderRepository(self.session)

        order = await order_repo.get(order_id)
        if not order:
            raise NotFoundError(resource="order", resource_id=order_id)

        flags: dict = {}
        risk_score = 0

        # High value vs seller history
        seller = await self.seller_repo.get_by_user_id(order.seller_id)
        if seller and seller.total_orders < 5 and float(order.total_amount) > 50000:
            flags["high_value_new_seller"] = True
            risk_score += 30

        # Velocity check — multiple orders in short period
        recent_q = (
            select(func.count())
            .select_from(Order)
            .where(
                Order.buyer_email == order.buyer_email,
                Order.seller_id == order.seller_id,
                Order.deleted_at.is_(None),
            )
        )
        recent_count = (await self.session.execute(recent_q)).scalar_one()
        if recent_count > 3:
            flags["velocity_check"] = f"{recent_count} orders from same buyer"
            risk_score += 20

        # First-time buyer + high value
        buyer_total_q = (
            select(func.count())
            .select_from(Order)
            .where(
                Order.buyer_email == order.buyer_email,
                Order.deleted_at.is_(None),
            )
        )
        buyer_total = (await self.session.execute(buyer_total_q)).scalar_one()
        if buyer_total <= 1 and float(order.total_amount) > 100000:
            flags["first_time_high_value"] = True
            risk_score += 25

        # Seller with high dispute rate
        if seller:
            dispute_q = (
                select(func.count())
                .select_from(Dispute)
                .where(
                    Dispute.seller_id == order.seller_id,
                    Dispute.deleted_at.is_(None),
                )
            )
            dispute_count = (await self.session.execute(dispute_q)).scalar_one()
            if seller.total_orders > 10 and dispute_count / seller.total_orders > 0.1:
                flags["high_dispute_rate"] = True
                risk_score += 25

        risk_score = min(risk_score, 100)

        # Determine action
        if risk_score >= 90:
            action = "hold_payout"
        elif risk_score >= 70:
            action = "review"
        else:
            action = "none"

        return await self.risk_repo.create(
            order_id=order_id,
            risk_score=risk_score,
            flags=flags,
            action_taken=action,
        )

    async def list_flagged_orders(
        self, offset: int = 0, limit: int = 20,
    ) -> tuple[list[OrderRiskFlag], int]:
        return await self.risk_repo.list_flagged(offset=offset, limit=limit)

    async def review_risk_flag(
        self, admin_id: str, flag_id: str, action: str,
    ) -> OrderRiskFlag:
        flag = await self.risk_repo.get_or_404(flag_id)
        return await self.risk_repo.update(
            flag_id,
            action_taken=action,
            reviewed_by=admin_id,
            reviewed_at=datetime.now(timezone.utc),
        )
