import pytest

from src.domain.ecommerce_rules import (
    DomainError,
    ensure_cart_not_empty,
    validate_cart_line_quantity,
    validate_product_price_and_stock,
    validate_quantity_vs_stock,
)
from decimal import Decimal


def test_product_price_negative() -> None:
    with pytest.raises(DomainError, match="price"):
        validate_product_price_and_stock(price=Decimal("-1"), stock_quantity=0)


def test_product_stock_negative() -> None:
    with pytest.raises(DomainError, match="Inventory"):
        validate_product_price_and_stock(price=Decimal("0"), stock_quantity=-1)


def test_product_ok() -> None:
    validate_product_price_and_stock(price=Decimal("9.99"), stock_quantity=10)


def test_cart_line_quantity_zero() -> None:
    with pytest.raises(DomainError, match="Quantity"):
        validate_cart_line_quantity(quantity=0)


def test_quantity_exceeds_stock() -> None:
    with pytest.raises(DomainError, match="inventory"):
        validate_quantity_vs_stock(quantity=5, stock_quantity=3)


def test_cart_empty() -> None:
    with pytest.raises(DomainError, match="empty"):
        ensure_cart_not_empty(line_count=0)
