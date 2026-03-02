"""Shared Pydantic schemas — reused across all modules (DRY)."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TimestampMixin(BaseModel):
    """Mixin that adds timestamp fields to any response schema."""

    created_at: datetime
    updated_at: datetime


class PaginationParams(BaseModel):
    """Standard pagination query parameters."""

    offset: int = 0
    limit: int = 20

    model_config = ConfigDict(frozen=True)


class PaginatedResponse[T](BaseModel):
    """Generic paginated response wrapper."""

    items: list[T]
    total: int
    offset: int
    limit: int
    has_more: bool


class ErrorResponse(BaseModel):
    """Standard error response body."""

    error: str
    detail: str | None = None
    code: str | None = None


class SuccessResponse(BaseModel):
    """Simple success acknowledgement."""

    message: str = "ok"
