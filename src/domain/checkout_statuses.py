"""Order and payment lifecycle strings for Stripe checkout (see docs/STRIPE_INTEGRATION_GUIDE.md §1)."""

from __future__ import annotations

from enum import StrEnum

from src.domain.ecommerce_rules import DomainError


class OrderStatus(StrEnum):
    """Order row `orders.status` — flow: pending → awaiting_payment → paid | failed | cancelled."""

    PENDING = "pending"
    AWAITING_PAYMENT = "awaiting_payment"
    PAID = "paid"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PaymentStatus(StrEnum):
    """Payment row `payments.status`."""

    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"


_ORDER_TRANSITIONS: dict[str, frozenset[str]] = {
    OrderStatus.PENDING.value: frozenset(
        {
            OrderStatus.AWAITING_PAYMENT.value,
            OrderStatus.CANCELLED.value,
        }
    ),
    OrderStatus.AWAITING_PAYMENT.value: frozenset(
        {
            OrderStatus.PAID.value,
            OrderStatus.FAILED.value,
            OrderStatus.CANCELLED.value,
        }
    ),
}

_PAYMENT_TRANSITIONS: dict[str, frozenset[str]] = {
    PaymentStatus.PENDING.value: frozenset(
        {
            PaymentStatus.PAID.value,
            PaymentStatus.FAILED.value,
        }
    ),
}


def require_known_order_status(status: str) -> None:
    try:
        OrderStatus(status)
    except ValueError as e:
        raise DomainError(f"Invalid order status: {status!r}") from e


def require_known_payment_status(status: str) -> None:
    try:
        PaymentStatus(status)
    except ValueError as e:
        raise DomainError(f"Invalid payment status: {status!r}") from e


def assert_valid_order_transition(*, from_status: str, to_status: str) -> None:
    """Raise DomainError if changing order status is not allowed. Same status is a no-op (idempotent)."""
    if from_status == to_status:
        return
    require_known_order_status(from_status)
    require_known_order_status(to_status)
    allowed = _ORDER_TRANSITIONS.get(from_status)
    if allowed is None or to_status not in allowed:
        raise DomainError(
            f"Invalid order status transition: {from_status!r} → {to_status!r}",
        )


def assert_valid_payment_transition(*, from_status: str, to_status: str) -> None:
    """Raise DomainError if changing payment status is not allowed. Same status is a no-op."""
    if from_status == to_status:
        return
    require_known_payment_status(from_status)
    require_known_payment_status(to_status)
    allowed = _PAYMENT_TRANSITIONS.get(from_status)
    if allowed is None or to_status not in allowed:
        raise DomainError(
            f"Invalid payment status transition: {from_status!r} → {to_status!r}",
        )
