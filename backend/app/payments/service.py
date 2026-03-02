"""Payment service — webhook processing, idempotent payment recording, payouts."""

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, NotFoundError
from app.payments.models import Payment, Payout
from app.payments.repository import PaymentRepository, PayoutRepository


class PaymentService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.payment_repo = PaymentRepository(session)
        self.payout_repo = PayoutRepository(session)

    async def record_payment(
        self,
        *,
        order_id: str,
        gateway: str,
        gateway_ref: str,
        gateway_session_id: str | None,
        amount: Decimal,
        currency: str,
    ) -> Payment:
        """Create a pending payment record (idempotent on gateway_ref)."""
        existing = await self.payment_repo.get_by_gateway_ref(gateway_ref)
        if existing:
            return existing

        return await self.payment_repo.create(
            order_id=order_id,
            gateway=gateway,
            gateway_ref=gateway_ref,
            gateway_session_id=gateway_session_id,
            amount=float(amount),
            currency=currency,
            status="pending",
        )

    async def process_webhook(
        self,
        *,
        gateway: str,
        event_type: str,
        gateway_ref: str,
        webhook_payload: dict,
    ) -> Payment | None:
        """Process a verified webhook event. Idempotent — safe to replay."""
        payment = await self.payment_repo.get_by_gateway_ref(gateway_ref)
        if not payment:
            return None

        # Already processed — idempotent
        if payment.status == "success" and event_type in (
            "checkout.session.completed",
            "charge.success",
        ):
            return payment

        now = datetime.now(timezone.utc)

        if event_type in ("checkout.session.completed", "charge.success"):
            payment = await self.payment_repo.update(
                payment.id,
                status="success",
                webhook_verified_at=now,
                webhook_payload=webhook_payload,
            )
            # Update order status
            from app.orders.service import OrderService
            order_svc = OrderService(self.session)
            await order_svc.mark_paid(payment.order_id)

        elif event_type in ("payment_intent.payment_failed", "charge.failed"):
            payment = await self.payment_repo.update(
                payment.id,
                status="failed",
                webhook_verified_at=now,
                webhook_payload=webhook_payload,
            )

        elif event_type in ("charge.refunded", "refund.processed"):
            payment = await self.payment_repo.update(
                payment.id,
                status="refunded",
                webhook_verified_at=now,
                webhook_payload=webhook_payload,
            )

        return payment

    async def get_payment_by_order(self, order_id: str) -> Payment:
        """Get payment for an order."""
        payment = await self.payment_repo.get_by_order(order_id)
        if not payment:
            raise NotFoundError(resource="payment", resource_id=order_id)
        return payment

    async def list_seller_payouts(
        self, seller_id: str, *, offset: int = 0, limit: int = 20,
    ) -> tuple[list[Payout], int]:
        """List payouts for a seller."""
        return await self.payout_repo.list_by_seller(seller_id, offset=offset, limit=limit)
