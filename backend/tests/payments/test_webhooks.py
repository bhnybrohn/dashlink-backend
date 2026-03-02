"""Payment webhook tests — idempotent processing."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.orders.models import Order, OrderItem
from app.payments.models import Payment
from app.payments.service import PaymentService
from app.sellers.models import SellerProfile
from app.users.models import User
from app.core.security import hash_password


async def _setup_payment(db_session: AsyncSession) -> tuple[Order, Payment]:
    """Create a seller, order, and pending payment."""
    seller_user = User(
        email="seller@payment.com",
        hashed_password=hash_password("pass12345678"),
        role="seller",
        is_active=True,
    )
    db_session.add(seller_user)
    await db_session.flush()
    await db_session.refresh(seller_user)

    profile = SellerProfile(
        user_id=seller_user.id,
        store_name="Pay Store",
        slug="paystore",
    )
    db_session.add(profile)
    await db_session.flush()
    await db_session.refresh(profile)

    order = Order(
        order_number="DL-PAY00001",
        seller_id=profile.id,
        status="pending",
        subtotal=100.00,
        platform_fee=5.00,
        total_amount=100.00,
        currency="NGN",
        buyer_email="buyer@pay.com",
    )
    db_session.add(order)
    await db_session.flush()
    await db_session.refresh(order)

    payment = Payment(
        order_id=order.id,
        gateway="stripe",
        gateway_ref="cs_test_123",
        amount=100.00,
        currency="NGN",
        status="pending",
    )
    db_session.add(payment)
    await db_session.commit()
    await db_session.refresh(payment)

    return order, payment


class TestWebhookProcessing:
    """Tests for payment webhook service logic."""

    async def test_successful_payment_marks_order_paid(self, db_session: AsyncSession):
        order, payment = await _setup_payment(db_session)

        svc = PaymentService(db_session)
        result = await svc.process_webhook(
            gateway="stripe",
            event_type="checkout.session.completed",
            gateway_ref="cs_test_123",
            webhook_payload={"id": "cs_test_123"},
        )
        await db_session.commit()

        assert result is not None
        assert result.status == "success"

        # Order should be marked as paid
        await db_session.refresh(order)
        assert order.status == "paid"

    async def test_idempotent_webhook(self, db_session: AsyncSession):
        """Processing the same webhook twice should not fail."""
        order, payment = await _setup_payment(db_session)

        svc = PaymentService(db_session)

        # Process first time
        result1 = await svc.process_webhook(
            gateway="stripe",
            event_type="checkout.session.completed",
            gateway_ref="cs_test_123",
            webhook_payload={"id": "cs_test_123"},
        )
        await db_session.commit()

        # Process again — should be idempotent
        result2 = await svc.process_webhook(
            gateway="stripe",
            event_type="checkout.session.completed",
            gateway_ref="cs_test_123",
            webhook_payload={"id": "cs_test_123"},
        )
        await db_session.commit()

        assert result1 is not None
        assert result2 is not None
        assert result1.id == result2.id
        assert result2.status == "success"

    async def test_failed_payment(self, db_session: AsyncSession):
        order, payment = await _setup_payment(db_session)

        svc = PaymentService(db_session)
        result = await svc.process_webhook(
            gateway="stripe",
            event_type="payment_intent.payment_failed",
            gateway_ref="cs_test_123",
            webhook_payload={"id": "cs_test_123", "failure_reason": "card_declined"},
        )
        await db_session.commit()

        assert result is not None
        assert result.status == "failed"

    async def test_unknown_ref_returns_none(self, db_session: AsyncSession):
        await _setup_payment(db_session)

        svc = PaymentService(db_session)
        result = await svc.process_webhook(
            gateway="stripe",
            event_type="checkout.session.completed",
            gateway_ref="cs_unknown_ref",
            webhook_payload={},
        )
        assert result is None
