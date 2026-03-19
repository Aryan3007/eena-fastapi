import razorpay

from app.config.settings import settings

razorpay_client: razorpay.Client | None = None


def get_razorpay_client() -> razorpay.Client:
    global razorpay_client
    if razorpay_client is None:
        razorpay_client = razorpay.Client(
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET)
        )
    return razorpay_client
