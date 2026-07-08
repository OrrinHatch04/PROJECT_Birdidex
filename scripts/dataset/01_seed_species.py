#!/usr/bin/env python3
"""01_seed_species.py — Write the deterministic local seed species list to CSV.

Offline: emits ``data/seeds/roi_species_seed.csv`` from the bundled SEQ seed list. This
seed list drives the dry-run scan; a live run would replace it with a taxonomy-derived
candidate set validated against ALA/GBIF.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for _pkg in ("bird_core", "bird_data"):
    sys.path.insert(0, str(REPO_ROOT / "packages" / _pkg / "src"))
sys.path.insert(0, str(REPO_ROOT / "apps/bird_roi_scan/src"))

from bird_roi_scan.seeds import seed_species  # noqa: E402


def main() -> None:
    out = REPO_ROOT / "data/seeds/roi_species_seed.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    seeds = seed_species()
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["species_id", "scientific_name", "common_name", "ebird_code", "manual_review"]
        )
        for s in seeds:
            writer.writerow(
                [s.species_id, s.scientific_name, s.common_name, s.ebird_code,
                 str(s.manual_review).lower()]
            )
    print(f"Wrote {len(seeds)} seed species -> {out}")


if __name__ == "__main__":
    main()
