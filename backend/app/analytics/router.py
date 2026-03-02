"""Analytics routes — event recording (public) and seller dashboard queries."""

from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_seller
from app.database import get_db
from app.analytics.schemas import (
    CustomerStatsResponse,
    FunnelResponse,
    OverviewResponse,
    RecordEventRequest,
    RevenueChartResponse,
    TopProductsResponse,
    TrafficResponse,
)
from app.analytics.service import AnalyticsService
from app.core.base_schemas import SuccessResponse
from app.users.models import User

router = APIRouter(prefix="/analytics", tags=["Analytics"])


def _get_service(db: AsyncSession = Depends(get_db)) -> AnalyticsService:
    return AnalyticsService(db)


# ── Public: Record Events ──


@router.post("/event", response_model=SuccessResponse, status_code=201)
async def record_event(
    body: RecordEventRequest,
    service: AnalyticsService = Depends(_get_service),
):
    """Record a storefront analytics event (public)."""
    await service.record_event(body)
    return SuccessResponse(message="Event recorded")


# ── Seller Dashboard ──


@router.get("/overview", response_model=OverviewResponse)
async def get_overview(
    current_user: User = Depends(get_current_seller),
    service: AnalyticsService = Depends(_get_service),
    start_date: date = Query(default_factory=lambda: date.today() - timedelta(days=30)),
    end_date: date = Query(default_factory=date.today),
):
    """Revenue, orders, views, and unique visitors overview."""
    return await service.get_overview(current_user.id, start_date, end_date)


@router.get("/products", response_model=TopProductsResponse)
async def get_top_products(
    current_user: User = Depends(get_current_seller),
    service: AnalyticsService = Depends(_get_service),
    start_date: date = Query(default_factory=lambda: date.today() - timedelta(days=30)),
    end_date: date = Query(default_factory=date.today),
    metric: str = Query("views", pattern="^(views|sales)$"),
):
    """Top products ranked by views or sales."""
    return await service.get_top_products(current_user.id, start_date, end_date, metric)


@router.get("/traffic", response_model=TrafficResponse)
async def get_traffic(
    current_user: User = Depends(get_current_seller),
    service: AnalyticsService = Depends(_get_service),
    start_date: date = Query(default_factory=lambda: date.today() - timedelta(days=30)),
    end_date: date = Query(default_factory=date.today),
):
    """Referrer traffic breakdown."""
    return await service.get_traffic(current_user.id, start_date, end_date)


@router.get("/customers", response_model=CustomerStatsResponse)
async def get_customer_stats(
    current_user: User = Depends(get_current_seller),
    service: AnalyticsService = Depends(_get_service),
    start_date: date = Query(default_factory=lambda: date.today() - timedelta(days=30)),
    end_date: date = Query(default_factory=date.today),
):
    """Customer count, repeat rate, and average order value."""
    return await service.get_customer_stats(current_user.id, start_date, end_date)


@router.get("/funnel", response_model=FunnelResponse)
async def get_funnel(
    current_user: User = Depends(get_current_seller),
    service: AnalyticsService = Depends(_get_service),
    start_date: date = Query(default_factory=lambda: date.today() - timedelta(days=30)),
    end_date: date = Query(default_factory=date.today),
):
    """View → purchase conversion funnel."""
    return await service.get_funnel(current_user.id, start_date, end_date)


@router.get("/revenue-chart", response_model=RevenueChartResponse)
async def get_revenue_chart(
    current_user: User = Depends(get_current_seller),
    service: AnalyticsService = Depends(_get_service),
    start_date: date = Query(default_factory=lambda: date.today() - timedelta(days=30)),
    end_date: date = Query(default_factory=date.today),
):
    """Time-series revenue chart data."""
    return await service.get_revenue_chart(current_user.id, start_date, end_date)
