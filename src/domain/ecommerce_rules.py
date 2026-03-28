"""Pure business rules for catalog, cart, and checkout (no FastAPI / DB imports)."""

from decimal import Decimal


class DomainError(ValueError):
    """Raised when an e-commerce rule is violated."""


def validate_product_price_and_stock(*, price: Decimal, stock_quantity: int) -> None:
    if price < 0:
        raise DomainError("Product price must be >= 0")
    if stock_quantity < 0:
        raise DomainError("Inventory must be >= 0")


def validate_cart_line_quantity(*, quantity: int) -> None:
    if quantity < 1:
        raise DomainError("Quantity must be at least 1")


def validate_quantity_vs_stock(*, quantity: int, stock_quantity: int) -> None:
    validate_cart_line_quantity(quantity=quantity)
    if quantity > stock_quantity:
        raise DomainError("Quantity exceeds available inventory")


def ensure_cart_not_empty(*, line_count: int) -> None:
    if line_count < 1:
        raise DomainError("Cart is empty")
