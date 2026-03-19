from pydantic import BaseModel, Field


class AddCartItemRequest(BaseModel):
    product: str
    quantity: int = Field(default=1, ge=1)


class UpdateCartItemRequest(BaseModel):
    product: str
    quantity: int = Field(..., ge=0)
