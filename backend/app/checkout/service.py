"""Checkout service — orchestrates lock → order → payment session flow."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.checkout.schemas import CheckoutInitiate, CheckoutSessionResponse, LockRequest, LockResponse
from app.checkout.stock_locker import StockLocker
from app.core.countries import get_country, is_gateway_supported
from app.core.exceptions import BadRequestError
from app.core.protocols import PaymentGateway
from app.payments.gateways import get_gateway
from app.products.repository import ProductRepository
from app.sellers.repository import SellerProfileRepository


class CheckoutService:
    def __init__(
        self,
        session: AsyncSession,
        redis: Redis,  # type: ignore[type-arg]
        payment_gateway: PaymentGateway | None = None,
    ) -> None:
        self.session = session
        self.redis = redis
        self.locker = StockLocker(session, redis)
        self.product_repo = ProductRepository(session)
        self.seller_repo = SellerProfileRepository(session)
        self.payment_gateway = payment_gateway

    async def lock_stock(self, data: LockRequest, session_id: str | None = None) -> LockResponse:
        """Lock stock for checkout (10-minute TTL)."""
        if not session_id:
            session_id = str(uuid4())

        # Verify product exists and is active
        product = await self.product_repo.get(data.product_id)
        if not product:
            raise BadRequestError(detail="Product not found")
        if product.status != "active":
            raise BadRequestError(detail="Product is not available for purchase")

        lock = await self.locker.acquire(
            product_id=data.product_id,
            variant_id=data.variant_id,
            quantity=data.quantity,
            session_id=session_id,
        )

        return LockResponse(
            lock_id=lock.id,
            product_id=lock.product_id,
            variant_id=lock.variant_id,
            quantity=lock.quantity,
            locked_at=lock.locked_at,
            expires_at=lock.expires_at,
            session_id=session_id,
        )

    async def release_lock(self, lock_id: str) -> None:
        """Release a stock lock."""
        await self.locker.release(lock_id)

    async def _resolve_gateway(self, product_seller_id: str, requested_gateway: str | None) -> PaymentGateway:
        """Resolve the payment gateway based on seller country and optional request."""
        seller = await self.seller_repo.get_by_user_id(product_seller_id)
        if not seller:
            raise BadRequestError(detail="Seller profile not found")

        country = get_country(seller.country)

        if requested_gateway:
            if not is_gateway_supported(seller.country, requested_gateway):
                raise BadRequestError(
                    detail=f"Payment gateway '{requested_gateway}' is not supported in "
                    f"{country.name}. Supported: {', '.join(country.supported_gateways)}"
                )
            return get_gateway(requested_gateway)

        return get_gateway(country.default_gateway)

    async def initiate_checkout(self, data: CheckoutInitiate) -> CheckoutSessionResponse:
        """Verify lock → create order → create payment session."""
        # 1. Verify the stock lock is still valid
        lock = await self.locker.verify(data.lock_id)

        # 2. Get product details for pricing
        product = await self.product_repo.get(lock.product_id)
        if not product:
            raise BadRequestError(detail="Product no longer available")

        # 3. Resolve payment gateway from seller's country
        gateway = self.payment_gateway or await self._resolve_gateway(
            product.seller_id, data.payment_gateway,
        )

        # 4. Calculate amounts using country-specific fee rate
        seller = await self.seller_repo.get_by_user_id(product.seller_id)
        country = get_country(seller.country) if seller else None
        fee_rate = country.platform_fee_rate if country else Decimal("0.05")

        unit_price = Decimal(str(product.price))
        subtotal = unit_price * lock.quantity
        platform_fee = (subtotal * fee_rate).quantize(Decimal("0.01"))
        total = subtotal

        # 5. Create order (import here to avoid circular dependency)
        from app.orders.service import OrderService
        order_svc = OrderService(self.session)
        order = await order_svc.create_from_checkout(
            buyer_email=data.buyer_email,
            buyer_phone=data.buyer_phone,
            seller_id=product.seller_id,
            product=product,
            variant_id=lock.variant_id,
            quantity=lock.quantity,
            unit_price=unit_price,
            subtotal=subtotal,
            platform_fee=platform_fee,
            total_amount=total,
            currency=product.currency,
            shipping_address=data.shipping_address,
        )

        # 6. Create payment session via gateway
        session_result = await gateway.create_checkout_session(
            order_id=order.id,
            amount=total,
            currency=product.currency,
            customer_email=data.buyer_email,
            success_url=data.success_url,
            cancel_url=data.cancel_url,
            metadata={"lock_id": data.lock_id, "order_id": order.id},
        )

        # 7. Update order with payment reference
        await order_svc.set_payment_ref(order.id, session_result["payment_ref"])

        return CheckoutSessionResponse(
            order_id=order.id,
            payment_session_url=session_result["url"],
            payment_ref=session_result["payment_ref"],
            expires_at=lock.expires_at,
        )
