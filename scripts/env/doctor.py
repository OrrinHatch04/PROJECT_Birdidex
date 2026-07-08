"""Small wrapper around ``birdidex doctor`` for users who run scripts directly."""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def main() -> int:
    from birdidex.cli import doctor

    doctor()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
