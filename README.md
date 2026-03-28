## E-Commerce API (Backend)

### Local development

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

Configuration (Chapter 3):

```bash
cp .env.example .env
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
