"""Deterministic, group-aware train/val/test splitting and dataset validation.

Splitting groups records so that all images sharing a grouping key (observation,
observer, or date) land in the same split — this prevents near-duplicate leakage
where the model memorises a bird seen from several angles in one observation.

Everything here is pure stdlib (``hashlib`` for deterministic bucketing) so it runs
without pandas/scikit-learn.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from bird_core.schemas import DatasetSplit

from bird_data.licensing import is_open_license
from bird_data.manifests import ImageManifestRecord

# Order of preference for the grouping key. The first field present on *every* record
# is used; otherwise each image is its own group.
DEFAULT_GROUP_PREFERENCE: tuple[str, ...] = ("observation_id", "observer", "event_date")


@dataclass(frozen=True)
class ValidationIssue:
    """A single dataset problem. ``level`` is ``"error"`` or ``"warning"``."""

    level: str
    code: str
    message: str


def _group_value(record: ImageManifestRecord, field: str) -> str | None:
    if field == "image_id":
        return str(record.image_id)
    if field == "event_date":
        return record.event_date.isoformat() if record.event_date else None
    val = record.extra.get(field)
    return val or None


def choose_group_field(
    records: list[ImageManifestRecord],
    preference: tuple[str, ...] = DEFAULT_GROUP_PREFERENCE,
) -> str:
    """Pick the finest grouping field present on all records, else ``"image_id"``."""
    for field in preference:
        if records and all(_group_value(r, field) is not None for r in records):
            return field
    return "image_id"


def _hash_frac(seed: int, value: str) -> float:
    digest = hashlib.md5(f"{seed}:{value}".encode()).hexdigest()  # noqa: S324 - not security
    return int(digest[:8], 16) / 0xFFFFFFFF


def _allocate(n: int, ratios: tuple[float, float, float]) -> tuple[int, int, int]:
    """Allocate ``n`` groups to (train, val, test), keeping each split non-empty when possible."""
    _, val_r, test_r = ratios
    if n <= 0:
        return (0, 0, 0)
    if n == 1:
        return (1, 0, 0)
    if n == 2:
        return (1, 1, 0)
    n_val = max(1, round(n * val_r))
    n_test = max(1, round(n * test_r))
    n_train = n - n_val - n_test
    if n_train < 1:
        n_train = 1
        over = (n_val + n_test) - (n - 1)
        while over > 0 and n_test > 1:
            n_test -= 1
            over -= 1
        while over > 0 and n_val > 1:
            n_val -= 1
            over -= 1
    return (n_train, n_val, n_test)


def assign_splits(
    records: list[ImageManifestRecord],
    *,
    ratios: tuple[float, float, float] = (0.7, 0.15, 0.15),
    seed: int = 42,
    group_field: str | None = None,
) -> tuple[list[ImageManifestRecord], str]:
    """Return ``(records_with_split_set, group_field_used)``.

    Splitting is **group-aware and class-stratified**: within each class, the distinct
    groups (observation/observer/date) are ordered deterministically by hash and then
    allotted to train/val/test by quota. All records sharing a group get the same split,
    so no group leaks across splits, while every class with enough groups appears in each
    split. Records are copied, not mutated.
    """
    if abs(sum(ratios) - 1.0) > 1e-6:
        raise ValueError(f"ratios must sum to 1.0, got {ratios}")
    field = group_field or choose_group_field(records)

    # class -> {group_value -> hash}
    class_groups: dict[str, dict[str, float]] = {}
    for record in records:
        gv = _group_value(record, field) or str(record.image_id)
        class_groups.setdefault(record.scientific_name, {})[gv] = _hash_frac(seed, gv)

    group_split: dict[str, DatasetSplit] = {}
    for groups in class_groups.values():
        ordered = sorted(groups.items(), key=lambda kv: (kv[1], kv[0]))
        n_train, n_val, _ = _allocate(len(ordered), ratios)
        for i, (gv, _h) in enumerate(ordered):
            if i < n_train:
                group_split[gv] = DatasetSplit.train
            elif i < n_train + n_val:
                group_split[gv] = DatasetSplit.val
            else:
                group_split[gv] = DatasetSplit.test

    out: list[ImageManifestRecord] = []
    for record in records:
        gv = _group_value(record, field) or str(record.image_id)
        out.append(record.model_copy(update={"split": group_split[gv]}))
    return out, field


def split_records(
    records: list[ImageManifestRecord],
) -> dict[DatasetSplit, list[ImageManifestRecord]]:
    """Bucket already-assigned records into a dict keyed by split."""
    buckets: dict[DatasetSplit, list[ImageManifestRecord]] = {
        DatasetSplit.train: [],
        DatasetSplit.val: [],
        DatasetSplit.test: [],
        DatasetSplit.review: [],
    }
    for record in records:
        buckets[record.split].append(record)
    return buckets


def validate_dataset(
    records: list[ImageManifestRecord],
    *,
    group_field: str,
    imbalance_ratio: float = 10.0,
    check_files: bool = False,
) -> list[ValidationIssue]:
    """Run dataset integrity checks and return a list of issues (possibly empty).

    ``check_files`` only inspects the filesystem when media has actually been
    retrieved; in dry-run mode leave it False so missing media is a single warning
    rather than one-per-row noise.
    """
    issues: list[ValidationIssue] = []
    buckets = split_records(records)

    # Invalid labels
    for record in records:
        if not record.scientific_name.strip():
            issues.append(
                ValidationIssue("error", "invalid_label", f"empty label for {record.image_id}")
            )

    # Group leakage across splits
    group_to_splits: dict[str, set[str]] = {}
    for record in records:
        gv = _group_value(record, group_field) or str(record.image_id)
        group_to_splits.setdefault(gv, set()).add(record.split.value)
    leaked = {g: s for g, s in group_to_splits.items() if len({x for x in s if x != "review"}) > 1}
    for g, s in sorted(leaked.items()):
        issues.append(
            ValidationIssue(
                "error", "leakage", f"group '{g}' spans multiple splits: {sorted(s)}"
            )
        )

    # Missing licence metadata
    unlicensed = [r for r in records if not is_open_license(r.license)]
    if unlicensed:
        issues.append(
            ValidationIssue(
                "error",
                "missing_license",
                f"{len(unlicensed)} record(s) lack an open licence",
            )
        )

    # Missing media files
    if check_files:
        missing = [r for r in records if r.local_path is None or not r.local_path.exists()]
        if missing:
            issues.append(
                ValidationIssue(
                    "error", "missing_file", f"{len(missing)} record(s) have no local file"
                )
            )
    else:
        no_path = [r for r in records if r.local_path is None]
        if no_path:
            issues.append(
                ValidationIssue(
                    "warning",
                    "no_media",
                    f"{len(no_path)} record(s) have no local media (expected in dry-run)",
                )
            )

    # Class balance + empty/singleton classes across splits
    from bird_data.manifest_build import class_counts

    counts = class_counts([r for r in records if r.split != DatasetSplit.review])
    if counts:
        hi, lo = max(counts.values()), min(counts.values())
        if lo > 0 and hi / lo > imbalance_ratio:
            issues.append(
                ValidationIssue(
                    "warning",
                    "class_imbalance",
                    f"class imbalance ratio {hi / lo:.1f} exceeds {imbalance_ratio:.0f}",
                )
            )
    empty = [name for name, n in counts.items() if n == 0]
    for name in empty:
        issues.append(ValidationIssue("warning", "empty_class", f"class '{name}' has no images"))

    # Classes that appear in train but are missing from val or test cannot be evaluated
    train_classes = {r.scientific_name for r in buckets[DatasetSplit.train]}
    val_classes = {r.scientific_name for r in buckets[DatasetSplit.val]}
    test_classes = {r.scientific_name for r in buckets[DatasetSplit.test]}
    for name in sorted(train_classes - test_classes):
        issues.append(
            ValidationIssue(
                "warning", "unevaluable_class", f"class '{name}' absent from test split"
            )
        )
    for name in sorted(train_classes - val_classes):
        issues.append(
            ValidationIssue("warning", "unvalidated_class", f"class '{name}' absent from val split")
        )

    return issues
