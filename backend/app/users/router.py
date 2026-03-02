"""User API routes."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.core.base_schemas import SuccessResponse
from app.database import get_db
from app.users.models import User
from app.users.schemas import (
    AddressCreate,
    AddressResponse,
    AddressUpdate,
    ChangePasswordRequest,
    FCMTokenRequest,
    UpdateProfileRequest,
    UserResponse,
)
from app.users.service import UserService

router = APIRouter(prefix="/users", tags=["Users"])


def _get_service(db: AsyncSession = Depends(get_db)) -> UserService:
    return UserService(db)


# ── Profile ──


@router.get("/me", response_model=UserResponse)
async def get_profile(
    current_user: User = Depends(get_current_user),
):
    """Get the currently authenticated user's profile."""
    return current_user


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    body: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(_get_service),
):
    """Update the current user's profile."""
    return await service.update_profile(
        current_user.id,
        email=body.email,
        phone=body.phone,
    )


@router.put("/me/password", response_model=SuccessResponse)
async def change_password(
    body: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(_get_service),
):
    """Change the current user's password."""
    await service.change_password(
        current_user.id, body.current_password, body.new_password
    )
    return SuccessResponse(message="Password updated successfully")


@router.delete("/me", response_model=SuccessResponse)
async def delete_account(
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(_get_service),
):
    """Delete account and anonymize data (GDPR)."""
    await service.delete_account(current_user.id)
    return SuccessResponse(message="Account deleted")


@router.get("/me/data-export")
async def export_data(
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(_get_service),
):
    """Export all user data as JSON (GDPR)."""
    return await service.export_data(current_user.id)


# ── Addresses ──


@router.get("/me/addresses", response_model=list[AddressResponse])
async def list_addresses(
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(_get_service),
):
    """List all saved addresses."""
    return await service.list_addresses(current_user.id)


@router.post("/me/addresses", response_model=AddressResponse, status_code=201)
async def create_address(
    body: AddressCreate,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(_get_service),
):
    """Add a new saved address."""
    return await service.create_address(current_user.id, **body.model_dump())


@router.patch("/me/addresses/{address_id}", response_model=AddressResponse)
async def update_address(
    address_id: str,
    body: AddressUpdate,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(_get_service),
):
    """Update a saved address."""
    return await service.update_address(
        current_user.id, address_id, **body.model_dump(exclude_unset=True)
    )


@router.delete("/me/addresses/{address_id}", response_model=SuccessResponse)
async def delete_address(
    address_id: str,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(_get_service),
):
    """Delete a saved address."""
    await service.delete_address(current_user.id, address_id)
    return SuccessResponse(message="Address deleted")


# ── FCM Token ──


@router.put("/me/fcm-token", response_model=SuccessResponse)
async def register_fcm_token(
    body: FCMTokenRequest,
    current_user: User = Depends(get_current_user),
    service: UserService = Depends(_get_service),
):
    """Register or update the user's FCM device token for push notifications."""
    await service.update_fcm_token(current_user.id, body.fcm_token)
    return SuccessResponse(message="FCM token registered")
