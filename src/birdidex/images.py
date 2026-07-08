"""Image dataset scaffold and metadata manifest utilities."""

from __future__ import annotations

import csv
import html
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

from birdidex.paths import images_dir as default_images_dir
from birdidex.providers import (
    FETCHERS,
    ImageMetadataRecord,
    validate_metadata_records,
)
from birdidex.taxonomy import (
    TaxonClass,
    classes_by_id,
    clean_classifier_classes,
    expected_class_folders,
    load_class_index,
    write_class_folder_index_csv,
)

IMAGE_STAGES: tuple[str, ...] = ("raw", "review", "quarantine", "processed")
SPLIT_NAMES: tuple[str, ...] = ("train", "val", "test")
METADATA_DIR = "metadata"
REPORTS_DIR = "reports"
CLASS_FOLDER_INDEX = "class_folder_index.csv"
DATASET_MANIFEST = "image_dataset_manifest.json"
IMAGE_RECORDS = "image_records.jsonl"


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def image_records_path(images_root: Path | None = None) -> Path:
    return (images_root or default_images_dir()) / METADATA_DIR / IMAGE_RECORDS


def dataset_manifest_path(images_root: Path | None = None) -> Path:
    return (images_root or default_images_dir()) / DATASET_MANIFEST


def class_folder_index_path(images_root: Path | None = None) -> Path:
    return (images_root or default_images_dir()) / CLASS_FOLDER_INDEX


def scaffold_image_dataset(
    *,
    class_index_path: Path | None = None,
    images_root: Path | None = None,
) -> list[Path]:
    """Create ImageFolder-style class directories from ``class_index.json`` only."""
    root = images_root or default_images_dir()
    classes = load_class_index(class_index_path)
    created: list[Path] = []

    for rel in (METADATA_DIR, REPORTS_DIR):
        path = root / rel
        path.mkdir(parents=True, exist_ok=True)
        created.append(path)

    for taxon in classes:
        for stage in IMAGE_STAGES:
            path = root / stage / taxon.folder_name
            path.mkdir(parents=True, exist_ok=True)
            created.append(path)
        for split in SPLIT_NAMES:
            path = root / "splits" / split / taxon.folder_name
            path.mkdir(parents=True, exist_ok=True)
            created.append(path)

    write_class_folder_index_csv(classes, class_folder_index_path(root))
    return created


def validate_no_extra_class_folders(
    *,
    images_root: Path | None = None,
    class_index_path: Path | None = None,
) -> list[Path]:
    """Return class folders that do not exist in the class index."""
    root = images_root or default_images_dir()
    classes = load_class_index(class_index_path)
    expected = expected_class_folders(classes)
    extras: list[Path] = []
    parents = [root / stage for stage in IMAGE_STAGES]
    parents += [root / "splits" / split for split in SPLIT_NAMES]
    for parent in parents:
        if not parent.exists():
            continue
        for child in parent.iterdir():
            if child.is_dir() and child.name not in expected:
                extras.append(child)
    return sorted(extras)


def write_metadata_jsonl(records: list[ImageMetadataRecord], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for record in records:
            fh.write(json.dumps(record.to_dict(), ensure_ascii=False, sort_keys=True) + "\n")


def read_metadata_jsonl(path: Path) -> list[ImageMetadataRecord]:
    if not path.exists():
        return []
    records: list[ImageMetadataRecord] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                records.append(ImageMetadataRecord.from_dict(json.loads(line)))
    return records


def fetch_image_manifest(
    *,
    class_index_path: Path | None = None,
    images_root: Path | None = None,
    provider_names: tuple[str, ...] = tuple(FETCHERS),
    live: bool = False,
    include_ambiguous: bool = False,
    limit_per_class: int = 10,
) -> list[ImageMetadataRecord]:
    """Fetch or initialize provider metadata records.

    With ``live=False`` this performs no provider requests and writes an empty
    manifest. Live mode remains metadata-only: it calls documented provider APIs and
    records image URLs, source URLs, licences, and attribution.
    """
    root = images_root or default_images_dir()
    classes = load_class_index(class_index_path)
    selected = classes if include_ambiguous else clean_classifier_classes(classes)
    lookup = classes_by_id(classes)
    records: list[ImageMetadataRecord] = []

    for provider_name in provider_names:
        fetcher = FETCHERS[provider_name]
        for taxon in selected:
            records.extend(fetcher(taxon, live=live, limit=limit_per_class))

    validated = validate_metadata_records(records, class_lookup=lookup)
    write_metadata_jsonl(validated, image_records_path(root))
    write_dataset_manifest(validated, classes, dataset_manifest_path(root), live=live)
    write_reports(validated, classes, images_root=root)
    return validated


def write_dataset_manifest(
    records: list[ImageMetadataRecord],
    classes: list[TaxonClass],
    output_path: Path,
    *,
    live: bool,
) -> None:
    payload = {
        "generated_at": utc_now(),
        "metadata_only": True,
        "live_provider_requests": live,
        "class_source": "class_index.json",
        "n_classes": len(classes),
        "n_clean_classifier_classes": sum(1 for taxon in classes if taxon.clean_classifier_class),
        "n_records": len(records),
        "n_accepted_records": sum(1 for record in records if record.status == "accepted"),
        "records_path": str(output_path.parent / METADATA_DIR / IMAGE_RECORDS),
        "notes": [
            "Image folders are generated from class_index.json only.",
            "No media is downloaded by scaffold or manifest commands.",
            "Ambiguous taxa are excluded from fetching by default.",
        ],
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_count_csv(path: Path, fieldnames: list[str], rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_reports(
    records: list[ImageMetadataRecord],
    classes: list[TaxonClass],
    *,
    images_root: Path | None = None,
) -> None:
    root = images_root or default_images_dir()
    reports = root / REPORTS_DIR

    by_class = Counter(record.class_id for record in records if record.status == "accepted")
    class_rows = [
        {
            "class_id": taxon.class_id,
            "label": taxon.label,
            "folder_name": taxon.folder_name,
            "accepted_records": by_class.get(taxon.class_id, 0),
            "clean_classifier_class": str(taxon.clean_classifier_class).lower(),
        }
        for taxon in classes
    ]
    _write_count_csv(
        reports / "class_counts.csv",
        ["class_id", "label", "folder_name", "accepted_records", "clean_classifier_class"],
        class_rows,
    )

    by_license = Counter(record.license_code or "unknown" for record in records)
    _write_count_csv(
        reports / "license_summary.csv",
        ["license_code", "records"],
        [{"license_code": key, "records": count} for key, count in sorted(by_license.items())],
    )

    by_provider = Counter(record.provider for record in records)
    _write_count_csv(
        reports / "provider_summary.csv",
        ["provider", "records"],
        [{"provider": key, "records": count} for key, count in sorted(by_provider.items())],
    )

    write_review_queue_html(records, reports / "review_queue.html")


def write_review_queue_html(records: list[ImageMetadataRecord], output_path: Path) -> None:
    rows = [record for record in records if record.status != "accepted"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "<!doctype html>",
        "<html lang=\"en\">",
        "<meta charset=\"utf-8\">",
        "<title>BIRDIDEX image review queue</title>",
        "<h1>BIRDIDEX image review queue</h1>",
        "<table>",
        "<thead><tr><th>Class</th><th>Provider</th><th>Record</th><th>Issues</th><th>Page</th></tr></thead>",
        "<tbody>",
    ]
    for record in rows:
        page = html.escape(record.page_url or "")
        page_cell = f"<a href=\"{page}\">source</a>" if page else ""
        lines.append(
            "<tr>"
            f"<td>{record.class_id:03d}.{html.escape(record.label)}</td>"
            f"<td>{html.escape(record.provider)}</td>"
            f"<td>{html.escape(record.provider_record_id)}</td>"
            f"<td>{html.escape(', '.join(record.validation_issues))}</td>"
            f"<td>{page_cell}</td>"
            "</tr>"
        )
    lines.extend(["</tbody>", "</table>", "</html>"])
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def report_image_dataset(
    *,
    class_index_path: Path | None = None,
    images_root: Path | None = None,
) -> dict[str, int]:
    """Regenerate image reports and return a small summary."""
    root = images_root or default_images_dir()
    classes = load_class_index(class_index_path)
    records = read_metadata_jsonl(image_records_path(root))
    write_reports(records, classes, images_root=root)
    extras = validate_no_extra_class_folders(images_root=root, class_index_path=class_index_path)
    return {
        "classes": len(classes),
        "records": len(records),
        "accepted_records": sum(1 for record in records if record.status == "accepted"),
        "extra_class_folders": len(extras),
    }
