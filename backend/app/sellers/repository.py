"""Seller profile repository."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import BaseRepository
from app.sellers.models import SellerProfile


class SellerProfileRepository(BaseRepository[SellerProfile]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(SellerProfile, session)

    async def get_by_slug(self, slug: str) -> SellerProfile | None:
        """Find a seller profile by storefront slug."""
        return await self.get_by(slug=slug)

    async def get_by_user_id(self, user_id: str) -> SellerProfile | None:
        """Find a seller profile by user ID."""
        return await self.get_by(user_id=user_id)

    async def increment_order_count(self, seller_id: str) -> None:
        """Increment total_orders (denormalized counter)."""
        profile = await self.get_or_404(seller_id)
        profile.total_orders += 1
        await self.session.flush()

    async def update_average_rating(self, seller_id: str, new_average: float) -> None:
        """Update the denormalized average rating."""
        await self.update(seller_id, average_rating=round(new_average, 1))
