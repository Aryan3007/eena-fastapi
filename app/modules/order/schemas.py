from pydantic import BaseModel


class CreateOrderRequest(BaseModel):
    source_reel: str | None = None  # Reel ID for affiliate tracking


class UpdateOrderStatusRequest(BaseModel):
    status: str  # SHIPPED | DELIVERED
