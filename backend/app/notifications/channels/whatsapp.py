"""WhatsApp notification channel — Twilio integration."""

from typing import Any

from app.config import settings


class WhatsAppChannel:
    """Send WhatsApp messages via Twilio."""

    def __init__(self) -> None:
        self._client = None

    def _ensure_client(self):
        if self._client is None:
            from twilio.rest import Client
            self._client = Client(settings.twilio_account_sid, settings.twilio_auth_token)

    async def send(
        self,
        *,
        recipient: str,
        subject: str | None = None,
        template: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Send a WhatsApp message.

        `recipient` should be the phone number in E.164 format (e.g. +234...).
        """
        self._ensure_client()

        body = self._render_template(template, context)

        message = self._client.messages.create(
            from_=f"whatsapp:{settings.twilio_whatsapp_from}",
            to=f"whatsapp:{recipient}",
            body=body,
        )
        return {"message_sid": message.sid, "status": message.status}

    @staticmethod
    def _render_template(template: str, context: dict[str, Any]) -> str:
        """Simple template rendering."""
        text = _TEMPLATES.get(template, template)
        for key, value in context.items():
            text = text.replace(f"{{{{{key}}}}}", str(value))
        return text


_TEMPLATES: dict[str, str] = {
    "order_confirmed": (
        "Hi {{buyer_name}}! Your order {{order_number}} has been confirmed. "
        "Total: {{currency}} {{total_amount}}. We'll notify you when it ships!"
    ),
    "order_shipped": (
        "Great news! Your order {{order_number}} has shipped. "
        "Tracking: {{tracking_number}}"
    ),
    "order_delivered": (
        "Your order {{order_number}} has been delivered. "
        "We hope you love it! Please leave a review."
    ),
    "new_order_seller": (
        "New order received! Order {{order_number}} for {{currency}} {{total_amount}}. "
        "Please pack and ship it promptly."
    ),
}
