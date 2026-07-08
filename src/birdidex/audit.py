"""Dataset audit across images, licenses, profiles, and Big Bird overlap.

Reads only local files (image records, class index, optional Big Bird records and
profiles) and writes three report artifacts under ``data/reports/``:

* ``dataset_audit.json`` — the full machine-readable audit;
* ``dataset_audit.html`` — a compact human review page;
* ``species_coverage.csv`` — one row per class with coverage counts.
"""

from __future__ import annotations

import csv
import html
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from birdidex.images import image_records_path, read_metadata_jsonl
from birdidex.paths import data_dir
from birdidex.paths import images_dir as default_images_dir
from birdidex.profiles import ENRICHABLE_FIELDS, species_profiles_path
from birdidex.providers import ImageMetadataRecord
from birdidex.taxonomy import load_class_index

WEAK_COVERAGE_THRESHOLD = 150


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def reports_dir() -> Path:
    return data_dir() / "reports"


def dataset_audit_json_path() -> Path:
    return reports_dir() / "dataset_audit.json"


def dataset_audit_html_path() -> Path:
    return reports_dir() / "dataset_audit.html"


def species_coverage_csv_path() -> Path:
    return reports_dir() / "species_coverage.csv"


def _resolution_bucket(record: ImageMetadataRecord) -> str:
    width = record.stored_width or record.width
    height = record.stored_height or record.height
    if not width or not height:
        return "unknown"
    longest = max(width, height)
    if longest <= 640:
        return "<=640"
    if longest <= 1280:
        return "641-1280"
    if longest <= 1920:
        return "1281-1920"
    return ">1920"


def _load_bigbird_overlap() -> dict[int, int]:
    """class_id -> auxiliary image count from bigbird_records.jsonl if present."""
    path = data_dir() / "images" / "metadata" / "bigbird_records.jsonl"
    counts: Counter[int] = Counter()
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            counts[int(row.get("class_id", -1))] += 1
    counts.pop(-1, None)
    return dict(counts)


def _load_profile_gaps() -> dict[int, list[str]]:
    """class_id -> list of unfilled enrichable profile fields."""
    path = species_profiles_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    gaps: dict[int, list[str]] = {}
    for profile in payload.get("profiles", []):
        missing = [name for name in ENRICHABLE_FIELDS if not profile.get(name)]
        gaps[int(profile["class_id"])] = missing
    return gaps


def build_audit(
    *,
    class_index_path: Path | None = None,
    images_root: Path | None = None,
) -> dict[str, Any]:
    classes = load_class_index(class_index_path)
    root = images_root or default_images_dir()
    records = read_metadata_jsonl(image_records_path(root))

    by_class_accepted: Counter[int] = Counter()
    by_class_status: dict[int, Counter[str]] = defaultdict(Counter)
    providers: Counter[str] = Counter()
    licenses: Counter[str] = Counter()
    resolutions: Counter[str] = Counter()
    reps: dict[int, bool] = defaultdict(bool)
    sha_seen: Counter[str] = Counter()
    phash_seen: Counter[str] = Counter()

    for record in records:
        by_class_status[record.class_id][record.status] += 1
        providers[record.provider] += 1
        licenses[record.license_code or "unknown"] += 1
        if record.status == "accepted":
            by_class_accepted[record.class_id] += 1
            resolutions[_resolution_bucket(record)] += 1
            if record.local_path:
                reps[record.class_id] = True
            if record.sha256:
                sha_seen[record.sha256] += 1
            if record.phash:
                phash_seen[record.phash] += 1

    bigbird_overlap = _load_bigbird_overlap()
    profile_gaps = _load_profile_gaps()

    per_class: list[dict[str, Any]] = []
    weak_classes: list[str] = []
    no_rep_classes: list[str] = []
    ambiguous_excluded: list[str] = []
    for taxon in classes:
        status_counts = by_class_status.get(taxon.class_id, Counter())
        accepted = by_class_accepted.get(taxon.class_id, 0)
        has_rep = reps.get(taxon.class_id, False)
        if taxon.is_ambiguous:
            ambiguous_excluded.append(taxon.folder_name)
        if not taxon.is_ambiguous and accepted < WEAK_COVERAGE_THRESHOLD:
            weak_classes.append(taxon.folder_name)
        if not taxon.is_ambiguous and not has_rep:
            no_rep_classes.append(taxon.folder_name)
        per_class.append(
            {
                "class_id": taxon.class_id,
                "label": taxon.label,
                "folder_name": taxon.folder_name,
                "common_name": taxon.common_name,
                "scientific_name": taxon.scientific_name or "",
                "clean_classifier_class": taxon.clean_classifier_class,
                "ambiguous_taxon": taxon.is_ambiguous,
                "accepted": accepted,
                "candidate": status_counts.get("candidate", 0),
                "review": status_counts.get("review", 0),
                "quarantine": status_counts.get("quarantine", 0),
                "rejected": status_counts.get("quarantine", 0),
                "has_representative_image": has_rep,
                "bigbird_auxiliary_images": bigbird_overlap.get(taxon.class_id, 0),
                "missing_profile_fields": profile_gaps.get(taxon.class_id, []),
            }
        )

    return {
        "generated_at": _utc_now(),
        "n_classes": len(classes),
        "n_clean_classes": sum(1 for t in classes if t.clean_classifier_class),
        "n_records": len(records),
        "n_accepted": sum(by_class_accepted.values()),
        "provider_distribution": dict(sorted(providers.items())),
        "license_distribution": dict(sorted(licenses.items())),
        "resolution_distribution": dict(sorted(resolutions.items())),
        "sha256_duplicate_groups": sum(1 for c in sha_seen.values() if c > 1),
        "perceptual_duplicate_groups": sum(1 for c in phash_seen.values() if c > 1),
        "weak_coverage_classes": weak_classes,
        "classes_without_representative_image": no_rep_classes,
        "ambiguous_excluded_classes": ambiguous_excluded,
        "bigbird_overlap_present": bool(bigbird_overlap),
        "weak_coverage_threshold": WEAK_COVERAGE_THRESHOLD,
        "per_class": per_class,
    }


def _write_species_coverage_csv(audit: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "class_id",
        "label",
        "folder_name",
        "common_name",
        "scientific_name",
        "clean_classifier_class",
        "accepted",
        "candidate",
        "quarantine",
        "has_representative_image",
        "bigbird_auxiliary_images",
        "missing_profile_field_count",
    ]
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in audit["per_class"]:
            writer.writerow(
                {
                    "class_id": row["class_id"],
                    "label": row["label"],
                    "folder_name": row["folder_name"],
                    "common_name": row["common_name"],
                    "scientific_name": row["scientific_name"],
                    "clean_classifier_class": str(row["clean_classifier_class"]).lower(),
                    "accepted": row["accepted"],
                    "candidate": row["candidate"],
                    "quarantine": row["quarantine"],
                    "has_representative_image": str(row["has_representative_image"]).lower(),
                    "bigbird_auxiliary_images": row["bigbird_auxiliary_images"],
                    "missing_profile_field_count": len(row["missing_profile_fields"]),
                }
            )


def _write_audit_html(audit: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "<!doctype html>",
        '<html lang="en">',
        '<meta charset="utf-8">',
        "<title>BIRDIDEX dataset audit</title>",
        "<h1>BIRDIDEX dataset audit</h1>",
        f"<p>Generated: {html.escape(audit['generated_at'])}</p>",
        "<ul>",
        f"<li>Classes: {audit['n_classes']} ({audit['n_clean_classes']} clean)</li>",
        f"<li>Records: {audit['n_records']} ({audit['n_accepted']} accepted)</li>",
        f"<li>Weak-coverage classes (&lt;{audit['weak_coverage_threshold']} accepted): "
        f"{len(audit['weak_coverage_classes'])}</li>",
        f"<li>Classes without representative image: "
        f"{len(audit['classes_without_representative_image'])}</li>",
        f"<li>Ambiguous classes excluded from fetching: "
        f"{len(audit['ambiguous_excluded_classes'])}</li>",
        f"<li>Big Bird auxiliary overlap present: {audit['bigbird_overlap_present']}</li>",
        "</ul>",
        "<h2>Provider distribution</h2>",
        "<pre>" + html.escape(json.dumps(audit["provider_distribution"], indent=2)) + "</pre>",
        "<h2>License distribution</h2>",
        "<pre>" + html.escape(json.dumps(audit["license_distribution"], indent=2)) + "</pre>",
        "<h2>Per-class coverage</h2>",
        "<table>",
        "<thead><tr><th>Class</th><th>Accepted</th><th>Candidate</th><th>Quarantine</th>"
        "<th>Rep image</th><th>Big Bird aux</th><th>Missing profile fields</th></tr></thead>",
        "<tbody>",
    ]
    for row in audit["per_class"]:
        lines.append(
            "<tr>"
            f"<td>{row['class_id']:03d}.{html.escape(row['label'])}</td>"
            f"<td>{row['accepted']}</td>"
            f"<td>{row['candidate']}</td>"
            f"<td>{row['quarantine']}</td>"
            f"<td>{'yes' if row['has_representative_image'] else 'no'}</td>"
            f"<td>{row['bigbird_auxiliary_images']}</td>"
            f"<td>{len(row['missing_profile_fields'])}</td>"
            "</tr>"
        )
    lines.extend(["</tbody>", "</table>", "</html>"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_dataset_audit(
    *,
    class_index_path: Path | None = None,
    images_root: Path | None = None,
) -> dict[str, Any]:
    """Build the audit and write JSON, HTML, and CSV reports."""
    audit = build_audit(class_index_path=class_index_path, images_root=images_root)
    json_path = dataset_audit_json_path()
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(audit, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    _write_audit_html(audit, dataset_audit_html_path())
    _write_species_coverage_csv(audit, species_coverage_csv_path())
    return audit
