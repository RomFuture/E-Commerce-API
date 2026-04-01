#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "Starting Postgres + API (Docker Compose)..."
docker compose -f docker-compose.yml -f docker-compose.app.yml up -d --build

echo
echo "Applying migrations..."
docker compose -f docker-compose.yml -f docker-compose.app.yml exec -T api uv run alembic upgrade head

echo
echo "API should be available at: http://localhost:8000"
echo "Swagger UI: http://localhost:8000/docs"

