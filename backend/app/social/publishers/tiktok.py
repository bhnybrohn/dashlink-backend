"""TikTok Content Posting API publisher — connect accounts and publish photos."""

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

import httpx

from app.config import settings

TIKTOK_AUTH_BASE = "https://open.tiktokapis.com/v2"


@dataclass(frozen=True)
class TikTokAccountInfo:
    """Resolved TikTok account info."""

    open_id: str
    display_name: str
    avatar_url: str | None
    access_token: str
    refresh_token: str
    token_expires_at: datetime | None


class TikTokPublisher:
    """Handles TikTok OAuth connection and photo publishing via Content Posting API."""

    async def exchange_code(self, code: str, redirect_uri: str | None = None) -> TikTokAccountInfo:
        """Exchange authorization code for tokens and fetch user info.

        Flow:
        1. Exchange code for access_token + refresh_token
        2. Fetch user info (open_id, display_name, avatar)
        """
        uri = redirect_uri or settings.tiktok_redirect_uri

        async with httpx.AsyncClient(timeout=30) as client:
            # Step 1: Exchange code for tokens
            token_resp = await client.post(
                f"{TIKTOK_AUTH_BASE}/oauth/token/",
                data={
                    "client_key": settings.tiktok_client_key,
                    "client_secret": settings.tiktok_client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()

            # TikTok can return HTTP 200 with an error body instead of token data
            if "access_token" not in token_data:
                err_desc = token_data.get("data", {}).get("description", "Unknown error")
                raise RuntimeError(f"TikTok authorization failed: {err_desc}")

            access_token = token_data["access_token"]
            refresh_token = token_data["refresh_token"]
            open_id = token_data["open_id"]
            expires_in = token_data.get("expires_in")
            token_expires_at = (
                datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                if expires_in
                else None
            )

            # Step 2: Fetch user info
            user_resp = await client.get(
                f"{TIKTOK_AUTH_BASE}/user/info/",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"fields": "open_id,display_name,avatar_url"},
            )
            user_resp.raise_for_status()
            user_data = user_resp.json().get("data", {}).get("user", {})

            return TikTokAccountInfo(
                open_id=open_id,
                display_name=user_data.get("display_name", ""),
                avatar_url=user_data.get("avatar_url"),
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires_at=token_expires_at,
            )

    async def publish_photo(
        self,
        *,
        access_token: str,
        image_url: str,
        caption: str,
    ) -> dict:
        """Publish a photo to TikTok via Content Posting API.

        Uses the direct post (PULL_FROM_URL) flow for photo posts.

        Returns: {"publish_id": str}
        """
        async with httpx.AsyncClient(timeout=60) as client:
            # Initialize photo post — TikTok pulls the image from the URL
            init_resp = await client.post(
                f"{TIKTOK_AUTH_BASE}/post/publish/content/init/",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "post_info": {
                        "title": caption[:150],  # TikTok title limit
                        "description": caption,
                        "disable_comment": False,
                        "privacy_level": "PUBLIC_TO_EVERYONE",
                    },
                    "source_info": {
                        "source": "PULL_FROM_URL",
                        "photo_images": [image_url],
                    },
                    "post_mode": "DIRECT_POST",
                    "media_type": "PHOTO",
                },
            )
            init_resp.raise_for_status()
            init_data = init_resp.json().get("data", {})
            publish_id = init_data.get("publish_id", "")

            return {"publish_id": publish_id}

    async def check_publish_status(
        self, *, access_token: str, publish_id: str,
    ) -> dict:
        """Check the status of a TikTok post."""
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{TIKTOK_AUTH_BASE}/post/publish/status/fetch/",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json={"publish_id": publish_id},
            )
            resp.raise_for_status()
            return resp.json().get("data", {})
