"""CRM routes — customer management, segmentation, broadcast."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_seller
from app.database import get_db
from app.crm.schemas import (
    BroadcastRequest,
    BroadcastResponse,
    CustomerListResponse,
    CustomerProfile,
    SegmentListResponse,
)
from app.crm.service import CrmService
from app.users.models import User

router = APIRouter(prefix="/crm", tags=["CRM"])


def _get_service(db: AsyncSession = Depends(get_db)) -> CrmService:
    return CrmService(db)


@router.get("/customers", response_model=CustomerListResponse)
async def list_customers(
    current_user: User = Depends(get_current_seller),
    service: CrmService = Depends(_get_service),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
):
    """List customers for the seller with purchase stats."""
    customers, total = await service.list_customers(
        current_user.id, offset=offset, limit=limit,
    )
    return CustomerListResponse(customers=customers, total=total)


@router.get("/customers/{buyer_email}/profile", response_model=CustomerProfile)
async def get_customer_profile(
    buyer_email: str,
    current_user: User = Depends(get_current_seller),
    service: CrmService = Depends(_get_service),
):
    """Get detailed customer profile with order history."""
    return await service.get_customer_profile(current_user.id, buyer_email)


@router.get("/segments", response_model=SegmentListResponse)
async def get_segments(
    current_user: User = Depends(get_current_seller),
    service: CrmService = Depends(_get_service),
):
    """Pre-defined customer segments with counts."""
    segments = await service.get_segments(current_user.id)
    return SegmentListResponse(segments=segments)


@router.post("/broadcast", response_model=BroadcastResponse)
async def send_broadcast(
    body: BroadcastRequest,
    current_user: User = Depends(get_current_seller),
    service: CrmService = Depends(_get_service),
):
    """Send a broadcast message to a customer segment."""
    emails = await service.get_segment_emails(current_user.id, body.segment)

    if emails:
        from app.tasks.crm_tasks import send_broadcast_task
        send_broadcast_task.delay(
            seller_id=current_user.id,
            emails=emails,
            channel=body.channel,
            subject=body.subject,
            message=body.message,
        )

    return BroadcastResponse(
        message=f"Broadcast queued for {len(emails)} recipients",
        recipient_count=len(emails),
    )
