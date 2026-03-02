"""OAuth provider clients — token exchange and user info fetching."""

import logging
from dataclasses import dataclass

import httpx

from app.config import settings
from app.core.exceptions import BadRequestError

logger = logging.getLogger("dashlink.oauth")


@dataclass(frozen=True)
class OAuthUserInfo:
    """Normalized user info from any OAuth provider."""

    provider: str
    provider_user_id: str
    email: str | None
    name: str | None
    picture_url: str | None
    access_token: str
    refresh_token: str | None
    expires_in: int | None  # seconds until access_token expires
    raw_data: dict | None = None  # full provider response for extra checks


class GoogleOAuthClient:
    """Google OAuth 2.0 token exchange and user info fetching."""

    TOKEN_URL = "https://oauth2.googleapis.com/token"
    USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

    async def exchange_code(self, code: str) -> OAuthUserInfo:
        async with httpx.AsyncClient(timeout=15.0) as client:
            token_resp = await client.post(
                self.TOKEN_URL,
                data={
                    "code": code,
                    "client_id": settings.google_oauth_client_id,
                    "client_secret": settings.google_oauth_client_secret,
                    "redirect_uri": settings.google_oauth_redirect_uri,
                    "grant_type": "authorization_code",
                },
            )

        if token_resp.status_code != 200:
            logger.error("Google token exchange failed: %s %s", token_resp.status_code, token_resp.text)
            raise BadRequestError(detail="Failed to exchange Google authorization code")

        token_data = token_resp.json()
        logger.info("Google token response: %s", token_data)
        access_token = token_data["access_token"]

        async with httpx.AsyncClient(timeout=10.0) as client:
            info_resp = await client.get(
                self.USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
            )

        if info_resp.status_code != 200:
            logger.error("Google userinfo failed: %s %s", info_resp.status_code, info_resp.text)
            raise BadRequestError(detail="Failed to fetch Google user info")

        info = info_resp.json()
        logger.info("Google userinfo response: %s", info)
        return OAuthUserInfo(
            provider="google",
            provider_user_id=info["id"],
            email=info.get("email"),
            name=info.get("name"),
            picture_url=info.get("picture"),
            access_token=access_token,
            refresh_token=token_data.get("refresh_token"),
            expires_in=token_data.get("expires_in"),
            raw_data=info,
        )


class FacebookOAuthClient:
    """Facebook/Meta OAuth 2.0 — covers both Facebook and Instagram accounts."""

    TOKEN_URL = "https://graph.facebook.com/v19.0/oauth/access_token"
    USERINFO_URL = "https://graph.facebook.com/v19.0/me"

    async def exchange_code(self, code: str) -> OAuthUserInfo:
        async with httpx.AsyncClient(timeout=15.0) as client:
            token_resp = await client.get(
                self.TOKEN_URL,
                params={
                    "code": code,
                    "client_id": settings.facebook_oauth_client_id,
                    "client_secret": settings.facebook_oauth_client_secret,
                    "redirect_uri": settings.facebook_oauth_redirect_uri,
                },
            )

        if token_resp.status_code != 200:
            logger.error("Facebook token exchange failed: %s %s", token_resp.status_code, token_resp.text)
            raise BadRequestError(detail="Failed to exchange Facebook authorization code")

        token_data = token_resp.json()
        access_token = token_data["access_token"]

        async with httpx.AsyncClient(timeout=10.0) as client:
            info_resp = await client.get(
                self.USERINFO_URL,
                params={
                    "fields": "id,name,email,picture.type(large)",
                    "access_token": access_token,
                },
            )

        if info_resp.status_code != 200:
            logger.error("Facebook userinfo failed: %s %s", info_resp.status_code, info_resp.text)
            raise BadRequestError(detail="Failed to fetch Facebook user info")

        info = info_resp.json()
        picture_url = info.get("picture", {}).get("data", {}).get("url")

        return OAuthUserInfo(
            provider="facebook",
            provider_user_id=info["id"],
            email=info.get("email"),
            name=info.get("name"),
            picture_url=picture_url,
            access_token=access_token,
            refresh_token=None,  # Facebook doesn't issue refresh tokens
            expires_in=token_data.get("expires_in"),
            raw_data=info,
        )


class TwitterOAuthClient:
    """Twitter/X OAuth 2.0 with PKCE."""

    TOKEN_URL = "https://api.x.com/2/oauth2/token"
    USERINFO_URL = "https://api.x.com/2/users/me"

    async def exchange_code(
        self, code: str, code_verifier: str | None = None,
    ) -> OAuthUserInfo:
        token_payload: dict[str, str] = {
            "code": code,
            "client_id": settings.twitter_oauth_client_id,
            "redirect_uri": settings.twitter_oauth_redirect_uri,
            "grant_type": "authorization_code",
        }
        if code_verifier:
            token_payload["code_verifier"] = code_verifier

        async with httpx.AsyncClient(timeout=15.0) as client:
            token_resp = await client.post(
                self.TOKEN_URL,
                data=token_payload,
                auth=(settings.twitter_oauth_client_id, settings.twitter_oauth_client_secret),
            )

        if token_resp.status_code != 200:
            logger.error("Twitter token exchange failed: %s %s", token_resp.status_code, token_resp.text)
            raise BadRequestError(detail="Failed to exchange Twitter authorization code")

        token_data = token_resp.json()
        logger.info("Twitter token response: %s", token_data)
        access_token = token_data["access_token"]

        async with httpx.AsyncClient(timeout=10.0) as client:
            info_resp = await client.get(
                self.USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                params={"user.fields": "id,name,username,profile_image_url,created_at,verified,public_metrics"},
            )

        if info_resp.status_code != 200:
            logger.error("Twitter userinfo failed: %s %s", info_resp.status_code, info_resp.text)
            raise BadRequestError(detail="Failed to fetch Twitter user info")

        logger.info("Twitter userinfo response: %s", info_resp.json())
        info = info_resp.json().get("data", {})

        return OAuthUserInfo(
            provider="twitter",
            provider_user_id=info["id"],
            email=None,  # Twitter does not return email by default
            name=info.get("name"),
            picture_url=info.get("profile_image_url"),
            access_token=access_token,
            refresh_token=token_data.get("refresh_token"),
            raw_data=info,
            expires_in=token_data.get("expires_in"),
        )


class TikTokOAuthClient:
    """TikTok OAuth 2.0 — uses client_key instead of client_id."""

    TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
    USERINFO_URL = "https://open.tiktokapis.com/v2/user/info/"

    async def exchange_code(self, code: str) -> OAuthUserInfo:
        async with httpx.AsyncClient(timeout=15.0) as client:
            token_resp = await client.post(
                self.TOKEN_URL,
                data={
                    "client_key": settings.tiktok_client_key,
                    "client_secret": settings.tiktok_client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": settings.tiktok_redirect_uri,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )

        if token_resp.status_code != 200:
            logger.error("TikTok token exchange failed: %s %s", token_resp.status_code, token_resp.text)
            raise BadRequestError(detail="Failed to exchange TikTok authorization code")

        token_data = token_resp.json()
        logger.info("TikTok token response: %s", token_data)

        # TikTok can return HTTP 200 with an error body instead of token data
        if "access_token" not in token_data:
            err_desc = token_data.get("data", {}).get("description", "Unknown error")
            err_msg = token_data.get("message", "")
            logger.error("TikTok token exchange returned error: %s — %s", err_msg, err_desc)
            raise BadRequestError(detail=f"TikTok authorization failed: {err_desc}")

        access_token = token_data["access_token"]
        open_id = token_data.get("open_id", "")

        async with httpx.AsyncClient(timeout=10.0) as client:
            info_resp = await client.get(
                self.USERINFO_URL,
                headers={"Authorization": f"Bearer {access_token}"},
                params={"fields": "open_id,union_id,avatar_url,display_name"},
            )

        if info_resp.status_code != 200:
            logger.error("TikTok userinfo failed: %s %s", info_resp.status_code, info_resp.text)
            raise BadRequestError(detail="Failed to fetch TikTok user info")

        resp_json = info_resp.json()
        logger.info("TikTok userinfo response: %s", resp_json)
        info = resp_json.get("data", {}).get("user", {})

        return OAuthUserInfo(
            provider="tiktok",
            provider_user_id=info.get("open_id", open_id),
            email=None,  # TikTok does not provide email
            name=info.get("display_name"),
            picture_url=info.get("avatar_url"),
            access_token=access_token,
            refresh_token=token_data.get("refresh_token"),
            expires_in=token_data.get("expires_in"),
            raw_data=info,
        )


# ── Provider Registry ──

_PROVIDERS: dict[str, GoogleOAuthClient | FacebookOAuthClient | TwitterOAuthClient | TikTokOAuthClient] = {
    "google": GoogleOAuthClient(),
    "facebook": FacebookOAuthClient(),
    "twitter": TwitterOAuthClient(),
    "tiktok": TikTokOAuthClient(),
}


def get_oauth_client(
    provider: str,
) -> GoogleOAuthClient | FacebookOAuthClient | TwitterOAuthClient | TikTokOAuthClient:
    """Get the OAuth client for a given provider."""
    client = _PROVIDERS.get(provider)
    if client is None:
        raise BadRequestError(detail=f"Unsupported OAuth provider: {provider}")
    return client
