#!/usr/bin/env python3
"""07_build_splits.py — Generate train/val/test splits from the image manifest.

Reads ``data/manifests/images_manifest.csv``, assigns deterministic group-aware splits
(grouping by observation/observer/date to prevent leakage), validates the dataset, and
writes per-split CSVs plus a split report.

Usage:
    uv run python scripts/dataset/07_build_splits.py
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for _pkg in ("bird_core", "bird_data"):
    sys.path.insert(0, str(REPO_ROOT / "packages" / _pkg / "src"))

from bird_core.schemas import DatasetSplit  # noqa: E402
from bird_data.csvio import load_manifest_csv, save_manifest_csv  # noqa: E402
from bird_data.reports import render_split_report  # noqa: E402
from bird_data.splits import assign_splits, split_records, validate_dataset  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", default=str(REPO_ROOT / "data/manifests/images_manifest.csv"))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    manifest_path = Path(args.manifest)
    if not manifest_path.exists():
        print(f"ERROR: manifest not found: {manifest_path}")
        print("  Run 06_build_image_manifest.py first.")
        sys.exit(1)

    records = load_manifest_csv(manifest_path)
    assigned, group_field = assign_splits(records, seed=args.seed)
    issues = validate_dataset(assigned, group_field=group_field)

    splits_dir = REPO_ROOT / "data/splits"
    buckets = split_records(assigned)
    for split in (DatasetSplit.train, DatasetSplit.val, DatasetSplit.test):
        save_manifest_csv(buckets[split], splits_dir / f"{split.value}.csv")

    report = render_split_report(assigned, group_field=group_field, issues=issues)
    (REPO_ROOT / "data/reports/split_report.md").write_text(report, encoding="utf-8")

    errors = sum(1 for i in issues if i.level == "error")
    warnings = sum(1 for i in issues if i.level == "warning")
    print(f"Grouping field: {group_field}")
    for split in (DatasetSplit.train, DatasetSplit.val, DatasetSplit.test):
        out_csv = splits_dir / f"{split.value}.csv"
        print(f"  {split.value}: {len(buckets[split])} images -> {out_csv}")
    print(f"Validation: {errors} error(s), {warnings} warning(s) -> data/reports/split_report.md")


if __name__ == "__main__":
    main()
