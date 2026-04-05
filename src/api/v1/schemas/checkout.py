from pydantic import BaseModel


class CheckoutSessionOut(BaseModel):
    order_id: int
    checkout_url: str
