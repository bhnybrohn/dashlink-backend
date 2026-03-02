"""Shared Protocols — abstractions for third-party services (SOLID: D + I).

Modules depend on these Protocols, never on concrete implementations.
This enables easy testing (mock implementations) and gateway swapping.
"""

from decimal import Decimal
from typing import Any, Protocol, runtime_checkable


# ── Payment Gateway ──


@runtime_checkable
class PaymentGateway(Protocol):
    """Abstract payment gateway — Stripe, Paystack, Flutterwave all implement this."""

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
        """Create a payment checkout session. Returns session data with redirect URL."""
        ...

    async def verify_webhook(
        self,
        *,
        payload: bytes,
        headers: dict[str, str],
    ) -> dict[str, Any]:
        """Verify and parse a webhook event. Raises on invalid signature."""
        ...

    async def refund(
        self,
        *,
        payment_ref: str,
        amount: Decimal | None = None,
    ) -> dict[str, Any]:
        """Issue a full or partial refund."""
        ...


# ── Notification Channel ──


@runtime_checkable
class NotificationChannel(Protocol):
    """Abstract notification sender — Email, SMS, WhatsApp, Push."""

    async def send(
        self,
        *,
        recipient: str,
        subject: str | None = None,
        template: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Send a notification. Returns delivery status/ID."""
        ...


# ── Storage Backend ──


@runtime_checkable
class StorageBackend(Protocol):
    """Abstract file storage — S3, R2, local filesystem."""

    async def upload(
        self,
        *,
        file_data: bytes,
        key: str,
        content_type: str,
    ) -> str:
        """Upload a file. Returns the public URL."""
        ...

    async def delete(self, *, key: str) -> None:
        """Delete a file by key."""
        ...

    def get_public_url(self, key: str) -> str:
        """Get the public URL for a stored file."""
        ...


# ── AI Provider ──


@runtime_checkable
class AIProvider(Protocol):
    """Abstract AI provider — OpenAI, Anthropic, etc."""

    async def generate_text(
        self,
        *,
        prompt: str,
        system_prompt: str | None = None,
        max_tokens: int = 500,
        temperature: float = 0.7,
    ) -> str:
        """Generate text from a prompt. Returns generated text."""
        ...

    async def generate_image(
        self,
        *,
        prompt: str,
        size: str = "1024x1024",
        quality: str = "standard",
    ) -> bytes:
        """Generate an image from a prompt. Returns image bytes."""
        ...
