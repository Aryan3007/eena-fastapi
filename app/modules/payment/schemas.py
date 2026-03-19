from pydantic import BaseModel


class CreatePaymentOrderRequest(BaseModel):
    amount: int  # Amount in paise
    source_reel: str | None = None


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    source_reel: str | None = None
