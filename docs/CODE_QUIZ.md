# Code quiz (викторина) — what we built so far

Use this to remember the project. Cover the questions, then scroll to **[Answer key](#answer-key)**.

---

## Part A — Multiple choice

**1.** What does `app = create_app()` at the bottom of `src/api/main.py` do?

- A) Starts the web server  
- B) Builds the FastAPI application object that Uvicorn will serve  
- C) Connects to PostgreSQL  
- D) Runs migrations  

**2.** In `create_app()`, why is `docs_url=None` when `APP_ENV=prod`?

- A) Production servers never use HTTP  
- B) To reduce attack surface and avoid exposing API docs publicly  
- C) FastAPI does not support docs in prod  
- D) Swagger only works on port 443  

**3.** What is `tags=["system"]` on a route?

- A) Required for security  
- B) Only a label to group endpoints in `/docs`  
- C) It changes the URL path  
- D) It enables JWT  

**4.** What does `SettingsDep` mean in `def info(s: SettingsDep)`?

- A) `s` is always `None`  
- B) FastAPI calls `get_settings()` and injects the result into `s`  
- C) Pydantic validates the request body into `Settings`  
- D) It reads only `openapi.json`  

**5.** Why is `get_settings()` decorated with `@lru_cache`?

- A) So `.env` is parsed on every request  
- B) So one `Settings` instance is reused (faster, consistent)  
- C) So secrets never load  
- D) So the database connects once  

**6.** In `Settings`, `model_config = SettingsConfigDict(env_file=".env", extra="ignore")` — what does `extra="ignore"` do?

- A) Deletes unknown keys from `.env`  
- B) Ignores unknown environment variables instead of erroring  
- C) Ignores the database  
- D) Disables JWT  

**7.** What happens if `APP_ENV=prod` and `JWT_SECRET=change-me`?

- A) Nothing special  
- B) `Settings()` validation raises an error on startup  
- C) `/docs` turns back on  
- D) Docker Compose fails  

**8.** In `session.py`, what is `engine = create_engine(..., pool_pre_ping=True)` mainly for?

- A) Faster CPU  
- B) Checking DB connections before use; replacing bad pooled connections  
- C) Automatic migrations  
- D) JWT signing  

**9.** In `get_db_session()`, why use `yield`?

- A) Because generators are faster than `return`  
- B) So FastAPI can run code before and after the request (`try` / `finally`)  
- C) Because SQLAlchemy requires it  
- D) To stream video  

**10.** Your `docker-compose.yml` maps `"5433:5432"`. What does the **left** `5433` mean?

- A) Port **inside** the container  
- B) Port on **your computer** (host)  
- C) Redis port  
- D) FastAPI port  

**11.** What command starts only the database from this project’s Compose file?

- A) `uv run uvicorn ...`  
- B) `docker compose up -d postgres`  
- C) `alembic upgrade head`  
- D) `pytest`  

**12.** Why did we add `pythonpath = ["."]` under `[tool.pytest.ini_options]` in `pyproject.toml`?

- A) So tests run slower  
- B) So `from src...` imports work when pytest runs from the project root  
- C) So Docker finds Postgres  
- D) So Swagger loads  

---

## Part B — Short answers (one sentence each)

**13.** Name two endpoints we defined and what each returns (shape / purpose).

**14.** What is the difference between `.env.example` and `.env`?

**15.** What is a Docker **named volume** `postgres_data` used for in this project?

**16.** What does `DbSession = Annotated[Session, Depends(get_db_session)]` achieve in plain English?

**17.** If the browser shows `ERR_CONNECTION_REFUSED` for `localhost:8000/docs`, what is the most likely problem?

---

## Part C — Match concepts (mental exercise)

**18.** Match each term to the file where it mainly lives (write pairs):

Terms: `create_app`, `Settings`, `get_db_session`, `DbSession`, `engine`

Files: `src/api/main.py`, `src/infrastructure/config/settings.py`, `src/infrastructure/db/session.py`, `src/api/dependencies.py`

---

## Answer key

**1.** B — `app` is the ASGI app; Uvicorn is the process that listens on a port.

**2.** B — Hiding `/docs`, `/redoc`, and `/openapi.json` in prod is a common safety choice (not a substitute for auth on real endpoints).

**3.** B — Tags only affect OpenAPI/Swagger grouping.

**4.** B — `Depends(get_settings)` tells FastAPI to call `get_settings` and pass the result as `s`.

**5.** B — `@lru_cache` caches the result of `get_settings()` so you do not rebuild settings repeatedly.

**6.** B — Unknown env vars won’t break startup.

**7.** B — The `@model_validator(mode="after")` enforces a non-placeholder secret in prod.

**8.** B — `pool_pre_ping` tests pooled connections and can refresh dead ones.

**9.** B — `yield` gives the session to the request handler, then `finally` closes it reliably.

**10.** B — Left side of `host:container` mapping is the host port.

**11.** B — Service name in Compose is `postgres`.

**12.** B — Pytest needs the project root on `sys.path` for the `src` package layout.

**13.** Example: `GET /health` → `{"status":"ok"}`; `GET /info` → `{"app_name": ..., "app_env": ...}` (no secrets).

**14.** `.env.example` is a safe template for the repo; `.env` is your local secrets (gitignored).

**15.** It persists PostgreSQL data under `/var/lib/postgresql/data` so data survives container restarts.

**16.** It is a reusable shortcut type meaning “inject a SQLAlchemy `Session` using `get_db_session`.”

**17.** The API server (Uvicorn) is not running on that host/port, or something else is wrong before HTTP.

**18.** `create_app` → `main.py`; `Settings` + `get_settings` → `settings.py`; `get_db_session` + `engine` → `session.py`; `DbSession` → `dependencies.py`.

---

## Spaced repetition tip

Re-do **Part A** tomorrow without scrolling. Missed items = re-read that file (`main.py`, `settings.py`, `session.py`, `dependencies.py`) for 5 minutes.
