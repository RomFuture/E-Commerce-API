# Stripe integration guide (plan)

This document is a **practical plan** to integrate **Stripe payments** into this FastAPI e-commerce API, aligned with:

- `docs/STEP_BY_STEP.md` (Chapter 11–12)
- current code structure (`src/api`, `src/application`, `src/domain`, `src/infrastructure`)

---

## 0) Choose your Stripe approach

Stripe has multiple integration styles. For this project the simplest is:

- **Stripe Checkout Session** (recommended): Stripe hosts the payment UI; you redirect the user to Stripe.

You can switch to **Payment Intents** later if you need a custom UI.

---

## 1) Payment domain model (what we will store)

### 1.1 Minimum payment information

Your DB should be able to answer:

- Which **order** is being paid?
- What is the **provider** (Stripe)?
- What is the provider’s identifier (checkout session id / payment intent id)?
- What is the **status**?
- Was the webhook already processed (idempotency)?

### 1.2 Recommended statuses

- **Order**: `pending` → `awaiting_payment` → `paid` / `failed` / `cancelled`
- **Payment**: `pending` → `paid` / `failed`

---

## 2) Database changes (models + Alembic)

### 2.1 Payments table

Ensure `payments` can store at least:

- `order_id` (FK)
- `status` (string/enum-like)
- `provider` (e.g. `"stripe"`)
- `provider_session_id` (Checkout Session id)
- `provider_payment_intent_id` (optional but useful)
- `amount` (decimal/int) + `currency` (e.g. `"usd"`)
- timestamps

### 2.2 Webhook idempotency table (recommended)

Create a table like `processed_webhook_events`:

- `event_id` (Stripe event id, **unique**)
- `processed_at`

This prevents duplicate webhook delivery from applying the same payment twice.

### 2.3 Migration

Create and run an Alembic migration:

- add missing columns to `payments`
- add `processed_webhook_events`

---

## 3) Settings and secrets

Add / confirm env vars (already listed in `.env.example`):

- `STRIPE_SECRET_KEY`
- `STRIPE_WEBHOOK_SECRET`

Rules:

- Never commit real secrets
- In production, store secrets in your hosting platform’s secrets manager

---

## 4) Infrastructure layer: Stripe client

### 4.1 Add dependency

```bash
uv add stripe
```

### 4.2 Create a Stripe adapter

Add a module like:

- `src/infrastructure/stripe/client.py`

Responsibilities:

- initialize Stripe SDK using `STRIPE_SECRET_KEY`
- provide a function/method to create a **Checkout Session**
- attach metadata (`order_id`) so you can map webhook events back to your DB

---

## 5) Application layer: checkout orchestration

Create a use-case module like:

- `src/application/checkout_service.py`

### 5.1 Checkout flow (sync)

1. Load cart
2. Validate cart not empty
3. Re-validate product availability, price, stock
4. Create `order` + `order_items` snapshot
5. Create `payment` row with `status=pending`
6. Call Stripe to create Checkout Session
7. Persist Stripe identifiers on the `payment` row
8. Return `{ checkout_url, order_id }`

### 5.2 Inventory policy decision

Pick one:

- **Decrease inventory only after payment is confirmed** (simple, common)
- Reserve/decrease inventory at order creation (more consistency, more complexity)

---

## 6) API layer: endpoints

### 6.1 `POST /api/v1/checkout`

- Auth required (current user)
- Calls `checkout_service`
- Returns:
  - `order_id`
  - `checkout_url` (Stripe hosted URL)

### 6.2 `POST /api/v1/webhooks/stripe`

- Public endpoint
- Must verify signature using `STRIPE_WEBHOOK_SECRET`
- Must be **idempotent**

Process:

1. Verify signature
2. Parse event
3. If `event.id` already processed → return 200 (ignore)
4. On success event:
   - mark payment `paid`
   - mark order `paid`
   - optionally decrement inventory
5. On failure event:
   - mark payment/order as failed/cancelled (your policy)
6. Store `event.id` as processed

Recommended event:

- `checkout.session.completed`

---

## 7) Testing plan

### 7.1 Unit tests

- empty cart → checkout rejected
- quantity exceeds stock → rejected

### 7.2 Integration tests

Do **not** call Stripe in CI.

- mock the Stripe adapter so it returns a fake session id + URL
- test webhook handler with:
  - “valid event” path (you can bypass signature verification in tests with a test-only flag or by factoring verification into a small function you can unit test)
  - idempotency (send same `event.id` twice)

---

## 8) Local webhook testing (Stripe CLI)

Use Stripe CLI to forward real events to your local server:

- Run API on `localhost:8000`
- Then:

```bash
stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe
```

Use the printed webhook secret to set `STRIPE_WEBHOOK_SECRET` for local testing.

---

## 9) CI/CD notes

- CI should run tests without real Stripe keys (mock adapter)
- CD image (GHCR) should document required env vars (`DATABASE_URL`, `JWT_SECRET`, Stripe keys)

---

## 10) Implementation order (recommended)

1. Add Stripe dependency + adapter skeleton
2. Add DB idempotency table + payment fields + migration
3. Implement `POST /api/v1/checkout` (mock Stripe first)
4. Implement webhook endpoint + idempotency
5. Add tests for checkout + webhook
6. Wire Stripe CLI for local verification

