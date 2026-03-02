"""Discount code repositories."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import BaseRepository
from app.discounts.models import DiscountCode, DiscountUsage


class DiscountCodeRepository(BaseRepository[DiscountCode]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(DiscountCode, session)

    async def get_by_seller_and_code(
        self, seller_id: str, code: str,
    ) -> DiscountCode | None:
        """Find a discount code by seller + code string."""
        return await self.get_by(seller_id=seller_id, code=code.upper())

    async def get_active_by_code(self, code: str) -> DiscountCode | None:
        """Find an active discount code by code string (for checkout)."""
        from datetime import datetime, timezone
        from sqlalchemy import select

        now = datetime.now(timezone.utc)
        query = (
            self._base_query()
            .where(
                DiscountCode.code == code.upper(),
                DiscountCode.is_active.is_(True),
            )
        )
        result = await self.session.execute(query)
        discount = result.scalar_one_or_none()

        if not discount:
            return None

        # Check date validity
        if discount.starts_at and discount.starts_at > now:
            return None
        if discount.expires_at and discount.expires_at < now:
            return None

        # Check usage limit
        if discount.max_uses and discount.used_count >= discount.max_uses:
            return None

        return discount

    async def increment_usage(self, discount_id: str) -> None:
        """Increment used_count for a discount code."""
        discount = await self.get_or_404(discount_id)
        discount.used_count += 1
        await self.session.flush()


class DiscountUsageRepository(BaseRepository[DiscountUsage]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(DiscountUsage, session)
