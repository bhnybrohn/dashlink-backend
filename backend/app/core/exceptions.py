"""Custom exception hierarchy for DashLink.

All domain errors inherit from DashLinkError so they can be caught
in a single error handler middleware.
"""

from typing import Any


class DashLinkError(Exception):
    """Base exception for all DashLink domain errors."""

    status_code: int = 500
    error_code: str = "INTERNAL_ERROR"

    def __init__(self, detail: str = "An unexpected error occurred", **context: Any) -> None:
        self.detail = detail
        self.context = context
        super().__init__(detail)


class NotFoundError(DashLinkError):
    status_code = 404
    error_code = "NOT_FOUND"

    def __init__(self, resource: str = "resource", resource_id: str = "") -> None:
        detail = f"{resource} not found"
        if resource_id:
            detail = f"{resource} with id '{resource_id}' not found"
        super().__init__(detail=detail, resource=resource, resource_id=resource_id)


class BadRequestError(DashLinkError):
    status_code = 400
    error_code = "BAD_REQUEST"


class ConflictError(DashLinkError):
    status_code = 409
    error_code = "CONFLICT"


class UnauthorizedError(DashLinkError):
    status_code = 401
    error_code = "UNAUTHORIZED"

    def __init__(self, detail: str = "Invalid or expired credentials") -> None:
        super().__init__(detail=detail)


class ForbiddenError(DashLinkError):
    status_code = 403
    error_code = "FORBIDDEN"

    def __init__(self, detail: str = "You do not have permission to perform this action") -> None:
        super().__init__(detail=detail)


class RateLimitError(DashLinkError):
    status_code = 429
    error_code = "RATE_LIMITED"

    def __init__(self, detail: str = "Too many requests, please try again later") -> None:
        super().__init__(detail=detail)


class PaymentError(DashLinkError):
    status_code = 402
    error_code = "PAYMENT_ERROR"


class StockLockError(DashLinkError):
    status_code = 409
    error_code = "STOCK_LOCK_FAILED"

    def __init__(self, detail: str = "Unable to reserve inventory") -> None:
        super().__init__(detail=detail)


class OptimisticLockError(DashLinkError):
    status_code = 409
    error_code = "OPTIMISTIC_LOCK_FAILED"

    def __init__(self, detail: str = "Resource was modified by another request") -> None:
        super().__init__(detail=detail)


class UsageLimitError(DashLinkError):
    status_code = 429
    error_code = "USAGE_LIMIT_EXCEEDED"

    def __init__(self, feature: str = "feature", limit: int = 0) -> None:
        detail = f"Monthly {feature} limit ({limit}) exceeded. Upgrade your plan for more."
        super().__init__(detail=detail, feature=feature, limit=limit)
