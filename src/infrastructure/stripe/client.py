"""Stripe Checkout Session creation (docs/STRIPE_INTEGRATION_GUIDE.md §4)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import stripe


@dataclass(frozen=True, slots=True)
class CheckoutLineInput:
    product_name: str
    unit_amount_cents: int
    quantity: int


@dataclass(frozen=True, slots=True)
class CreatedCheckoutSession:
    session_id: str
    url: str
    payment_intent_id: str | None


def usd_decimal_to_cents(amount: Decimal) -> int:
    quantized = amount.quantize(Decimal("0.01"))
    cents = int(quantized * 100)
    if cents < 0:
        msg = "Amount must be >= 0"
        raise ValueError(msg)
    return cents


def _payment_intent_id_from_session(session: Any) -> str | None:
    pi = getattr(session, "payment_intent", None)
    if pi is None:
        return None
    if isinstance(pi, str):
        return pi
    return getattr(pi, "id", None)


def create_checkout_session_for_order(
    *,
    api_key: str,
    line_items: list[CheckoutLineInput],
    order_id: int,
    success_url: str,
    cancel_url: str,
    currency: str = "usd",
) -> CreatedCheckoutSession:
    stripe.api_key = api_key
    payload_line_items = [
        {
            "price_data": {
                "currency": currency,
                "product_data": {"name": item.product_name},
                "unit_amount": item.unit_amount_cents,
            },
            "quantity": item.quantity,
        }
        for item in line_items
    ]
    session = stripe.checkout.Session.create(
        mode="payment",
        line_items=payload_line_items,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={"order_id": str(order_id)},
        client_reference_id=str(order_id),
    )
    url = session.url
    if not url:
        msg = "Stripe Checkout Session created without a redirect URL"
        raise RuntimeError(msg)
    return CreatedCheckoutSession(
        session_id=session.id,
        url=url,
        payment_intent_id=_payment_intent_id_from_session(session),
    )
