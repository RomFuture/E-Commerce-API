from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from src.domain.ecommerce_rules import (
    validate_cart_line_quantity,
    validate_quantity_vs_stock,
)
from src.infrastructure.db.models.cart_item import CartItem
from src.infrastructure.db.models.product import Product


class CartError(Exception):
    """Raised when a cart operation cannot be completed (e.g. invalid product)."""


@dataclass(frozen=True, slots=True)
class CartLineView:
    product_id: int
    name: str
    unit_price: Decimal
    quantity: int
    line_total: Decimal


@dataclass(frozen=True, slots=True)
class CartSummary:
    lines: list[CartLineView]
    line_count: int
    item_quantity_total: int
    subtotal: Decimal


def get_cart_summary(db: Session, user_id: int) -> CartSummary:
    items = db.scalars(
        select(CartItem)
        .options(joinedload(CartItem.product))
        .where(CartItem.user_id == user_id)
        .order_by(CartItem.id),
    ).all()
    lines: list[CartLineView] = []
    subtotal = Decimal("0")
    qty_total = 0
    for row in items:
        product = row.product
        line_total = product.price * row.quantity
        lines.append(
            CartLineView(
                product_id=product.id,
                name=product.name,
                unit_price=product.price,
                quantity=row.quantity,
                line_total=line_total,
            ),
        )
        subtotal += line_total
        qty_total += row.quantity
    return CartSummary(
        lines=lines,
        line_count=len(lines),
        item_quantity_total=qty_total,
        subtotal=subtotal,
    )


def add_cart_item(db: Session, *, user_id: int, product_id: int, quantity: int) -> CartSummary:
    validate_cart_line_quantity(quantity=quantity)
    product = db.get(Product, product_id)
    if product is None or not product.is_active:
        raise CartError("Product not available")

    existing = db.scalar(
        select(CartItem).where(
            CartItem.user_id == user_id,
            CartItem.product_id == product_id,
        ),
    )
    new_qty = quantity + (existing.quantity if existing else 0)
    validate_quantity_vs_stock(quantity=new_qty, stock_quantity=product.stock_quantity)
    if existing:
        existing.quantity = new_qty
    else:
        db.add(CartItem(user_id=user_id, product_id=product_id, quantity=quantity))
    db.commit()
    return get_cart_summary(db, user_id)


def update_cart_item_quantity(
    db: Session,
    *,
    user_id: int,
    product_id: int,
    quantity: int,
) -> CartSummary | None:
    validate_cart_line_quantity(quantity=quantity)
    row = db.scalar(
        select(CartItem)
        .options(joinedload(CartItem.product))
        .where(
            CartItem.user_id == user_id,
            CartItem.product_id == product_id,
        ),
    )
    if row is None:
        return None
    product = row.product
    if not product.is_active:
        raise CartError("Product not available")
    validate_quantity_vs_stock(quantity=quantity, stock_quantity=product.stock_quantity)
    row.quantity = quantity
    db.commit()
    return get_cart_summary(db, user_id)


def remove_cart_item(db: Session, *, user_id: int, product_id: int) -> CartSummary:
    row = db.scalar(
        select(CartItem).where(
            CartItem.user_id == user_id,
            CartItem.product_id == product_id,
        ),
    )
    if row is not None:
        db.delete(row)
        db.commit()
    return get_cart_summary(db, user_id)
