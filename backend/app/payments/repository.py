"""Payment and payout repositories."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import BaseRepository
from app.payments.models import Payment, Payout


class PaymentRepository(BaseRepository[Payment]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Payment, session)

    async def get_by_order(self, order_id: str) -> Payment | None:
        return await self.get_by(order_id=order_id)

    async def get_by_gateway_ref(self, gateway_ref: str) -> Payment | None:
        return await self.get_by(gateway_ref=gateway_ref)


class PayoutRepository(BaseRepository[Payout]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Payout, session)

    async def list_by_seller(
        self, seller_id: str, *, offset: int = 0, limit: int = 20,
    ) -> tuple[list[Payout], int]:
        return await self.list(offset=offset, limit=limit, filters={"seller_id": seller_id})
