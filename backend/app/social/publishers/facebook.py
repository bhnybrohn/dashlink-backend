"""Facebook Graph API publisher — connect accounts and publish content."""

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

import httpx

from app.config import settings

GRAPH_API_BASE = "https://graph.facebook.com/v19.0"


@dataclass(frozen=True)
class FacebookAccountInfo:
    """Resolved Facebook Page/profile info for publishing."""

    page_id: str
    page_name: str
    page_access_token: str
    user_access_token: str
    token_expires_at: datetime | None


class FacebookPublisher:
    """Handles Facebook OAuth connection and content publishing via Graph API."""

    async def exchange_code(self, code: str, redirect_uri: str | None = None) -> FacebookAccountInfo:
        """Exchange authorization code for tokens and resolve Facebook Page.

        Flow:
        1. Exchange code for short-lived user access token
        2. Exchange for long-lived token (60 days)
        3. Fetch user's Facebook Pages
        4. Return the first Page with its Page access token
        """
        uri = redirect_uri or settings.facebook_social_redirect_uri

        async with httpx.AsyncClient(timeout=30) as client:
            # Step 1: Exchange code for short-lived token
            token_resp = await client.get(
                f"{GRAPH_API_BASE}/oauth/access_token",
                params={
                    "client_id": settings.facebook_oauth_client_id,
                    "client_secret": settings.facebook_oauth_client_secret,
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
                    "client_id": settings.facebook_oauth_client_id,
                    "client_secret": settings.facebook_oauth_client_secret,
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
                raise ValueError(
                    "No Facebook Pages found. A Facebook Page is required for publishing."
                )

            # Use the first page (most common scenario for sellers)
            page = pages[0]
            return FacebookAccountInfo(
                page_id=page["id"],
                page_name=page.get("name", ""),
                page_access_token=page["access_token"],
                user_access_token=long_token,
                token_expires_at=token_expires_at,
            )

    async def publish_to_page(
        self,
        *,
        page_id: str,
        page_access_token: str,
        post_type: str = "photo",
        caption: str = "",
        image_url: str | None = None,
        link_url: str | None = None,
    ) -> dict:
        """Publish content to a Facebook Page.

        Returns: {"id": post_id, "permalink": url | None}
        """
        async with httpx.AsyncClient(timeout=60) as client:
            if post_type == "photo" and image_url:
                resp = await client.post(
                    f"{GRAPH_API_BASE}/{page_id}/photos",
                    data={
                        "url": image_url,
                        "caption": caption,
                        "access_token": page_access_token,
                    },
                )
            elif post_type == "link" and link_url:
                resp = await client.post(
                    f"{GRAPH_API_BASE}/{page_id}/feed",
                    data={
                        "message": caption,
                        "link": link_url,
                        "access_token": page_access_token,
                    },
                )
            else:
                # Text-only post
                resp = await client.post(
                    f"{GRAPH_API_BASE}/{page_id}/feed",
                    data={
                        "message": caption,
                        "access_token": page_access_token,
                    },
                )

            resp.raise_for_status()
            post_id = resp.json().get("id", "")

            # Try to get the permalink
            permalink = None
            if post_id:
                perm_resp = await client.get(
                    f"{GRAPH_API_BASE}/{post_id}",
                    params={
                        "fields": "permalink_url",
                        "access_token": page_access_token,
                    },
                )
                if perm_resp.status_code == 200:
                    permalink = perm_resp.json().get("permalink_url")

            return {"id": post_id, "permalink": permalink}

    async def publish_to_profile(
        self,
        *,
        user_access_token: str,
        post_type: str = "photo",
        caption: str = "",
        image_url: str | None = None,
        link_url: str | None = None,
    ) -> dict:
        """Publish content to the user's personal Facebook profile.

        Returns: {"id": post_id, "permalink": None}
        """
        async with httpx.AsyncClient(timeout=60) as client:
            if post_type == "photo" and image_url:
                resp = await client.post(
                    f"{GRAPH_API_BASE}/me/photos",
                    data={
                        "url": image_url,
                        "caption": caption,
                        "access_token": user_access_token,
                    },
                )
            elif post_type == "link" and link_url:
                resp = await client.post(
                    f"{GRAPH_API_BASE}/me/feed",
                    data={
                        "message": caption,
                        "link": link_url,
                        "access_token": user_access_token,
                    },
                )
            else:
                resp = await client.post(
                    f"{GRAPH_API_BASE}/me/feed",
                    data={
                        "message": caption,
                        "access_token": user_access_token,
                    },
                )

            resp.raise_for_status()
            post_id = resp.json().get("id", "")
            return {"id": post_id, "permalink": None}
