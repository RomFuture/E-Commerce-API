## E-Commerce API - Full Step-by-step Guide (Backend Only)

This guide covers your full backend roadmap using:
- Docker Compose
- `uv`
- FastAPI
- Onion architecture
- SQLAlchemy
- PostgreSQL
- Alembic
- Stripe
- Postman
- CI/CD

---

## Chapter 1 - Project initialization

### Goal
- Start FastAPI locally.
- Use `uv` for dependency management.
- Prepare Onion structure for scale.

### 1.1 Install `uv`
On Ubuntu/Debian, avoid `pip install --user ...` for system Python (PEP 668).

Option A (recommended):

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
exec $SHELL
uv --version
```

Option B (`pipx`):

```bash
sudo apt update
sudo apt install -y pipx
pipx ensurepath
pipx install uv
exec $SHELL
uv --version
```

### 1.2 Install dependencies

```bash
uv venv
uv sync
```

### 1.3 Run the app

```bash
uv run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

Check:
- `GET http://localhost:8000/health` -> `{"status":"ok"}`

---

## Chapter 2 - Project structure (Onion architecture)

### Goal
Separate business rules from frameworks and external tools.

### Suggested structure

```text
src/
  api/                # FastAPI routers, dependencies, schemas
  application/        # Use-cases, services, command/query handlers
  domain/             # Entities, value objects, business rules
  infrastructure/     # DB models, repositories, stripe client, settings
```

### Rules
- `domain` does not import FastAPI, SQLAlchemy, Stripe, or Postgres.
- `application` depends on `domain`.
- `api` calls `application`.
- `infrastructure` implements interfaces required by `application`.

---

## Chapter 3 - Configuration and environments

### Goal
Manage local/dev/prod settings safely: one typed object, secrets outside the repo, injectable in routes.

### 3.1 Template vs real secrets
- Keep [`.env.example`](../.env.example) committed with **placeholder** values only.
- Copy to `.env` locally:

```bash
cp .env.example .env
```

- Add `.env` to [`.gitignore`](../.gitignore) (already present).

### 3.2 Important variables
| Variable | Purpose |
|----------|---------|
| `APP_ENV` | `local`, `dev`, `staging`, or `prod` (when `prod`, `/docs` is disabled) |
| `APP_NAME` | API title in Swagger |
| `DATABASE_URL` | PostgreSQL URL for SQLAlchemy |
| `JWT_SECRET` | Signing key for JWT (must be strong in production) |
| `JWT_ALGORITHM` | Usually `HS256` |
| `JWT_ACCESS_TOKEN_EXPIRES_MINUTES` | Access token lifetime |
| `ADMIN_EMAIL` | Only this user email may use admin routes (later) |
| `STRIPE_SECRET_KEY` | Stripe server secret |
| `STRIPE_WEBHOOK_SECRET` | Verify Stripe webhooks |

### 3.3 Implementation in this repo
- **Typed settings**: [`src/infrastructure/config/settings.py`](../src/infrastructure/config/settings.py)
  - `Settings` extends `BaseSettings`, reads `.env` and process environment variables.
  - `get_settings()` uses `@lru_cache` so config is built once per process.
  - When `APP_ENV=prod`, `JWT_SECRET` cannot stay as the placeholder `change-me` (startup validation error).
- **Inject in routes**: [`SettingsDep`](../src/api/dependencies.py) — same pattern as `DbSession`.
- **Try it**: `GET /info` returns only `app_name` and `app_env` (no secrets).
- **App wiring**: [`src/api/main.py`](../src/api/main.py) uses `get_settings()` for docs on/off and the FastAPI title.

### 3.4 Checklist before Chapter 4
- [ ] `cp .env.example .env` and adjust if needed.
- [ ] `GET /health` and `GET /info` work.
- [ ] With `APP_ENV=prod`, set a real `JWT_SECRET` or the app will refuse to start.

---

## Chapter 4 - PostgreSQL with Docker Compose

### Goal
Run local database and persist data.

### 4.1 Start DB

```bash
docker compose up -d postgres
```

### 4.2 Verify DB is healthy

```bash
docker compose ps
```

Expected: service `postgres` is `healthy`.

### 4.3 Stop DB

```bash
docker compose down
```

Use `docker compose down -v` only when you want to delete DB data.

---

## Chapter 5 - SQLAlchemy setup

### Goal
Connect app to database using SQLAlchemy 2.x style.

### 5.1 Dependencies
Already in `pyproject.toml`: `sqlalchemy`, `psycopg[binary]`, `alembic`.

### 5.2 DB foundation (this repo)
- Engine + session: [`src/infrastructure/db/session.py`](../src/infrastructure/db/session.py)
- Declarative base: [`src/infrastructure/db/base.py`](../src/infrastructure/db/base.py)
- FastAPI DB dependency: [`DbSession`](../src/api/dependencies.py)

### 5.3 ORM models (minimum e-commerce schema)
All under [`src/infrastructure/db/models/`](../src/infrastructure/db/models/):
- `users`
- `products`
- `cart_items` (unique per user + product)
- `orders`, `order_items`, `payments`

Import the package once so metadata is registered (Alembic does this via `import src.infrastructure.db.models` in [`alembic/env.py`](../alembic/env.py)).

### 5.4 Domain vs infrastructure
- `src/domain/`: pure business logic (no SQLAlchemy) — fill in later chapters
- `src/infrastructure/db/models/`: table mappings only

---

## Chapter 6 - Alembic migrations

### Goal
Track schema changes safely and reproducibly.

### 6.1 Layout
- Config: [`alembic.ini`](../alembic.ini) (URL is overridden from `Settings` in `env.py`)
- Environment: [`alembic/env.py`](../alembic/env.py) — `target_metadata = Base.metadata`, URL from `get_settings().database_url`

### 6.2 First revision
Hand-maintained initial migration (autogenerate needs a working DB and matching credentials):

- [`alembic/versions/3e4cdc71234d_init_ecommerce_tables.py`](../alembic/versions/3e4cdc71234d_init_ecommerce_tables.py)

### 6.3 Apply migrations

```bash
docker compose up -d postgres
# Ensure .env DATABASE_URL matches Postgres (see .env.example)
uv run alembic upgrade head
```

### 6.4 New changes later

```bash
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head
```

If `FATAL: password authentication failed`, fix `DATABASE_URL` in `.env` (Compose uses host port **5433** in this repo). If port bind fails, free the port or change the mapping in `docker-compose.yml`.

---

## Chapter 7 - Data model design

### Goal
Create core e-commerce entities.

### 7.1 Minimum tables
- `users`
- `products`
- `cart_items` (one active cart per user can be represented by status or table design)
- `orders`
- `order_items`
- `payments`

### 7.2 Business constraints (domain layer)
Pure helpers in [`src/domain/ecommerce_rules.py`](../src/domain/ecommerce_rules.py) (no FastAPI / SQLAlchemy):
- `validate_product_price_and_stock` — price >= 0, inventory >= 0
- `validate_cart_line_quantity` / `validate_quantity_vs_stock` — positive qty, qty <= stock
- `ensure_cart_not_empty` — at least one cart line before checkout

Use these from application services when you add cart/checkout endpoints (Chapter 10–11).

---

## Chapter 8 - Authentication (JWT)

### Goal
Sign up, login, protect endpoints.

### 8.1 Dependencies (in `pyproject.toml`)
- `python-jose[cryptography]`, `bcrypt`, `email-validator`, `python-multipart` (form login)

### 8.2 Implementation in this repo
- Password hashing: [`src/infrastructure/security/password.py`](../src/infrastructure/security/password.py)
- JWT create/decode: [`src/infrastructure/security/jwt_tokens.py`](../src/infrastructure/security/jwt_tokens.py)
- Register / login / lookup: [`src/application/auth_service.py`](../src/application/auth_service.py)
- API (under `/api/v1/auth`):
  - `POST /api/v1/auth/signup` — JSON `{ "email", "password" }`
  - `POST /api/v1/auth/login` — OAuth2 form (`username` = email, `password`) — works with Swagger **Authorize**
  - `GET /api/v1/auth/me` — Bearer JWT, returns public user
- Current user / admin deps: [`src/api/v1/deps/auth.py`](../src/api/v1/deps/auth.py) (`CurrentUser`, `AdminUser`)
- Example admin-only route: `GET /api/v1/admin/health` (email must match `ADMIN_EMAIL` in `.env`)

---

## Chapter 9 - Product management

### Goal
Public browse/search + admin CRUD.

### 9.1 Public endpoints
- `GET /products`
- `GET /products/{product_id}`
- Query params: `q`, `min_price`, `max_price`, `limit`, `offset`

### 9.2 Admin-only endpoints
- `POST /admin/products`
- `PATCH /admin/products/{product_id}`
- `DELETE /admin/products/{product_id}`

### 9.3 Inventory behavior
- Decrease inventory only when order is confirmed/paid (depending on your policy).

---

## Chapter 10 - Cart operations

### Goal
Users can manage their cart.

### Endpoints
- `GET /cart`
- `POST /cart/items` (add item)
- `PATCH /cart/items/{product_id}` (change quantity)
- `DELETE /cart/items/{product_id}` (remove item)

### Business rules
- Quantity must be positive.
- Check inventory before allowing quantity updates.
- Return calculated totals in response.

---

## Chapter 11 - Checkout and orders

### Goal
Convert cart into order and begin payment.

### 11.1 Checkout flow
1. Validate cart is not empty.
2. Re-validate prices and stock.
3. Create order + order_items snapshot.
4. Create Stripe checkout session (or payment intent).
5. Return checkout URL/session id.

### 11.2 Order status examples
- `pending`
- `awaiting_payment`
- `paid`
- `cancelled`
- `failed`

---

## Chapter 12 - Stripe integration

### Goal
Handle real payment lifecycle with webhook confirmation.

### 12.1 Add dependency

```bash
uv add stripe
```

### 12.2 Create endpoints
- `POST /checkout` (authenticated)
- `POST /webhooks/stripe` (public, signature-verified)

### 12.3 Webhook handling
- Verify signature with `STRIPE_WEBHOOK_SECRET`.
- On success event: mark payment/order paid.
- On failure event: mark as failed.
- Store event id to ensure idempotency (ignore duplicates).

### 12.4 Local webhook testing
Use Stripe CLI to forward events locally to your API.

---

## Chapter 13 - API docs and Postman

### Goal
Test all flows quickly without frontend.

### 13.1 FastAPI docs
- Swagger UI: `/docs`
- ReDoc: `/redoc`

### 13.2 Postman setup
Create environment variables:
- `base_url`
- `access_token`
- `user_email`
- `admin_email`

### 13.3 Collections
- Auth: signup/login
- Products: list/detail/search
- Admin products: create/update/delete
- Cart: add/update/remove/view
- Checkout + webhook test flow

---

## Chapter 14 - Testing strategy

### Goal
Protect critical business rules.

### 14.1 Add test dependencies

```bash
uv add --dev pytest pytest-asyncio httpx
```

### 14.2 What to test
- Unit tests: domain rules (pricing, stock, cart totals)
- Integration tests: API + DB
- Auth tests: token required/admin required
- Checkout tests: invalid stock, empty cart, successful order creation

---

## Chapter 15 - CI/CD (GitHub Actions)

### Goal
Automatically validate quality on every push/PR.

### 15.1 CI pipeline should run
- Lint (`ruff check`)
- Format check (`ruff format --check`)
- Tests (`pytest`)
- Optional: build Docker image

### 15.2 Typical workflow
1. Checkout code
2. Install `uv`
3. `uv sync`
4. Run lint + tests

### 15.3 Optional CD
- Build and push image to registry
- Deploy to your platform (later step)

---

## Chapter 16 - Security baseline checklist

- Use strong secrets in production.
- Never expose `.env` in repo.
- Restrict DB network access.
- Validate all input schemas.
- Add request rate limits for auth endpoints.
- Add structured logging and error monitoring.

---

## Chapter 17 - Suggested implementation order

1. Health endpoint (done)
2. Settings + DB session
3. Users + auth
4. Products (public + admin)
5. Cart
6. Checkout
7. Stripe webhooks
8. Tests
9. CI/CD

---

## Quick command reference

```bash
# install deps
uv sync

# run app
uv run uvicorn src.api.main:app --reload

# migrations
uv run alembic revision --autogenerate -m "message"
uv run alembic upgrade head

# tests
uv run pytest -q

# lint/format
uv run ruff check .
uv run ruff format .
```

