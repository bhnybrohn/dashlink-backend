"""Instagram Graph API publisher — connect accounts and publish photos."""

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

import httpx

from app.config import settings

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"


@dataclass(frozen=True)
class InstagramAccountInfo:
    """Resolved Instagram Business Account info."""

    ig_user_id: str
    username: str
    page_id: str
    page_access_token: str
    access_token: str
    token_expires_at: datetime | None


class InstagramPublisher:
    """Handles Instagram OAuth connection and photo publishing via Meta Graph API."""

    async def exchange_code(self, code: str, redirect_uri: str | None = None) -> InstagramAccountInfo:
        """Exchange authorization code for tokens and resolve IG Business Account.

        Flow:
        1. Exchange code for short-lived user access token
        2. Exchange for long-lived token (60 days)
        3. Fetch user's Facebook Pages
        4. Find the Page linked to an Instagram Business Account
        """
        uri = redirect_uri or settings.instagram_redirect_uri

        async with httpx.AsyncClient(timeout=30) as client:
            # Step 1: Exchange code for short-lived token
            token_resp = await client.get(
                f"{GRAPH_API_BASE}/oauth/access_token",
                params={
                    "client_id": settings.instagram_app_id,
                    "client_secret": settings.instagram_app_secret,
                    "redirect_uri": uri,
                    "code": code,
                },
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()
            short_token = token_data["access_token"]

            # Step 2: Exchange for long-lived token (60 days)
            long_resp = await client.get(
                f"{GRAPH_API_BASE}/oauth/access_token",
                params={
                    "grant_type": "fb_exchange_token",
                    "client_id": settings.instagram_app_id,
                    "client_secret": settings.instagram_app_secret,
                    "fb_exchange_token": short_token,
                },
            )
            long_resp.raise_for_status()
            long_data = long_resp.json()
            long_token = long_data["access_token"]
            expires_in = long_data.get("expires_in")
            token_expires_at = (
                datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                if expires_in
                else None
            )

            # Step 3: Fetch user's Facebook Pages
            pages_resp = await client.get(
                f"{GRAPH_API_BASE}/me/accounts",
                params={"access_token": long_token},
            )
            pages_resp.raise_for_status()
            pages = pages_resp.json().get("data", [])

            if not pages:
                raise ValueError("No Facebook Pages found. A Page linked to an Instagram Business Account is required.")

            # Step 4: Find IG Business Account linked to a Page
            for page in pages:
                ig_resp = await client.get(
                    f"{GRAPH_API_BASE}/{page['id']}",
                    params={
                        "fields": "instagram_business_account{id,username}",
                        "access_token": page["access_token"],
                    },
                )
                ig_resp.raise_for_status()
                ig_data = ig_resp.json()
                ig_account = ig_data.get("instagram_business_account")

                if ig_account:
                    return InstagramAccountInfo(
                        ig_user_id=ig_account["id"],
                        username=ig_account.get("username", ""),
                        page_id=page["id"],
                        page_access_token=page["access_token"],
                        access_token=long_token,
                        token_expires_at=token_expires_at,
                    )

            raise ValueError(
                "No Instagram Business Account found linked to your Facebook Pages. "
                "Please connect an Instagram Professional account to a Facebook Page first."
            )

    async def publish_photo(
        self,
        *,
        ig_user_id: str,
        page_access_token: str,
        image_url: str,
        caption: str,
    ) -> dict:
        """Publish a photo to Instagram.

        1. Create a media container with image_url + caption
        2. Publish the container

        Returns: {"id": platform_post_id, "permalink": url}
        """
        async with httpx.AsyncClient(timeout=60) as client:
            # Step 1: Create media container
            container_resp = await client.post(
                f"{GRAPH_API_BASE}/{ig_user_id}/media",
                data={
                    "image_url": image_url,
                    "caption": caption,
                    "access_token": page_access_token,
                },
            )
            container_resp.raise_for_status()
            creation_id = container_resp.json()["id"]

            # Wait briefly for container processing
            await asyncio.sleep(2)

            # Step 2: Publish the container
            publish_resp = await client.post(
                f"{GRAPH_API_BASE}/{ig_user_id}/media_publish",
                data={
                    "creation_id": creation_id,
                    "access_token": page_access_token,
                },
            )
            publish_resp.raise_for_status()
            post_id = publish_resp.json()["id"]

            # Step 3: Get permalink
            permalink_resp = await client.get(
                f"{GRAPH_API_BASE}/{post_id}",
                params={
                    "fields": "permalink",
                    "access_token": page_access_token,
                },
            )
            permalink = None
            if permalink_resp.status_code == 200:
                permalink = permalink_resp.json().get("permalink")

            return {"id": post_id, "permalink": permalink}
