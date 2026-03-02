"""Generic CRUD repository — all module repositories inherit from this (DRY).

Provides: create, get, get_or_404, list (paginated), update, soft_delete.
Domain-specific queries are added in each module's repository subclass.
"""

from datetime import datetime, timezone
from typing import Any, Generic, TypeVar
from uuid import uuid4

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.base_model import BaseModel
from app.core.exceptions import NotFoundError

T = TypeVar("T", bound=BaseModel)


class BaseRepository(Generic[T]):
    """Generic async repository with soft-delete awareness."""

    def __init__(self, model: type[T], session: AsyncSession) -> None:
        self.model = model
        self.session = session

    def _base_query(self) -> Select[tuple[T]]:
        """Base query that excludes soft-deleted records."""
        return select(self.model).where(self.model.deleted_at.is_(None))

    async def create(self, **kwargs: Any) -> T:
        """Create and persist a new record."""
        if "id" not in kwargs:
            kwargs["id"] = str(uuid4())
        instance = self.model(**kwargs)
        self.session.add(instance)
        await self.session.flush()
        await self.session.refresh(instance)
        return instance

    async def get(self, record_id: str) -> T | None:
        """Get a single record by ID, returns None if not found or deleted."""
        query = self._base_query().where(self.model.id == record_id)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def get_or_404(self, record_id: str) -> T:
        """Get a single record by ID, raises NotFoundError if missing."""
        record = await self.get(record_id)
        if record is None:
            raise NotFoundError(
                resource=self.model.__tablename__,
                resource_id=record_id,
            )
        return record

    async def get_by(self, **filters: Any) -> T | None:
        """Get a single record matching the given filters."""
        query = self._base_query()
        for field, value in filters.items():
            query = query.where(getattr(self.model, field) == value)
        result = await self.session.execute(query)
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        offset: int = 0,
        limit: int = 20,
        order_by: str = "created_at",
        descending: bool = True,
        filters: dict[str, Any] | None = None,
    ) -> tuple[list[T], int]:
        """List records with pagination. Returns (items, total_count)."""
        query = self._base_query()

        if filters:
            for field, value in filters.items():
                if value is not None:
                    query = query.where(getattr(self.model, field) == value)

        # Count total
        count_query = select(func.count()).select_from(query.subquery())
        total = (await self.session.execute(count_query)).scalar_one()

        # Order and paginate
        order_col = getattr(self.model, order_by)
        query = query.order_by(order_col.desc() if descending else order_col.asc())
        query = query.offset(offset).limit(limit)

        result = await self.session.execute(query)
        items = list(result.scalars().all())

        return items, total

    async def update(self, record_id: str, **kwargs: Any) -> T:
        """Update a record. Increments version for optimistic locking."""
        record = await self.get_or_404(record_id)

        # Optimistic concurrency check
        if "expected_version" in kwargs:
            expected = kwargs.pop("expected_version")
            if record.version != expected:
                raise ValueError(
                    f"Optimistic lock failed: expected version {expected}, "
                    f"got {record.version}"
                )

        for field, value in kwargs.items():
            if hasattr(record, field):
                setattr(record, field, value)

        record.version += 1
        await self.session.flush()
        await self.session.refresh(record)
        return record

    async def soft_delete(self, record_id: str) -> None:
        """Soft-delete a record by setting deleted_at."""
        record = await self.get_or_404(record_id)
        record.deleted_at = datetime.now(timezone.utc)
        record.version += 1
        await self.session.flush()
