"""Manifest storage helpers (read/write parquet or JSONL).

TODO: Implement duckdb-backed manifest store for fast queries.
TODO: Add integrity checks (duplicate image IDs, missing local paths).
"""

from __future__ import annotations

import json
from pathlib import Path

from bird_data.manifests import ImageManifestRecord


def load_manifest_jsonl(path: Path) -> list[ImageManifestRecord]:
    """Load a JSONL manifest file into a list of ImageManifestRecord."""
    records: list[ImageManifestRecord] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(ImageManifestRecord.model_validate_json(line))
    return records


def save_manifest_jsonl(records: list[ImageManifestRecord], path: Path) -> None:
    """Write a list of ImageManifestRecord to a JSONL file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(rec.model_dump_json() + "\n")
