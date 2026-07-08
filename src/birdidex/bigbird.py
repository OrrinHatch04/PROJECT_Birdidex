"""Big Bird UAV dataset audit and auxiliary import.

The Big Bird zip is large (tens of GB), so the audit inspects the archive metadata and
streams a small sample of entries instead of extracting everything. Import brings only
species-level, overlapping data into an *auxiliary* area that is kept out of the normal
ground-photo classifier splits by default.

The archive layout is not perfectly standardized, so the parser is heuristic and
documents its assumptions:

* image files are detected by extension;
* annotation files are JSON (COCO-like or per-image), CSV, TXT (YOLO), or XML (VOC);
* a COCO-style ``categories``/``annotations``/``images`` block, when present, drives
  per-species image/annotation/type counts;
* otherwise species names are inferred from the directory that contains each image.
"""

from __future__ import annotations

import csv
import json
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from birdidex.paths import data_dir
from birdidex.taxonomy import (
    TaxonClass,
    load_class_index,
    normalise_scientific_name,
    slugify,
)

IMAGE_EXTENSIONS: frozenset[str] = frozenset(
    {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"}
)
ANNOTATION_EXTENSIONS: frozenset[str] = frozenset({".json", ".csv", ".txt", ".xml"})
RESOLUTION_SAMPLE_LIMIT = 64
# COCO-style annotation keys that map to the annotation-type flags we report.
_TYPE_KEYS = {
    "bbox": "boxes",
    "segmentation": "polygons",
    "posture": "posture",
    "age": "age",
    "sex": "sex",
    "category_id": "species",
    "species": "species",
}


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def bigbird_external_dir() -> Path:
    return data_dir() / "external" / "bigbird"


def bigbird_auxiliary_dir() -> Path:
    return data_dir() / "images" / "auxiliary" / "bigbird"


def bigbird_records_path() -> Path:
    return data_dir() / "images" / "metadata" / "bigbird_records.jsonl"


def bigbird_audit_json_path() -> Path:
    return data_dir() / "reports" / "bigbird_audit.json"


def bigbird_overlap_csv_path() -> Path:
    return data_dir() / "reports" / "bigbird_overlap.csv"


@dataclass
class BigBirdAudit:
    zip_path: str
    zip_size_bytes: int
    file_count: int
    image_count: int
    annotation_files: list[dict[str, str]]
    species_names: list[str]
    per_species_image_counts: dict[str, int]
    per_species_annotation_counts: dict[str, int]
    annotation_types: dict[str, bool]
    resolution_distribution: dict[str, int]
    empty_image_count: int
    non_empty_image_count: int
    estimated_extracted_bytes: int
    overlap: list[dict[str, Any]]
    recommended_import_plan: list[str]
    generated_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "zip_path": self.zip_path,
            "zip_size_bytes": self.zip_size_bytes,
            "file_count": self.file_count,
            "image_count": self.image_count,
            "annotation_files": self.annotation_files,
            "species_names": self.species_names,
            "per_species_image_counts": self.per_species_image_counts,
            "per_species_annotation_counts": self.per_species_annotation_counts,
            "annotation_types": self.annotation_types,
            "resolution_distribution": self.resolution_distribution,
            "empty_image_count": self.empty_image_count,
            "non_empty_image_count": self.non_empty_image_count,
            "estimated_extracted_bytes": self.estimated_extracted_bytes,
            "overlap": self.overlap,
            "recommended_import_plan": self.recommended_import_plan,
            "generated_at": self.generated_at,
        }


@dataclass
class _ArchiveScan:
    file_count: int = 0
    image_infos: list[zipfile.ZipInfo] = field(default_factory=list)
    annotation_infos: list[zipfile.ZipInfo] = field(default_factory=list)
    estimated_extracted_bytes: int = 0


def _scan_archive(zf: zipfile.ZipFile) -> _ArchiveScan:
    scan = _ArchiveScan()
    for info in zf.infolist():
        if info.is_dir():
            continue
        scan.file_count += 1
        scan.estimated_extracted_bytes += info.file_size
        suffix = Path(info.filename).suffix.lower()
        if suffix in IMAGE_EXTENSIONS:
            scan.image_infos.append(info)
        elif suffix in ANNOTATION_EXTENSIONS:
            scan.annotation_infos.append(info)
    return scan


def _species_from_path(filename: str) -> str:
    """Infer a species name from the directory holding an image."""
    parts = Path(filename).parts
    if len(parts) >= 2:
        return parts[-2].replace("_", " ").strip()
    return "unknown"


def _load_coco(zf: zipfile.ZipFile, info: zipfile.ZipInfo) -> dict[str, Any] | None:
    try:
        payload = json.loads(zf.read(info).decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError, KeyError):
        return None
    if isinstance(payload, dict) and "annotations" in payload and "images" in payload:
        return payload
    return None


def _coco_counts(
    coco: dict[str, Any],
) -> tuple[dict[str, int], dict[str, int], dict[str, bool], int, int]:
    categories = {
        cat.get("id"): cat.get("name") or cat.get("species") or str(cat.get("id"))
        for cat in coco.get("categories", [])
        if isinstance(cat, dict)
    }
    per_species_annotations: Counter[str] = Counter()
    images_with_annotations: set[Any] = set()
    types: dict[str, bool] = {value: False for value in _TYPE_KEYS.values()}
    for ann in coco.get("annotations", []):
        if not isinstance(ann, dict):
            continue
        name = categories.get(ann.get("category_id"), "unknown")
        per_species_annotations[name] += 1
        images_with_annotations.add(ann.get("image_id"))
        for key, flag in _TYPE_KEYS.items():
            if ann.get(key) not in (None, "", [], {}):
                types[flag] = True

    per_species_images: Counter[str] = Counter()
    image_to_species: dict[Any, str] = {}
    for ann in coco.get("annotations", []):
        if isinstance(ann, dict):
            image_to_species.setdefault(
                ann.get("image_id"), categories.get(ann.get("category_id"), "unknown")
            )
    total_images = 0
    for image in coco.get("images", []):
        if not isinstance(image, dict):
            continue
        total_images += 1
        species = image_to_species.get(image.get("id"))
        if species:
            per_species_images[species] += 1
    non_empty = len(images_with_annotations)
    empty = max(0, total_images - non_empty)
    return (
        dict(per_species_images),
        dict(per_species_annotations),
        types,
        empty,
        non_empty,
    )


def _resolution_bucket(width: int, height: int) -> str:
    longest = max(width, height)
    if longest <= 640:
        return "<=640"
    if longest <= 1280:
        return "641-1280"
    if longest <= 1920:
        return "1281-1920"
    if longest <= 3840:
        return "1921-3840"
    return ">3840"


def _sample_resolutions(zf: zipfile.ZipFile, image_infos: list[zipfile.ZipInfo]) -> dict[str, int]:
    try:
        from PIL import Image
    except ImportError:  # pragma: no cover - vision group optional
        return {}
    distribution: Counter[str] = Counter()
    step = max(1, len(image_infos) // RESOLUTION_SAMPLE_LIMIT)
    for info in image_infos[::step][:RESOLUTION_SAMPLE_LIMIT]:
        try:
            with zf.open(info) as handle, Image.open(handle) as img:
                distribution[_resolution_bucket(*img.size)] += 1
        except Exception:  # noqa: BLE001 - skip unreadable samples
            continue
    return dict(distribution)


def _match_overlap(
    species_names: list[str],
    per_species_images: dict[str, int],
    per_species_annotations: dict[str, int],
    classes: list[TaxonClass],
) -> list[dict[str, Any]]:
    by_scientific = {
        normalise_scientific_name(t.scientific_name).lower(): t
        for t in classes
        if t.scientific_name
    }
    by_common = {t.common_name.lower(): t for t in classes}
    by_slug = {slugify(t.common_name): t for t in classes}
    by_slug.update({slugify(t.scientific_name): t for t in classes if t.scientific_name})

    overlaps: list[dict[str, Any]] = []
    for name in species_names:
        normalized = name.strip().lower()
        taxon = (
            by_scientific.get(normalized) or by_common.get(normalized) or by_slug.get(slugify(name))
        )
        if taxon is None:
            continue
        image_count = per_species_images.get(name, 0)
        annotation_count = per_species_annotations.get(name, 0)
        overlaps.append(
            {
                "bigbird_species": name,
                "class_id": taxon.class_id,
                "label": taxon.label,
                "common_name": taxon.common_name,
                "scientific_name": taxon.scientific_name or "",
                "bigbird_image_count": image_count,
                "bigbird_annotation_count": annotation_count,
                "likely_usefulness": _usefulness(image_count, annotation_count),
            }
        )
    overlaps.sort(key=lambda row: row["class_id"])
    return overlaps


def _usefulness(image_count: int, annotation_count: int) -> str:
    if annotation_count >= 50:
        return "high (detector + auxiliary validation)"
    if annotation_count > 0 or image_count >= 10:
        return "medium (detector / localisation)"
    return "low (few annotated frames)"


def _recommended_plan(
    overlaps: list[dict[str, Any]], annotation_types: dict[str, bool]
) -> list[str]:
    plan = [
        "Import overlapping species only, as dataset_role=auxiliary (view_type=uav_top_down).",
        "Do not add auxiliary frames to train/val/test unless --include-auxiliary is passed.",
    ]
    if annotation_types.get("boxes") or annotation_types.get("polygons"):
        plan.append("Use boxes/polygons for detector training and bird/background localisation.")
    if not overlaps:
        plan.append("No class_index.json overlap found; use for detector pretraining only.")
    else:
        plan.append(
            f"{len(overlaps)} overlapping classes are candidates for aerial/top-down robustness."
        )
    return plan


def audit_zip(zip_path: Path, *, class_index_path: Path | None = None) -> BigBirdAudit:
    """Audit a Big Bird zip without extracting it."""
    classes = load_class_index(class_index_path)
    zip_size = zip_path.stat().st_size
    with zipfile.ZipFile(zip_path) as zf:
        scan = _scan_archive(zf)

        annotation_files = [
            {"name": info.filename, "format": Path(info.filename).suffix.lower().lstrip(".")}
            for info in scan.annotation_infos
        ]

        coco: dict[str, Any] | None = None
        for info in scan.annotation_infos:
            if info.filename.lower().endswith(".json"):
                coco = _load_coco(zf, info)
                if coco is not None:
                    break

        if coco is not None:
            (
                per_species_images,
                per_species_annotations,
                annotation_types,
                empty,
                non_empty,
            ) = _coco_counts(coco)
            species_names = sorted(set(per_species_images) | set(per_species_annotations))
        else:
            counts: Counter[str] = Counter(
                _species_from_path(info.filename) for info in scan.image_infos
            )
            per_species_images = dict(counts)
            per_species_annotations = {}
            annotation_types = {value: False for value in set(_TYPE_KEYS.values())}
            species_names = sorted(per_species_images)
            empty = 0
            non_empty = 0

        resolution_distribution = _sample_resolutions(zf, scan.image_infos)

    overlap = _match_overlap(species_names, per_species_images, per_species_annotations, classes)
    return BigBirdAudit(
        zip_path=str(zip_path),
        zip_size_bytes=zip_size,
        file_count=scan.file_count,
        image_count=len(scan.image_infos),
        annotation_files=annotation_files,
        species_names=species_names,
        per_species_image_counts=per_species_images,
        per_species_annotation_counts=per_species_annotations,
        annotation_types=annotation_types,
        resolution_distribution=resolution_distribution,
        empty_image_count=empty,
        non_empty_image_count=non_empty,
        estimated_extracted_bytes=scan.estimated_extracted_bytes,
        overlap=overlap,
        recommended_import_plan=_recommended_plan(overlap, annotation_types),
        generated_at=_utc_now(),
    )


def write_audit_reports(audit: BigBirdAudit) -> tuple[Path, Path]:
    json_path = bigbird_audit_json_path()
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(audit.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    csv_path = bigbird_overlap_csv_path()
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "class_id",
        "label",
        "common_name",
        "scientific_name",
        "bigbird_species",
        "bigbird_image_count",
        "bigbird_annotation_count",
        "likely_usefulness",
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in audit.overlap:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
    return json_path, csv_path


@dataclass
class ImportSummary:
    mode: str
    extracted_images: int
    classes_touched: int
    records_path: str
    included_in_splits: bool


def import_zip(
    zip_path: Path,
    *,
    class_index_path: Path | None = None,
    mode: str = "auxiliary",
    include_auxiliary: bool = False,
    limit_per_class: int | None = None,
) -> ImportSummary:
    """Extract overlapping species-level frames into the auxiliary area.

    Only images whose inferred species overlaps ``class_index.json`` are extracted. Each
    record is marked ``dataset_role=auxiliary`` and ``view_type=uav_top_down`` and is
    excluded from classifier splits unless ``include_auxiliary`` is set. Bounding
    boxes/polygons from a COCO annotation file are preserved on the record when present.
    """
    audit = audit_zip(zip_path, class_index_path=class_index_path)
    overlap_by_species = {row["bigbird_species"]: row for row in audit.overlap}
    aux_root = bigbird_auxiliary_dir()
    records_path = bigbird_records_path()
    records_path.parent.mkdir(parents=True, exist_ok=True)

    coco_boxes = _load_coco_boxes(zip_path)
    per_class_written: Counter[int] = Counter()
    written = 0
    records: list[dict[str, Any]] = []

    with zipfile.ZipFile(zip_path) as zf, records_path.open("w", encoding="utf-8") as out:
        for info in zf.infolist():
            if info.is_dir():
                continue
            suffix = Path(info.filename).suffix.lower()
            if suffix not in IMAGE_EXTENSIONS:
                continue
            species = _species_from_path(info.filename)
            overlap = overlap_by_species.get(species)
            if overlap is None:
                continue
            class_id = int(overlap["class_id"])
            if limit_per_class is not None and per_class_written[class_id] >= limit_per_class:
                continue
            folder = f"{class_id:03d}.{overlap['label']}"
            dest_dir = aux_root / folder
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / Path(info.filename).name
            dest.write_bytes(zf.read(info))
            record = {
                "class_id": class_id,
                "label": overlap["label"],
                "common_name": overlap["common_name"],
                "scientific_name": overlap["scientific_name"],
                "source_frame_path": info.filename,
                "local_path": str(dest),
                "crop_path": None,
                "boxes": _boxes_for(info.filename, coco_boxes),
                "view_type": "uav_top_down",
                "dataset_role": "auxiliary",
                "included_in_splits": include_auxiliary,
                "imported_at": _utc_now(),
            }
            out.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            records.append(record)
            per_class_written[class_id] += 1
            written += 1

    return ImportSummary(
        mode=mode,
        extracted_images=written,
        classes_touched=len(per_class_written),
        records_path=str(records_path),
        included_in_splits=include_auxiliary,
    )


def _load_coco_boxes(zip_path: Path) -> dict[str, list[list[float]]]:
    """Map a COCO ``file_name`` (its full relative path) -> list of bounding boxes.

    Keys are the annotation ``file_name`` values as written, matched against archive
    entries by path suffix so identically named frames in different species folders do
    not collide.
    """
    boxes: dict[str, list[list[float]]] = defaultdict(list)
    with zipfile.ZipFile(zip_path) as zf:
        coco: dict[str, Any] | None = None
        for info in zf.infolist():
            if info.filename.lower().endswith(".json"):
                coco = _load_coco(zf, info)
                if coco is not None:
                    break
        if coco is None:
            return {}
        image_names = {
            image.get("id"): image.get("file_name", "")
            for image in coco.get("images", [])
            if isinstance(image, dict)
        }
        for ann in coco.get("annotations", []):
            if not isinstance(ann, dict):
                continue
            name = image_names.get(ann.get("image_id"))
            bbox = ann.get("bbox")
            if name and isinstance(bbox, list):
                boxes[name].append([float(v) for v in bbox])
    return dict(boxes)


def _boxes_for(entry_path: str, coco_boxes: dict[str, list[list[float]]]) -> list[list[float]]:
    """Return boxes whose COCO ``file_name`` path matches the archive entry by suffix."""
    entry_parts = Path(entry_path).parts
    for name, boxes in coco_boxes.items():
        coco_parts = Path(name).parts
        if not coco_parts:
            continue
        length = min(len(entry_parts), len(coco_parts))
        if entry_parts[-length:] == coco_parts[-length:]:
            return boxes
    return []
