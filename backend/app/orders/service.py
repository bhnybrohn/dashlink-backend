"""Order service — lifecycle management, status machine, seller/buyer views."""

import json
import secrets
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.orders.models import Order
from app.orders.repository import OrderItemRepository, OrderRepository
from app.products.models import Product

# Valid status transitions (seller-driven)
_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "pending": {"cancelled"},
    "paid": {"packed", "cancelled"},
    "packed": {"shipped", "cancelled"},
    "shipped": {"delivered"},
    "delivered": set(),
    "cancelled": set(),
    "refunded": set(),
}

PAYOUT_HOLD_DAYS = 7


def _generate_order_number() -> str:
    """Generate a unique order number like DL-A3X7K2M9."""
    code = secrets.token_hex(4).upper()
    return f"DL-{code}"


class OrderService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.order_repo = OrderRepository(session)
        self.item_repo = OrderItemRepository(session)

    # ── Creation (called by checkout) ──

    async def create_from_checkout(
        self,
        *,
        buyer_email: str,
        buyer_phone: str | None,
        seller_id: str,
        product: Product,
        variant_id: str | None,
        quantity: int,
        unit_price: Decimal,
        subtotal: Decimal,
        platform_fee: Decimal,
        total_amount: Decimal,
        currency: str,
        shipping_address: dict | None = None,
        buyer_id: str | None = None,
    ) -> Order:
        """Create an order from a successful checkout."""
        order_number = _generate_order_number()
        while await self.order_repo.order_number_exists(order_number):
            order_number = _generate_order_number()

        encrypted_address = json.dumps(shipping_address) if shipping_address else None

        order = await self.order_repo.create(
            order_number=order_number,
            buyer_id=buyer_id,
            seller_id=seller_id,
            status="pending",
            subtotal=float(subtotal),
            platform_fee=float(platform_fee),
            total_amount=float(total_amount),
            currency=currency,
            shipping_address=encrypted_address,
            buyer_email=buyer_email,
            buyer_phone=buyer_phone,
        )

        # Snapshot product data into order item
        variant_info = None
        if variant_id:
            for v in product.variants:
                if v.id == variant_id:
                    variant_info = {
                        "type": v.variant_type,
                        "value": v.variant_value,
                        "sku": v.sku,
                    }
                    break

        await self.item_repo.create(
            order_id=order.id,
            product_id=product.id,
            variant_id=variant_id,
            quantity=quantity,
            unit_price=float(unit_price),
            product_name=product.name,
            variant_info=variant_info,
        )

        return await self.order_repo.get_with_items(order.id)  # type: ignore[return-value]

    async def set_payment_ref(self, order_id: str, payment_ref: str) -> None:
        """Set the payment reference on an order."""
        await self.order_repo.update(order_id, payment_ref=payment_ref)

    # ── Status Transitions ──

    async def mark_paid(self, order_id: str) -> Order:
        """Mark an order as paid (called by payment webhook)."""
        order = await self.order_repo.get_or_404(order_id)
        if order.status != "pending":
            return order  # Idempotent

        now = datetime.now(timezone.utc)
        payout_at = now + timedelta(days=PAYOUT_HOLD_DAYS)

        return await self.order_repo.update(
            order_id,
            status="paid",
            paid_at=now,
            payout_eligible_at=payout_at,
        )

    async def update_status(
        self,
        order_id: str,
        seller_id: str,
        new_status: str,
        *,
        tracking_number: str | None = None,
        delivery_notes: str | None = None,
    ) -> Order:
        """Seller updates order status with validation."""
        order = await self._get_seller_order(order_id, seller_id)
        allowed = _STATUS_TRANSITIONS.get(order.status, set())
        if new_status not in allowed:
            raise BadRequestError(
                detail=f"Cannot transition from '{order.status}' to '{new_status}'. "
                f"Allowed: {', '.join(sorted(allowed)) or 'none'}",
            )

        update_fields: dict = {"status": new_status}
        now = datetime.now(timezone.utc)

        if new_status == "shipped":
            update_fields["shipped_at"] = now
            if tracking_number:
                update_fields["tracking_number"] = tracking_number
        elif new_status == "delivered":
            update_fields["delivered_at"] = now

        if delivery_notes:
            update_fields["delivery_notes"] = delivery_notes

        order = await self.order_repo.update(order_id, **update_fields)
        return await self.order_repo.get_with_items(order.id)  # type: ignore[return-value]

    async def add_tracking(
        self, order_id: str, seller_id: str, tracking_number: str, delivery_notes: str | None,
    ) -> Order:
        """Add tracking number to an order."""
        order = await self._get_seller_order(order_id, seller_id)
        if order.status not in ("packed", "shipped"):
            raise BadRequestError(detail="Can only add tracking to packed or shipped orders")
        update_fields: dict = {"tracking_number": tracking_number}
        if delivery_notes:
            update_fields["delivery_notes"] = delivery_notes
        order = await self.order_repo.update(order_id, **update_fields)
        return await self.order_repo.get_with_items(order.id)  # type: ignore[return-value]

    async def bulk_update_status(
        self, seller_id: str, order_ids: list[str], new_status: str,
        tracking_number: str | None = None,
    ) -> list[Order]:
        """Bulk update order status for a seller."""
        results = []
        for oid in order_ids:
            try:
                order = await self.update_status(
                    oid, seller_id, new_status, tracking_number=tracking_number,
                )
                results.append(order)
            except (BadRequestError, ForbiddenError, NotFoundError):
                continue
        return results

    # ── Queries ──

    async def get_seller_order(self, order_id: str, seller_id: str) -> Order:
        """Get a single order for a seller."""
        order = await self._get_seller_order(order_id, seller_id)
        return await self.order_repo.get_with_items(order.id)  # type: ignore[return-value]

    async def list_seller_orders(
        self,
        seller_id: str,
        *,
        status: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Order], int]:
        return await self.order_repo.list_by_seller(
            seller_id, status=status, offset=offset, limit=limit,
        )

    async def get_buyer_order(self, order_id: str, buyer_id: str) -> Order:
        """Get a single order for a buyer."""
        order = await self.order_repo.get_with_items(order_id)
        if not order:
            raise NotFoundError(resource="order", resource_id=order_id)
        if order.buyer_id != buyer_id:
            raise ForbiddenError(detail="This order does not belong to you")
        return order

    async def list_buyer_orders(
        self, buyer_id: str, *, offset: int = 0, limit: int = 20,
    ) -> tuple[list[Order], int]:
        return await self.order_repo.list_by_buyer(buyer_id, offset=offset, limit=limit)

    async def get_buyer_dashboard(self, buyer_id: str) -> dict:
        """Consolidated buyer dashboard — active orders, spend, top sellers."""
        active_orders = await self.order_repo.list_active_by_buyer(buyer_id)
        _, total_orders = await self.order_repo.list_by_buyer(buyer_id, offset=0, limit=1)
        total_spent = await self.order_repo.buyer_total_spent(buyer_id)
        top_sellers = await self.order_repo.buyer_top_sellers(buyer_id)

        return {
            "active_orders": active_orders,
            "active_count": len(active_orders),
            "total_orders": total_orders,
            "total_spent": total_spent,
            "top_sellers": top_sellers,
        }

    # ── Internal Helpers ──

    async def _get_seller_order(self, order_id: str, seller_id: str) -> Order:
        order = await self.order_repo.get_or_404(order_id)
        if order.seller_id != seller_id:
            raise ForbiddenError(detail="This order does not belong to your store")
        return order
