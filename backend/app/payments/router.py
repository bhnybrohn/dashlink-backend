"""Payment routes — webhook handlers and payout endpoints."""

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_seller
from app.core.base_schemas import PaginatedResponse, SuccessResponse
from app.core.pagination import paginate
from app.database import get_db
from app.payments.schemas import PayoutResponse
from app.payments.service import PaymentService
from app.sellers.repository import SellerProfileRepository
from app.users.models import User

router = APIRouter(prefix="/payments", tags=["Payments"])


# ── Webhook Handlers ──


@router.post("/webhook/stripe", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle Stripe webhook events."""
    from app.payments.gateways.stripe import StripeGateway

    payload = await request.body()
    headers = dict(request.headers)

    gateway = StripeGateway()
    event = await gateway.verify_webhook(payload=payload, headers=headers)

    svc = PaymentService(db)
    await svc.process_webhook(
        gateway="stripe",
        event_type=event["event_type"],
        gateway_ref=event["gateway_ref"],
        webhook_payload=event["data"],
    )
    return SuccessResponse(message="ok")


@router.post("/webhook/paystack", include_in_schema=False)
async def paystack_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle Paystack webhook events."""
    from app.payments.gateways.paystack import PaystackGateway

    payload = await request.body()
    headers = dict(request.headers)

    gateway = PaystackGateway()
    event = await gateway.verify_webhook(payload=payload, headers=headers)

    svc = PaymentService(db)
    await svc.process_webhook(
        gateway="paystack",
        event_type=event["event_type"],
        gateway_ref=event["gateway_ref"],
        webhook_payload=event["data"],
    )
    return SuccessResponse(message="ok")


@router.post("/webhook/flutterwave", include_in_schema=False)
async def flutterwave_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Handle Flutterwave webhook events."""
    from app.payments.gateways.flutterwave import FlutterwaveGateway

    payload = await request.body()
    headers = dict(request.headers)

    gateway = FlutterwaveGateway()
    event = await gateway.verify_webhook(payload=payload, headers=headers)

    svc = PaymentService(db)
    await svc.process_webhook(
        gateway="flutterwave",
        event_type=event["event_type"],
        gateway_ref=event["gateway_ref"],
        webhook_payload=event["data"],
    )
    return SuccessResponse(message="ok")


# ── Seller Payout Endpoints ──


@router.get("/seller/payouts", response_model=PaginatedResponse[PayoutResponse])
async def list_payouts(
    current_user: User = Depends(get_current_seller),
    db: AsyncSession = Depends(get_db),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """List payout history for the current seller."""
    seller_repo = SellerProfileRepository(db)
    profile = await seller_repo.get_by_user_id(current_user.id)
    if not profile:
        return paginate([], 0, offset, limit)

    svc = PaymentService(db)
    items, total = await svc.list_seller_payouts(profile.id, offset=offset, limit=limit)
    return paginate(items, total, offset, limit)
