"""Product, image, and variant repositories."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.base_repository import BaseRepository
from app.products.models import Product, ProductImage, ProductVariant


class ProductRepository(BaseRepository[Product]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Product, session)

    async def get_with_relations(self, product_id: str) -> Product | None:
        """Get a product with images and variants eagerly loaded."""
        query = (
            self._base_query()
            .where(Product.id == product_id)
            .options(selectinload(Product.images), selectinload(Product.variants))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_slug(self, slug: str) -> Product | None:
        """Find a product by its slug."""
        query = (
            self._base_query()
            .where(Product.slug == slug)
            .options(selectinload(Product.images), selectinload(Product.variants))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list_by_seller(
        self,
        seller_id: str,
        *,
        status: str | None = None,
        category: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Product], int]:
        """List products for a seller with optional filters."""
        filters: dict = {"seller_id": seller_id}
        if status:
            filters["status"] = status
        if category:
            filters["category"] = category
        return await self.list(offset=offset, limit=limit, filters=filters)

    async def slug_exists(self, slug: str) -> bool:
        """Check if a slug is already taken."""
        query = select(Product.id).where(Product.slug == slug)
        result = await self.session.execute(query)
        return result.scalar_one_or_none() is not None


class ProductImageRepository(BaseRepository[ProductImage]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ProductImage, session)

    async def list_by_product(self, product_id: str) -> list[ProductImage]:
        """Get all images for a product ordered by position."""
        query = (
            self._base_query()
            .where(ProductImage.product_id == product_id)
            .order_by(ProductImage.position.asc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def count_by_product(self, product_id: str) -> int:
        """Count images for a product."""
        images = await self.list_by_product(product_id)
        return len(images)


class ProductVariantRepository(BaseRepository[ProductVariant]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(ProductVariant, session)

    async def list_by_product(self, product_id: str) -> list[ProductVariant]:
        """Get all variants for a product."""
        query = (
            self._base_query()
            .where(ProductVariant.product_id == product_id)
            .order_by(ProductVariant.created_at.asc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())
