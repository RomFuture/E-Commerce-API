#!/usr/bin/env bash
# Install and run api-comerce-in on a Linux host or server.
#
# Usage (from repository root):
#   ./scripts/install-linux.sh              # Docker: API + Postgres, migrations
#   ./scripts/install-linux.sh --native     # uv on host + Postgres in Docker only
#   sudo ./scripts/install-linux.sh --install-docker   # Debian/Ubuntu: install Docker first
#
# Environment:
#   SKIP_MIGRATIONS=1   — start containers only, skip alembic
#   SKIP_BUILD=1        — docker compose up without --build (use existing images)

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="docker"
INSTALL_DOCKER="false"

usage() {
  sed -n '2,12p' "$0" | tr -d '#'
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --native)
      MODE="native"
      shift
      ;;
    --install-docker)
      INSTALL_DOCKER="true"
      shift
      ;;
    -h | --help)
      usage 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage 1
      ;;
  esac
done

if [[ ! -f "$ROOT_DIR/pyproject.toml" ]]; then
  echo "error: pyproject.toml not found. Clone the repo and run from its root:" >&2
  echo "  git clone <url> && cd api-comerce-in && ./scripts/install-linux.sh" >&2
  exit 1
fi

have_cmd() {
  command -v "$1" >/dev/null 2>&1
}

install_docker_debian() {
  if [[ "${EUID:-}" -ne 0 ]]; then
    echo "error: --install-docker must be run as root (use sudo)." >&2
    exit 1
  fi
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y docker.io docker-compose-plugin curl ca-certificates
  echo
  echo "Docker installed. Add your user to the docker group (then re-login):"
  echo "  sudo usermod -aG docker \"\$USER\""
}

ensure_docker() {
  if have_cmd docker && docker compose version >/dev/null 2>&1; then
    return 0
  fi
  if ! have_cmd docker || ! docker compose version >/dev/null 2>&1; then
    echo "error: Docker and 'docker compose' are required." >&2
    echo "  Debian/Ubuntu: sudo ./scripts/install-linux.sh --install-docker" >&2
    echo "  Or see: https://docs.docker.com/engine/install/" >&2
    exit 1
  fi
}

ensure_env_file() {
  if [[ ! -f "$ROOT_DIR/.env" ]]; then
    if [[ -f "$ROOT_DIR/.env.example" ]]; then
      cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
      echo "Created .env from .env.example — edit secrets before production."
    else
      echo "warning: no .env.example; create .env manually (DATABASE_URL, JWT_SECRET, ...)." >&2
    fi
  fi
}

run_migrations_in_api_container() {
  if [[ "${SKIP_MIGRATIONS:-}" == "1" ]]; then
    echo "SKIP_MIGRATIONS=1 — skipping alembic."
    return 0
  fi
  echo "Applying database migrations..."
  docker compose -f docker-compose.yml -f docker-compose.app.yml exec -T api uv run alembic upgrade head
}

docker_stack_up() {
  ensure_docker
  ensure_env_file
  local build_flag=(--build)
  if [[ "${SKIP_BUILD:-}" == "1" ]]; then
    build_flag=()
  fi
  echo "Starting Postgres + API (docker compose)..."
  docker compose -f docker-compose.yml -f docker-compose.app.yml up -d "${build_flag[@]}"
  run_migrations_in_api_container
  echo
  echo "API:  http://localhost:8000"
  echo "Docs: http://localhost:8000/docs"
  echo "Stop: ./scripts/stop.sh"
}

install_uv_user() {
  if have_cmd uv; then
    return 0
  fi
  echo "Installing uv (user)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="${HOME}/.local/bin:${PATH}"
  if ! have_cmd uv; then
    echo "error: uv not found after install. Add ~/.local/bin to PATH and re-run." >&2
    exit 1
  fi
}

native_dev_up() {
  ensure_docker
  ensure_env_file
  install_uv_user
  echo "Starting Postgres only (port 5433 on host)..."
  docker compose -f docker-compose.yml up -d postgres
  echo "Syncing Python dependencies..."
  uv sync
  echo "Waiting for Postgres..."
  for _ in $(seq 1 30); do
    if docker compose -f docker-compose.yml exec -T postgres pg_isready -U postgres -d ecommerce >/dev/null 2>&1; then
      break
    fi
    sleep 1
  done
  if [[ "${SKIP_MIGRATIONS:-}" != "1" ]]; then
    uv run alembic upgrade head
  fi
  echo
  echo "Postgres: localhost:5433 (see DATABASE_URL in .env)"
  echo "Run API:"
  echo "  cd \"$ROOT_DIR\" && uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8000"
}

if [[ "${INSTALL_DOCKER}" == "true" ]]; then
  install_docker_debian
  extra=""
  if [[ "${MODE}" != "docker" ]]; then
    extra=" --${MODE}"
  fi
  echo "Re-run without sudo (as your user): ./scripts/install-linux.sh${extra}"
  exit 0
fi

case "$MODE" in
  docker)
    docker_stack_up
    ;;
  native)
    native_dev_up
    ;;
  *)
    echo "internal error: bad MODE=$MODE" >&2
    exit 1
    ;;
esac
