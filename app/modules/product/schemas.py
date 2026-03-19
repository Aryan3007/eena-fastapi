from pydantic import BaseModel, Field


class CreateProductRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=200)
    description: str = Field(..., min_length=10)
    price: float = Field(..., gt=0)
    discounted_price: float | None = None
    category: str = Field(..., min_length=1)
    images: list[str] = Field(default_factory=list)
    stock: int = Field(default=0, ge=0)


class UpdateProductRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    price: float | None = None
    discounted_price: float | None = None
    category: str | None = None
    images: list[str] | None = None
    stock: int | None = None
