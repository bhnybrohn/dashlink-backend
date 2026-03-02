"""Email notification channel — Resend integration."""

from pathlib import Path
from typing import Any

import resend

from app.config import settings

_TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"


class EmailChannel:
    """Send transactional emails via Resend."""

    def __init__(self) -> None:
        resend.api_key = settings.resend_api_key

    async def send(
        self,
        *,
        recipient: str,
        subject: str | None = None,
        template: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Send an email notification."""
        params: resend.Emails.SendParams = {
            "from": settings.resend_from_email,
            "to": [recipient],
            "subject": subject or "DashLink Notification",
            "html": self._render_template(template, context),
        }
        result = resend.Emails.send(params)
        return {"message_id": result.get("id"), "status": "sent"}

    @staticmethod
    def _render_template(template: str, context: dict[str, Any]) -> str:
        """Load an HTML template from disk and replace {{key}} placeholders."""
        template_path = _TEMPLATES_DIR / f"{template}.html"
        html = template_path.read_text(encoding="utf-8")
        for key, value in context.items():
            html = html.replace(f"{{{{{key}}}}}", str(value))
        return html
