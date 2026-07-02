#!/usr/bin/env python3
"""02_pull_structured_occurrences.py — Pull occurrence records from ALA/GBIF/eBird/iNat.

TODO: Load species seed from data/seeds/.
TODO: For each species, call enabled providers from configs/scanner/providers.yaml.
TODO: Write raw occurrence records to data/raw/ as JSONL files.
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
    print("TODO: Wire up ALAProvider, GBIFProvider, EBirdProvider, INaturalistProvider.")


if __name__ == "__main__":
    main()
