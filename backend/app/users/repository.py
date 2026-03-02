"""User repository — data access for User and Address models."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_repository import BaseRepository
from app.users.models import Address, User


class UserRepository(BaseRepository[User]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(User, session)

    async def get_by_email(self, email: str) -> User | None:
        """Find a user by email (case-insensitive)."""
        query = (
            self._base_query()
            .where(User.email.ilike(email))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_by_phone(self, phone: str) -> User | None:
        """Find a user by phone number."""
        query = self._base_query().where(User.phone == phone)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def email_exists(self, email: str) -> bool:
        """Check if an email is already registered."""
        user = await self.get_by_email(email)
        return user is not None

    async def get_shadow_by_email(self, email: str) -> User | None:
        """Find a shadow account by email."""
        query = (
            self._base_query()
            .where(User.email.ilike(email), User.is_shadow.is_(True))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()


class AddressRepository(BaseRepository[Address]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Address, session)

    async def get_user_addresses(self, user_id: str) -> list[Address]:
        """Get all addresses for a user."""
        query = (
            self._base_query()
            .where(Address.user_id == user_id)
            .order_by(Address.is_default.desc(), Address.created_at.desc())
        )
        result = await self.session.execute(query)
        return list(result.scalars().all())

    async def get_default_address(self, user_id: str) -> Address | None:
        """Get user's default address."""
        query = (
            self._base_query()
            .where(Address.user_id == user_id, Address.is_default.is_(True))
        )
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def clear_default(self, user_id: str) -> None:
        """Unset the default flag on all addresses for a user."""
        addresses = await self.get_user_addresses(user_id)
        for addr in addresses:
            if addr.is_default:
                addr.is_default = False
        await self.session.flush()
