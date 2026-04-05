"""Apply Stripe webhook events to local orders (guide §6)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from src.domain.checkout_statuses import (
    OrderStatus,
    PaymentStatus,
    assert_valid_order_transition,
    assert_valid_payment_transition,
)
from src.domain.ecommerce_rules import DomainError
from src.infrastructure.db.models.order import Order
from src.infrastructure.db.models.order_item import OrderItem
from src.infrastructure.db.models.processed_webhook_event import ProcessedWebhookEvent


def _session_metadata_order_id(session_obj: dict[str, Any]) -> int | None:
    meta = session_obj.get("metadata") or {}
    raw = meta.get("order_id")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def process_checkout_webhook_event(db: Session, event: Any) -> None:
    """
    Idempotent handler for verified Stripe events. Persists `event['id']` only after success.
    """
    if not isinstance(event, dict):
        event = event.to_dict_recursive()

    event_id = event.get("id")
    if not event_id or not isinstance(event_id, str):
        return

    if db.scalar(select(ProcessedWebhookEvent).where(ProcessedWebhookEvent.event_id == event_id)):
        return

    if event.get("type") != "checkout.session.completed":
        return

    data = event.get("data") or {}
    session_obj = data.get("object")
    if not isinstance(session_obj, dict):
        return

    if session_obj.get("payment_status") != "paid":
        return

    order_id = _session_metadata_order_id(session_obj)
    if order_id is None:
        return

    order = db.scalar(
        select(Order)
        .options(
            selectinload(Order.items).selectinload(OrderItem.product),
            selectinload(Order.payment),
        )
        .where(Order.id == order_id),
    )
    if order is None or order.payment is None:
        return

    payment = order.payment

    if order.status == OrderStatus.PAID.value and payment.status == PaymentStatus.PAID.value:
        db.add(ProcessedWebhookEvent(event_id=event_id))
        db.commit()
        return

    if order.status != OrderStatus.AWAITING_PAYMENT.value:
        return

    pi = session_obj.get("payment_intent")
    if isinstance(pi, str) and not payment.stripe_payment_intent_id:
        payment.stripe_payment_intent_id = pi

    try:
        for item in order.items:
            product = item.product
            if product is None:
                continue
            product.stock_quantity -= item.quantity

        assert_valid_payment_transition(
            from_status=payment.status, to_status=PaymentStatus.PAID.value
        )
        payment.status = PaymentStatus.PAID.value
        payment.stripe_event_id = event_id

        assert_valid_order_transition(from_status=order.status, to_status=OrderStatus.PAID.value)
        order.status = OrderStatus.PAID.value

        db.add(ProcessedWebhookEvent(event_id=event_id))
        db.commit()
    except DomainError:
        db.rollback()
        raise
