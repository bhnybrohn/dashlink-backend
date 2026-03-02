"""User and Address models — owned by the users module."""

from sqlalchemy import Boolean, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.base_model import BaseModel


class User(BaseModel):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    hashed_password: Mapped[str | None] = mapped_column(String(255), nullable=True)
    role: Mapped[str] = mapped_column(
        Enum("seller", "buyer", "admin", name="user_role_enum", create_constraint=True),
        nullable=False,
    )
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    mfa_secret: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    last_login_at: Mapped[str | None] = mapped_column(nullable=True)
    is_shadow: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    fcm_token: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Relationships
    addresses: Mapped[list["Address"]] = relationship(back_populates="user", lazy="selectin")
    seller_profile: Mapped["SellerProfile | None"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="user",
        lazy="selectin",
        uselist=False,
    )
    oauth_accounts: Mapped[list["OAuthAccount"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        back_populates="user",
        lazy="selectin",
    )


class Address(BaseModel):
    __tablename__ = "addresses"

    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)  # encrypted at app layer
    line_1: Mapped[str] = mapped_column(String(500), nullable=False)     # encrypted
    line_2: Mapped[str | None] = mapped_column(String(500), nullable=True)  # encrypted
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False)  # ISO 3166-1 alpha-2
    phone: Mapped[str | None] = mapped_column(String(255), nullable=True)  # encrypted
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="addresses")
