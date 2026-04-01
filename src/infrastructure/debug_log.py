from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.engine.url import URL, make_url

_LOG_PATH = Path("/home/romfuture/Projects/Personal/api-comerce-in/.cursor/debug-131b75.log")
_SESSION_ID = "131b75"


def _now_ms() -> int:
    return int(time.time() * 1000)


def _write(payload: dict[str, Any]) -> None:
    _LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with _LOG_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def log(
    *, run_id: str, hypothesis_id: str, location: str, message: str, data: dict[str, Any]
) -> None:
    _write(
        {
            "sessionId": _SESSION_ID,
            "id": f"log_{_now_ms()}_{uuid.uuid4().hex[:8]}",
            "timestamp": _now_ms(),
            "runId": run_id,
            "hypothesisId": hypothesis_id,
            "location": location,
            "message": message,
            "data": data,
        },
    )


def redact_db_url(database_url: str) -> dict[str, Any]:
    """Return non-secret parts of DATABASE_URL for debugging."""
    url: URL = make_url(database_url)
    return {
        "drivername": url.drivername,
        "host": url.host,
        "port": url.port,
        "database": url.database,
    }
