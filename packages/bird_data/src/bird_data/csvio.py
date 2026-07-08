"""CSV (de)serialisation for :class:`ImageManifestRecord`.

Manifests are stored as CSV so they are diff-friendly and openable without pandas.
Nested values are flattened: enums use their ``.value``, ``Path`` becomes a string,
``date`` becomes ISO format, and the free-form ``extra`` dict is JSON-encoded.
Only the stdlib ``csv``/``json`` modules are used — no pandas dependency.
"""

from __future__ import annotations

import csv
import json
from datetime import date
from pathlib import Path

from bird_core.ids import ImageId, SourceRecordId
from bird_core.schemas import DatasetSplit, EvidenceSource

from bird_data.manifests import ImageManifestRecord

# Column order for the manifest CSV. Kept explicit so the schema is stable and
# tests can assert on it.
MANIFEST_CSV_FIELDS: list[str] = [
    "image_id",
    "source",
    "license",
    "photo_url",
    "local_path",
    "scientific_name",
    "common_name",
    "taxon_id",
    "latitude",
    "longitude",
    "event_date",
    "inside_roi",
    "quality_grade",
    "captive_or_cultivated",
    "split",
    "bbox_path",
    "source_record_id",
    "width_px",
    "height_px",
    "extra",
]


def _bool_to_cell(value: bool | None) -> str:
    if value is None:
        return ""
    return "true" if value else "false"


def _cell_to_bool(value: str) -> bool | None:
    v = value.strip().lower()
    if v == "":
        return None
    return v in ("true", "1", "yes")


def record_to_row(record: ImageManifestRecord) -> dict[str, str]:
    """Flatten an :class:`ImageManifestRecord` into a CSV-safe string dict."""
    return {
        "image_id": str(record.image_id),
        "source": record.source.value,
        "license": record.license or "",
        "photo_url": record.photo_url or "",
        "local_path": str(record.local_path) if record.local_path is not None else "",
        "scientific_name": record.scientific_name,
        "common_name": record.common_name or "",
        "taxon_id": record.taxon_id or "",
        "latitude": "" if record.latitude is None else repr(record.latitude),
        "longitude": "" if record.longitude is None else repr(record.longitude),
        "event_date": record.event_date.isoformat() if record.event_date else "",
        "inside_roi": _bool_to_cell(record.inside_roi),
        "quality_grade": record.quality_grade or "",
        "captive_or_cultivated": _bool_to_cell(record.captive_or_cultivated),
        "split": record.split.value,
        "bbox_path": str(record.bbox_path) if record.bbox_path is not None else "",
        "source_record_id": str(record.source_record_id)
        if record.source_record_id is not None
        else "",
        "width_px": "" if record.width_px is None else str(record.width_px),
        "height_px": "" if record.height_px is None else str(record.height_px),
        "extra": json.dumps(record.extra, sort_keys=True) if record.extra else "",
    }


def row_to_record(row: dict[str, str]) -> ImageManifestRecord:
    """Parse a CSV row dict back into an :class:`ImageManifestRecord`."""

    def opt(key: str) -> str | None:
        val = (row.get(key) or "").strip()
        return val or None

    def opt_float(key: str) -> float | None:
        val = opt(key)
        return float(val) if val is not None else None

    def opt_int(key: str) -> int | None:
        val = opt(key)
        return int(val) if val is not None else None

    def opt_path(key: str) -> Path | None:
        val = opt(key)
        return Path(val) if val is not None else None

    event_raw = opt("event_date")
    extra_raw = opt("extra")
    src_rec = opt("source_record_id")
    return ImageManifestRecord(
        image_id=ImageId(row["image_id"]),
        source=EvidenceSource(row["source"]),
        license=opt("license"),
        photo_url=opt("photo_url"),
        local_path=opt_path("local_path"),
        scientific_name=row["scientific_name"],
        common_name=opt("common_name"),
        taxon_id=opt("taxon_id"),
        latitude=opt_float("latitude"),
        longitude=opt_float("longitude"),
        event_date=date.fromisoformat(event_raw) if event_raw else None,
        inside_roi=_cell_to_bool(row.get("inside_roi", "")),
        quality_grade=opt("quality_grade"),
        captive_or_cultivated=_cell_to_bool(row.get("captive_or_cultivated", "")),
        split=(
            DatasetSplit(row["split"]) if (row.get("split") or "").strip() else DatasetSplit.review
        ),
        bbox_path=opt_path("bbox_path"),
        source_record_id=SourceRecordId(src_rec) if src_rec is not None else None,
        width_px=opt_int("width_px"),
        height_px=opt_int("height_px"),
        extra=json.loads(extra_raw) if extra_raw else {},
    )


def save_manifest_csv(records: list[ImageManifestRecord], path: Path) -> None:
    """Write manifest records to a CSV file (creating parent dirs)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=MANIFEST_CSV_FIELDS)
        writer.writeheader()
        for record in records:
            writer.writerow(record_to_row(record))


def load_manifest_csv(path: Path) -> list[ImageManifestRecord]:
    """Load manifest records from a CSV file written by :func:`save_manifest_csv`."""
    records: list[ImageManifestRecord] = []
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            records.append(row_to_record(row))
    return records
