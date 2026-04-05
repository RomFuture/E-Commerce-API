from decimal import Decimal
from unittest.mock import patch

import pytest
from sqlalchemy import func, select

from src.application.cart_service import add_cart_item
from src.application.checkout_service import CheckoutError, start_checkout_from_cart
from src.domain.checkout_statuses import OrderStatus, PaymentStatus
from src.infrastructure.config.settings import Settings
from src.infrastructure.db.models.cart_item import CartItem
from src.infrastructure.db.models.order import Order
from src.infrastructure.db.models.payment import Payment
from src.infrastructure.db.models.product import Product
from src.infrastructure.db.models.user import User
from src.infrastructure.security.password import hash_password
from src.infrastructure.stripe.client import CreatedCheckoutSession


def _settings_for_test() -> Settings:
    return Settings(
        stripe_secret_key="sk_test_valid_fake",
        stripe_checkout_success_url="http://test/success?session_id={CHECKOUT_SESSION_ID}",
        stripe_checkout_cancel_url="http://test/cancel",
    )


def test_start_checkout_empty_cart(db_session):
    user = User(email="c1@test.com", hashed_password=hash_password("password12"))
    db_session.add(user)
    db_session.commit()

    with pytest.raises(CheckoutError, match="empty"):
        start_checkout_from_cart(db_session, user.id, _settings_for_test())


def test_start_checkout_happy_path(db_session):
    user = User(email="c2@test.com", hashed_password=hash_password("password12"))
    db_session.add(user)
    db_session.flush()
    p = Product(name="Mug", price=Decimal("10.00"), stock_quantity=5, is_active=True)
    db_session.add(p)
    db_session.commit()
    add_cart_item(db_session, user_id=user.id, product_id=p.id, quantity=2)

    fake = CreatedCheckoutSession(
        session_id="cs_test_abc",
        url="https://checkout.stripe.test/cdn-cgi/abc",
        payment_intent_id="pi_test_1",
    )
    with patch(
        "src.application.checkout_service.create_checkout_session_for_order",
        return_value=fake,
    ):
        result = start_checkout_from_cart(db_session, user.id, _settings_for_test())

    assert result.order_id >= 1
    assert result.checkout_url == fake.url

    order = db_session.get(Order, result.order_id)
    assert order is not None
    assert order.status == OrderStatus.AWAITING_PAYMENT.value
    assert order.total_amount == Decimal("20.00")

    pay = db_session.scalar(select(Payment).where(Payment.order_id == order.id))
    assert pay is not None
    assert pay.status == PaymentStatus.PENDING.value
    assert pay.stripe_checkout_session_id == "cs_test_abc"
    assert pay.stripe_payment_intent_id == "pi_test_1"
    assert pay.amount == Decimal("20.00")

    cart_remaining = db_session.scalar(
        select(func.count()).select_from(CartItem).where(CartItem.user_id == user.id),
    )
    assert cart_remaining == 0
