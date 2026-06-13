#!/usr/bin/env python3
"""01_seed_species.py — Build the initial species seed list.

TODO: Load from a curated source (IOC World Bird List XLSX, or a manual CSV).
TODO: Write to data/seeds/species_seed.parquet via polars.
TODO: Validate scientific names against ALA taxonomy API.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "packages/bird_core/src"))
sys.path.insert(0, str(REPO_ROOT / "packages/bird_data/src"))


def main() -> None:
    print("01_seed_species: not yet implemented")
    print("TODO: Load IOC or Clements species list for Queensland.")
    print("TODO: Write to data/seeds/species_seed.parquet")


if __name__ == "__main__":
    main()
