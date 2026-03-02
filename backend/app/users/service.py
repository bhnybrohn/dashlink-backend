"""User service — profile management, address CRUD, GDPR operations."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.encryption import decrypt_value, encrypt_value
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.security import hash_password, verify_password
from app.users.models import Address, User
from app.users.repository import AddressRepository, UserRepository


class UserService:
    def __init__(self, session: AsyncSession) -> None:
        self.user_repo = UserRepository(session)
        self.address_repo = AddressRepository(session)

    # ── Profile ──

    async def get_profile(self, user_id: str) -> User:
        return await self.user_repo.get_or_404(user_id)

    async def update_profile(
        self,
        user_id: str,
        *,
        email: str | None = None,
        phone: str | None = None,
    ) -> User:
        update_data: dict = {}
        if email is not None:
            existing = await self.user_repo.get_by_email(email)
            if existing and existing.id != user_id:
                raise BadRequestError(detail="Email already in use")
            update_data["email"] = email

        if phone is not None:
            update_data["phone"] = phone

        if not update_data:
            return await self.user_repo.get_or_404(user_id)

        return await self.user_repo.update(user_id, **update_data)

    async def change_password(
        self, user_id: str, current_password: str, new_password: str
    ) -> None:
        user = await self.user_repo.get_or_404(user_id)
        if user.hashed_password and not verify_password(current_password, user.hashed_password):
            raise BadRequestError(detail="Current password is incorrect")
        await self.user_repo.update(user_id, hashed_password=hash_password(new_password))

    async def update_fcm_token(self, user_id: str, fcm_token: str) -> None:
        """Store or update the user's FCM device token."""
        await self.user_repo.update(user_id, fcm_token=fcm_token)

    async def merge_shadow_account(self, shadow_user: User, password: str) -> User:
        """Convert a shadow account into a full account."""
        return await self.user_repo.update(
            shadow_user.id,
            hashed_password=hash_password(password),
            is_shadow=False,
        )

    # ── GDPR ──

    async def export_data(self, user_id: str) -> dict:
        """Export all user data as a dict (GDPR right to data export)."""
        user = await self.user_repo.get_or_404(user_id)
        addresses = await self.address_repo.get_user_addresses(user_id)

        return {
            "user": {
                "id": user.id,
                "email": user.email,
                "phone": user.phone,
                "role": user.role,
                "created_at": str(user.created_at),
            },
            "addresses": [
                {
                    "full_name": decrypt_value(a.full_name) if a.full_name else None,
                    "city": a.city,
                    "country": a.country,
                }
                for a in addresses
            ],
        }

    async def delete_account(self, user_id: str) -> None:
        """Soft-delete and anonymize user data (GDPR right to deletion)."""
        await self.user_repo.update(
            user_id,
            email=f"deleted_{user_id}@anon.dashlink.to",
            phone=None,
            hashed_password=None,
            mfa_secret=None,
            mfa_enabled=False,
            is_active=False,
        )
        await self.user_repo.soft_delete(user_id)

    # ── Addresses ──

    async def list_addresses(self, user_id: str) -> list[Address]:
        return await self.address_repo.get_user_addresses(user_id)

    async def create_address(self, user_id: str, **data: str | bool | None) -> Address:
        # Encrypt PII fields
        encrypted: dict = {**data, "user_id": user_id}
        for field in ("full_name", "line_1", "line_2", "phone"):
            if encrypted.get(field):
                encrypted[field] = encrypt_value(str(encrypted[field]))

        if data.get("is_default"):
            await self.address_repo.clear_default(user_id)

        return await self.address_repo.create(**encrypted)

    async def update_address(self, user_id: str, address_id: str, **data: str | bool | None) -> Address:
        address = await self.address_repo.get_or_404(address_id)
        if address.user_id != user_id:
            raise NotFoundError(resource="address", resource_id=address_id)

        # Encrypt updated PII fields
        for field in ("full_name", "line_1", "line_2", "phone"):
            if field in data and data[field] is not None:
                data[field] = encrypt_value(str(data[field]))

        if data.get("is_default"):
            await self.address_repo.clear_default(user_id)

        return await self.address_repo.update(address_id, **{k: v for k, v in data.items() if v is not None})

    async def delete_address(self, user_id: str, address_id: str) -> None:
        address = await self.address_repo.get_or_404(address_id)
        if address.user_id != user_id:
            raise NotFoundError(resource="address", resource_id=address_id)
        await self.address_repo.soft_delete(address_id)
