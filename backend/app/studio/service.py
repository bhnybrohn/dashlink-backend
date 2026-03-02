"""Studio service — orchestrates AI generation with usage tracking and tier limits."""

from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, UsageLimitError
from app.core.protocols import StorageBackend
from app.integrations.openai_client import OpenAIClient
from app.integrations.removebg_client import RemoveBgClient
from app.studio import prompts
from app.studio.models import StudioGeneration
from app.studio.repository import StudioGenerationRepository

# Usage limits per subscription tier
_TIER_LIMITS: dict[str, dict[str, int | float]] = {
    "free": {
        "title": 10, "description": 10, "caption": 10,
        "image": 5, "background_removal": 5,
    },
    "pro": {
        "title": float("inf"), "description": float("inf"), "caption": float("inf"),
        "image": 30, "background_removal": 50,
    },
    "business": {
        "title": float("inf"), "description": float("inf"), "caption": float("inf"),
        "image": float("inf"), "background_removal": float("inf"),
    },
}


class StudioService:
    def __init__(
        self,
        session: AsyncSession,
        ai_client: OpenAIClient | None = None,
        removebg_client: RemoveBgClient | None = None,
        storage: StorageBackend | None = None,
    ) -> None:
        self.session = session
        self.repo = StudioGenerationRepository(session)
        self.ai = ai_client
        self.removebg = removebg_client
        self.storage = storage

    async def _check_limit(self, seller_id: str, tier: str, gen_type: str) -> None:
        """Check if the seller has remaining quota for this generation type."""
        limits = _TIER_LIMITS.get(tier, _TIER_LIMITS["free"])
        limit = limits.get(gen_type, 0)
        if limit == float("inf"):
            return
        current = await self.repo.count_monthly_usage(seller_id, gen_type)
        if current >= int(limit):
            raise UsageLimitError(feature=gen_type, limit=int(limit))

    async def _record(
        self,
        seller_id: str,
        gen_type: str,
        input_data: dict,
        *,
        product_id: str | None = None,
    ) -> StudioGeneration:
        """Create a generation record in 'processing' status."""
        return await self.repo.create(
            seller_id=seller_id,
            product_id=product_id,
            generation_type=gen_type,
            input_data=input_data,
            status="processing",
        )

    async def _complete(
        self, gen: StudioGeneration, output: dict, model: str, tokens: int = 0,
    ) -> StudioGeneration:
        """Mark generation as completed."""
        return await self.repo.update(
            gen.id,
            output_data=output,
            status="completed",
            ai_model=model,
            tokens_used=tokens,
        )

    async def _fail(self, gen: StudioGeneration, error: str) -> StudioGeneration:
        return await self.repo.update(
            gen.id, output_data={"error": error}, status="failed",
        )

    # ── Title Generation ──

    async def generate_title(
        self,
        seller_id: str,
        tier: str,
        *,
        category: str | None = None,
        keywords: list[str] | None = None,
        image_url: str | None = None,
        product_id: str | None = None,
    ) -> StudioGeneration:
        await self._check_limit(seller_id, tier, "title")
        if not self.ai:
            raise BadRequestError(detail="AI client not configured")

        prompt = prompts.build_title_prompt(category, keywords or [], image_url)
        gen = await self._record(
            seller_id, "title",
            {"category": category, "keywords": keywords, "image_url": image_url},
            product_id=product_id,
        )
        try:
            result = await self.ai.generate_text(
                prompt=prompt, system_prompt=prompts.TITLE_SYSTEM, max_tokens=200,
            )
            titles = [t.strip() for t in result.strip().split("\n") if t.strip()]
            return await self._complete(gen, {"titles": titles}, "gpt-4o-mini")
        except Exception as e:
            return await self._fail(gen, str(e))

    # ── Description Generation ──

    async def generate_description(
        self,
        seller_id: str,
        tier: str,
        *,
        title: str,
        category: str | None = None,
        tone: str = "professional",
        image_url: str | None = None,
        product_id: str | None = None,
    ) -> StudioGeneration:
        await self._check_limit(seller_id, tier, "description")
        if not self.ai:
            raise BadRequestError(detail="AI client not configured")

        prompt = prompts.build_description_prompt(title, category, tone, image_url)
        gen = await self._record(
            seller_id, "description",
            {"title": title, "category": category, "tone": tone},
            product_id=product_id,
        )
        try:
            result = await self.ai.generate_text(
                prompt=prompt, system_prompt=prompts.DESCRIPTION_SYSTEM, max_tokens=500,
            )
            return await self._complete(gen, {"description": result.strip()}, "gpt-4o-mini")
        except Exception as e:
            return await self._fail(gen, str(e))

    # ── Caption Generation ──

    async def generate_caption(
        self,
        seller_id: str,
        tier: str,
        *,
        product_name: str,
        platform: str = "instagram",
        tone: str = "casual",
        product_id: str | None = None,
    ) -> StudioGeneration:
        await self._check_limit(seller_id, tier, "caption")
        if not self.ai:
            raise BadRequestError(detail="AI client not configured")

        prompt = prompts.build_caption_prompt(product_name, platform, tone)
        gen = await self._record(
            seller_id, "caption",
            {"product_name": product_name, "platform": platform, "tone": tone},
            product_id=product_id,
        )
        try:
            result = await self.ai.generate_text(
                prompt=prompt, system_prompt=prompts.CAPTION_SYSTEM, max_tokens=300,
            )
            return await self._complete(gen, {"caption": result.strip()}, "gpt-4o-mini")
        except Exception as e:
            return await self._fail(gen, str(e))

    # ── Image Generation ──

    async def generate_image(
        self,
        seller_id: str,
        tier: str,
        *,
        prompt: str,
        style: str = "product-photo",
        product_id: str | None = None,
    ) -> StudioGeneration:
        await self._check_limit(seller_id, tier, "image")
        if not self.ai:
            raise BadRequestError(detail="AI client not configured")
        if not self.storage:
            raise BadRequestError(detail="Storage backend not configured")

        full_prompt = prompts.build_image_prompt(prompt, style)
        gen = await self._record(
            seller_id, "image",
            {"prompt": prompt, "style": style},
            product_id=product_id,
        )
        try:
            image_bytes = await self.ai.generate_image(prompt=full_prompt)
            key = f"studio/{seller_id}/{gen.id}.png"
            url = await self.storage.upload(
                file_data=image_bytes, key=key, content_type="image/png",
            )
            return await self._complete(gen, {"image_url": url}, "dall-e-3")
        except Exception as e:
            return await self._fail(gen, str(e))

    # ── Background Removal ──

    async def remove_background(
        self,
        seller_id: str,
        tier: str,
        *,
        image_url: str,
        product_id: str | None = None,
    ) -> StudioGeneration:
        await self._check_limit(seller_id, tier, "background_removal")
        if not self.removebg:
            raise BadRequestError(detail="Remove.bg client not configured")
        if not self.storage:
            raise BadRequestError(detail="Storage backend not configured")

        gen = await self._record(
            seller_id, "background_removal",
            {"image_url": image_url},
            product_id=product_id,
        )
        try:
            processed = await self.removebg.remove_background_from_url(image_url)
            key = f"studio/{seller_id}/{gen.id}_nobg.png"
            url = await self.storage.upload(
                file_data=processed, key=key, content_type="image/png",
            )
            return await self._complete(gen, {"image_url": url}, "removebg")
        except Exception as e:
            return await self._fail(gen, str(e))

    # ── Full Product Enhance ──

    async def enhance_product(
        self,
        seller_id: str,
        tier: str,
        *,
        product_id: str,
        category: str | None = None,
        tone: str = "professional",
    ) -> dict[str, StudioGeneration]:
        """Generate title + description + caption in one call."""
        title_gen = await self.generate_title(
            seller_id, tier, category=category, product_id=product_id,
        )
        # Use the first generated title for description + caption
        title_text = ""
        if title_gen.output_data and title_gen.output_data.get("titles"):
            title_text = title_gen.output_data["titles"][0]

        desc_gen = await self.generate_description(
            seller_id, tier, title=title_text or "Product",
            category=category, tone=tone, product_id=product_id,
        )
        caption_gen = await self.generate_caption(
            seller_id, tier, product_name=title_text or "Product",
            product_id=product_id,
        )
        return {"title": title_gen, "description": desc_gen, "caption": caption_gen}

    # ── Queries ──

    async def get_generation(self, generation_id: str) -> StudioGeneration:
        return await self.repo.get_or_404(generation_id)

    async def list_generations(
        self, seller_id: str, *, offset: int = 0, limit: int = 20,
    ) -> tuple[list[StudioGeneration], int]:
        return await self.repo.list_by_seller(seller_id, offset=offset, limit=limit)

    async def get_usage(self, seller_id: str, tier: str) -> dict:
        """Get current month usage vs tier limits."""
        usage = await self.repo.get_all_monthly_usage(seller_id)
        limits = _TIER_LIMITS.get(tier, _TIER_LIMITS["free"])
        now = datetime.now(timezone.utc)
        return {
            "tier": tier,
            "month": now.strftime("%Y-%m"),
            "usage": usage,
            "limits": {k: "unlimited" if v == float("inf") else int(v) for k, v in limits.items()},
        }
