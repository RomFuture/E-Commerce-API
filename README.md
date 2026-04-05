## E-Commerce API (Backend)

Backend API for a minimal e-commerce system built with **FastAPI** + **SQLAlchemy** + **PostgreSQL**.

### Features

- **Auth**: signup/login with JWT, `/me`
- **Products**: public list/detail/search
- **Cart**: add/update/remove items, totals
- **Checkout**: `POST /api/v1/checkout` — cart → order snapshot → **Stripe Checkout** session (redirect URL)
- **Stripe webhooks**: `POST /api/v1/webhooks/stripe` — signature-verified events, idempotent processing, stock decremented after payment
- **Admin**: admin-only endpoints via `ADMIN_EMAIL`
- **Migrations**: Alembic
- **Quality**: Ruff (lint + format), pytest, GitHub Actions CI

**Payment integration:** step-by-step plan, testing, CI notes, and Stripe CLI — [docs/STRIPE_INTEGRATION_GUIDE.md](docs/STRIPE_INTEGRATION_GUIDE.md).

---

## Installation and usage

### 1) Local development (uv + local process)

Install `uv` (recommended). On Ubuntu/Debian, avoid `pip install --user` because system Python may be externally managed (PEP 668).

Option A (recommended): official installer:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
exec $SHELL
```

Create environment and install dependencies:

```bash
uv venv
uv sync --extra dev
```

(`--extra dev` includes `pytest`, `httpx`, and `ruff` for tests and linting.)

Configuration:

```bash
cp .env.example .env
```

Edit `.env`: `DATABASE_URL`, `JWT_SECRET`, and for Stripe tests **`STRIPE_SECRET_KEY`**, **`STRIPE_WEBHOOK_SECRET`**, checkout redirect URLs (see `.env.example`).

Start Postgres (Docker):

```bash
docker compose up -d postgres
```

Apply migrations:

```bash
uv run alembic upgrade head
```

Run the API:

```bash
uv run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

Useful endpoints:

- `GET /health` — liveness
- `GET /info` — `app_name` and `app_env` (no secrets)
- `GET /docs` — Swagger (disabled when `APP_ENV=prod`)
- `POST /api/v1/auth/signup` — JSON `email`, `password` (min 8 chars)
- `POST /api/v1/auth/login` — form `username` (email) + `password` → JWT
- `GET /api/v1/auth/me` — `Authorization: Bearer <token>`
- `POST /api/v1/checkout` — starts Stripe Checkout; returns `order_id`, `checkout_url` (requires Bearer token)
- `POST /api/v1/webhooks/stripe` — called by Stripe (raw body + `Stripe-Signature`; no JWT)
- `GET /api/v1/admin/health` — admin only (`ADMIN_EMAIL` must match logged-in user)

Run tests:

```bash
uv run pytest -q
```

### Database migrations (Alembic)

Ensure Postgres is running and `DATABASE_URL` in `.env` matches your DB. Docker Compose maps Postgres to **host port 5433** (container still uses 5432) so it does not fight with a local PostgreSQL on 5432 — see [`.env.example`](.env.example).

```bash
docker compose up -d postgres
uv run alembic upgrade head
```

Apply new migrations after model changes (or add a new revision with `uv run alembic revision --autogenerate -m "describe change"` when the DB is reachable).

Full guide: [docs/STEP_BY_STEP.md](docs/STEP_BY_STEP.md).

---

### 2) Local run with Docker (one command) — API + Postgres

This repo includes a `Dockerfile` and a compose overlay to run the **API** together with **Postgres**.

**Linux (fresh machine or server):**

```bash
chmod +x scripts/install-linux.sh
./scripts/install-linux.sh              # Docker: API + Postgres + migrations
./scripts/install-linux.sh --native     # uv on host + Postgres in Docker only
sudo ./scripts/install-linux.sh --install-docker   # Debian/Ubuntu: install Docker, then re-run without sudo
```

Equivalent manual flow:

```bash
./scripts/start.sh
```

Stop:

```bash
./scripts/stop.sh
```

API: `http://localhost:8000`  
Swagger: `http://localhost:8000/docs`

Compose env template: [`docker-compose.app.yml`](docker-compose.app.yml) (includes Stripe placeholders; replace for real checkout).

---

### 3) Server deployment using GHCR (docker pull)

This project can be deployed without cloning the repo: you **pull** the Docker image from **GHCR** and run it.

#### What runs where

- **GitHub**: stores your source code (repo) and your built Docker images (GHCR)
- **Your server**: downloads the image once and runs it as a container
- **PostgreSQL**: must be reachable from the API container (same server via Docker Compose, or external managed DB)

#### Image location and tags

The CD workflow publishes:

- **Image**: `ghcr.io/<owner>/<repo>`
- **Tags**: `latest`, `sha-<commit>`

#### Pull and run (example)

1) (If the image is private) login once:

```bash
docker login ghcr.io
```

2) Pull:

```bash
docker pull ghcr.io/<owner>/<repo>:latest
```

3) Run the container (extend `-e` with all variables your deployment needs; **migrations** are not run automatically — execute `alembic upgrade head` once per deploy, e.g. via an init job or one-off `docker run ... uv run alembic upgrade head`):

```bash
docker run -d --name api \
  -p 8000:8000 \
  -e APP_ENV=prod \
  -e DATABASE_URL="postgresql+psycopg://postgres:postgres@<db-host>:5432/ecommerce" \
  -e JWT_SECRET="replace-me-with-a-strong-secret" \
  -e ADMIN_EMAIL="you@example.com" \
  -e STRIPE_SECRET_KEY="sk_live_..." \
  -e STRIPE_WEBHOOK_SECRET="whsec_..." \
  -e STRIPE_CHECKOUT_SUCCESS_URL="https://your-frontend/success?session_id={CHECKOUT_SESSION_ID}" \
  -e STRIPE_CHECKOUT_CANCEL_URL="https://your-frontend/cancel" \
  ghcr.io/<owner>/<repo>:latest
```

Notes:

- GHCR is only used to **download** the image. Once the container is running, it does **not** need GitHub to stay online.
- Replace `<db-host>` with a real hostname/IP. If you want `@postgres:5432/...`, you must run Postgres as a **Docker container on the same Docker network** (e.g. Docker Compose).
- Live webhooks require **HTTPS** on your public URL. Use the Dashboard signing secret for `STRIPE_WEBHOOK_SECRET` in production.

---

## CI/CD

### CI

- Workflow: `.github/workflows/ci.yml`
- Runs on every push/PR: Ruff lint, Ruff format check, pytest (SQLite + Postgres job)
- Tests use **placeholder** Stripe env vars (no calls to the real Stripe API; client code is mocked)

### CD (publish Docker image to GHCR)

This repo contains a GitHub Actions workflow that builds and publishes a Docker image to **GitHub Container Registry (GHCR)** on every push to `master`:

- workflow: `.github/workflows/deploy-ghcr.yml`
- image: `ghcr.io/<owner>/<repo>`
- tags: `latest` and `sha-<commit>`

---

## Documentation

| Doc | Purpose |
|-----|---------|
| [docs/STEP_BY_STEP.md](docs/STEP_BY_STEP.md) | Project walkthrough |
| [docs/STRIPE_INTEGRATION_GUIDE.md](docs/STRIPE_INTEGRATION_GUIDE.md) | Stripe Checkout, webhooks, tests, CI, CLI |
| [docs/PROJECT_DIAGRAM.md](docs/PROJECT_DIAGRAM.md) | Architecture overview |
| [docs/MICROSERVICES_MIGRATION_GUIDE.md](docs/MICROSERVICES_MIGRATION_GUIDE.md) | Possible service split |

---

## TODO / follow-ups

| Done | Task |
|------|------|
| [x] | Stripe Checkout + webhook + tests (see `docs/STRIPE_INTEGRATION_GUIDE.md`) |
| [ ] | Understand how these tools work: Ruff, httpx, uv, FastAPI `TestClient`, bcrypt |
| [ ] | Clean repo and code (delete unnecessary files, ensure caches/logs are not tracked) |
