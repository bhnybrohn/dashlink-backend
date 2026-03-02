"""Paystack payment gateway — implements PaymentGateway Protocol."""

import hashlib
import hmac
from decimal import Decimal
from typing import Any

import httpx

from app.config import settings
from app.core.exceptions import BadRequestError, PaymentError

PAYSTACK_BASE_URL = "https://api.paystack.co"


class PaystackGateway:
    """Paystack implementation of the PaymentGateway Protocol."""

    def __init__(self) -> None:
        self._secret_key = settings.paystack_secret_key
        self._headers = {
            "Authorization": f"Bearer {self._secret_key}",
            "Content-Type": "application/json",
        }

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
        """Initialize a Paystack transaction."""
        # Paystack expects amount in smallest currency unit (kobo for NGN)
        amount_kobo = int(amount * 100)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PAYSTACK_BASE_URL}/transaction/initialize",
                headers=self._headers,
                json={
                    "email": customer_email,
                    "amount": amount_kobo,
                    "currency": currency.upper(),
                    "callback_url": success_url,
                    "metadata": {**(metadata or {}), "order_id": order_id, "cancel_url": cancel_url},
                },
            )

        data = response.json()
        if not data.get("status"):
            raise PaymentError(detail=f"Paystack error: {data.get('message', 'Unknown error')}")

        return {
            "url": data["data"]["authorization_url"],
            "payment_ref": data["data"]["reference"],
            "gateway_session_id": data["data"]["access_code"],
        }

    async def verify_webhook(
        self, *, payload: bytes, headers: dict[str, str],
    ) -> dict[str, Any]:
        """Verify Paystack webhook HMAC-SHA512 signature."""
        signature = headers.get("x-paystack-signature", "")
        expected = hmac.new(
            self._secret_key.encode(), payload, hashlib.sha512,
        ).hexdigest()

        if not hmac.compare_digest(signature, expected):
            raise BadRequestError(detail="Invalid Paystack webhook signature")

        import json
        event = json.loads(payload)
        return {
            "event_type": event.get("event"),
            "data": event.get("data", {}),
            "gateway_ref": event.get("data", {}).get("reference"),
        }

    async def refund(
        self, *, payment_ref: str, amount: Decimal | None = None,
    ) -> dict[str, Any]:
        """Create a Paystack refund."""
        body: dict = {"transaction": payment_ref}
        if amount is not None:
            body["amount"] = int(amount * 100)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PAYSTACK_BASE_URL}/refund",
                headers=self._headers,
                json=body,
            )

        data = response.json()
        if not data.get("status"):
            raise PaymentError(detail=f"Paystack refund error: {data.get('message')}")

        return {"refund_id": data["data"]["id"], "status": data["data"]["status"]}
