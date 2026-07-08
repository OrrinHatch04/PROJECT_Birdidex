"""Minimal local FastAPI UI.

The UI is intentionally small. It reads only local files/databases and does not make
provider requests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from birdidex.db import ObservationLog
from birdidex.paths import db_dir

try:
    from fastapi import FastAPI
except ImportError as exc:  # pragma: no cover - exercised only without the ui group
    raise ImportError("fastapi is required for birdidex.ui.server; sync the ui group") from exc

app = FastAPI(title="BIRDIDEX")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/")
def index(limit: int = 25) -> dict[str, Any]:
    db_path = db_dir() / "observations.sqlite3"
    if not Path(db_path).exists():
        return {"observations": [], "database": str(db_path)}
    with ObservationLog(db_path) as log:
        return {"observations": log.list_observations(limit=limit), "database": str(db_path)}
