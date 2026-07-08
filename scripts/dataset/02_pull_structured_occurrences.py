#!/usr/bin/env python3
"""02_pull_structured_occurrences.py - Retrieve occurrence records from ALA/GBIF/eBird/iNat.

TODO: Load species seed from data/seeds/.
TODO: For each species, request records from explicitly enabled providers.
TODO: Write provider occurrence records to data/raw/ as JSONL files.
TODO: Respect provider rate limits using tenacity retry + sleep.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "packages/bird_core/src"))
sys.path.insert(0, str(REPO_ROOT / "apps/bird_roi_scan/src"))


def main() -> None:
    print("02_pull_structured_occurrences: not yet implemented")
    print("TODO: Wire up explicitly configured ALA, GBIF, eBird, and iNaturalist providers.")


if __name__ == "__main__":
    main()
