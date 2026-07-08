"""Local SQLite observation log for the cyberdeck.

Stores everything needed to review field sightings offline: the image/crop paths, the
predicted species and full top-k JSON, confidence, model version, timestamp, optional
GPS/weather, the field session, and the user's verdict. Pure stdlib ``sqlite3`` — no
external database. Databases live under ``data/db/`` and are git-ignored.
"""

from __future__ import annotations

import csv
import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS model_versions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    version    TEXT UNIQUE NOT NULL,
    backbone   TEXT,
    created_at TEXT NOT NULL,
    notes      TEXT
);

CREATE TABLE IF NOT EXISTS species (
    species_id      TEXT PRIMARY KEY,
    scientific_name TEXT NOT NULL,
    common_name     TEXT
);

CREATE TABLE IF NOT EXISTS field_sessions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    name       TEXT NOT NULL,
    started_at TEXT NOT NULL,
    ended_at   TEXT,
    location   TEXT,
    notes      TEXT
);

CREATE TABLE IF NOT EXISTS observations (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    image_path           TEXT,
    crop_path            TEXT,
    predicted_species_id TEXT,
    top5_json            TEXT,
    confidence           REAL,
    model_version        TEXT,
    timestamp            TEXT NOT NULL,
    latitude             REAL,
    longitude            REAL,
    weather              TEXT,
    session_id           INTEGER,
    user_verdict         TEXT,
    FOREIGN KEY (session_id) REFERENCES field_sessions (id)
    -- predicted_species_id is intentionally NOT foreign-keyed: a prediction may name a
    -- label-map species not yet present in the species card table.
);
"""

OBSERVATION_COLUMNS = [
    "id", "image_path", "crop_path", "predicted_species_id", "top5_json", "confidence",
    "model_version", "timestamp", "latitude", "longitude", "weather", "session_id", "user_verdict",
]


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


class ObservationLog:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self.init_schema()

    def init_schema(self) -> None:
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    # ── writes ────────────────────────────────────────────────────────────────
    def log_model_version(
        self, version: str, *, backbone: str | None = None, notes: str | None = None
    ) -> None:
        self._conn.execute(
            "INSERT OR IGNORE INTO model_versions (version, backbone, created_at, notes) "
            "VALUES (?, ?, ?, ?)",
            (version, backbone, _utc_now(), notes),
        )
        self._conn.commit()

    def upsert_species(
        self, species_id: str, scientific_name: str, common_name: str | None = None
    ) -> None:
        self._conn.execute(
            "INSERT INTO species (species_id, scientific_name, common_name) VALUES (?, ?, ?) "
            "ON CONFLICT(species_id) DO UPDATE SET scientific_name=excluded.scientific_name, "
            "common_name=excluded.common_name",
            (species_id, scientific_name, common_name),
        )
        self._conn.commit()

    def start_session(self, name: str, *, location: str | None = None) -> int:
        cur = self._conn.execute(
            "INSERT INTO field_sessions (name, started_at, location) VALUES (?, ?, ?)",
            (name, _utc_now(), location),
        )
        self._conn.commit()
        return int(cur.lastrowid or 0)

    def end_session(self, session_id: int) -> None:
        self._conn.execute(
            "UPDATE field_sessions SET ended_at = ? WHERE id = ?", (_utc_now(), session_id)
        )
        self._conn.commit()

    def log_observation(
        self,
        *,
        image_path: str | None = None,
        crop_path: str | None = None,
        predicted_species_id: str | None = None,
        top5: list[dict[str, Any]] | None = None,
        confidence: float | None = None,
        model_version: str | None = None,
        timestamp: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        weather: str | None = None,
        session_id: int | None = None,
        user_verdict: str | None = None,
    ) -> int:
        cur = self._conn.execute(
            "INSERT INTO observations (image_path, crop_path, predicted_species_id, top5_json, "
            "confidence, model_version, timestamp, latitude, longitude, weather, session_id, "
            "user_verdict) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                image_path, crop_path, predicted_species_id,
                json.dumps(top5) if top5 is not None else None,
                confidence, model_version, timestamp or _utc_now(),
                latitude, longitude, weather, session_id, user_verdict,
            ),
        )
        self._conn.commit()
        return int(cur.lastrowid or 0)

    def set_verdict(self, observation_id: int, verdict: str) -> None:
        self._conn.execute(
            "UPDATE observations SET user_verdict = ? WHERE id = ?", (verdict, observation_id)
        )
        self._conn.commit()

    # ── reads ─────────────────────────────────────────────────────────────────
    def latest_observation(self) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM observations ORDER BY id DESC LIMIT 1"
        ).fetchone()
        return _row_to_dict(row) if row else None

    def list_observations(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM observations ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def get_species(self, species_id: str) -> dict[str, Any] | None:
        row = self._conn.execute(
            "SELECT * FROM species WHERE species_id = ?", (species_id,)
        ).fetchone()
        return _row_to_dict(row) if row else None

    # ── export ────────────────────────────────────────────────────────────────
    def export_csv(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = self._conn.execute("SELECT * FROM observations ORDER BY id").fetchall()
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(fh, fieldnames=OBSERVATION_COLUMNS)
            writer.writeheader()
            for r in rows:
                writer.writerow(_row_to_dict(r))

    def export_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        cursor = self._conn.execute("SELECT * FROM observations ORDER BY id")
        rows = [_row_to_dict(r) for r in cursor]
        path.write_text(json.dumps(rows, indent=2), encoding="utf-8")

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> ObservationLog:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return dict(zip(row.keys(), tuple(row), strict=True))
