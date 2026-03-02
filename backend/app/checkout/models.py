"""Stock lock model — owned by the checkout module."""

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class StockLock(BaseModel):
    __tablename__ = "stock_locks"

    product_id: Mapped[str] = mapped_column(ForeignKey("products.id"), nullable=False, index=True)
    variant_id: Mapped[str | None] = mapped_column(ForeignKey("product_variants.id"), nullable=True)
    session_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    locked_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[str] = mapped_column(DateTime(timezone=True), nullable=False)
