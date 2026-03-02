"""Checkout routes — stock locking, checkout initiation, and country config."""

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_optional_user
from app.checkout.schemas import CheckoutInitiate, CheckoutSessionResponse, LockRequest, LockResponse
from app.checkout.service import CheckoutService
from app.core.base_schemas import SuccessResponse
from app.core.countries import get_country, list_supported_countries
from app.database import get_db
from app.redis import get_redis
from app.users.models import User

router = APIRouter(prefix="/checkout", tags=["Checkout"])


# ── Country Config Schemas ──


class CountryConfigResponse(BaseModel):
    code: str
    name: str
    currency: str
    currency_symbol: str
    supported_gateways: list[str]
    default_gateway: str


class CountryListResponse(BaseModel):
    countries: list[CountryConfigResponse]


# ── Endpoints ──


@router.post("/lock", response_model=LockResponse, status_code=201)
async def lock_stock(
    data: LockRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    current_user: User | None = Depends(get_optional_user),
):
    """Lock 1+ units of a product for 10 minutes."""
    session_id = str(current_user.id) if current_user else None
    svc = CheckoutService(db, redis)
    return await svc.lock_stock(data, session_id=session_id)


@router.delete("/lock/{lock_id}", response_model=SuccessResponse)
async def release_lock(
    lock_id: str,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _current_user: User | None = Depends(get_optional_user),
):
    """Release a stock lock."""
    svc = CheckoutService(db, redis)
    await svc.release_lock(lock_id)
    return SuccessResponse(message="Lock released")


@router.post("/initiate", response_model=CheckoutSessionResponse)
async def initiate_checkout(
    data: CheckoutInitiate,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
    _current_user: User | None = Depends(get_optional_user),
):
    """Verify lock → create order → create payment session.

    If payment_gateway is omitted, the default gateway for the seller's
    country is used automatically. If provided, it must be supported in
    the seller's country.
    """
    svc = CheckoutService(db, redis)
    return await svc.initiate_checkout(data)


@router.get("/countries", response_model=CountryListResponse)
async def list_countries():
    """List all supported countries with their currency and payment gateway info."""
    countries = list_supported_countries()
    return CountryListResponse(
        countries=[
            CountryConfigResponse(
                code=c.code,
                name=c.name,
                currency=c.currency,
                currency_symbol=c.currency_symbol,
                supported_gateways=list(c.supported_gateways),
                default_gateway=c.default_gateway,
            )
            for c in countries
        ]
    )


@router.get("/country-config/{country_code}", response_model=CountryConfigResponse)
async def get_country_config(country_code: str):
    """Get payment and currency config for a specific country."""
    c = get_country(country_code)
    return CountryConfigResponse(
        code=c.code,
        name=c.name,
        currency=c.currency,
        currency_symbol=c.currency_symbol,
        supported_gateways=list(c.supported_gateways),
        default_gateway=c.default_gateway,
    )
