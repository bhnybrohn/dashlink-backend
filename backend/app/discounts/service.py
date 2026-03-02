"""Discount code service — CRUD and checkout validation."""

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ConflictError, NotFoundError
from app.discounts.models import DiscountCode
from app.discounts.repository import DiscountCodeRepository, DiscountUsageRepository
from app.discounts.schemas import ApplyDiscountRequest, DiscountCodeCreate, DiscountCodeUpdate


class DiscountService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.code_repo = DiscountCodeRepository(session)
        self.usage_repo = DiscountUsageRepository(session)

    async def create_code(self, seller_id: str, data: DiscountCodeCreate) -> DiscountCode:
        """Create a new discount code."""
        normalized = data.code.upper()
        existing = await self.code_repo.get_by_seller_and_code(seller_id, normalized)
        if existing:
            raise ConflictError(detail=f"Discount code '{normalized}' already exists")

        if data.discount_type == "percentage" and data.discount_value > 100:
            raise BadRequestError(detail="Percentage discount cannot exceed 100%")

        return await self.code_repo.create(
            seller_id=seller_id,
            code=normalized,
            discount_type=data.discount_type,
            discount_value=data.discount_value,
            min_order_amount=data.min_order_amount,
            max_uses=data.max_uses,
            starts_at=data.starts_at,
            expires_at=data.expires_at,
        )

    async def list_codes(
        self, seller_id: str, offset: int = 0, limit: int = 20,
    ) -> tuple[list[DiscountCode], int]:
        return await self.code_repo.list(
            offset=offset, limit=limit, filters={"seller_id": seller_id},
        )

    async def update_code(
        self, seller_id: str, code_id: str, data: DiscountCodeUpdate,
    ) -> DiscountCode:
        code = await self.code_repo.get_or_404(code_id)
        if code.seller_id != seller_id:
            raise NotFoundError(resource="discount_code", resource_id=code_id)
        update_data = data.model_dump(exclude_unset=True)
        if update_data:
            return await self.code_repo.update(code_id, **update_data)
        return code

    async def deactivate_code(self, seller_id: str, code_id: str) -> None:
        code = await self.code_repo.get_or_404(code_id)
        if code.seller_id != seller_id:
            raise NotFoundError(resource="discount_code", resource_id=code_id)
        await self.code_repo.update(code_id, is_active=False)

    async def apply_discount(self, data: ApplyDiscountRequest) -> dict:
        """Validate and preview a discount code application."""
        discount = await self.code_repo.get_active_by_code(data.code)
        if not discount:
            raise BadRequestError(detail="Invalid or expired discount code")

        if discount.min_order_amount and data.order_subtotal < discount.min_order_amount:
            raise BadRequestError(
                detail=f"Minimum order amount of {discount.min_order_amount} required"
            )

        if discount.discount_type == "percentage":
            amount_saved = round(data.order_subtotal * (discount.discount_value / 100), 2)
        else:
            amount_saved = min(discount.discount_value, data.order_subtotal)

        new_total = max(data.order_subtotal - amount_saved, 0)

        return {
            "code": discount.code,
            "discount_type": discount.discount_type,
            "discount_value": float(discount.discount_value),
            "amount_saved": amount_saved,
            "new_total": round(new_total, 2),
        }

    async def record_usage(
        self, discount_code: str, order_id: str,
        buyer_email: str, amount_saved: float,
    ) -> None:
        """Record discount usage after successful checkout."""
        discount = await self.code_repo.get_active_by_code(discount_code)
        if discount:
            await self.code_repo.increment_usage(discount.id)
            await self.usage_repo.create(
                discount_code_id=discount.id,
                order_id=order_id,
                buyer_email=buyer_email,
                amount_saved=amount_saved,
            )
