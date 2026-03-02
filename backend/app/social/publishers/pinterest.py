"""Pinterest API v5 publisher — connect accounts and publish Pins."""

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta

import httpx

from app.config import settings

PINTEREST_API_BASE = "https://api.pinterest.com/v5"
PINTEREST_AUTH_URL = "https://www.pinterest.com/oauth/"


@dataclass(frozen=True)
class PinterestAccountInfo:
    """Resolved Pinterest account info for publishing."""

    user_id: str
    username: str
    profile_image: str | None
    access_token: str
    refresh_token: str | None
    token_expires_at: datetime | None
    default_board_id: str | None
    default_board_name: str | None


class PinterestPublisher:
    """Handles Pinterest OAuth connection and Pin publishing via API v5."""

    async def exchange_code(self, code: str, redirect_uri: str | None = None) -> PinterestAccountInfo:
        """Exchange authorization code for tokens and fetch user + boards.

        Flow:
        1. POST /oauth/token with Basic auth (client_id:secret) + code
        2. GET /user_account for profile info
        3. GET /boards to fetch first board (used as default for publishing)
        """
        uri = redirect_uri or settings.pinterest_redirect_uri

        async with httpx.AsyncClient(timeout=30) as client:
            # Step 1: Exchange code for tokens
            token_resp = await client.post(
                f"{PINTEREST_API_BASE}/oauth/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": uri,
                },
                auth=(settings.pinterest_app_id, settings.pinterest_app_secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
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

            # Step 2: Fetch user profile
            user_resp = await client.get(
                f"{PINTEREST_API_BASE}/user_account",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            user_resp.raise_for_status()
            user_data = user_resp.json()

            # Step 3: Fetch boards to get the default publishing board
            boards_resp = await client.get(
                f"{PINTEREST_API_BASE}/boards",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"page_size": 1},
            )
            boards_resp.raise_for_status()
            boards = boards_resp.json().get("items", [])
            default_board = boards[0] if boards else None

            return PinterestAccountInfo(
                user_id=user_data.get("id", ""),
                username=user_data.get("username", ""),
                profile_image=user_data.get("profile_image"),
                access_token=access_token,
                refresh_token=refresh_token,
                token_expires_at=token_expires_at,
                default_board_id=default_board["id"] if default_board else None,
                default_board_name=default_board.get("name") if default_board else None,
            )

    async def publish_pin(
        self,
        *,
        access_token: str,
        board_id: str,
        title: str = "",
        description: str = "",
        image_url: str | None = None,
        link_url: str | None = None,
    ) -> dict:
        """Create a Pin on the specified board.

        Supports image pins (with optional link) and link pins (no image).
        Returns: {"id": pin_id, "permalink": url | None}
        """
        payload: dict = {
            "board_id": board_id,
            "title": title[:100] if title else "",
            "description": description[:500] if description else "",
        }

        if image_url:
            payload["media_source"] = {
                "source_type": "image_url",
                "url": image_url,
            }

        if link_url:
            payload["link"] = link_url

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{PINTEREST_API_BASE}/pins",
                json=payload,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
            )
            resp.raise_for_status()
            data = resp.json()
            pin_id = data.get("id", "")
            permalink = f"https://pinterest.com/pin/{pin_id}" if pin_id else None
            return {"id": pin_id, "permalink": permalink}
