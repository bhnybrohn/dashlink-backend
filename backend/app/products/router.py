"""Product routes — CRUD, images, variants, status, stock."""

from uuid import uuid4

from fastapi import APIRouter, Depends, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_seller, get_onboarded_seller
from app.core.base_schemas import PaginatedResponse
from app.core.pagination import paginate
from app.database import get_db
from app.products.schemas import (
    ProductCreate,
    ProductListResponse,
    ProductResponse,
    ProductStatusUpdate,
    ProductUpdate,
    StockUpdate,
    VariantCreate,
    VariantUpdate,
)
from app.products.service import ProductService
from app.sellers.repository import SellerProfileRepository
from app.users.models import User

router = APIRouter(prefix="/products", tags=["Products"])


async def _get_seller_profile_id(
    current_user: User = Depends(get_onboarded_seller),
    db: AsyncSession = Depends(get_db),
) -> str:
    """Resolve the seller_profile.id for the current user (requires completed onboarding)."""
    repo = SellerProfileRepository(db)
    profile = await repo.get_by_user_id(current_user.id)
    if not profile:
        from app.core.exceptions import BadRequestError
        raise BadRequestError(detail="Seller profile not found. Create one first.")
    return profile.id


# ── Product CRUD ──


@router.post("", status_code=201, response_model=ProductResponse)
async def create_product(
    data: ProductCreate,
    seller_id: str = Depends(_get_seller_profile_id),
    db: AsyncSession = Depends(get_db),
):
    """Create a new product."""
    svc = ProductService(db)
    return await svc.create_product(seller_id, data)


@router.get("", response_model=PaginatedResponse[ProductListResponse])
async def list_products(
    seller_id: str = Depends(_get_seller_profile_id),
    db: AsyncSession = Depends(get_db),
    status: str | None = Query(None),
    category: str | None = Query(None),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """List the current seller's products."""
    svc = ProductService(db)
    items, total = await svc.list_products(
        seller_id, status=status, category=category, offset=offset, limit=limit,
    )
    return paginate(items, total, offset, limit)


@router.get("/{product_id}", response_model=ProductResponse)
async def get_product(
    product_id: str,
    seller_id: str = Depends(_get_seller_profile_id),
    db: AsyncSession = Depends(get_db),
):
    """Get a single product."""
    svc = ProductService(db)
    return await svc.get_product(product_id, seller_id)


@router.patch("/{product_id}", response_model=ProductResponse)
async def update_product(
    product_id: str,
    data: ProductUpdate,
    seller_id: str = Depends(_get_seller_profile_id),
    db: AsyncSession = Depends(get_db),
):
    """Update product details."""
    svc = ProductService(db)
    return await svc.update_product(product_id, seller_id, data)


@router.delete("/{product_id}", status_code=204)
async def delete_product(
    product_id: str,
    seller_id: str = Depends(_get_seller_profile_id),
    db: AsyncSession = Depends(get_db),
):
    """Soft-delete a product."""
    svc = ProductService(db)
    await svc.delete_product(product_id, seller_id)


# ── Status & Stock ──


@router.patch("/{product_id}/status", response_model=ProductResponse)
async def update_status(
    product_id: str,
    data: ProductStatusUpdate,
    seller_id: str = Depends(_get_seller_profile_id),
    db: AsyncSession = Depends(get_db),
):
    """Transition product status."""
    svc = ProductService(db)
    return await svc.update_status(product_id, seller_id, data.status)


@router.patch("/{product_id}/stock", response_model=ProductResponse)
async def update_stock(
    product_id: str,
    data: StockUpdate,
    seller_id: str = Depends(_get_seller_profile_id),
    db: AsyncSession = Depends(get_db),
):
    """Update stock count."""
    svc = ProductService(db)
    return await svc.update_stock(product_id, seller_id, data.stock_count)


# ── Images ──


@router.post("/{product_id}/images", response_model=ProductResponse, status_code=201)
async def upload_image(
    product_id: str,
    file: UploadFile,
    seller_id: str = Depends(_get_seller_profile_id),
    db: AsyncSession = Depends(get_db),
):
    """Upload an image to a product (max 5)."""
    from app.integrations.storage_client import get_storage
    file_data = await file.read()
    svc = ProductService(db, storage=get_storage())
    return await svc.upload_image(
        product_id, seller_id, file_data, file.content_type or "image/jpeg",
    )


@router.delete("/{product_id}/images/{image_id}", response_model=ProductResponse)
async def delete_image(
    product_id: str,
    image_id: str,
    seller_id: str = Depends(_get_seller_profile_id),
    db: AsyncSession = Depends(get_db),
):
    """Remove an image from a product."""
    from app.integrations.storage_client import get_storage
    svc = ProductService(db, storage=get_storage())
    return await svc.delete_image(product_id, image_id, seller_id)


# ── Variants ──


@router.post("/{product_id}/variants", response_model=ProductResponse, status_code=201)
async def add_variant(
    product_id: str,
    data: VariantCreate,
    seller_id: str = Depends(_get_seller_profile_id),
    db: AsyncSession = Depends(get_db),
):
    """Add a variant to a product."""
    svc = ProductService(db)
    return await svc.add_variant(product_id, seller_id, data)


@router.patch("/{product_id}/variants/{variant_id}", response_model=ProductResponse)
async def update_variant(
    product_id: str,
    variant_id: str,
    data: VariantUpdate,
    seller_id: str = Depends(_get_seller_profile_id),
    db: AsyncSession = Depends(get_db),
):
    """Update a product variant."""
    svc = ProductService(db)
    return await svc.update_variant(product_id, variant_id, seller_id, data)


@router.delete("/{product_id}/variants/{variant_id}", response_model=ProductResponse)
async def delete_variant(
    product_id: str,
    variant_id: str,
    seller_id: str = Depends(_get_seller_profile_id),
    db: AsyncSession = Depends(get_db),
):
    """Remove a variant from a product."""
    svc = ProductService(db)
    return await svc.delete_variant(product_id, variant_id, seller_id)


# ── Bulk CSV Upload ──


class BulkUploadResponse(BaseModel):
    job_id: str
    message: str


class BulkUploadStatusResponse(BaseModel):
    job_id: str
    status: str
    total: int
    processed: int
    succeeded: int
    failed: int
    errors: list[str]


@router.post("/bulk-upload", response_model=BulkUploadResponse, status_code=201)
async def bulk_upload(
    file: UploadFile,
    seller_id: str = Depends(_get_seller_profile_id),
    current_user: User = Depends(get_current_seller),
):
    """Upload a CSV file to create products in bulk."""
    if not file.filename or not file.filename.endswith(".csv"):
        from app.core.exceptions import BadRequestError
        raise BadRequestError(detail="Only CSV files are supported")

    csv_data = (await file.read()).decode("utf-8")
    job_id = str(uuid4())

    from app.tasks.product_tasks import process_bulk_upload
    process_bulk_upload.delay(job_id, seller_id, csv_data)

    return BulkUploadResponse(job_id=job_id, message="CSV upload processing started")


@router.get("/bulk-upload/{job_id}/status", response_model=BulkUploadStatusResponse)
async def bulk_upload_status(
    job_id: str,
    current_user: User = Depends(get_current_seller),
):
    """Check bulk upload processing status."""
    from app.redis import get_redis
    redis = await get_redis()
    data = await redis.hgetall(f"bulk_upload:{job_id}")

    if not data:
        from app.core.exceptions import NotFoundError
        raise NotFoundError(resource="bulk_upload_job", resource_id=job_id)

    errors_raw = data.get("errors", "")
    errors = errors_raw.split("|||") if errors_raw else []

    return BulkUploadStatusResponse(
        job_id=job_id,
        status=data.get("status", "unknown"),
        total=int(data.get("total", 0)),
        processed=int(data.get("processed", 0)),
        succeeded=int(data.get("succeeded", 0)),
        failed=int(data.get("failed", 0)),
        errors=errors[:50],
    )
