"""Deterministic ImageFolder split creation from accepted local image records."""

from __future__ import annotations

import hashlib
import shutil
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path

from birdidex.images import SPLIT_NAMES, image_records_path, read_metadata_jsonl
from birdidex.paths import images_dir as default_images_dir
from birdidex.paths import repo_root
from birdidex.providers import ImageMetadataRecord
from birdidex.taxonomy import class_folder_name, load_class_index


@dataclass(frozen=True)
class SplitSummary:
    train: int
    val: int
    test: int
    linked_or_copied: int
    duplicate_groups: int

    @property
    def total(self) -> int:
        return self.train + self.val + self.test


def validate_split_ratios(train: float, val: float, test: float) -> None:
    if min(train, val, test) < 0:
        raise ValueError("split ratios must be non-negative")
    if abs((train + val + test) - 1.0) > 1e-6:
        raise ValueError(f"split ratios must sum to 1.0, got {train + val + test:.6f}")


def _hash(seed: int, value: str) -> str:
    return hashlib.sha256(f"{seed}:{value}".encode()).hexdigest()


def _group_key(record: ImageMetadataRecord) -> str:
    if record.sha256:
        return f"sha256:{record.sha256}"
    if record.provider and record.provider_record_id:
        return f"{record.provider}:{record.provider_record_id}"
    if record.image_url:
        return f"url:{record.image_url}"
    return f"path:{record.local_path}"


def _allocate_count(n: int, train: float, val: float, test: float) -> tuple[int, int, int]:
    if n <= 0:
        return 0, 0, 0
    if n == 1:
        return 1, 0, 0
    n_train = round(n * train)
    n_val = round(n * val)
    n_test = n - n_train - n_val
    if n_train <= 0:
        n_train, n_test = 1, max(0, n_test - 1)
    if n >= 3 and n_val <= 0 and val > 0:
        n_val, n_train = 1, max(1, n_train - 1)
    if n >= 3 and n_test <= 0 and test > 0:
        n_test, n_train = 1, max(1, n_train - 1)
    while n_train + n_val + n_test > n:
        if n_train >= n_val and n_train >= n_test and n_train > 1:
            n_train -= 1
        elif n_val >= n_test and n_val > 0:
            n_val -= 1
        else:
            n_test -= 1
    while n_train + n_val + n_test < n:
        n_train += 1
    return n_train, n_val, n_test


def assign_split_names(
    records: list[ImageMetadataRecord],
    *,
    train: float = 0.75,
    val: float = 0.15,
    test: float = 0.10,
    seed: int = 42,
) -> dict[str, str]:
    """Return ``group_key -> split`` with class-stratified deterministic grouping."""
    validate_split_ratios(train, val, test)
    groups_by_class: dict[int, dict[str, list[ImageMetadataRecord]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for record in records:
        groups_by_class[record.class_id][_group_key(record)].append(record)

    group_to_split: dict[str, str] = {}
    for class_id, groups in sorted(groups_by_class.items()):
        keys = sorted(groups, key=lambda key: (_hash(seed, f"{class_id}:{key}"), key))
        n_train, n_val, _ = _allocate_count(len(keys), train, val, test)
        for index, key in enumerate(keys):
            if index < n_train:
                split = "train"
            elif index < n_train + n_val:
                split = "val"
            else:
                split = "test"
            group_to_split[key] = split
    return group_to_split


def _resolve_local_path(path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    return repo_root() / candidate


def _safe_filename(record: ImageMetadataRecord, source: Path) -> str:
    stem = f"{record.provider}_{record.provider_record_id}".replace("/", "_").replace(":", "_")
    suffix = source.suffix or ".jpg"
    return f"{stem}{suffix}"


def create_splits(
    *,
    records: list[ImageMetadataRecord] | None = None,
    class_index_path: Path | None = None,
    images_root: Path | None = None,
    train: float = 0.75,
    val: float = 0.15,
    test: float = 0.10,
    seed: int = 42,
    copy: bool = False,
) -> SplitSummary:
    """Create symlink or copy splits from accepted records with local files."""
    root = images_root or default_images_dir()
    source_records = (
        records if records is not None else read_metadata_jsonl(image_records_path(root))
    )
    accepted = [
        record
        for record in source_records
        if record.status == "accepted"
        and record.local_path
        and _resolve_local_path(record.local_path).exists()
    ]
    classes = {taxon.class_id: taxon for taxon in load_class_index(class_index_path)}
    group_to_split = assign_split_names(accepted, train=train, val=val, test=test, seed=seed)

    for split in SPLIT_NAMES:
        for taxon in classes.values():
            (root / "splits" / split / taxon.folder_name).mkdir(parents=True, exist_ok=True)

    counts: Counter[str] = Counter()
    linked = 0
    group_counts = Counter(_group_key(record) for record in accepted)
    for record in accepted:
        split = group_to_split[_group_key(record)]
        source = _resolve_local_path(record.local_path or "")
        folder = class_folder_name(record.class_id, record.label)
        dest = root / "splits" / split / folder / _safe_filename(record, source)
        if dest.exists() or dest.is_symlink():
            dest.unlink()
        if copy:
            shutil.copy2(source, dest)
        else:
            dest.symlink_to(source)
        counts[split] += 1
        linked += 1

    return SplitSummary(
        train=counts["train"],
        val=counts["val"],
        test=counts["test"],
        linked_or_copied=linked,
        duplicate_groups=sum(1 for count in group_counts.values() if count > 1),
    )
