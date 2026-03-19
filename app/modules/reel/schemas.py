from pydantic import BaseModel, Field


class TaggedProductInput(BaseModel):
    product: str
    x: float = 0.0
    y: float = 0.0


class CreateReelRequest(BaseModel):
    video_url: str
    thumbnail_url: str
    caption: str | None = None
    hashtags: list[str] = Field(default_factory=list)
    tagged_products: list[TaggedProductInput] = Field(..., min_length=1)
    is_sponsored: bool = False
    sponsor_brand: str | None = None
    sponsored_campaign_id: str | None = None
