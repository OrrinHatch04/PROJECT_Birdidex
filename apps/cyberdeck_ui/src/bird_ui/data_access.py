"""Local data access for the UI: observation log + species cards.

All reads are local (SQLite + CSV) — the UI never touches the network. The observation
DB path can be overridden with the ``BIRDIDEX_OBS_DB`` environment variable so tests can
point at a temporary database.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any

from bird_core.paths import get_db_dir, get_manifests_dir
from bird_data.observation_log import ObservationLog


def obs_db_path() -> Path:
    override = os.environ.get("BIRDIDEX_OBS_DB")
    return Path(override) if override else get_db_dir() / "observations.sqlite3"


def open_log() -> ObservationLog:
    return ObservationLog(obs_db_path())


def candidates_csv_path() -> Path:
    override = os.environ.get("BIRDIDEX_CANDIDATES_CSV")
    return Path(override) if override else get_manifests_dir() / "roi_species_candidates.csv"


def species_card(species_id: str) -> dict[str, Any] | None:
    """Return a species card from the observation DB, falling back to the candidates CSV."""
    with open_log() as log:
        row = log.get_species(species_id)
    if row:
        return {"source": "observation_log", **row}

    csv_path = candidates_csv_path()
    if csv_path.exists():
        with csv_path.open(encoding="utf-8", newline="") as fh:
            for r in csv.DictReader(fh):
                if r.get("species_id") == species_id:
                    return {
                        "source": "roi_candidates",
                        "species_id": r["species_id"],
                        "scientific_name": r.get("scientific_name"),
                        "common_name": r.get("common_name"),
                        "tier": r.get("tier"),
                        "final_score": r.get("final_score"),
                    }
    return None
