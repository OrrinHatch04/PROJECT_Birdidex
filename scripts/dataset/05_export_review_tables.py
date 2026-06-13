#!/usr/bin/env python3
"""05_export_review_tables.py — Export human-readable review tables.

TODO: Load scored species from data/processed/.
TODO: Write CSV/markdown tables to data/reports/ for human review.
TODO: Flag species in 'review' status with evidence summaries.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    print("05_export_review_tables: not yet implemented")
    print("TODO: Export species_accepted.csv, species_review.csv, species_rejected.csv")


if __name__ == "__main__":
    main()
