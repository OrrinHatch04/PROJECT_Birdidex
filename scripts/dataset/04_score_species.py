#!/usr/bin/env python3
"""04_score_species.py — Apply scoring weights to produce accepted/review/rejected lists.

TODO: Load occurrence records from data/raw/.
TODO: Load keyword evidence from data/interim/.
TODO: Apply configs/scanner/scoring.yaml weights.
TODO: Write scored species to data/processed/species_scored.parquet.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    print("04_score_species: not yet implemented")
    print("TODO: Load raw data, apply scoring weights, write processed output.")


if __name__ == "__main__":
    main()
