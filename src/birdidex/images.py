"""Image dataset scaffold and metadata manifest utilities."""

from __future__ import annotations

import csv
import html
import json
import shutil
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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
DEPRECATED_MARKER = "DEPRECATED_DO_NOT_TRAIN.txt"
DEPRECATED_FOLDER_REPORT = "deprecated_ambiguous_folders.csv"
IMAGE_EXTENSIONS: frozenset[str] = frozenset(
    {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tif", ".tiff"}
)


def is_deprecated_class(taxon: TaxonClass) -> bool:
    """A class whose folder must be marked deprecated and kept out of training."""
    return taxon.is_deprecated or taxon.is_ambiguous


@dataclass(frozen=True)
class ImageInspection:
    path: str
    can_open: bool
    width: int | None = None
    height: int | None = None
    mode: str | None = None
    sharpness_score: float | None = None
    error: str | None = None


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _pillow() -> Any:
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - depends on optional vision group
        raise RuntimeError("Pillow is required for image inspection utilities") from exc
    return Image


def validate_image_can_open(path: Path) -> bool:
    """Return True when Pillow can decode the image header and pixel data."""
    Image = _pillow()
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            image.load()
    except Exception:  # noqa: BLE001 - corrupt image formats raise many exception types
        return False
    return True


def image_dimensions(path: Path) -> tuple[int, int]:
    """Return image dimensions without applying any model transform."""
    Image = _pillow()
    with Image.open(path) as image:
        return image.size


def open_image_rgb(path: Path) -> Any:
    """Open an image as RGB so later transforms receive a stable color mode."""
    Image = _pillow()
    with Image.open(path) as image:
        image.load()
        return image.convert("RGB")


def resize_with_aspect(image: Any, max_edge: int, *, allow_upscale: bool = False) -> Any:
    """Resize while preserving aspect ratio and never distort bird detail."""
    if max_edge <= 0:
        raise ValueError("max_edge must be positive")
    rgb = image.convert("RGB")
    longest = max(rgb.size)
    if longest <= max_edge and not allow_upscale:
        return rgb.copy()
    scale = max_edge / longest
    new_size = (max(1, round(rgb.width * scale)), max(1, round(rgb.height * scale)))
    Image = _pillow()
    return rgb.resize(new_size, Image.Resampling.LANCZOS)


def letterbox_image(
    image: Any,
    size: int | tuple[int, int],
    *,
    fill: tuple[int, int, int] = (0, 0, 0),
) -> Any:
    """Fit an RGB image inside ``size`` and pad the remaining area."""
    target = (size, size) if isinstance(size, int) else size
    if target[0] <= 0 or target[1] <= 0:
        raise ValueError("letterbox target dimensions must be positive")

    contained = resize_with_aspect(image, max(target), allow_upscale=True)
    if contained.width > target[0] or contained.height > target[1]:
        scale = min(target[0] / contained.width, target[1] / contained.height)
        Image = _pillow()
        contained = contained.resize(
            (max(1, round(contained.width * scale)), max(1, round(contained.height * scale))),
            Image.Resampling.LANCZOS,
        )

    Image = _pillow()
    canvas = Image.new("RGB", target, fill)
    offset = ((target[0] - contained.width) // 2, (target[1] - contained.height) // 2)
    canvas.paste(contained, offset)
    return canvas


def basic_sharpness_score(image: Any) -> float:
    """Compute a cheap edge-variance score for triaging very soft images."""
    from PIL import ImageFilter, ImageStat

    gray = image.convert("L")
    edges = gray.filter(ImageFilter.FIND_EDGES)
    return float(ImageStat.Stat(edges).var[0])


def inspect_image(path: Path) -> ImageInspection:
    """Return decode, dimensions, mode, and sharpness without mutating files."""
    try:
        image = open_image_rgb(path)
        return ImageInspection(
            path=str(path),
            can_open=True,
            width=image.width,
            height=image.height,
            mode=image.mode,
            sharpness_score=basic_sharpness_score(image),
        )
    except Exception as exc:  # noqa: BLE001 - notebook audit should report, not crash
        return ImageInspection(path=str(path), can_open=False, error=f"{type(exc).__name__}: {exc}")


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
    move_reviewed: bool = False,
) -> list[Path]:
    """Create ImageFolder-style class directories from ``class_index.json`` only.

    New concrete classes get folders. Deprecated (ambiguous) classes keep their folders
    but are marked with a ``DEPRECATED`` file and are never used for training. No image
    files are moved unless ``move_reviewed=True`` is passed, in which case any images in
    deprecated folders are quarantined for manual per-species reassignment.
    """
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
    write_deprecated_markers(classes, images_root=root)
    quarantined = quarantine_deprecated_images(classes, images_root=root, move=move_reviewed)
    write_deprecated_folder_report(classes, quarantined, images_root=root)
    return created


def write_deprecated_markers(
    classes: list[TaxonClass],
    *,
    images_root: Path | None = None,
) -> list[Path]:
    """Drop a DEPRECATED marker in every deprecated (ambiguous) class folder."""
    root = images_root or default_images_dir()
    written: list[Path] = []
    for taxon in classes:
        if not is_deprecated_class(taxon):
            continue
        reasons = ", ".join(taxon.ambiguity_reasons) or "deprecated"
        replacements = taxon.raw.get("replacement_class_ids") or []
        text = (
            f"DEPRECATED CLASS: {taxon.folder_name}\n"
            "This is an ambiguous taxon (not a single concrete species). It is excluded "
            "from classifier training and from automatic image download.\n"
            f"Ambiguity reasons: {reasons}\n"
            f"Replacement class ids: {replacements}\n"
            "Do not train on these images. Reassign each image to a concrete species "
            "folder (see data/taxonomy/class_replacement_map.csv), then remove this file.\n"
        )
        for stage in IMAGE_STAGES:
            folder = root / stage / taxon.folder_name
            if folder.exists():
                marker = folder / DEPRECATED_MARKER
                marker.write_text(text, encoding="utf-8")
                written.append(marker)
    return written


def _class_images(folder: Path) -> list[Path]:
    return [
        path
        for path in folder.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    ]


def scan_class_folders(
    classes: list[TaxonClass],
    *,
    images_root: Path | None = None,
) -> dict[str, Any]:
    """Report class folders vs the class index without moving any files."""
    root = images_root or default_images_dir()
    expected = {taxon.folder_name for taxon in classes}
    deprecated = {taxon.folder_name for taxon in classes if is_deprecated_class(taxon)}

    parents = [root / stage for stage in IMAGE_STAGES]
    parents += [root / "splits" / split for split in SPLIT_NAMES]

    extra_folders: list[str] = []
    deprecated_with_images: list[dict[str, Any]] = []
    for parent in parents:
        if not parent.exists():
            continue
        for child in sorted(parent.iterdir()):
            if not child.is_dir():
                continue
            if child.name not in expected:
                extra_folders.append(str(child.relative_to(root)))
            if child.name in deprecated:
                images = _class_images(child)
                if images:
                    deprecated_with_images.append(
                        {"folder": str(child.relative_to(root)), "image_count": len(images)}
                    )
    return {
        "extra_folders": sorted(set(extra_folders)),
        "deprecated_with_images": deprecated_with_images,
    }


def quarantine_deprecated_images(
    classes: list[TaxonClass],
    *,
    images_root: Path | None = None,
    move: bool = False,
) -> list[dict[str, Any]]:
    """List (and, when ``move`` is True, relocate) images in deprecated folders.

    Images are moved into ``<root>/quarantine/<folder>/`` so a human can reassign them
    to a concrete species. With ``move=False`` this only reports what *would* move.
    """
    root = images_root or default_images_dir()
    deprecated = {taxon.folder_name for taxon in classes if is_deprecated_class(taxon)}
    source_stages = [stage for stage in IMAGE_STAGES if stage != "quarantine"]
    parents = [root / stage for stage in source_stages]
    parents += [root / "splits" / split for split in SPLIT_NAMES]

    actions: list[dict[str, Any]] = []
    for parent in parents:
        for folder_name in sorted(deprecated):
            folder = parent / folder_name
            if not folder.exists():
                continue
            for image in _class_images(folder):
                dest = root / "quarantine" / folder_name / image.name
                if move:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if dest.exists():
                        dest = dest.with_name(f"{image.stem}_{parent.name}{image.suffix}")
                    shutil.move(str(image), str(dest))
                actions.append(
                    {
                        "src": str(image.relative_to(root)),
                        "dest": str(dest.relative_to(root)),
                        "moved": move,
                    }
                )
    return actions


def write_deprecated_folder_report(
    classes: list[TaxonClass],
    quarantined: list[dict[str, Any]] | None = None,
    *,
    images_root: Path | None = None,
) -> dict[str, Any]:
    """Write ``reports/deprecated_ambiguous_folders.csv`` and return the scan summary."""
    root = images_root or default_images_dir()
    scan = scan_class_folders(classes, images_root=root)
    quarantined = quarantined or []
    moved = sum(1 for action in quarantined if action["moved"])
    rows = [
        {
            "folder": entry["folder"],
            "image_count": entry["image_count"],
            "quarantined": str(moved > 0).lower(),
            "needs_manual_review": "true",
        }
        for entry in scan["deprecated_with_images"]
    ]
    _write_count_csv(
        root / REPORTS_DIR / DEPRECATED_FOLDER_REPORT,
        ["folder", "image_count", "quarantined", "needs_manual_review"],
        rows,
    )
    return {
        "deprecated_folders_with_images": len(scan["deprecated_with_images"]),
        "images_needing_review": sum(e["image_count"] for e in scan["deprecated_with_images"]),
        "images_quarantined": moved,
        "extra_folders": len(scan["extra_folders"]),
    }


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
        '<html lang="en">',
        '<meta charset="utf-8">',
        "<title>BIRDIDEX image review queue</title>",
        "<h1>BIRDIDEX image review queue</h1>",
        "<table>",
        "<thead><tr><th>Class</th><th>Provider</th><th>Record</th><th>Issues</th><th>Page</th></tr></thead>",
        "<tbody>",
    ]
    for record in rows:
        page = html.escape(record.page_url or "")
        page_cell = f'<a href="{page}">source</a>' if page else ""
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
