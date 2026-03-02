"""Flutterwave payment gateway — implements PaymentGateway Protocol."""

import hashlib
import hmac
from decimal import Decimal
from typing import Any

import httpx

from app.config import settings
from app.core.exceptions import BadRequestError, PaymentError

FLUTTERWAVE_BASE_URL = "https://api.flutterwave.com/v3"


class FlutterwaveGateway:
    """Flutterwave implementation of the PaymentGateway Protocol."""

    def __init__(self) -> None:
        self._secret_key = settings.flutterwave_secret_key
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
        """Create a Flutterwave payment link."""
        tx_ref = f"dl_{order_id}"

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{FLUTTERWAVE_BASE_URL}/payments",
                headers=self._headers,
                json={
                    "tx_ref": tx_ref,
                    "amount": str(amount),
                    "currency": currency.upper(),
                    "redirect_url": success_url,
                    "customer": {"email": customer_email},
                    "meta": {**(metadata or {}), "order_id": order_id},
                    "customizations": {"title": "DashLink Payment"},
                },
            )

        data = response.json()
        if data.get("status") != "success":
            raise PaymentError(
                detail=f"Flutterwave error: {data.get('message', 'Unknown error')}",
            )

        return {
            "url": data["data"]["link"],
            "payment_ref": tx_ref,
            "gateway_session_id": None,
        }

    async def verify_webhook(
        self, *, payload: bytes, headers: dict[str, str],
    ) -> dict[str, Any]:
        """Verify Flutterwave webhook signature."""
        signature = headers.get("verif-hash", "")
        if signature != settings.flutterwave_webhook_secret:
            raise BadRequestError(detail="Invalid Flutterwave webhook signature")

        import json
        event = json.loads(payload)
        return {
            "event_type": event.get("event"),
            "data": event.get("data", {}),
            "gateway_ref": event.get("data", {}).get("tx_ref"),
        }

    async def refund(
        self, *, payment_ref: str, amount: Decimal | None = None,
    ) -> dict[str, Any]:
        """Create a Flutterwave refund."""
        # Flutterwave requires the transaction ID for refunds
        body: dict = {}
        if amount is not None:
            body["amount"] = str(amount)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{FLUTTERWAVE_BASE_URL}/transactions/{payment_ref}/refund",
                headers=self._headers,
                json=body,
            )

        data = response.json()
        if data.get("status") != "success":
            raise PaymentError(
                detail=f"Flutterwave refund error: {data.get('message')}",
            )

        return {"refund_id": data["data"]["id"], "status": data["data"]["status"]}
