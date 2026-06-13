#!/usr/bin/env python3
"""03_run_keyword_scan.py — Run web keyword evidence scan.

NOTE: Web keyword evidence is weak supplementary signal only.
      Configure SEARCH_API_KEY in .env before running.
      Do NOT call this without a legitimate search API key.

TODO: Load species from data/seeds/.
TODO: Run WebSearchProvider for enabled species.
TODO: Write keyword evidence to data/interim/ as JSONL.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "packages/bird_core/src"))
sys.path.insert(0, str(REPO_ROOT / "apps/scanner/src"))


def main() -> None:
    print("03_run_keyword_scan: not yet implemented")
    print("TODO: Requires SEARCH_API_KEY in .env and WebSearchProvider implementation.")


if __name__ == "__main__":
    main()
