"""Dispute service — open, respond, escalate, resolve."""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ConflictError, ForbiddenError, NotFoundError
from app.disputes.models import Dispute
from app.disputes.repository import DisputeRepository
from app.disputes.schemas import DisputeCreate, DisputeResolve, DisputeRespond
from app.orders.models import Order


class DisputeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.dispute_repo = DisputeRepository(session)

    async def open_dispute(self, buyer_id: str, data: DisputeCreate) -> Dispute:
        """Buyer opens a dispute on a delivered order."""
        from app.orders.repository import OrderRepository
        order_repo = OrderRepository(self.session)

        order = await order_repo.get(data.order_id)
        if not order:
            raise NotFoundError(resource="order", resource_id=data.order_id)

        if order.status != "delivered":
            raise BadRequestError(detail="Disputes can only be opened on delivered orders")

        existing = await self.dispute_repo.get_by_order(data.order_id)
        if existing:
            raise ConflictError(detail="A dispute already exists for this order")

        dispute = await self.dispute_repo.create(
            order_id=data.order_id,
            initiated_by=buyer_id,
            seller_id=order.seller_id,
            reason=data.reason,
            description=data.description,
            status="open",
        )
        await self.session.commit()
        return dispute

    async def get_dispute(self, dispute_id: str) -> Dispute:
        return await self.dispute_repo.get_or_404(dispute_id)

    async def list_disputes(
        self, user_id: str, role: str,
        *, status: str | None = None, offset: int = 0, limit: int = 20,
    ) -> tuple[list[Dispute], int]:
        """List disputes based on role (buyer, seller, admin)."""
        if role == "admin":
            filters: dict = {}
            if status:
                filters["status"] = status
            return await self.dispute_repo.list(
                offset=offset, limit=limit, filters=filters if filters else None,
            )
        elif role == "seller":
            return await self.dispute_repo.list_by_seller(
                user_id, status=status, offset=offset, limit=limit,
            )
        else:
            return await self.dispute_repo.list_by_buyer(user_id, offset=offset, limit=limit)

    async def seller_respond(
        self, seller_id: str, dispute_id: str, data: DisputeRespond,
    ) -> Dispute:
        """Seller responds to a dispute."""
        dispute = await self.dispute_repo.get_or_404(dispute_id)
        if dispute.seller_id != seller_id:
            raise ForbiddenError(detail="This dispute belongs to another seller")
        if dispute.status not in ("open", "escalated"):
            raise BadRequestError(detail=f"Cannot respond to a '{dispute.status}' dispute")

        return await self.dispute_repo.update(
            dispute_id,
            seller_response=data.response,
            status="seller_responded",
        )

    async def escalate(self, buyer_id: str, dispute_id: str) -> Dispute:
        """Buyer escalates a dispute for admin review."""
        dispute = await self.dispute_repo.get_or_404(dispute_id)
        if dispute.initiated_by != buyer_id:
            raise ForbiddenError(detail="Only the dispute initiator can escalate")
        if dispute.status not in ("open", "seller_responded"):
            raise BadRequestError(detail=f"Cannot escalate a '{dispute.status}' dispute")

        return await self.dispute_repo.update(dispute_id, status="escalated")

    async def resolve(
        self, admin_id: str, dispute_id: str, data: DisputeResolve,
    ) -> Dispute:
        """Admin resolves a dispute."""
        dispute = await self.dispute_repo.get_or_404(dispute_id)
        if dispute.status in ("resolved", "closed"):
            raise BadRequestError(detail="Dispute is already resolved")

        return await self.dispute_repo.update(
            dispute_id,
            status="resolved",
            resolution=data.resolution,
            admin_notes=data.admin_notes,
            resolved_at=datetime.now(timezone.utc),
            resolved_by=admin_id,
        )
