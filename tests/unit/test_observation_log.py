"""SQLite observation log: schema, logging, verdict, and CSV/JSON export."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from bird_data.observation_log import ObservationLog


def _log(tmp_path: Path) -> ObservationLog:
    return ObservationLog(tmp_path / "obs.sqlite3")


def test_schema_creates_all_tables(tmp_path: Path) -> None:
    log = _log(tmp_path)
    names = {
        r["name"]
        for r in log._conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert {"model_versions", "species", "observations", "field_sessions"} <= names
    log.close()


def test_log_and_read_latest(tmp_path: Path) -> None:
    log = _log(tmp_path)
    log.log_model_version("v1", backbone="mock")
    log.upsert_species("sp_a", "Species A", "Common A")
    sid = log.start_session("s1", location="Brisbane")
    oid = log.log_observation(
        image_path="/img.jpg",
        predicted_species_id="sp_a",
        top5=[{"rank": 1, "species_id": "sp_a", "score": 0.9}],
        confidence=0.9,
        model_version="v1",
        session_id=sid,
    )
    assert oid == 1
    latest = log.latest_observation()
    assert latest is not None
    assert latest["predicted_species_id"] == "sp_a"
    assert json.loads(latest["top5_json"])[0]["species_id"] == "sp_a"
    log.close()


def test_verdict_and_species_lookup(tmp_path: Path) -> None:
    log = _log(tmp_path)
    log.upsert_species("sp_a", "Species A", "Common A")
    oid = log.log_observation(predicted_species_id="sp_a", confidence=0.5)
    log.set_verdict(oid, "confirmed")
    assert log.list_observations()[0]["user_verdict"] == "confirmed"
    assert log.get_species("sp_a")["scientific_name"] == "Species A"
    assert log.get_species("missing") is None
    log.close()


def test_upsert_species_updates(tmp_path: Path) -> None:
    log = _log(tmp_path)
    log.upsert_species("sp_a", "Old name")
    log.upsert_species("sp_a", "New name", "Common")
    assert log.get_species("sp_a")["scientific_name"] == "New name"
    log.close()


def test_export_csv_and_json(tmp_path: Path) -> None:
    log = _log(tmp_path)
    log.log_observation(predicted_species_id="sp_a", confidence=0.5)
    log.log_observation(predicted_species_id="sp_b", confidence=0.7)
    csv_path = tmp_path / "out.csv"
    json_path = tmp_path / "out.json"
    log.export_csv(csv_path)
    log.export_json(json_path)
    with csv_path.open(newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert len(rows) == 2
    assert json.loads(json_path.read_text())[0]["predicted_species_id"] == "sp_a"
    log.close()
