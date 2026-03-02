"""Studio module tests — generation tracking, usage limits, tier enforcement."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.sellers.models import SellerProfile
from app.studio.models import StudioGeneration
from app.studio.service import StudioService
from app.users.models import User


async def _create_seller(
    db_session: AsyncSession, *, tier: str = "free",
) -> tuple[User, SellerProfile, str]:
    """Helper: create a seller user + profile."""
    user = User(
        email="studio@test.com",
        hashed_password=hash_password("pass12345678"),
        role="seller",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.flush()
    await db_session.refresh(user)

    profile = SellerProfile(
        user_id=user.id,
        store_name="Studio Store",
        slug="studiostore",
        subscription_tier=tier,
    )
    db_session.add(profile)
    await db_session.flush()
    await db_session.refresh(profile)

    token = create_access_token({"sub": user.id, "role": "seller", "email": user.email})
    return user, profile, token


class TestStudioGenerationTracking:
    """Tests for generation record creation and status tracking."""

    async def test_generate_title_records_generation(self, db_session: AsyncSession):
        """Title generation creates a StudioGeneration record."""
        _, profile, _ = await _create_seller(db_session)
        await db_session.commit()

        mock_ai = AsyncMock()
        mock_ai.generate_text = AsyncMock(return_value="Cool Product\nAmazing Item\nBest Deal")

        svc = StudioService(db_session, ai_client=mock_ai)
        gen = await svc.generate_title(
            profile.id, "free",
            category="beauty", keywords=["lipstick", "matte"],
        )

        assert gen.generation_type == "title"
        assert gen.status == "completed"
        assert gen.seller_id == profile.id
        assert gen.output_data is not None
        assert len(gen.output_data["titles"]) == 3

    async def test_generate_description_records_generation(self, db_session: AsyncSession):
        _, profile, _ = await _create_seller(db_session)
        await db_session.commit()

        mock_ai = AsyncMock()
        mock_ai.generate_text = AsyncMock(return_value="A beautiful matte lipstick for everyday wear.")

        svc = StudioService(db_session, ai_client=mock_ai)
        gen = await svc.generate_description(
            profile.id, "free",
            title="Red Lipstick", category="beauty", tone="professional",
        )

        assert gen.generation_type == "description"
        assert gen.status == "completed"
        assert "lipstick" in gen.output_data["description"].lower()

    async def test_generate_caption_records_generation(self, db_session: AsyncSession):
        _, profile, _ = await _create_seller(db_session)
        await db_session.commit()

        mock_ai = AsyncMock()
        mock_ai.generate_text = AsyncMock(return_value="Get this amazing product! #beauty #style")

        svc = StudioService(db_session, ai_client=mock_ai)
        gen = await svc.generate_caption(
            profile.id, "free",
            product_name="Red Lipstick", platform="instagram",
        )

        assert gen.generation_type == "caption"
        assert gen.status == "completed"

    async def test_failed_generation_records_error(self, db_session: AsyncSession):
        """When AI call fails, generation is marked as failed."""
        _, profile, _ = await _create_seller(db_session)
        await db_session.commit()

        mock_ai = AsyncMock()
        mock_ai.generate_text = AsyncMock(side_effect=RuntimeError("API error"))

        svc = StudioService(db_session, ai_client=mock_ai)
        gen = await svc.generate_title(profile.id, "free", category="beauty")

        assert gen.status == "failed"
        assert "API error" in gen.output_data["error"]

    async def test_no_ai_client_raises_error(self, db_session: AsyncSession):
        """Calling generation without AI client configured raises BadRequestError."""
        _, profile, _ = await _create_seller(db_session)
        await db_session.commit()

        svc = StudioService(db_session, ai_client=None)
        with pytest.raises(Exception, match="AI client not configured"):
            await svc.generate_title(profile.id, "free", category="beauty")


class TestStudioUsageLimits:
    """Tests for tier-based usage limits."""

    async def test_free_tier_limit_enforced(self, db_session: AsyncSession):
        """Free tier should be limited to 10 title generations per month."""
        _, profile, _ = await _create_seller(db_session)
        await db_session.commit()

        # Pre-fill 10 title generations
        for i in range(10):
            gen = StudioGeneration(
                seller_id=profile.id,
                generation_type="title",
                input_data={"category": "test"},
                status="completed",
            )
            db_session.add(gen)
        await db_session.flush()
        await db_session.commit()

        mock_ai = AsyncMock()
        mock_ai.generate_text = AsyncMock(return_value="New Title")

        svc = StudioService(db_session, ai_client=mock_ai)
        with pytest.raises(Exception, match="limit"):
            await svc.generate_title(profile.id, "free", category="beauty")

    async def test_pro_tier_unlimited_text(self, db_session: AsyncSession):
        """Pro tier should allow unlimited text generations."""
        _, profile, _ = await _create_seller(db_session, tier="pro")
        await db_session.commit()

        # Pre-fill many title generations
        for i in range(50):
            gen = StudioGeneration(
                seller_id=profile.id,
                generation_type="title",
                input_data={"category": "test"},
                status="completed",
            )
            db_session.add(gen)
        await db_session.flush()
        await db_session.commit()

        mock_ai = AsyncMock()
        mock_ai.generate_text = AsyncMock(return_value="Pro Title")

        svc = StudioService(db_session, ai_client=mock_ai)
        gen = await svc.generate_title(profile.id, "pro", category="beauty")
        assert gen.status == "completed"

    async def test_usage_report(self, db_session: AsyncSession):
        """Usage endpoint returns correct counts."""
        _, profile, _ = await _create_seller(db_session)
        await db_session.commit()

        # Add some generations
        for gen_type in ["title", "title", "description", "image"]:
            gen = StudioGeneration(
                seller_id=profile.id,
                generation_type=gen_type,
                input_data={},
                status="completed",
            )
            db_session.add(gen)
        await db_session.flush()
        await db_session.commit()

        svc = StudioService(db_session)
        usage = await svc.get_usage(profile.id, "free")

        assert usage["tier"] == "free"
        assert usage["usage"]["title"] == 2
        assert usage["usage"]["description"] == 1
        assert usage["usage"]["image"] == 1
        assert usage["limits"]["title"] == 10
        assert usage["limits"]["image"] == 5


class TestStudioListGenerations:
    """Tests for listing past generations."""

    async def test_list_seller_generations(self, db_session: AsyncSession):
        _, profile, _ = await _create_seller(db_session)
        await db_session.commit()

        for i in range(3):
            gen = StudioGeneration(
                seller_id=profile.id,
                generation_type="title",
                input_data={"i": i},
                status="completed",
            )
            db_session.add(gen)
        await db_session.flush()
        await db_session.commit()

        svc = StudioService(db_session)
        items, total = await svc.list_generations(profile.id)
        assert total == 3
        assert len(items) == 3
