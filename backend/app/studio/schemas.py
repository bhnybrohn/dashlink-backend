"""Studio request/response schemas."""

from pydantic import BaseModel, ConfigDict, Field

from app.core.base_schemas import TimestampMixin


class TitleRequest(BaseModel):
    product_id: str | None = None
    category: str | None = None
    keywords: list[str] = Field(default_factory=list)
    image_url: str | None = None


class DescriptionRequest(BaseModel):
    product_id: str | None = None
    title: str
    category: str | None = None
    tone: str = Field(default="professional", pattern="^(professional|casual|luxury|playful|minimal)$")
    image_url: str | None = None


class CaptionRequest(BaseModel):
    product_name: str
    platform: str = Field(default="instagram", pattern="^(instagram|x|tiktok)$")
    tone: str = Field(default="casual", pattern="^(professional|casual|luxury|playful|minimal)$")
    product_id: str | None = None


class ImageGenRequest(BaseModel):
    prompt: str = Field(..., max_length=1000)
    style: str = Field(default="product-photo", max_length=50)
    product_id: str | None = None


class BackgroundRemoveRequest(BaseModel):
    image_url: str
    product_id: str | None = None


class EnhanceRequest(BaseModel):
    product_id: str
    category: str | None = None
    tone: str = Field(default="professional", pattern="^(professional|casual|luxury|playful|minimal)$")


class GenerationResponse(TimestampMixin):
    model_config = ConfigDict(from_attributes=True)

    id: str
    seller_id: str
    product_id: str | None
    generation_type: str
    input_data: dict
    output_data: dict | None
    status: str
    ai_model: str | None
    tokens_used: int | None
    cost_cents: int | None


class UsageResponse(BaseModel):
    """Monthly usage vs tier limits."""

    tier: str
    month: str
    usage: dict[str, int]
    limits: dict[str, int | str]
