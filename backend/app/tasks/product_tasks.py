"""Celery tasks for product scheduling and bulk CSV upload."""

from app.tasks import celery_app


@celery_app.task(name="app.tasks.product_tasks.publish_scheduled_products", queue="default")
def publish_scheduled_products():
    """Publish draft products whose scheduled_at time has passed.

    Runs every 60s via Celery beat. Transitions draft → active
    when scheduled_at <= now() and stock_count > 0.
    """
    import asyncio
    from datetime import datetime, timezone

    from sqlalchemy import select
    from app.database import async_session_factory
    from app.products.models import Product

    async def _run():
        async with async_session_factory() as session:
            now = datetime.now(timezone.utc)
            query = (
                select(Product)
                .where(
                    Product.status == "draft",
                    Product.scheduled_at.is_not(None),
                    Product.scheduled_at <= now,
                    Product.stock_count > 0,
                    Product.deleted_at.is_(None),
                )
            )
            result = await session.execute(query)
            products = list(result.scalars().all())

            for product in products:
                product.status = "active"
                product.scheduled_at = None
                product.version += 1

            await session.commit()

    asyncio.get_event_loop().run_until_complete(_run())


@celery_app.task(name="app.tasks.product_tasks.process_bulk_upload", queue="media")
def process_bulk_upload(job_id: str, seller_id: str, csv_data: str):
    """Process a bulk CSV upload and create products.

    Stores progress in Redis so the seller can poll for status.
    Expected CSV columns: name, description, price, stock_count, category
    """
    import asyncio
    import csv
    import io

    from app.database import async_session_factory

    async def _run():
        import redis.asyncio as aioredis
        from app.config import settings
        from app.core.countries import get_currency_for_country
        from app.core.slug import generate_slug
        from app.products.repository import ProductRepository
        from app.sellers.repository import SellerProfileRepository

        r = aioredis.from_url(settings.redis_url, decode_responses=True)
        key = f"bulk_upload:{job_id}"

        try:
            reader = csv.DictReader(io.StringIO(csv_data))
            rows = list(reader)
        except Exception as e:
            await r.hset(key, mapping={
                "status": "failed", "total": 0, "processed": 0,
                "succeeded": 0, "failed": 0, "errors": str(e),
            })
            await r.expire(key, 3600)
            await r.aclose()
            return

        total = len(rows)
        await r.hset(key, mapping={
            "status": "processing", "total": total,
            "processed": 0, "succeeded": 0, "failed": 0, "errors": "",
        })
        await r.expire(key, 3600)

        async with async_session_factory() as session:
            product_repo = ProductRepository(session)
            seller_repo = SellerProfileRepository(session)

            seller = await seller_repo.get(seller_id)
            currency = get_currency_for_country(seller.country) if seller else "NGN"

            succeeded = 0
            failed = 0
            errors: list[str] = []

            for i, row in enumerate(rows, 1):
                try:
                    name = row.get("name", "").strip()
                    if not name:
                        raise ValueError("name is required")

                    price = float(row.get("price", 0))
                    if price <= 0:
                        raise ValueError("price must be positive")

                    stock = int(row.get("stock_count", 0))

                    slug = generate_slug(name)
                    while await product_repo.slug_exists(slug):
                        slug = generate_slug(name)

                    await product_repo.create(
                        seller_id=seller_id,
                        name=name,
                        slug=slug,
                        description=row.get("description", "").strip() or None,
                        price=price,
                        currency=currency,
                        stock_count=stock,
                        category=row.get("category", "").strip() or None,
                    )
                    succeeded += 1
                except Exception as e:
                    failed += 1
                    errors.append(f"Row {i}: {e}")

                # Update progress every 10 rows
                if i % 10 == 0 or i == total:
                    await r.hset(key, mapping={
                        "processed": i,
                        "succeeded": succeeded,
                        "failed": failed,
                    })

            await session.commit()

        await r.hset(key, mapping={
            "status": "completed",
            "processed": total,
            "succeeded": succeeded,
            "failed": failed,
            "errors": "|||".join(errors[:50]),
        })
        await r.aclose()

    asyncio.get_event_loop().run_until_complete(_run())
