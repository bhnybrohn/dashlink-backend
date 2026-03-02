"""Push notification channel — Firebase Cloud Messaging."""

from typing import Any

from app.config import settings


class PushChannel:
    """Send push notifications via Firebase Cloud Messaging."""

    def __init__(self) -> None:
        self._initialized = False

    def _ensure_init(self) -> None:
        """Lazily initialize Firebase Admin SDK."""
        if self._initialized:
            return
        if not settings.firebase_credentials_path:
            return
        try:
            import firebase_admin
            from firebase_admin import credentials

            if not firebase_admin._apps:
                cred = credentials.Certificate(settings.firebase_credentials_path)
                firebase_admin.initialize_app(cred)
            self._initialized = True
        except Exception:
            pass

    async def send(
        self,
        *,
        recipient: str,
        subject: str | None = None,
        template: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        """Send a push notification to a device token.

        `recipient` is the FCM device token.
        """
        self._ensure_init()

        try:
            from firebase_admin import messaging

            message = messaging.Message(
                notification=messaging.Notification(
                    title=subject or context.get("title", "DashLink"),
                    body=context.get("body", ""),
                ),
                data={k: str(v) for k, v in context.items() if k not in ("title", "body")},
                token=recipient,
            )
            response = messaging.send(message)
            return {"message_id": response, "status": "sent"}
        except Exception as e:
            return {"error": str(e), "status": "failed"}
