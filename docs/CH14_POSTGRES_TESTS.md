# Chapter 14 (Option B): Run tests against Postgres

Your current pytest setup uses **SQLite in-memory** by default. This guide shows how to run the same tests against **PostgreSQL** locally.

## 1) Start a dedicated Postgres for tests

From the repo root:

```bash
docker compose -f docker-compose.test.yml up -d
docker compose -f docker-compose.test.yml ps
```

Wait until `postgres_test` is `healthy`.

## 2) Run tests with `TEST_DATABASE_URL`

```bash
TEST_DATABASE_URL="postgresql+psycopg://postgres:postgres@localhost:5434/ecommerce_test" \
  uv run pytest -q
```

## Notes

- Tests create tables via `Base.metadata.create_all()` and drop them after the run.
- Keep dev Postgres (port 5433) separate from test Postgres (port 5434) so tests never pollute your real data.

