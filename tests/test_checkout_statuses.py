import pytest

from src.domain.checkout_statuses import (
    OrderStatus,
    PaymentStatus,
    assert_valid_order_transition,
    assert_valid_payment_transition,
    require_known_order_status,
    require_known_payment_status,
)
from src.domain.ecommerce_rules import DomainError


def test_order_transition_happy_path() -> None:
    assert_valid_order_transition(
        from_status=OrderStatus.PENDING.value,
        to_status=OrderStatus.AWAITING_PAYMENT.value,
    )
    assert_valid_order_transition(
        from_status=OrderStatus.AWAITING_PAYMENT.value,
        to_status=OrderStatus.PAID.value,
    )


def test_order_same_status_noop() -> None:
    assert_valid_order_transition(
        from_status=OrderStatus.PAID.value,
        to_status=OrderStatus.PAID.value,
    )


def test_order_invalid_transition() -> None:
    with pytest.raises(DomainError, match="Invalid order status transition"):
        assert_valid_order_transition(
            from_status=OrderStatus.PENDING.value,
            to_status=OrderStatus.PAID.value,
        )


def test_order_unknown_status() -> None:
    with pytest.raises(DomainError, match="Invalid order status"):
        require_known_order_status("shipped")


def test_payment_transition() -> None:
    assert_valid_payment_transition(
        from_status=PaymentStatus.PENDING.value,
        to_status=PaymentStatus.PAID.value,
    )


def test_payment_terminal_blocked() -> None:
    with pytest.raises(DomainError, match="Invalid payment status transition"):
        assert_valid_payment_transition(
            from_status=PaymentStatus.PAID.value,
            to_status=PaymentStatus.FAILED.value,
        )


def test_payment_unknown() -> None:
    with pytest.raises(DomainError, match="Invalid payment status"):
        require_known_payment_status("authorized")
