"""Trust & fraud scoring request/response schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.base_schemas import TimestampMixin


# ── Responses ──


class TrustScoreResponse(TimestampMixin):
    model_config = ConfigDict(from_attributes=True)

    id: str
    seller_id: str
    score: int
    level: str
    factors: dict | None = None
    last_calculated_at: datetime | None = None


class TrustScoreListResponse(BaseModel):
    scores: list[TrustScoreResponse]
    total: int


class OrderRiskFlagResponse(TimestampMixin):
    model_config = ConfigDict(from_attributes=True)

    id: str
    order_id: str
    risk_score: int
    flags: dict | None = None
    action_taken: str
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None


class OrderRiskFlagListResponse(BaseModel):
    flagged_orders: list[OrderRiskFlagResponse]
    total: int


# ── Requests ──


class ReviewRiskFlagRequest(BaseModel):
    action: str = Field(..., pattern="^(none|review|hold_payout|block)$")
