"""Storefront service — assemble public storefront and flash page data."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.products.repository import ProductRepository
from app.sellers.repository import SellerProfileRepository


class StorefrontService:
    def __init__(self, session: AsyncSession) -> None:
        self.seller_repo = SellerProfileRepository(session)
        self.product_repo = ProductRepository(session)

    async def get_storefront(
        self, slug: str, *, offset: int = 0, limit: int = 20,
    ) -> dict:
        """Get public storefront data for /@slug."""
        seller = await self.seller_repo.get_by_slug(slug)
        if not seller:
            raise NotFoundError(resource="storefront", resource_id=slug)

        products, total = await self.product_repo.list_by_seller(
            seller.id, status="active", offset=offset, limit=limit,
        )

        return {
            "seller": seller,
            "products": products,
            "total_products": total,
        }

    async def get_store_products(
        self, slug: str, *, offset: int = 0, limit: int = 20,
    ) -> tuple[list, int]:
        """Get paginated active products for a store."""
        seller = await self.seller_repo.get_by_slug(slug)
        if not seller:
            raise NotFoundError(resource="storefront", resource_id=slug)
        return await self.product_repo.list_by_seller(
            seller.id, status="active", offset=offset, limit=limit,
        )

    async def get_flash_page(self, product_slug: str) -> dict:
        """Get product data for the Flash Page (single-product page)."""
        product = await self.product_repo.get_by_slug(product_slug)
        if not product or product.status != "active":
            raise NotFoundError(resource="product", resource_id=product_slug)

        seller = await self.seller_repo.get(product.seller_id)
        if not seller:
            raise NotFoundError(resource="seller")

        return {"product": product, "seller": seller}
