from decimal import Decimal

from pydantic import BaseModel, Field


class CartLineOut(BaseModel):
    product_id: int
    name: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal


class CartOut(BaseModel):
    lines: list[CartLineOut]
    line_count: int
    item_quantity_total: int
    subtotal: Decimal


class CartItemAdd(BaseModel):
    product_id: int = Field(ge=1)
    quantity: int = Field(ge=1)


class CartItemQuantityPatch(BaseModel):
    quantity: int = Field(ge=1)
