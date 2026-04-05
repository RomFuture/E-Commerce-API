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

This chapter describes how to expose Stripe in the HTTP API in a way that matches this repo: `FastAPI` routers under `src/api/v1/routers/`, registration in `src/api/v1/router.py`, `CurrentUser` and `DbSession` from existing deps, and settings via `get_settings()` / `STRIPE_SECRET_KEY` and `STRIPE_WEBHOOK_SECRET` (see §3).

The `Payment` model already has `stripe_payment_intent_id`, `stripe_event_id`, `status`, `amount`, and `currency` (`src/infrastructure/db/models/payment.py`). For Checkout Session you will typically persist the **Checkout Session id** as well (either add a nullable `stripe_checkout_session_id` column or store the session id in metadata only until you resolve the PaymentIntent). The examples below assume your checkout use case writes Stripe identifiers and order/payment status before returning the redirect URL.

### 6.1 Router module layout

Add a new router file, for example `src/api/v1/routers/checkout.py`, and a small response schema under `src/api/v1/schemas/checkout.py` (or inline models in the router if you prefer minimal surface area). Register it in `src/api/v1/router.py`:

```python
api_v1_router.include_router(checkout.router, prefix="/checkout", tags=["checkout"])
```

Keep **checkout** behind authentication and **webhooks** completely public (no `CurrentUser` dependency).

### 6.2 `POST /api/v1/checkout`

**Purpose:** Authenticated user starts payment; server creates an order snapshot, a `payments` row, and a Stripe Checkout Session, then returns the hosted payment URL.

**Authentication:** Reuse `CurrentUser` from `src/api/v1/deps/auth.py` the same way as `cart.py`.

**Request body:** Usually empty `{}` or optional fields such as `success_url` / `cancel_url` if you do not hard-code them from settings.

**Response model (example):**

| Field           | Type   | Description                                      |
|----------------|--------|--------------------------------------------------|
| `order_id`     | int    | Internal order id                                |
| `checkout_url` | string | `session.url` from Stripe (redirect the browser) |

**Handler shape (illustrative):**

1. Inject `user: CurrentUser`, `db: DbSession`, and settings (or a service that already holds Stripe config).
2. Call your application-layer function (§5), e.g. `create_checkout_session(db, user_id=user.id, ...)`.
3. Map domain errors to `HTTPException` with `400` / `404` / `409` as appropriate (mirror `cart.py`).

**Errors to plan for:** empty cart, stale price/stock, duplicate checkout for an already-paid order, Stripe API failures (often `502` or `503` with a safe message—never leak raw Stripe errors to clients in production).

### 6.3 `POST /api/v1/webhooks/stripe`

**Purpose:** Stripe calls this URL when payment state changes. This is where you mark `payments.status` and the related `orders` row as paid (or failed) and apply inventory policy (§5.2).

**Critical properties:**

- **Raw body required:** Signature verification must use the **exact** request body bytes. In FastAPI, use `Request` and `await request.body()` (or a dependency that reads the body once). Do not parse JSON first and re-serialize; that breaks verification.
- **Public route:** No JWT. Security is the Stripe-Signature header + `STRIPE_WEBHOOK_SECRET`.
- **Idempotent:** Stripe retries webhooks. The same `event.id` may arrive multiple times; processing twice must not double-apply business effects.

**Recommended primary event:** `checkout.session.completed` (Checkout Session integration). Retrieve the session with expanded `line_items` or rely on `metadata` you set at session creation (e.g. `order_id`) to load your DB rows.

**Handler outline:**

1. Read raw payload: `payload = await request.body()`.
2. Read header: `sig = request.headers.get("stripe-signature")`.
3. Construct event: `stripe.Webhook.construct_event(payload, sig, settings.stripe_webhook_secret)` (from the `stripe` Python package). On failure return `400` (invalid signature).
4. **Idempotency check:** If you use a dedicated `processed_webhook_events` table (§2.2), `SELECT` by `event.id`; if present, return `200` immediately. If you only store `stripe_event_id` on `payments`, ensure your update is conditional or use a unique constraint so a duplicate event does not create inconsistent state.
5. Branch on `event["type"]`:
   - For `checkout.session.completed`, load `order_id` from `session.metadata`, set payment to `paid` and order to your paid status, then optionally adjust inventory.
   - For failure/expired events (depending on which types you subscribe to), apply your cancellation/failure policy.
6. Record `event.id` as processed (insert into idempotency table or set on the payment row if that fits your schema).
7. Return `200` with a small JSON body (e.g. `{"received": true}`). Stripe treats non-2xx as failure and retries.

**Route registration:** Mount at `/webhooks/stripe` (full path `/api/v1/webhooks/stripe` after the existing `prefix="/api/v1"` in `main.py`). You can define a dedicated router with `prefix="/webhooks"` and `tags=["webhooks"]` to keep concerns separate from checkout.

### 6.4 Testing and local verification

- **Unit tests:** Mock Stripe client methods; assert your router returns the fake `checkout_url` and that the webhook handler updates DB state when given a constructed dict (bypass signature in tests by calling the inner “handle event” function directly, or use Stripe’s test fixtures).
- **Local end-to-end:** Use Stripe CLI (§8) so `STRIPE_WEBHOOK_SECRET` matches the signing secret printed by `stripe listen`.

### 6.5 Operational checklist

- Expose the webhook URL over **HTTPS** in deployed environments (Stripe requires it for live mode).
- Return `200` quickly after committing DB changes; defer slow work (emails, analytics) to a background task if needed.
- Log `event.id` and your `order_id` on success and on structured failures to simplify support.

---

## 7) Testing plan

This section maps the guide to **what exists in the repo** and what to add when you extend behaviour.

### 7.1 Unit and service-level tests

| Scenario | Where it lives (or note) |
|----------|-------------------------|
| Empty cart → checkout rejected | `tests/test_checkout_service.py` (`test_start_checkout_empty_cart`), `tests/test_checkout_and_webhook_api.py` (`test_checkout_requires_auth` for 401; empty cart via API) |
| Quantity exceeds stock → rejected | `tests/test_checkout_and_webhook_api.py` (`test_checkout_rejects_insufficient_stock`) |
| Order / payment status transitions | `tests/test_checkout_statuses.py` |

Keep **domain rules** (`ensure_cart_not_empty`, `validate_quantity_vs_stock`) covered when you change checkout or cart flows.

### 7.2 Integration / API tests (no real Stripe)

**Rule:** CI and default pytest runs must **not** call `api.stripe.com`. Use **mocks** or **patches** on the boundary:

| Scenario | Approach in this repo |
|----------|------------------------|
| `POST /api/v1/checkout` returns `checkout_url` | Patch `src.application.checkout_service.create_checkout_session_for_order` with a fake `CreatedCheckoutSession` — see `tests/test_checkout_and_webhook_api.py` |
| Webhook “happy path” updates DB | Patch `stripe.Webhook.construct_event` in the router test to return a dict-shaped event; assert order/payment/stock — same file |
| Webhook idempotency (same `event.id` twice) | `test_webhook_duplicate_event_idempotent` |
| Missing `Stripe-Signature` | `test_webhook_missing_signature` |

Optional next steps when you grow the product:

- Contract test for **raw body**: ensure no middleware parses the webhook body before `construct_event`.
- Tests for **failure** Stripe events (`checkout.session.expired`, etc.) if you subscribe to them.

### 7.3 Environment for pytest

`tests/conftest.py` sets placeholder **`STRIPE_SECRET_KEY`** / **`STRIPE_WEBHOOK_SECRET`** so `start_checkout_from_cart` does not reject the default `sk_test_xxx` during API tests. **GitHub Actions** sets the same class of placeholders (see §9).

---

## 8) Local webhook testing (Stripe CLI)

End-to-end verification uses **real** Stripe test-mode events forwarded to your laptop.

### 8.1 Prerequisites

- [Stripe CLI](https://stripe.com/docs/stripe-cli) installed and logged in: `stripe login`
- API running locally, e.g. `uv run uvicorn src.api.main:app --reload --port 8000`
- Database migrated: `uv run alembic upgrade head`
- Real **test** API key in `.env`: `STRIPE_SECRET_KEY=sk_test_...` (not the placeholder)

### 8.2 Forward events

In a separate terminal:

```bash
stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe
```

The CLI prints a **webhook signing secret** (`whsec_...`). Put it in `.env` as **`STRIPE_WEBHOOK_SECRET`** for this shell session (it differs from the Dashboard endpoint secret while using `stripe listen`).

Restart the API so it picks up the new secret.

### 8.3 Trigger a test event

Examples:

```bash
stripe trigger checkout.session.completed
```

Or complete a real Checkout Session from your app using [test card numbers](https://stripe.com/docs/testing).

### 8.4 What to verify

- Your logs / DB: `orders.status` → `paid`, `payments.status` → `paid`, stock decremented.
- `processed_webhook_events` contains the Stripe `event.id`.
- If something fails, fix before relying on production webhooks.

---

## 9) CI/CD notes

### 9.1 Continuous integration (`.github/workflows/ci.yml`)

- **Lint / format:** `ruff check`, `ruff format --check`
- **Tests:** `pytest` on SQLite (in-memory) and optionally **Postgres** service job with `TEST_DATABASE_URL`
- **No live Stripe:** jobs use placeholder `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` in `env` so settings validation and checkout paths behave like local pytest. Network calls to Stripe remain mocked in tests.

If you add a job that imports `create_app()` without the conftest `app` fixture, keep the same placeholders in that job’s `env`.

### 9.2 Container image / CD (`.github/workflows/deploy-ghcr.yml`, `Dockerfile`)

- The image **does not** bake secrets. At **runtime** inject at least:

  | Variable | Purpose |
  |----------|---------|
  | `DATABASE_URL` | Postgres DSN |
  | `JWT_SECRET` | Auth |
  | `APP_ENV` | e.g. `prod` (disables `/docs` when prod) |
  | `STRIPE_SECRET_KEY` | Server-side Stripe API |
  | `STRIPE_WEBHOOK_SECRET` | Webhook signature verification |
  | `STRIPE_CHECKOUT_SUCCESS_URL` / `STRIPE_CHECKOUT_CANCEL_URL` | Checkout redirects |

- Reference **`docker-compose.app.yml`** for a local template of env names; production should use your host’s **secret store**, not committed files.

### 9.3 Production checklist

- `APP_ENV=prod` requires strong `JWT_SECRET` and **live** Stripe keys (`sk_live_...`) per `Settings` validators.
- Webhook URL must be **HTTPS** for live mode.
- Run `alembic upgrade head` before or on deploy so `payments` columns and `processed_webhook_events` exist.

---

## 10) Implementation order (status in this repo)

Use this as a checklist for new clones or audits.

| Step | Item | Status |
|------|------|--------|
| 1 | Stripe dependency + adapter (`src/infrastructure/stripe/client.py`) | Done |
| 2 | DB: `payments` fields + `processed_webhook_events` + Alembic migration | Done |
| 3 | Settings / `.env.example` / prod guards | Done |
| 4 | Application: `checkout_service`, `stripe_webhook_service` | Done |
| 5 | API: `POST /api/v1/checkout`, `POST /api/v1/webhooks/stripe` | Done |
| 6 | Tests (checkout, webhook, idempotency) + pytest env in `conftest` / CI | Done |
| 7 | Local verification with **Stripe CLI** (§8) | Manual / optional per developer |
| 8 | (Future) Extra event types, refunds, admin reconciliation, monitoring | Not in scope |

When extending (refunds, subscriptions, Connect), add migrations, handlers, and tests in the same order: **domain → DB → service → API → tests → CLI smoke**.

