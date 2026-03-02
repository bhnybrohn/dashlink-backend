"""Twitter/X API publisher — connect accounts and publish tweets."""

import base64
import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

import httpx

from app.config import settings

TWITTER_API_V2 = "https://api.x.com/2"
TWITTER_UPLOAD_V1 = "https://upload.twitter.com/1.1"


@dataclass(frozen=True)
class TwitterAccountInfo:
    """Resolved Twitter account info for publishing."""

    user_id: str
    username: str
    access_token: str
    refresh_token: str | None
    token_expires_at: datetime | None


class TwitterPublisher:
    """Handles Twitter OAuth 2.0 connection and tweet publishing."""

    @staticmethod
    def generate_pkce() -> tuple[str, str]:
        """Generate PKCE code_verifier and S256 code_challenge."""
        code_verifier = secrets.token_urlsafe(64)[:128]
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        return code_verifier, code_challenge

    async def exchange_code(
        self, code: str, code_verifier: str | None = None, redirect_uri: str | None = None,
    ) -> TwitterAccountInfo:
        """Exchange authorization code for tokens and fetch user info.

        Flow:
        1. Exchange code for access_token + refresh_token (OAuth 2.0 with PKCE)
        2. Fetch user info (id, username)
        """
        uri = redirect_uri or settings.twitter_social_redirect_uri

        token_payload: dict[str, str] = {
            "code": code,
            "client_id": settings.twitter_oauth_client_id,
            "redirect_uri": uri,
            "grant_type": "authorization_code",
        }
        if code_verifier:
            token_payload["code_verifier"] = code_verifier

        async with httpx.AsyncClient(timeout=30) as client:
            # Step 1: Exchange code for tokens
            token_resp = await client.post(
                f"{TWITTER_API_V2}/oauth2/token",
                data=token_payload,
                auth=(settings.twitter_oauth_client_id, settings.twitter_oauth_client_secret),
            )
            token_resp.raise_for_status()
            token_data = token_resp.json()

            access_token = token_data["access_token"]
            refresh_token = token_data.get("refresh_token")
            expires_in = token_data.get("expires_in")
            token_expires_at = (
                datetime.now(timezone.utc) + timedelta(seconds=expires_in)
                if expires_in
                else None
            )

            # Step 2: Fetch user info
            user_resp = await client.get(
                f"{TWITTER_API_V2}/users/me",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"user.fields": "id,username,name,profile_image_url"},
            )
            user_resp.raise_for_status()
            user_data = user_resp.json().get("data", {})

            return TwitterAccountInfo(
                user_id=user_data["id"],
                username=user_data.get("username", ""),
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires_at=token_expires_at,
            )

    async def publish_tweet(
        self,
        *,
        access_token: str,
        caption: str,
        link_url: str | None = None,
    ) -> dict:
        """Publish a text or link tweet.

        Returns: {"id": tweet_id, "permalink": url}
        """
        text = caption
        if link_url:
            text = f"{caption}\n{link_url}"

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{TWITTER_API_V2}/tweets",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json={"text": text},
            )
            resp.raise_for_status()
            data = resp.json().get("data", {})
            tweet_id = data.get("id", "")

            return {
                "id": tweet_id,
                "permalink": f"https://x.com/i/status/{tweet_id}" if tweet_id else None,
            }

    async def publish_tweet_with_media(
        self,
        *,
        access_token: str,
        caption: str,
        image_url: str,
        link_url: str | None = None,
    ) -> dict:
        """Upload an image and publish a tweet with it.

        Uses v1.1 media upload endpoint, then attaches to v2 tweet.

        Returns: {"id": tweet_id, "permalink": url}
        """
        async with httpx.AsyncClient(timeout=60) as client:
            # Step 1: Download the image
            img_resp = await client.get(image_url)
            img_resp.raise_for_status()
            image_bytes = img_resp.content

            # Step 2: Upload media via v1.1 (uses OAuth 2.0 Bearer token)
            upload_resp = await client.post(
                f"{TWITTER_UPLOAD_V1}/media/upload.json",
                headers={"Authorization": f"Bearer {access_token}"},
                files={"media_data": (None, base64.b64encode(image_bytes).decode())},
            )
            upload_resp.raise_for_status()
            media_id = upload_resp.json().get("media_id_string", "")

            # Step 3: Create tweet with media
            text = caption
            if link_url:
                text = f"{caption}\n{link_url}"

            tweet_resp = await client.post(
                f"{TWITTER_API_V2}/tweets",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json={
                    "text": text,
                    "media": {"media_ids": [media_id]},
                },
            )
            tweet_resp.raise_for_status()
            data = tweet_resp.json().get("data", {})
            tweet_id = data.get("id", "")

            return {
                "id": tweet_id,
                "permalink": f"https://x.com/i/status/{tweet_id}" if tweet_id else None,
            }
