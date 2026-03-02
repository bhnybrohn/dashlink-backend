"""Product service — CRUD, status machine, stock management, image/variant ops."""

from io import BytesIO

from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.countries import get_currency_for_country
from app.core.exceptions import BadRequestError, ForbiddenError, NotFoundError
from app.core.protocols import StorageBackend
from app.core.slug import generate_slug
from app.products.models import Product
from app.products.repository import (
    ProductImageRepository,
    ProductRepository,
    ProductVariantRepository,
)
from app.products.schemas import ProductCreate, ProductUpdate, VariantCreate, VariantUpdate
from app.sellers.repository import SellerProfileRepository

# Valid status transitions
_STATUS_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"active", "archived"},
    "active": {"paused", "sold_out", "archived"},
    "paused": {"active", "archived"},
    "sold_out": {"active", "archived"},
    "archived": {"draft"},
}

MAX_IMAGES_PER_PRODUCT = 5
MAX_IMAGE_DIMENSION = 2048
ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


class ProductService:
    def __init__(
        self,
        session: AsyncSession,
        storage: StorageBackend | None = None,
    ) -> None:
        self.session = session
        self.storage = storage
        self.product_repo = ProductRepository(session)
        self.image_repo = ProductImageRepository(session)
        self.variant_repo = ProductVariantRepository(session)
        self.seller_repo = SellerProfileRepository(session)

    # ── CRUD ──

    async def create_product(
        self, seller_id: str, data: ProductCreate,
    ) -> Product:
        """Create a new product with optional variants."""
        # Auto-set currency from seller's country
        seller = await self.seller_repo.get_by_user_id(seller_id)
        if not seller:
            raise BadRequestError(detail="Seller profile not found")
        currency = get_currency_for_country(seller.country)

        slug = generate_slug(data.name)
        while await self.product_repo.slug_exists(slug):
            slug = generate_slug(data.name)

        product = await self.product_repo.create(
            seller_id=seller_id,
            name=data.name,
            slug=slug,
            description=data.description,
            price=float(data.price),
            compare_at_price=float(data.compare_at_price) if data.compare_at_price else None,
            currency=currency,
            stock_count=data.stock_count,
            low_stock_threshold=data.low_stock_threshold,
            category=data.category,
            is_pinned=data.is_pinned,
        )

        if data.variants:
            for v in data.variants:
                await self.variant_repo.create(
                    product_id=product.id,
                    variant_type=v.variant_type,
                    variant_value=v.variant_value,
                    stock_count=v.stock_count,
                    price_override=float(v.price_override) if v.price_override else None,
                    sku=v.sku,
                )

        return await self.product_repo.get_with_relations(product.id)  # type: ignore[return-value]

    async def get_product(self, product_id: str, seller_id: str | None = None) -> Product:
        """Get a product by ID. Optionally verify seller ownership."""
        product = await self.product_repo.get_with_relations(product_id)
        if not product:
            raise NotFoundError(resource="product", resource_id=product_id)
        if seller_id and product.seller_id != seller_id:
            raise ForbiddenError(detail="You do not own this product")
        return product

    async def list_products(
        self,
        seller_id: str,
        *,
        status: str | None = None,
        category: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[Product], int]:
        """List products for a seller."""
        return await self.product_repo.list_by_seller(
            seller_id, status=status, category=category, offset=offset, limit=limit,
        )

    async def update_product(
        self, product_id: str, seller_id: str, data: ProductUpdate,
    ) -> Product:
        """Update product fields."""
        product = await self.get_product(product_id, seller_id)
        update_data = data.model_dump(exclude_unset=True)
        if "price" in update_data and update_data["price"] is not None:
            update_data["price"] = float(update_data["price"])
        if "compare_at_price" in update_data and update_data["compare_at_price"] is not None:
            update_data["compare_at_price"] = float(update_data["compare_at_price"])
        if update_data:
            product = await self.product_repo.update(product.id, **update_data)
        return await self.product_repo.get_with_relations(product.id)  # type: ignore[return-value]

    async def delete_product(self, product_id: str, seller_id: str) -> None:
        """Soft-delete a product."""
        await self.get_product(product_id, seller_id)
        await self.product_repo.soft_delete(product_id)

    # ── Status Machine ──

    async def update_status(
        self, product_id: str, seller_id: str, new_status: str,
    ) -> Product:
        """Transition product status with validation."""
        product = await self.get_product(product_id, seller_id)
        allowed = _STATUS_TRANSITIONS.get(product.status, set())
        if new_status not in allowed:
            raise BadRequestError(
                detail=f"Cannot transition from '{product.status}' to '{new_status}'. "
                f"Allowed: {', '.join(sorted(allowed))}",
            )
        if new_status == "active" and product.stock_count <= 0:
            raise BadRequestError(detail="Cannot activate a product with zero stock")
        product = await self.product_repo.update(product.id, status=new_status)
        return await self.product_repo.get_with_relations(product.id)  # type: ignore[return-value]

    # ── Stock Management ──

    async def update_stock(
        self, product_id: str, seller_id: str, stock_count: int,
    ) -> Product:
        """Update stock count. Auto-transitions to sold_out if zero."""
        product = await self.get_product(product_id, seller_id)
        update_fields: dict = {"stock_count": stock_count}
        if stock_count == 0 and product.status == "active":
            update_fields["status"] = "sold_out"
        product = await self.product_repo.update(product.id, **update_fields)
        return await self.product_repo.get_with_relations(product.id)  # type: ignore[return-value]

    # ── Image Management ──

    async def upload_image(
        self,
        product_id: str,
        seller_id: str,
        file_data: bytes,
        content_type: str,
        alt_text: str | None = None,
    ) -> Product:
        """Upload and attach an image to a product."""
        product = await self.get_product(product_id, seller_id)

        if content_type not in ALLOWED_IMAGE_TYPES:
            raise BadRequestError(detail=f"Image type '{content_type}' not allowed")

        current_count = await self.image_repo.count_by_product(product_id)
        if current_count >= MAX_IMAGES_PER_PRODUCT:
            raise BadRequestError(
                detail=f"Maximum {MAX_IMAGES_PER_PRODUCT} images per product",
            )

        # Process with Pillow — resize if needed
        processed = self._process_image(file_data, content_type)

        if not self.storage:
            raise BadRequestError(detail="Storage backend not configured")

        ext = content_type.split("/")[-1]
        if ext == "jpeg":
            ext = "jpg"
        key = f"products/{product.seller_id}/{product.id}/{product.id}_{current_count}.{ext}"
        url = await self.storage.upload(file_data=processed, key=key, content_type=content_type)

        await self.image_repo.create(
            product_id=product_id,
            url=url,
            alt_text=alt_text,
            position=current_count,
        )

        return await self.product_repo.get_with_relations(product.id)  # type: ignore[return-value]

    async def delete_image(
        self, product_id: str, image_id: str, seller_id: str,
    ) -> Product:
        """Remove an image from a product."""
        await self.get_product(product_id, seller_id)
        image = await self.image_repo.get_or_404(image_id)
        if image.product_id != product_id:
            raise BadRequestError(detail="Image does not belong to this product")
        if self.storage:
            key = image.url.split("/", 3)[-1] if "/" in image.url else image.url
            try:
                await self.storage.delete(key=key)
            except Exception:
                pass  # Best-effort storage cleanup
        await self.image_repo.soft_delete(image_id)
        return await self.product_repo.get_with_relations(product_id)  # type: ignore[return-value]

    @staticmethod
    def _process_image(file_data: bytes, content_type: str) -> bytes:
        """Resize images that exceed max dimensions."""
        img = Image.open(BytesIO(file_data))
        if max(img.size) > MAX_IMAGE_DIMENSION:
            img.thumbnail((MAX_IMAGE_DIMENSION, MAX_IMAGE_DIMENSION), Image.Resampling.LANCZOS)
            buf = BytesIO()
            fmt = "JPEG" if "jpeg" in content_type else content_type.split("/")[-1].upper()
            if fmt == "JPG":
                fmt = "JPEG"
            img.save(buf, format=fmt, quality=85)
            return buf.getvalue()
        return file_data

    # ── Variant Management ──

    async def add_variant(
        self, product_id: str, seller_id: str, data: VariantCreate,
    ) -> Product:
        """Add a variant to a product."""
        await self.get_product(product_id, seller_id)
        await self.variant_repo.create(
            product_id=product_id,
            variant_type=data.variant_type,
            variant_value=data.variant_value,
            stock_count=data.stock_count,
            price_override=float(data.price_override) if data.price_override else None,
            sku=data.sku,
        )
        return await self.product_repo.get_with_relations(product_id)  # type: ignore[return-value]

    async def update_variant(
        self, product_id: str, variant_id: str, seller_id: str, data: VariantUpdate,
    ) -> Product:
        """Update a product variant."""
        await self.get_product(product_id, seller_id)
        variant = await self.variant_repo.get_or_404(variant_id)
        if variant.product_id != product_id:
            raise BadRequestError(detail="Variant does not belong to this product")
        update_data = data.model_dump(exclude_unset=True)
        if "price_override" in update_data and update_data["price_override"] is not None:
            update_data["price_override"] = float(update_data["price_override"])
        if update_data:
            await self.variant_repo.update(variant_id, **update_data)
        return await self.product_repo.get_with_relations(product_id)  # type: ignore[return-value]

    async def delete_variant(
        self, product_id: str, variant_id: str, seller_id: str,
    ) -> Product:
        """Remove a variant from a product."""
        await self.get_product(product_id, seller_id)
        variant = await self.variant_repo.get_or_404(variant_id)
        if variant.product_id != product_id:
            raise BadRequestError(detail="Variant does not belong to this product")
        await self.variant_repo.soft_delete(variant_id)
        return await self.product_repo.get_with_relations(product_id)  # type: ignore[return-value]
