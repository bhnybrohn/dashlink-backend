"""Social media service — connect accounts, post content, schedule."""

import base64
import hashlib
import secrets
from datetime import datetime, timezone
from urllib.parse import urlencode

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.encryption import decrypt_value, encrypt_value
from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.social.models import SocialAccount, SocialPost
from app.social.publishers.facebook import FacebookPublisher
from app.social.publishers.instagram import InstagramPublisher
from app.social.publishers.pinterest import PinterestPublisher
from app.social.publishers.tiktok import TikTokPublisher
from app.social.publishers.twitter import TwitterPublisher
from app.products.repository import ProductRepository
from app.social.repository import SocialAccountRepository, SocialPostRepository
from app.social.schemas import ProductPostCreate, SocialConnectRequest, SocialPostCreate


class SocialService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.account_repo = SocialAccountRepository(session)
        self.post_repo = SocialPostRepository(session)
        self.product_repo = ProductRepository(session)

    # ── OAuth URL Generation ──

    @staticmethod
    def _generate_pkce() -> tuple[str, str]:
        code_verifier = secrets.token_urlsafe(64)[:128]
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        return code_verifier, code_challenge

    @staticmethod
    def get_connect_url(platform: str) -> dict:
        """Build the OAuth authorization URL for connecting a social publishing account."""
        state = secrets.token_urlsafe(32)
        result: dict = {"platform": platform, "state": state}

        if platform == "instagram":
            params = {
                "client_id": settings.instagram_app_id,
                "redirect_uri": settings.instagram_redirect_uri,
                "response_type": "code",
                "scope": "instagram_basic,instagram_content_publish,pages_show_list,pages_read_engagement",
                "state": state,
            }
            result["url"] = f"https://www.facebook.com/v19.0/dialog/oauth?{urlencode(params)}"

        elif platform == "tiktok":
            params = {
                "client_key": settings.tiktok_client_key,
                "redirect_uri": settings.tiktok_redirect_uri,
                "response_type": "code",
                "scope": "user.info.basic,video.publish",
                "state": state,
            }
            result["url"] = f"https://www.tiktok.com/v2/auth/authorize/?{urlencode(params)}"

        elif platform == "facebook":
            params = {
                "client_id": settings.facebook_oauth_client_id,
                "redirect_uri": settings.facebook_social_redirect_uri or settings.facebook_oauth_redirect_uri,
                "response_type": "code",
                "scope": "pages_show_list,pages_read_engagement,pages_manage_posts,publish_to_groups",
                "state": state,
            }
            result["url"] = f"https://www.facebook.com/v19.0/dialog/oauth?{urlencode(params)}"

        elif platform == "twitter":
            code_verifier, code_challenge = SocialService._generate_pkce()
            params = {
                "client_id": settings.twitter_oauth_client_id,
                "redirect_uri": settings.twitter_social_redirect_uri or settings.twitter_oauth_redirect_uri,
                "response_type": "code",
                "scope": "tweet.write tweet.read users.read offline.access",
                "state": state,
                "code_challenge": code_challenge,
                "code_challenge_method": "S256",
            }
            result["url"] = f"https://x.com/i/oauth2/authorize?{urlencode(params)}"
            result["code_verifier"] = code_verifier

        elif platform == "pinterest":
            params = {
                "client_id": settings.pinterest_app_id,
                "redirect_uri": settings.pinterest_redirect_uri,
                "response_type": "code",
                "scope": "boards:read,pins:read,pins:write,user_accounts:read",
                "state": state,
            }
            result["url"] = f"https://www.pinterest.com/oauth/?{urlencode(params)}"

        else:
            raise BadRequestError(detail=f"Unsupported platform: {platform}")

        return result

    # ── Account Connection ──

    async def connect_instagram(
        self, seller_id: str, data: SocialConnectRequest,
    ) -> SocialAccount:
        """Connect an Instagram Business Account via Facebook OAuth."""
        # Check if already connected
        existing = await self.account_repo.get_by_seller_and_platform(seller_id, "instagram")
        if existing:
            raise ConflictError(detail="Instagram account is already connected")

        publisher = InstagramPublisher()
        try:
            info = await publisher.exchange_code(data.code, redirect_uri=data.redirect_uri)
        except Exception as e:
            raise BadRequestError(detail=f"Failed to connect Instagram: {e}")

        account = await self.account_repo.create(
            seller_id=seller_id,
            platform="instagram",
            platform_user_id=info.ig_user_id,
            platform_username=info.username,
            access_token_encrypted=encrypt_value(info.access_token),
            refresh_token_encrypted=(
                encrypt_value(info.page_access_token) if info.page_access_token else None
            ),
            token_expires_at=info.token_expires_at,
            account_metadata={
                "ig_user_id": info.ig_user_id,
                "page_id": info.page_id,
                "page_access_token_encrypted": encrypt_value(info.page_access_token),
            },
        )
        await self.session.commit()
        return account

    async def connect_tiktok(
        self, seller_id: str, data: SocialConnectRequest,
    ) -> SocialAccount:
        """Connect a TikTok account via TikTok Login Kit."""
        existing = await self.account_repo.get_by_seller_and_platform(seller_id, "tiktok")
        if existing:
            raise ConflictError(detail="TikTok account is already connected")

        publisher = TikTokPublisher()
        try:
            info = await publisher.exchange_code(data.code, redirect_uri=data.redirect_uri)
        except Exception as e:
            raise BadRequestError(detail=f"Failed to connect TikTok: {e}")

        account = await self.account_repo.create(
            seller_id=seller_id,
            platform="tiktok",
            platform_user_id=info.open_id,
            platform_username=info.display_name,
            access_token_encrypted=encrypt_value(info.access_token),
            refresh_token_encrypted=(
                encrypt_value(info.refresh_token) if info.refresh_token else None
            ),
            token_expires_at=info.token_expires_at,
            account_metadata={
                "open_id": info.open_id,
                "avatar_url": info.avatar_url,
            },
        )
        await self.session.commit()
        return account

    async def connect_facebook(
        self, seller_id: str, data: SocialConnectRequest,
    ) -> SocialAccount:
        """Connect a Facebook Page for publishing."""
        existing = await self.account_repo.get_by_seller_and_platform(seller_id, "facebook")
        if existing:
            raise ConflictError(detail="Facebook account is already connected")

        publisher = FacebookPublisher()
        try:
            info = await publisher.exchange_code(data.code, redirect_uri=data.redirect_uri)
        except Exception as e:
            raise BadRequestError(detail=f"Failed to connect Facebook: {e}")

        account = await self.account_repo.create(
            seller_id=seller_id,
            platform="facebook",
            platform_user_id=info.page_id,
            platform_username=info.page_name,
            access_token_encrypted=encrypt_value(info.user_access_token),
            refresh_token_encrypted=None,
            token_expires_at=info.token_expires_at,
            account_metadata={
                "page_id": info.page_id,
                "page_name": info.page_name,
                "page_access_token_encrypted": encrypt_value(info.page_access_token),
            },
        )
        await self.session.commit()
        return account

    async def connect_twitter(
        self, seller_id: str, data: SocialConnectRequest,
    ) -> SocialAccount:
        """Connect a Twitter/X account for publishing."""
        existing = await self.account_repo.get_by_seller_and_platform(seller_id, "twitter")
        if existing:
            raise ConflictError(detail="Twitter account is already connected")

        publisher = TwitterPublisher()
        try:
            info = await publisher.exchange_code(
                data.code, code_verifier=data.code_verifier, redirect_uri=data.redirect_uri,
            )
        except Exception as e:
            raise BadRequestError(detail=f"Failed to connect Twitter: {e}")

        account = await self.account_repo.create(
            seller_id=seller_id,
            platform="twitter",
            platform_user_id=info.user_id,
            platform_username=info.username,
            access_token_encrypted=encrypt_value(info.access_token),
            refresh_token_encrypted=(
                encrypt_value(info.refresh_token) if info.refresh_token else None
            ),
            token_expires_at=info.token_expires_at,
            account_metadata={
                "user_id": info.user_id,
                "username": info.username,
            },
        )
        await self.session.commit()
        return account

    async def connect_pinterest(
        self, seller_id: str, data: SocialConnectRequest,
    ) -> SocialAccount:
        """Connect a Pinterest account for Pin publishing."""
        existing = await self.account_repo.get_by_seller_and_platform(seller_id, "pinterest")
        if existing:
            raise ConflictError(detail="Pinterest account is already connected")

        publisher = PinterestPublisher()
        try:
            info = await publisher.exchange_code(data.code, redirect_uri=data.redirect_uri)
        except Exception as e:
            raise BadRequestError(detail=f"Failed to connect Pinterest: {e}")

        account = await self.account_repo.create(
            seller_id=seller_id,
            platform="pinterest",
            platform_user_id=info.user_id,
            platform_username=info.username,
            access_token_encrypted=encrypt_value(info.access_token),
            refresh_token_encrypted=(
                encrypt_value(info.refresh_token) if info.refresh_token else None
            ),
            token_expires_at=info.token_expires_at,
            account_metadata={
                "user_id": info.user_id,
                "username": info.username,
                "profile_image": info.profile_image,
                "default_board_id": info.default_board_id,
                "default_board_name": info.default_board_name,
            },
        )
        await self.session.commit()
        return account

    async def disconnect_account(self, seller_id: str, platform: str) -> None:
        """Disconnect a social media account."""
        account = await self.account_repo.get_by_seller_and_platform(seller_id, platform)
        if not account:
            raise NotFoundError(resource="social_account", resource_id=platform)
        await self.account_repo.soft_delete(account.id)
        await self.session.commit()

    async def list_accounts(self, seller_id: str) -> list[SocialAccount]:
        """List all connected social accounts for a seller."""
        return await self.account_repo.get_all_for_seller(seller_id)

    # ── Posting ──

    async def create_post(
        self, seller_id: str, data: SocialPostCreate,
    ) -> SocialPost:
        """Create a social media post — immediate or scheduled."""
        account = await self.account_repo.get(data.social_account_id)
        if not account or account.seller_id != seller_id:
            raise BadRequestError(detail="Social account not found or not owned by you")
        if account.deleted_at is not None:
            raise BadRequestError(detail="Social account has been disconnected")

        status = "scheduled" if data.scheduled_at else "pending"

        post = await self.post_repo.create(
            seller_id=seller_id,
            social_account_id=account.id,
            product_id=data.product_id,
            platform=account.platform,
            post_type=data.post_type,
            caption=data.caption,
            image_url=data.image_url,
            link_url=data.link_url,
            status=status,
            scheduled_at=data.scheduled_at,
        )
        await self.session.commit()

        # If no scheduling, publish immediately
        if status == "pending":
            await self.publish_post(post.id)

        return await self.post_repo.get_or_404(post.id)

    @staticmethod
    def _build_product_caption(
        product, seller_slug: str, include_link: bool = True,
    ) -> str:
        """Auto-generate a social caption from product data."""
        lines = [product.name]
        lines.append(f"{product.currency} {product.price:,.0f}")
        if product.description:
            lines.append("")
            lines.append(product.description[:300])
        if include_link:
            lines.append("")
            lines.append(f"Shop now → https://dashlink.to/{seller_slug}/{product.slug}")
        return "\n".join(lines)

    async def create_product_post(
        self, seller_id: str, seller_slug: str, data: ProductPostCreate,
    ) -> SocialPost:
        """Post a product directly — auto-resolves image and caption from product data."""
        # Validate social account
        account = await self.account_repo.get(data.social_account_id)
        if not account or account.seller_id != seller_id:
            raise BadRequestError(detail="Social account not found or not owned by you")
        if account.deleted_at is not None:
            raise BadRequestError(detail="Social account has been disconnected")

        # Fetch product with images
        product = await self.product_repo.get_with_relations(data.product_id)
        if not product or product.seller_id != seller_id:
            raise BadRequestError(detail="Product not found or not owned by you")
        if product.status != "active":
            raise BadRequestError(detail="Only active products can be posted")
        if not product.images:
            raise BadRequestError(detail="Product has no images. Add at least one image before posting.")

        # Auto-resolve image and caption
        image_url = product.images[0].url
        caption = data.caption or self._build_product_caption(
            product, seller_slug, include_link=data.include_link,
        )

        # Build product link for link posts
        link_url = f"https://dashlink.to/{seller_slug}/{product.slug}" if data.post_type == "link" else None

        status = "scheduled" if data.scheduled_at else "pending"

        post = await self.post_repo.create(
            seller_id=seller_id,
            social_account_id=account.id,
            product_id=product.id,
            platform=account.platform,
            post_type=data.post_type,
            caption=caption,
            image_url=image_url,
            link_url=link_url,
            status=status,
            scheduled_at=data.scheduled_at,
        )
        await self.session.commit()

        if status == "pending":
            # For Instagram with multiple images, store all URLs for carousel
            all_image_urls = [img.url for img in product.images]
            await self.publish_post(post.id, product_image_urls=all_image_urls)

        return await self.post_repo.get_or_404(post.id)

    async def publish_post(self, post_id: str, *, product_image_urls: list[str] | None = None) -> SocialPost:
        """Actually publish a post to the platform API."""
        post = await self.post_repo.get_or_404(post_id)
        account = await self.account_repo.get_or_404(post.social_account_id)

        # Mark as publishing
        post = await self.post_repo.update(post.id, status="publishing")

        try:
            if post.platform == "instagram":
                result = await self._publish_instagram(account, post, image_urls=product_image_urls)
            elif post.platform == "tiktok":
                result = await self._publish_tiktok(account, post)
            elif post.platform == "facebook":
                result = await self._publish_facebook(account, post)
            elif post.platform == "twitter":
                result = await self._publish_twitter(account, post)
            elif post.platform == "pinterest":
                result = await self._publish_pinterest(account, post)
            else:
                raise BadRequestError(detail=f"Unsupported platform: {post.platform}")

            post = await self.post_repo.update(
                post.id,
                status="published",
                platform_post_id=result.get("id") or result.get("publish_id"),
                platform_post_url=result.get("permalink"),
                published_at=datetime.now(timezone.utc),
            )
        except Exception as e:
            post = await self.post_repo.update(
                post.id,
                status="failed",
                error_message=str(e)[:500],
            )

        await self.session.commit()
        return post

    async def _publish_instagram(
        self, account: SocialAccount, post: SocialPost,
        *, image_urls: list[str] | None = None,
    ) -> dict:
        """Publish to Instagram — carousel if multiple images, single photo otherwise."""
        metadata = account.account_metadata or {}
        ig_user_id = metadata.get("ig_user_id", account.platform_user_id)
        page_token_enc = metadata.get("page_access_token_encrypted")

        if not page_token_enc:
            raise BadRequestError(detail="Instagram page access token not found")

        page_access_token = decrypt_value(page_token_enc)
        publisher = InstagramPublisher()

        # Use carousel for multiple product images
        if image_urls and len(image_urls) > 1:
            return await publisher.publish_carousel(
                ig_user_id=ig_user_id,
                page_access_token=page_access_token,
                image_urls=image_urls,
                caption=post.caption,
            )

        return await publisher.publish_photo(
            ig_user_id=ig_user_id,
            page_access_token=page_access_token,
            image_url=post.image_url,
            caption=post.caption,
        )

    async def _publish_tiktok(
        self, account: SocialAccount, post: SocialPost,
    ) -> dict:
        """Publish a photo to TikTok."""
        access_token = decrypt_value(account.access_token_encrypted)

        publisher = TikTokPublisher()
        return await publisher.publish_photo(
            access_token=access_token,
            image_url=post.image_url,
            caption=post.caption,
        )

    async def _publish_facebook(
        self, account: SocialAccount, post: SocialPost,
    ) -> dict:
        """Publish content to Facebook (Page or profile)."""
        metadata = account.account_metadata or {}
        page_token_enc = metadata.get("page_access_token_encrypted")
        user_access_token = decrypt_value(account.access_token_encrypted)

        publisher = FacebookPublisher()

        # Prefer publishing to Page if page token is available
        if page_token_enc:
            page_access_token = decrypt_value(page_token_enc)
            page_id = metadata.get("page_id", account.platform_user_id)
            return await publisher.publish_to_page(
                page_id=page_id,
                page_access_token=page_access_token,
                post_type=post.post_type,
                caption=post.caption,
                image_url=post.image_url,
                link_url=post.link_url,
            )

        # Fallback to personal profile
        return await publisher.publish_to_profile(
            user_access_token=user_access_token,
            post_type=post.post_type,
            caption=post.caption,
            image_url=post.image_url,
            link_url=post.link_url,
        )

    async def _publish_twitter(
        self, account: SocialAccount, post: SocialPost,
    ) -> dict:
        """Publish a tweet to Twitter/X."""
        access_token = decrypt_value(account.access_token_encrypted)

        publisher = TwitterPublisher()

        if post.post_type == "photo" and post.image_url:
            return await publisher.publish_tweet_with_media(
                access_token=access_token,
                caption=post.caption,
                image_url=post.image_url,
                link_url=post.link_url,
            )

        return await publisher.publish_tweet(
            access_token=access_token,
            caption=post.caption,
            link_url=post.link_url,
        )

    async def _publish_pinterest(
        self, account: SocialAccount, post: SocialPost,
    ) -> dict:
        """Publish a Pin to Pinterest."""
        access_token = decrypt_value(account.access_token_encrypted)
        metadata = account.account_metadata or {}
        board_id = metadata.get("default_board_id")

        if not board_id:
            raise BadRequestError(detail="No Pinterest board found. Reconnect your Pinterest account.")

        publisher = PinterestPublisher()
        return await publisher.publish_pin(
            access_token=access_token,
            board_id=board_id,
            title=post.caption[:100] if post.caption else "",
            description=post.caption,
            image_url=post.image_url,
            link_url=post.link_url,
        )

    async def list_posts(
        self,
        seller_id: str,
        *,
        platform: str | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[SocialPost], int]:
        """List post history for a seller."""
        return await self.post_repo.list_by_seller(
            seller_id, platform=platform, status=status, offset=offset, limit=limit,
        )
