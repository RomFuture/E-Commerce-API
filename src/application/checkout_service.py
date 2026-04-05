"""Checkout orchestration: cart → order snapshot → Stripe Checkout Session (guide §5)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import stripe
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.application.cart_service import get_cart_summary
from src.domain.checkout_statuses import OrderStatus, PaymentStatus, assert_valid_order_transition
from src.domain.ecommerce_rules import (
    DomainError,
    ensure_cart_not_empty,
    validate_quantity_vs_stock,
)
from src.infrastructure.config.settings import Settings
from src.infrastructure.db.models.cart_item import CartItem
from src.infrastructure.db.models.order import Order
from src.infrastructure.db.models.order_item import OrderItem
from src.infrastructure.db.models.payment import Payment
from src.infrastructure.db.models.product import Product
from src.infrastructure.stripe.client import (
    CheckoutLineInput,
    create_checkout_session_for_order,
    usd_decimal_to_cents,
)


class CheckoutError(Exception):
    """Checkout cannot be completed (cart, stock, Stripe, etc.)."""


@dataclass(frozen=True, slots=True)
class CheckoutStarted:
    order_id: int
    checkout_url: str


def start_checkout_from_cart(db: Session, user_id: int, settings: Settings) -> CheckoutStarted:
    """
    Build order + payment from the current cart, create a Stripe Checkout Session, clear the cart.

    Inventory is decreased only after payment is confirmed (webhook), not here (guide §5.2).
    """
    summary = get_cart_summary(db, user_id)
    try:
        ensure_cart_not_empty(line_count=summary.line_count)
    except DomainError as e:
        raise CheckoutError(str(e)) from e

    product_ids = [line.product_id for line in summary.lines]
    products = db.scalars(select(Product).where(Product.id.in_(product_ids))).all()
    by_id = {p.id: p for p in products}

    stripe_lines: list[CheckoutLineInput] = []
    subtotal = Decimal("0")
    for line in summary.lines:
        product = by_id.get(line.product_id)
        if product is None or not product.is_active:
            raise CheckoutError("Product not available")
        try:
            validate_quantity_vs_stock(
                quantity=line.quantity, stock_quantity=product.stock_quantity
            )
        except DomainError as e:
            raise CheckoutError(str(e)) from e
        line_total = product.price * line.quantity
        subtotal += line_total
        stripe_lines.append(
            CheckoutLineInput(
                product_name=product.name,
                unit_amount_cents=usd_decimal_to_cents(product.price),
                quantity=line.quantity,
            ),
        )

    key = settings.stripe_secret_key.strip()
    if not key or key == "sk_test_xxx":
        raise CheckoutError("Stripe API key is not configured")

    order = Order(
        user_id=user_id,
        status=OrderStatus.PENDING.value,
        total_amount=subtotal,
    )
    db.add(order)
    db.flush()
    for line in summary.lines:
        product = by_id[line.product_id]
        db.add(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                quantity=line.quantity,
                unit_price=product.price,
            ),
        )
    payment = Payment(
        order_id=order.id,
        provider="stripe",
        amount=subtotal,
        currency="USD",
        status=PaymentStatus.PENDING.value,
    )
    db.add(payment)
    db.flush()

    try:
        created = create_checkout_session_for_order(
            api_key=key,
            line_items=stripe_lines,
            order_id=order.id,
            success_url=settings.stripe_checkout_success_url,
            cancel_url=settings.stripe_checkout_cancel_url,
            currency="usd",
        )
    except stripe.StripeError as e:
        db.rollback()
        raise CheckoutError("Could not start payment with the provider") from e
    except (RuntimeError, ValueError) as e:
        db.rollback()
        raise CheckoutError(str(e)) from e

    payment.stripe_checkout_session_id = created.session_id
    payment.stripe_payment_intent_id = created.payment_intent_id
    assert_valid_order_transition(
        from_status=order.status,
        to_status=OrderStatus.AWAITING_PAYMENT.value,
    )
    order.status = OrderStatus.AWAITING_PAYMENT.value
    db.execute(delete(CartItem).where(CartItem.user_id == user_id))
    db.commit()
    return CheckoutStarted(order_id=order.id, checkout_url=created.url)
