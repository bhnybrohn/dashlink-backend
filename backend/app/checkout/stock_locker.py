"""Redis + DB double-write stock locking for checkout.

Locking strategy (CP — Consistency + Partition tolerance):
1. Acquire Redis distributed lock (prevents race conditions)
2. Check DB stock availability
3. Write lock to DB (source of truth)
4. Decrement stock in DB atomically
5. Set Redis TTL key for auto-expiry
"""

from datetime import datetime, timedelta, timezone

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.checkout.models import StockLock
from app.core.exceptions import BadRequestError, StockLockError
from app.products.models import Product, ProductVariant

LOCK_TTL_MINUTES = 10
REDIS_LOCK_PREFIX = "stock_lock:"


class StockLocker:
    def __init__(self, session: AsyncSession, redis: Redis) -> None:  # type: ignore[type-arg]
        self.session = session
        self.redis = redis

    async def acquire(
        self,
        *,
        product_id: str,
        variant_id: str | None,
        quantity: int,
        session_id: str,
    ) -> StockLock:
        """Acquire a stock lock with Redis distributed lock + DB write."""
        redis_key = f"{REDIS_LOCK_PREFIX}{product_id}:{variant_id or 'base'}:{session_id}"

        # 1. Acquire Redis distributed lock to prevent race conditions
        lock_key = f"lock:stock:{product_id}:{variant_id or 'base'}"
        acquired = await self.redis.set(lock_key, session_id, nx=True, ex=30)
        if not acquired:
            raise StockLockError(detail="Another checkout is in progress for this item")

        try:
            # 2. Check DB stock
            if variant_id:
                variant = await self.session.get(ProductVariant, variant_id)
                if not variant or variant.product_id != product_id:
                    raise BadRequestError(detail="Variant not found")
                if variant.stock_count < quantity:
                    raise StockLockError(
                        detail=f"Only {variant.stock_count} units available"
                    )
                # 3. Decrement stock atomically
                variant.stock_count -= quantity
            else:
                product = await self.session.get(Product, product_id)
                if not product:
                    raise BadRequestError(detail="Product not found")
                if product.stock_count < quantity:
                    raise StockLockError(
                        detail=f"Only {product.stock_count} units available"
                    )
                product.stock_count -= quantity

            # 4. Write lock to DB
            now = datetime.now(timezone.utc)
            expires_at = now + timedelta(minutes=LOCK_TTL_MINUTES)

            lock = StockLock(
                product_id=product_id,
                variant_id=variant_id,
                session_id=session_id,
                quantity=quantity,
                locked_at=now,
                expires_at=expires_at,
            )
            self.session.add(lock)
            await self.session.flush()
            await self.session.refresh(lock)

            # 5. Set Redis TTL for auto-expiry tracking
            await self.redis.setex(
                redis_key, LOCK_TTL_MINUTES * 60, lock.id,
            )

            return lock

        finally:
            # Release distributed lock
            await self.redis.delete(lock_key)

    async def release(self, lock_id: str) -> None:
        """Release a stock lock — restore stock and clean up."""
        lock = await self.session.get(StockLock, lock_id)
        if not lock or lock.deleted_at:
            return

        # Restore stock
        if lock.variant_id:
            variant = await self.session.get(ProductVariant, lock.variant_id)
            if variant:
                variant.stock_count += lock.quantity
        else:
            product = await self.session.get(Product, lock.product_id)
            if product:
                product.stock_count += lock.quantity

        # Soft-delete the lock
        lock.deleted_at = datetime.now(timezone.utc)
        await self.session.flush()

        # Clean up Redis
        redis_key = f"{REDIS_LOCK_PREFIX}{lock.product_id}:{lock.variant_id or 'base'}:{lock.session_id}"
        await self.redis.delete(redis_key)

    async def verify(self, lock_id: str) -> StockLock:
        """Verify a lock is still valid (not expired or released)."""
        lock = await self.session.get(StockLock, lock_id)
        if not lock or lock.deleted_at:
            raise StockLockError(detail="Stock lock not found or already released")

        now = datetime.now(timezone.utc)
        expires_at = lock.expires_at if isinstance(lock.expires_at, datetime) else datetime.fromisoformat(str(lock.expires_at))
        if expires_at < now:
            # Auto-release expired lock
            await self.release(lock_id)
            raise StockLockError(detail="Stock lock has expired")

        return lock

    async def cleanup_expired(self) -> int:
        """Clean up expired locks and restore stock. Returns count of cleaned locks."""
        now = datetime.now(timezone.utc)
        query = (
            select(StockLock)
            .where(StockLock.deleted_at.is_(None))
            .where(StockLock.expires_at < now)
        )
        result = await self.session.execute(query)
        expired_locks = list(result.scalars().all())

        for lock in expired_locks:
            await self.release(lock.id)

        return len(expired_locks)
