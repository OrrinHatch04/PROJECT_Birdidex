#!/usr/bin/env python3
"""04_score_species.py — Score ROI species candidates and write manifests/report.

Dry-run (default): scores the deterministic seed list using
``configs/scanner/scoring.yaml`` and writes:
  - data/manifests/roi_species_candidates.csv
  - data/manifests/species_priority_tiers.csv
  - data/reports/roi_species_candidates_report.md

No provider requests are made.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for _pkg in ("bird_core", "bird_data", "bird_geo"):
    sys.path.insert(0, str(REPO_ROOT / "packages" / _pkg / "src"))
sys.path.insert(0, str(REPO_ROOT / "apps/bird_roi_scan/src"))

from bird_roi_scan.pipeline import run_candidate_scan  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2025, help="Reference year for recency")
    args = parser.parse_args()

    scoring = REPO_ROOT / "configs/scanner/scoring.yaml"
    result = run_candidate_scan(
        scoring_config=scoring if scoring.exists() else None, current_year=args.year
    )
    tiers = {
        t: sum(1 for s in result.scored if s.tier == t) for t in ("core", "review", "rejected")
    }
    print(f"Scored {len(result.scored)} species: {tiers}")
    print(f"  candidates: {result.candidates_csv}")
    print(f"  tiers:      {result.tiers_csv}")
    print(f"  report:     {result.report_md}")


if __name__ == "__main__":
    main()
