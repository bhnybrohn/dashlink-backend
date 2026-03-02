"""Auth dependencies — FastAPI dependency injection for authentication."""

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.database import get_db
from app.users.models import User
from app.users.repository import UserRepository

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Decode JWT, load user from DB, return User object.

    Raises UnauthorizedError if token is missing, invalid, or user not found.
    """
    if credentials is None:
        raise UnauthorizedError(detail="Unathenticated — no credentials provided")

    payload = decode_token(credentials.credentials)

    if payload.get("type") != "access":
        raise UnauthorizedError(detail="Invalid token type — expected access token")

    user_id: str | None = payload.get("sub")
    if not user_id:
        raise UnauthorizedError(detail="Token missing subject")

    user_repo = UserRepository(db)
    user = await user_repo.get(user_id)

    if not user:
        raise UnauthorizedError(detail="User not found")

    if not user.is_active:
        raise UnauthorizedError(detail="Account is deactivated")

    return user


async def get_current_seller(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure the current user is a seller."""
    if current_user.role != "seller":
        raise ForbiddenError(detail="Seller access required")
    return current_user


async def get_onboarded_seller(
    current_user: User = Depends(get_current_seller),
) -> User:
    """Ensure the seller has completed onboarding."""
    if not current_user.seller_profile:
        raise ForbiddenError(detail="Seller profile not found")
    if current_user.seller_profile.onboarding_step != 0:
        raise ForbiddenError(detail="Complete onboarding first")
    return current_user


async def get_current_buyer(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure the current user is a buyer."""
    if current_user.role != "buyer":
        raise ForbiddenError(detail="Buyer access required")
    return current_user


async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    """Ensure the current user is an admin."""
    if current_user.role != "admin":
        raise ForbiddenError(detail="Admin access required")
    return current_user


async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Optionally authenticate — returns None if no valid token present.

    Used for endpoints that work for both authenticated and anonymous users
    (e.g., checkout can be anonymous or authenticated).
    """
    if credentials is None:
        return None

    try:
        payload = decode_token(credentials.credentials)
        user_id = payload.get("sub")
        if not user_id:
            return None
        user_repo = UserRepository(db)
        return await user_repo.get(user_id)
    except Exception:
        return None
