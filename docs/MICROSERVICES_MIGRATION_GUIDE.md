# Guideline: Migrating This Project to a Microservices Architecture

This document is a **practical playbook** for evolving the current FastAPI e-commerce API (see [STEP_BY_STEP.md](./STEP_BY_STEP.md)) into independently deployable services **without** a risky “big bang” rewrite.

**Repository strategy:** you will keep **one Git repository (monorepo)** for all services and shared tooling; §3 explains layout, benefits, and CI implications.

---

## 1. Why migrate (clarify the goal)

Typical reasons that match this repo:

- **Cognitive load**: layered onion layout spreads one flow across many folders (`api` → `application` → `infrastructure`). Microservices (or **vertical modules** inside one repo) shrink the surface you open for one feature.
- **Independent change**: deploy or scale one area (e.g. payments) separately later.

**Microservices do not remove indirection**; they replace Python imports with **HTTP/gRPC + explicit contracts**. You gain **smaller codebases per service** and **hard boundaries**; you pay **more operations and integration work**.

---

## 2. Principles to follow

1. **Strangler fig pattern**: keep the current app running; move **one slice** at a time behind stable routes.
2. **Contracts before code**: each extracted service exposes a versioned **OpenAPI** (or protobuf) contract; callers depend on the contract, not on internal modules.
3. **One system of record per data concept**: e.g. only the **catalog** service mutates product rows; others call it or consume events—avoid two writers to the same table from different services.
4. **Minimize the number of services early**: for a small team, prefer **3–4 services** over eight.
5. **Monorepo in Git**: keep **all services in one repository** (this project’s choice); see §3 for layout, CI, and how that differs from polyrepo.

---

## 3. Repository layout: monorepo (this project)

You will use a **monorepo**: **one Git repository** contains the gateway, every microservice, optional shared contracts/packages, and—during migration—the shrinking legacy app. That is **not** the same as one **process** or one **database**; each service remains its own deployable with its own container, env, and HTTP API.

### Why monorepo matters here

- **One clone, one history**: changes that touch several services (e.g. checkout payload + payments client) live in **one commit or PR**; no cross-repo version dance.
- **Single place for tooling**: shared Ruff rules, `uv` workflows, and `.github/workflows` at the root; use **path filters** so CI only runs tests for folders that changed.
- **Simpler local dev**: one repo checkout, one root [`docker-compose.yml`](../docker-compose.yml) (or `compose/` files) that builds every `Dockerfile` without installing private libs from other remotes.
- **Solo/small team fit**: you still get **service boundaries at runtime** (HTTP, separate DBs if you want); you avoid the overhead of many repos until you have a strong reason to split Git hosting.

### Typical folder shape (example)

```text
repo-root/
  services/
    gateway/
    identity/
    catalog/
    commerce/
    payments/
  packages/           # optional; keep tiny (generated clients, shared types)
  contracts/          # optional; versioned OpenAPI YAML per service
  docker-compose.yml
  .github/workflows/  # e.g. path-filter: services/payments/**
```

The current monolith can live under `services/legacy-api/` (or similar) until the strangler removes it.

### Monorepo vs polyrepo

| | **Monorepo** (your choice) | **Polyrepo** (one Git repo per service) |
|--|----------------------------|----------------------------------------|
| **Refactors across services** | Easier | Harder (multiple PRs, semver bumps) |
| **CI** | Path-filtered jobs | One pipeline per repo |
| **Access / cadence** | Same rules for all code | Different teams or release cycles per repo |

Prefer **polyrepo** mainly when different teams need **isolated permissions** or **unrelated release cycles**. For your case, **monorepo is an explicit architecture decision in Git** to reduce cognitive and operational load while still running **multiple services** in production.

### CI reminder

Configure workflows so a change under `services/payments/**` does not necessarily run the full test suite for every other service—see §13.

---

## 4. Suggested target boundaries (aligned with this project)

Current routers are wired in [`src/api/v1/router.py`](../src/api/v1/router.py): `auth`, `products`, `cart`, `admin`. Checkout and Stripe appear in STEP_BY_STEP as the next major slice.

| Service (suggested name) | Owns (data / responsibility) | Public / internal APIs |
|---------------------------|------------------------------|-------------------------|
| **identity** (or `auth-service`) | Users, credentials, JWT issue/verify policy | Signup, login, `/me`; internal: validate token or user lookup |
| **catalog** | Products, inventory, admin product CRUD | List/detail/search; admin mutations |
| **commerce** (optional merge) | Cart, orders, order lines, checkout orchestration | Cart CRUD, checkout, order read APIs |
| **payments** | Stripe client, webhooks, `payments` rows, idempotency | Create session/intent; `POST /webhooks/stripe` |

**Solo-dev simplification**: you may ship **two** deployables first—**commerce-api** (auth + catalog + cart + orders in one process but **packaged as clear submodules**) and **payments**—then split further when painful. The guideline below still applies slice-by-slice.

---

## 5. Phase 0 — Prepare inside the monolith (strongly recommended)

Do this **before** adding new deployables (extra `Dockerfile`s / Compose services). You stay in the **same monorepo**; you are not creating a new Git repository per service.

### 5.1 Vertical modules (feature folders)

Re-home code so one business area lives together (onion **inside** each module is fine):

```text
src/modules/
  identity/     # api, application, domain, infrastructure (user-specific)
  catalog/
  commerce/     # cart + orders + checkout orchestration when added
  payments/
shared/         # only truly generic helpers (keep tiny; prefer duplication over a heavy “shared kernel”)
```

Rule: **no cross-module imports** that skip the public interface of that module (e.g. catalog must not import commerce repositories).

### 5.2 Define “module public API”

For each module, expose only:

- use-case functions / application services intended for other modules, or
- stable read models / DTOs.

Everything else stays private to the folder. This mirrors what will become **service clients** later.

### 5.3 Document one happy path per feature

One short section per flow (auth login, list products, add to cart, checkout): entry route → main service → external calls. This becomes the seed for **per-service README** and Postman collections (STEP_BY_STEP Ch. 13).

---

## 6. Phase 1 — Introduce an edge (gateway or BFF)

**Goal**: clients always talk to **one base URL**; the edge routes to monolith or new service.

Options:

- **Reverse proxy** (Traefik, nginx): path-based routing, e.g. `/api/v1/webhooks/stripe` → payments service; everything else → monolith.
- **Thin FastAPI “BFF”** in Python: same routing idea, can attach cross-cutting auth.

Keep **path prefixes stable** (`/api/v1/...`) so Postman and frontends do not churn.

---

## 7. Phase 2 — Extract services in a safe order

Extract **the most isolated or highest-risk slice first** (fewest inbound dependencies).

Suggested order for **this** domain:

1. **Payments + Stripe webhooks** — clear boundary, external provider, idempotency (STEP_BY_STEP Ch. 12). Webhook URL moves to the new service first; monolith calls it internally via HTTP until the gateway routes publicly.
2. **Catalog** — read-heavy; cart/checkout will call it (sync client or cache).
3. **Identity** — other services need tokens or user id; after extraction, standardize **JWT validation** (shared secret or JWKS) and **trusted headers** on internal network only if you use a gateway.
4. **Commerce** (cart + orders + checkout orchestration) — depends on catalog + payments; extract last or keep as the “core” monolith until the edges are stable.

For each extraction:

1. **Copy** (or move) the module into a new deployable with its own `pyproject.toml`, `Dockerfile`, and `uv` env.
2. **Create a dedicated database or schema** for that service when it owns tables (see §8).
3. **Replace in-process calls** with an HTTP/gRPC client generated from OpenAPI / protobuf.
4. **Run dual routing**: gateway sends traffic to new service; run **contract tests** against both paths during transition.
5. **Delete** dead code from the monolith only when traffic no longer hits it.

---

## 8. Data and migrations

### 8.1 Starting point

Today you likely have **one PostgreSQL** database (`ecommerce` in [docker-compose.yml](../docker-compose.yml)) and Alembic ([`alembic/`](../alembic/)) managing **all** tables.

### 8.2 Target options (pick one strategy and stay consistent)

| Strategy | When to use | Notes |
|----------|-------------|--------|
| **Separate database per service** | You want strict ownership and independent deploys | Each service has its own Alembic lineage and `DATABASE_URL`. |
| **One cluster, separate DBs** | Same ops as today, clearer boundaries | Still one Compose “postgres” host; multiple DB names. |
| **One database, separate schemas** | Transition / solo dev compromise | Use Postgres schemas + DB roles; plan to split later. |

**Rule**: after split, **no foreign keys** across service databases. Reference other aggregates by **UUID/id** only; enforce consistency via APIs or events.

### 8.3 Moving data

- **New service, new tables**: new migrations only in that service; backfill from monolith DB with a one-off script if needed.
- **Strangler with shared DB temporarily**: allowed only as a **short** bridge; document the exit (which service will own which table and when).

---

## 9. Inter-service communication

### 9.1 Synchronous (default for checkout)

- **REST + OpenAPI** fits your current FastAPI stack.
- Use **timeouts, retries with backoff**, and **circuit breakers** where libraries exist; fail fast on catalog/payment outages.

### 9.2 Asynchronous (after payment succeeds)

- Message broker (Redis Streams, RabbitMQ, NATS, or cloud queue) for: `PaymentSucceeded` → order marked paid → optional inventory decrement in catalog.
- **Idempotency** on consumers (Stripe already pushes you here—STEP_BY_STEP Ch. 12).

Start **sync-only** if you want fewer moving parts; add events when you feel cross-service coupling.

---

## 10. Authentication and authorization

- **JWT**: either every service validates tokens with the same secret/JWKS, or the **gateway** validates and forwards `X-User-Id` / roles on an **internal network** (never trust those headers from the public internet).
- **Admin** (`ADMIN_EMAIL` in settings): keep policy in **one** place—gateway or identity service—documented in OpenAPI security schemes.

---

## 11. Local development

Evolve [docker-compose.yml](../docker-compose.yml) incrementally:

- One service definition per container: `gateway`, `identity`, `catalog`, `commerce`, `payments`, `postgres` (or multiple DBs).
- **Service discovery**: use Compose **service names** as hostnames (`http://payments:8000`).
- **`.env`**: per-service env files or one `.env` with prefixed vars (`PAYMENTS_DATABASE_URL`, …).

Keep **STEP_BY_STEP** workflows working: `uv run uvicorn`, health checks, and Postman `base_url` pointing at the gateway.

---

## 12. Testing strategy (map to STEP_BY_STEP Ch. 14)

| Layer | What to add when splitting |
|-------|----------------------------|
| **Unit** | Domain rules per service (same as today). |
| **Contract** | Consumer tests against provider OpenAPI; or Pact-style if you adopt it. |
| **Integration** | Per service: API + its Postgres (Testcontainers recommended). |
| **E2E** | Minimal: one path through gateway (signup → browse → cart → checkout → webhook simulation). |

---

## 13. CI/CD (STEP_BY_STEP Ch. 15)

- **Per service in the monorepo**: lint, test, build image when that service’s path changes (GitHub Actions `paths` / `paths-ignore`, or similar), so unrelated services do not always rebuild.
- **Shared**: pin Python/`uv` versions; same Ruff rules where possible.

---

## 14. Per-slice checklist (repeat for each extraction)

- [ ] OpenAPI published and versioned; breaking changes documented.
- [ ] Database owner decided; migrations owned by one service only.
- [ ] Gateway routes updated; old monolith routes deprecated or proxied.
- [ ] Env vars and secrets documented (no secrets in git—STEP_BY_STEP Ch. 3).
- [ ] Observability: request id / trace propagation across calls (STEP_BY_STEP Ch. 16).
- [ ] Rollback plan: toggle routing back to monolith if needed.
- [ ] README: 5-minute “how to run this service alone.”

---

## 15. Common mistakes to avoid

- **Too many services too soon**: each service is a long-term tax.
- **Shared database with cross-service SQL**: you re-create a distributed monolith with worse debugging.
- **No contract tests**: refactors break silent callers.
- **Unclear ownership of checkout**: one orchestrator should own the saga/steps (validate cart → price snapshot → order → payment session → webhook completion).

---

## 16. Relationship to STEP_BY_STEP.md

Use [STEP_BY_STEP.md](./STEP_BY_STEP.md) as the **feature checklist**; use **this file** as the **migration mechanics** checklist:

| STEP_BY_STEP topic | Microservice note |
|--------------------|-------------------|
| Ch. 2–5 DB / SQLAlchemy | Split models and sessions per owning service. |
| Ch. 6 Alembic | One migration history per database owner. |
| Ch. 7–8 Domain / auth | `identity` service; shared JWT contract. |
| Ch. 9 Products | `catalog` service. |
| Ch. 10 Cart | `commerce` (or standalone cart service). |
| Ch. 11–12 Orders / Stripe | Orchestration in `commerce`; Stripe + webhooks in `payments`. |

---

## 17. Summary

1. **Monorepo in Git**: all services live in **one repository**; deployables are split by folders and CI path filters, not by defaulting to many Git remotes.  
2. **Modularize vertically** in that repo until boundaries are obvious.  
3. Add a **gateway** and stable paths.  
4. **Extract** payments → catalog → identity → commerce (or your chosen grouping).  
5. **One owner per table**; communicate with APIs/events, not cross-service SQL.  
6. **Small number of services**, strong contracts, and repeatable checklists beat a large mesh—especially for a small team.

When in doubt, **extract one router group at a time** and keep the old implementation behind a feature flag or proxy until the new service proves stable in local and CI environments.
