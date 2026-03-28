from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ProductPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    price: Decimal
    stock_quantity: int


class ProductListResponse(BaseModel):
    items: list[ProductPublic]
    total: int


class ProductAdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    price: Decimal
    stock_quantity: int
    is_active: bool


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    price: Decimal = Field(ge=0)
    stock_quantity: int = Field(ge=0)
    is_active: bool = True

    @field_validator("price")
    @classmethod
    def price_two_decimals(cls, v: Decimal) -> Decimal:
        return v.quantize(Decimal("0.01"))


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    price: Decimal | None = Field(default=None, ge=0)
    stock_quantity: int | None = Field(default=None, ge=0)
    is_active: bool | None = None

    @field_validator("price")
    @classmethod
    def price_two_decimals(cls, v: Decimal | None) -> Decimal | None:
        if v is None:
            return None
        return v.quantize(Decimal("0.01"))
