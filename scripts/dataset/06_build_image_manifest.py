#!/usr/bin/env python3
"""06_build_image_manifest.py — Build a licensed image manifest from observations.

Dry-run (default) reads a committed iNaturalist-style fixture and emits an open-licensed
image manifest plus licence / class-balance / duplicate reports. No media is downloaded.

Explicit media retrieval is gated behind ``--retrieve-media`` and is intentionally NOT
implemented in this MVP: doing so would fetch remote files. The flag documents the
required behaviour (max-per-class, resume, checksum, licence filter) without acting.

Usage:
    uv run python scripts/dataset/06_build_image_manifest.py
    uv run python scripts/dataset/06_build_image_manifest.py --observations path/to/obs.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for _pkg in ("bird_core", "bird_data", "bird_geo"):
    sys.path.insert(0, str(REPO_ROOT / "packages" / _pkg / "src"))

from bird_data.csvio import save_manifest_csv  # noqa: E402
from bird_data.licensing import filter_open_licensed  # noqa: E402
from bird_data.manifest_build import parse_inat_observations  # noqa: E402
from bird_data.reports import (  # noqa: E402
    render_class_balance_report,
    render_duplicate_audit,
    render_license_report,
)

DEFAULT_OBS = REPO_ROOT / "data/seeds/inat_observations.sample.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--observations", default=str(DEFAULT_OBS), help="iNat observations JSON")
    parser.add_argument("--max-per-class", type=int, default=0, help="0 = no cap (metadata stage)")
    parser.add_argument(
        "--retrieve-media",
        action="store_true",
        help="Download media (NOT implemented — refuses and exits non-zero)",
    )
    args = parser.parse_args()

    if args.retrieve_media:
        print(
            "ERROR: media retrieval is not implemented in this MVP.\n"
            "  When implemented it MUST: filter to open licences, cap at --max-per-class,\n"
            "  resume from existing files, verify checksums, and never commit media."
        )
        sys.exit(2)

    obs_path = Path(args.observations)
    observations = json.loads(obs_path.read_text())
    records = parse_inat_observations(observations)
    if args.max_per_class > 0:
        records = _cap_per_class(records, args.max_per_class)

    kept, rejected = filter_open_licensed(records)
    print(
        f"Parsed {len(records)} image records "
        f"({len(kept)} open-licensed, {len(rejected)} rejected)."
    )

    manifests = REPO_ROOT / "data/manifests"
    reports = REPO_ROOT / "data/reports"
    manifest_csv = manifests / "images_manifest.csv"
    save_manifest_csv(kept, manifest_csv)

    reports.mkdir(parents=True, exist_ok=True)
    (reports / "license_report.md").write_text(render_license_report(records), encoding="utf-8")
    (reports / "class_balance_report.md").write_text(
        render_class_balance_report(kept), encoding="utf-8"
    )
    (reports / "duplicate_audit.md").write_text(render_duplicate_audit(kept), encoding="utf-8")

    print(f"  manifest: {manifest_csv}")
    print(f"  reports:  {reports}/license_report.md, class_balance_report.md, duplicate_audit.md")


def _cap_per_class(records: list, limit: int) -> list:  # type: ignore[type-arg]
    seen: dict[str, int] = {}
    out = []
    for r in records:
        n = seen.get(r.scientific_name, 0)
        if n < limit:
            out.append(r)
            seen[r.scientific_name] = n + 1
    return out


if __name__ == "__main__":
    main()
