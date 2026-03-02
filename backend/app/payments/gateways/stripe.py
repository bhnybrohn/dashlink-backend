"""Stripe payment gateway — implements PaymentGateway Protocol."""

import hmac
import hashlib
from decimal import Decimal
from typing import Any

import stripe

from app.config import settings
from app.core.exceptions import BadRequestError, PaymentError


class StripeGateway:
    """Stripe implementation of the PaymentGateway Protocol."""

    def __init__(self) -> None:
        stripe.api_key = settings.stripe_secret_key

    async def create_checkout_session(
        self,
        *,
        order_id: str,
        amount: Decimal,
        currency: str,
        customer_email: str,
        success_url: str,
        cancel_url: str,
        metadata: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        """Create a Stripe Checkout session."""
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[{
                    "price_data": {
                        "currency": currency.lower(),
                        "unit_amount": int(amount * 100),
                        "product_data": {"name": f"Order {order_id}"},
                    },
                    "quantity": 1,
                }],
                mode="payment",
                customer_email=customer_email,
                success_url=success_url,
                cancel_url=cancel_url,
                metadata={**(metadata or {}), "order_id": order_id},
            )
            return {
                "url": session.url,
                "payment_ref": session.id,
                "gateway_session_id": session.id,
            }
        except stripe.StripeError as e:
            raise PaymentError(detail=f"Stripe error: {e.user_message or str(e)}")

    async def verify_webhook(
        self, *, payload: bytes, headers: dict[str, str],
    ) -> dict[str, Any]:
        """Verify Stripe webhook signature and return event data."""
        sig = headers.get("stripe-signature", "")
        try:
            event = stripe.Webhook.construct_event(
                payload, sig, settings.stripe_webhook_secret,
            )
            return {
                "event_type": event["type"],
                "data": event["data"]["object"],
                "gateway_ref": event["data"]["object"].get("id"),
            }
        except (stripe.SignatureVerificationError, ValueError) as e:
            raise BadRequestError(detail=f"Invalid webhook signature: {e}")

    async def refund(
        self, *, payment_ref: str, amount: Decimal | None = None,
    ) -> dict[str, Any]:
        """Issue a Stripe refund."""
        try:
            params: dict = {"payment_intent": payment_ref}
            if amount is not None:
                params["amount"] = int(amount * 100)
            refund = stripe.Refund.create(**params)
            return {"refund_id": refund.id, "status": refund.status}
        except stripe.StripeError as e:
            raise PaymentError(detail=f"Stripe refund error: {e.user_message or str(e)}")
