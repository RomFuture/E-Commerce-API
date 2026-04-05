from decimal import Decimal
from unittest.mock import patch

from sqlalchemy import select

from src.domain.checkout_statuses import OrderStatus, PaymentStatus
from src.infrastructure.db.models.order import Order
from src.infrastructure.db.models.order_item import OrderItem
from src.infrastructure.db.models.payment import Payment
from src.infrastructure.db.models.processed_webhook_event import ProcessedWebhookEvent
from src.infrastructure.db.models.product import Product
from src.infrastructure.db.models.user import User
from src.infrastructure.security.password import hash_password
from src.infrastructure.stripe.client import CreatedCheckoutSession


def _auth_header(client) -> dict[str, str]:
    client.post(
        "/api/v1/auth/signup",
        json={"email": "pay@test.com", "password": "password12"},
    )
    token = client.post(
        "/api/v1/auth/login",
        data={"username": "pay@test.com", "password": "password12"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_checkout_requires_auth(client):
    r = client.post("/api/v1/checkout")
    assert r.status_code == 401


def test_checkout_endpoint_with_cart(client, db_session):
    headers = _auth_header(client)
    p = Product(name="Book", price=Decimal("12.00"), stock_quantity=20, is_active=True)
    db_session.add(p)
    db_session.commit()
    client.post(
        "/api/v1/cart/items",
        headers=headers,
        json={"product_id": p.id, "quantity": 1},
    )
    fake = CreatedCheckoutSession(
        session_id="cs_test_api",
        url="https://checkout.stripe.test/pay",
        payment_intent_id="pi_test_api",
    )
    with patch("src.application.checkout_service.create_checkout_session_for_order", return_value=fake):
        r = client.post("/api/v1/checkout", headers=headers)
    assert r.status_code == 200
    body = r.json()
    assert body["order_id"] >= 1
    assert body["checkout_url"] == fake.url


def test_checkout_rejects_insufficient_stock(client, db_session):
    email = "stockfail@test.com"
    client.post(
        "/api/v1/auth/signup",
        json={"email": email, "password": "password12"},
    )
    token = client.post(
        "/api/v1/auth/login",
        data={"username": email, "password": "password12"},
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    p = Product(name="Rare", price=Decimal("1.00"), stock_quantity=2, is_active=True)
    db_session.add(p)
    db_session.commit()
    client.post(
        "/api/v1/cart/items",
        headers=headers,
        json={"product_id": p.id, "quantity": 2},
    )
    prod = db_session.get(Product, p.id)
    assert prod is not None
    prod.stock_quantity = 1
    db_session.commit()

    r = client.post("/api/v1/checkout", headers=headers)
    assert r.status_code == 400
    assert "inventory" in r.json()["detail"].lower()


def _completed_event(order_id: int, event_id: str = "evt_test_1") -> dict:
    return {
        "id": event_id,
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "payment_status": "paid",
                "metadata": {"order_id": str(order_id)},
                "payment_intent": "pi_from_webhook",
            },
        },
    }


def test_webhook_marks_order_paid_and_reduces_stock(client, db_session):
    user = User(email="wh@test.com", hashed_password=hash_password("password12"))
    db_session.add(user)
    db_session.flush()
    p = Product(name="Widget", price=Decimal("5.00"), stock_quantity=10, is_active=True)
    db_session.add(p)
    db_session.flush()
    order = Order(
        user_id=user.id,
        status=OrderStatus.AWAITING_PAYMENT.value,
        total_amount=Decimal("10.00"),
    )
    db_session.add(order)
    db_session.flush()
    db_session.add(
        OrderItem(
            order_id=order.id,
            product_id=p.id,
            quantity=2,
            unit_price=Decimal("5.00"),
        ),
    )
    db_session.add(
        Payment(
            order_id=order.id,
            amount=Decimal("10.00"),
            status=PaymentStatus.PENDING.value,
        ),
    )
    db_session.commit()
    oid = order.id

    with patch(
        "src.api.v1.routers.webhooks.stripe.Webhook.construct_event",
        return_value=_completed_event(oid),
    ):
        r = client.post(
            "/api/v1/webhooks/stripe",
            content=b"{}",
            headers={"stripe-signature": "t=0,v1=fake"},
        )
    assert r.status_code == 200
    assert r.json() == {"received": True}

    db_session.expire_all()
    order_db = db_session.get(Order, oid)
    pay_db = db_session.scalar(select(Payment).where(Payment.order_id == oid))
    prod_db = db_session.get(Product, p.id)
    assert order_db.status == OrderStatus.PAID.value
    assert pay_db.status == PaymentStatus.PAID.value
    assert pay_db.stripe_payment_intent_id == "pi_from_webhook"
    assert prod_db.stock_quantity == 8


def test_webhook_duplicate_event_idempotent(client, db_session):
    user = User(email="wh2@test.com", hashed_password=hash_password("password12"))
    db_session.add(user)
    db_session.flush()
    p = Product(name="W2", price=Decimal("1.00"), stock_quantity=5, is_active=True)
    db_session.add(p)
    db_session.flush()
    order = Order(
        user_id=user.id,
        status=OrderStatus.AWAITING_PAYMENT.value,
        total_amount=Decimal("1.00"),
    )
    db_session.add(order)
    db_session.flush()
    db_session.add(
        OrderItem(
            order_id=order.id,
            product_id=p.id,
            quantity=1,
            unit_price=Decimal("1.00"),
        ),
    )
    db_session.add(
        Payment(
            order_id=order.id,
            amount=Decimal("1.00"),
            status=PaymentStatus.PENDING.value,
        ),
    )
    db_session.commit()
    oid = order.id
    ev = _completed_event(oid, event_id="evt_dup_1")

    with patch(
        "src.api.v1.routers.webhooks.stripe.Webhook.construct_event",
        return_value=ev,
    ):
        assert client.post(
            "/api/v1/webhooks/stripe",
            content=b"{}",
            headers={"stripe-signature": "t=0,v1=a"},
        ).status_code == 200
        assert client.post(
            "/api/v1/webhooks/stripe",
            content=b"{}",
            headers={"stripe-signature": "t=0,v1=b"},
        ).status_code == 200

    db_session.expire_all()
    assert db_session.get(Product, p.id).stock_quantity == 4
    assert db_session.scalar(select(ProcessedWebhookEvent).where(ProcessedWebhookEvent.event_id == "evt_dup_1"))


def test_webhook_missing_signature(client):
    r = client.post("/api/v1/webhooks/stripe", content=b"{}")
    assert r.status_code == 400
