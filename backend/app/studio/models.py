"""Studio generation tracking model."""

from sqlalchemy import Enum, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.base_model import BaseModel


class StudioGeneration(BaseModel):
    __tablename__ = "studio_generations"
    __table_args__ = (
        Index("ix_studio_seller_type", "seller_id", "generation_type"),
    )

    seller_id: Mapped[str] = mapped_column(ForeignKey("seller_profiles.id"), nullable=False, index=True)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id"), nullable=True)
    generation_type: Mapped[str] = mapped_column(
        Enum(
            "image", "title", "description", "caption", "background_removal",
            name="generation_type_enum",
            create_constraint=True,
        ),
        nullable=False,
    )
    input_data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    output_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        Enum(
            "pending", "processing", "completed", "failed",
            name="generation_status_enum",
            create_constraint=True,
        ),
        default="pending",
        nullable=False,
    )
    ai_model: Mapped[str | None] = mapped_column(String(50), nullable=True)
    tokens_used: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cost_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)
