"""RBAC permissions — FastAPI dependency for role and permission checks."""

from enum import StrEnum
from typing import Any

from fastapi import Depends

from app.core.exceptions import ForbiddenError


class Role(StrEnum):
    SELLER = "seller"
    BUYER = "buyer"
    ADMIN = "admin"


class Permission(StrEnum):
    """Granular permissions for team roles within a seller account."""

    MANAGE_PRODUCTS = "manage_products"
    MANAGE_ORDERS = "manage_orders"
    MANAGE_PAYOUTS = "manage_payouts"
    MANAGE_TEAM = "manage_team"
    VIEW_ANALYTICS = "view_analytics"
    MANAGE_STOREFRONT = "manage_storefront"
    USE_STUDIO = "use_studio"


# Default permissions by team role
TEAM_ROLE_PERMISSIONS: dict[str, set[Permission]] = {
    "owner": set(Permission),  # all permissions
    "manager": {
        Permission.MANAGE_PRODUCTS,
        Permission.MANAGE_ORDERS,
        Permission.VIEW_ANALYTICS,
        Permission.MANAGE_STOREFRONT,
        Permission.USE_STUDIO,
    },
    "fulfiller": {
        Permission.MANAGE_ORDERS,
    },
}


class RequireRole:
    """Dependency that enforces the user has one of the allowed roles.

    Usage:
        @router.get("/admin-only", dependencies=[Depends(RequireRole(Role.ADMIN))])
    """

    def __init__(self, *roles: Role) -> None:
        self.roles = roles

    def __call__(self, current_user: Any) -> Any:
        if current_user.role not in self.roles:
            raise ForbiddenError(
                detail=f"Requires role: {', '.join(self.roles)}"
            )
        return current_user


class RequirePermission:
    """Dependency that enforces the user has a specific permission.

    Used for team-based RBAC within a seller account.
    """

    def __init__(self, permission: Permission) -> None:
        self.permission = permission

    def __call__(self, current_user: Any) -> Any:
        # Owner always has all permissions
        if hasattr(current_user, "role") and current_user.role == Role.ADMIN:
            return current_user

        # Check team_role permissions if applicable
        team_role = getattr(current_user, "team_role", "owner")
        allowed = TEAM_ROLE_PERMISSIONS.get(team_role, set())

        if self.permission not in allowed:
            raise ForbiddenError(
                detail=f"Missing permission: {self.permission}"
            )
        return current_user
